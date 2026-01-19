import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import uuid4
from celery import current_task
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.onec_client import OneCClient, OneCApiError
from app.services.websocket_manager import manager, WebSocketMessage, WebSocketMessageType
from app.models.integration import Integration, IntegrationStatus, SyncLog, IntegrationLog
from app.models.product import Product
from app.crud.integration import get_integration, update_integration, create_sync_log
from app.crud.product import create_or_update_product, get_product_by_external_id
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def sync_nomenclature(self, integration_id: Optional[str] = None):
    """
    Задача синхронизации номенклатуры из 1С.
    
    Args:
        integration_id: ID интеграции (если None, синхронизирует все активные интеграции)
    """
    task_id = current_task.request.id if current_task else str(uuid4())
    
    db: Session = SessionLocal()
    try:
        logger.info(f"Starting nomenclature sync task {task_id}")
        
        # Отправляем WebSocket уведомление
        asyncio.run(_send_sync_started("nomenclature", task_id))
        
        # Получаем интеграции для синхронизации
        integrations = _get_integrations_for_sync(db, integration_id, "onec")
        
        if not integrations:
            logger.warning(f"No active 1C integrations found for sync {task_id}")
            asyncio.run(_send_sync_completed(
                "nomenclature", task_id, 0, 0, 0, "No active integrations"
            ))
            return {"status": "skipped", "reason": "No active integrations"}
        
        total_processed = 0
        total_created = 0
        total_updated = 0
        errors = []
        
        for integration in integrations:
            try:
                # Создаем запись в логе синхронизации
                sync_log = create_sync_log(
                    db,
                    integration_id=integration.id,
                    sync_type="incremental",
                    entity_type="nomenclature",
                    status="running"
                )
                
                # Синхронизируем для этой интеграции
                result = _sync_integration_nomenclature(
                    db, integration, sync_log.id, task_id
                )
                
                # Обновляем статистику
                total_processed += result["processed"]
                total_created += result["created"]
                total_updated += result["updated"]
                
                if result["errors"]:
                    errors.extend(result["errors"])
                
                # Обновляем интеграцию
                integration.last_sync_at = datetime.now()
                integration.total_syncs += 1
                integration.successful_syncs += 1
                db.commit()
                
                logger.info(f"Sync completed for integration {integration.name}")
                
            except Exception as e:
                logger.error(f"Error syncing integration {integration.name}: {e}")
                errors.append(str(e))
                
                # Обновляем интеграцию
                integration.failed_syncs += 1
                integration.last_error = str(e)
                integration.is_healthy = False
                db.commit()
        
        # Отправляем финальное уведомление
        error_message = "; ".join(errors) if errors else None
        asyncio.run(_send_sync_completed(
            "nomenclature", task_id, total_processed, 
            total_created, total_updated, error_message
        ))
        
        logger.info(f"Nomenclature sync task {task_id} completed: "
                   f"processed={total_processed}, created={total_created}, "
                   f"updated={total_updated}, errors={len(errors)}")
        
        return {
            "status": "completed",
            "processed": total_processed,
            "created": total_created,
            "updated": total_updated,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Error in nomenclature sync task {task_id}: {e}")
        asyncio.run(_send_sync_error("nomenclature", task_id, str(e)))
        
        # Повторная попытка
        if self:
            self.retry(exc=e, countdown=60)
        
        return {"status": "failed", "error": str(e)}
    
    finally:
        db.close()

def _get_integrations_for_sync(
    db: Session, 
    integration_id: Optional[str],
    integration_type: str
) -> List[Integration]:
    """Получение интеграций для синхронизации"""
    from app.crud.integration import get_integrations
    
    query_filters = {
        "integration_type": integration_type,
        "is_enabled": True,
        "status": IntegrationStatus.ACTIVE
    }
    
    if integration_id:
        integration = get_integration(db, integration_id)
        return [integration] if integration else []
    
    return get_integrations(db, **query_filters)

def _sync_integration_nomenclature(
    db: Session,
    integration: Integration,
    sync_log_id: str,
    task_id: str
) -> Dict[str, Any]:
    """Синхронизация номенклатуры для конкретной интеграции"""
    
    # Создаем клиент 1С
    client = OneCClient(
        base_url=integration.base_url,
        api_key=integration.api_key,
        username=integration.username,
        password=integration.password,
        timeout=integration.settings.get("timeout", 30),
        max_retries=integration.settings.get("max_retries", 3)
    )
    
    processed = 0
    created = 0
    updated = 0
    errors = []
    
    try:
        # Определяем время последней синхронизации
        last_sync = integration.last_sync_at
        updated_since = last_sync if last_sync else None
        
        # Получаем товары из 1С
        products = asyncio.run(client.get_nomenclature(
            updated_since=updated_since,
            limit=1000
        ))
        
        # Обрабатываем каждый товар
        for onec_product in products:
            try:
                processed += 1
                
                # Проверяем, существует ли товар
                existing_product = get_product_by_external_id(
                    db, onec_product.id, integration.id
                )
                
                product_data = {
                    "name": onec_product.name,
                    "description": onec_product.full_name or onec_product.name,
                    "price": onec_product.price or 0.0,
                    "quantity": onec_product.quantity or 0,
                    "category": onec_product.category,
                    "external_id": onec_product.id,
                    "external_code": onec_product.code,
                    "external_data": {
                        "article": onec_product.article,
                        "unit": onec_product.unit,
                        "characteristics": onec_product.characteristics,
                        "manufacturer": onec_product.manufacturer,
                        "updated_at": onec_product.updated_at.isoformat() if onec_product.updated_at else None
                    },
                    "integration_id": integration.id,
                    "is_synced": True,
                    "sync_status": "synced",
                    "last_sync_at": datetime.now(),
                    "sync_version": (existing_product.sync_version + 1) if existing_product else 1
                }
                
                # Создаем или обновляем товар
                if existing_product:
                    # Проверяем, нужно ли обновлять
                    if (_should_update_product(existing_product, product_data)):
                        updated_product = create_or_update_product(
                            db, product_data, existing_product.id
                        )
                        updated += 1
                        
                        # Отправляем WebSocket уведомление
                        asyncio.run(_send_product_updated(updated_product))
                else:
                    new_product = create_or_update_product(db, product_data)
                    created += 1
                    
                    # Отправляем WebSocket уведомление
                    asyncio.run(_send_product_updated(new_product))
                
                # Отправляем прогресс каждые 10 товаров
                if processed % 10 == 0:
                    asyncio.run(_send_sync_progress(
                        "nomenclature", task_id, processed, len(products)
                    ))
                
                # Коммитим каждые 50 товаров
                if processed % 50 == 0:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Error processing product {onec_product.id}: {e}")
                errors.append(f"Product {onec_product.id}: {str(e)}")
        
        # Финальный коммит
        db.commit()
        
        # Обновляем лог синхронизации
        from app.crud.integration import update_sync_log
        update_sync_log(
            db,
            sync_log_id,
            status="completed",
            processed_items=processed,
            created_items=created,
            updated_items=updated,
            failed_items=len(errors),
            duration_seconds=(datetime.now() - integration.last_sync_at).total_seconds() if integration.last_sync_at else 0
        )
        
        return {
            "processed": processed,
            "created": created,
            "updated": updated,
            "errors": errors
        }
        
    except OneCApiError as e:
        logger.error(f"1C API error during sync: {e}")
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error during sync: {e}")
        raise

def _should_update_product(existing_product: Product, new_data: Dict[str, Any]) -> bool:
    """Определяет, нужно ли обновлять товар"""
    # Проверяем изменение критичных полей
    critical_fields = ["name", "price", "quantity"]
    
    for field in critical_fields:
        if field in new_data and getattr(existing_product, field) != new_data[field]:
            return True
    
    # Проверяем версию синхронизации
    if new_data.get("sync_version", 0) > existing_product.sync_version:
        return True
    
    return False

@celery_app.task
def sync_stock(integration_id: Optional[str] = None):
    """Задача синхронизации остатков из 1С"""
    # Аналогично sync_nomenclature, но для остатков
    pass

@celery_app.task
def check_integrations_health():
    """Задача проверки здоровья интеграций"""
    db: Session = SessionLocal()
    try:
        from app.crud.integration import get_integrations
        
        integrations = get_integrations(db, is_enabled=True)
        
        for integration in integrations:
            try:
                # Проверяем соединение
                client = OneCClient(
                    base_url=integration.base_url,
                    api_key=integration.api_key
                )
                
                is_healthy = asyncio.run(client.health_check())
                
                # Обновляем статус
                integration.is_healthy = is_healthy
                integration.last_health_check = datetime.now()
                
                if not is_healthy:
                    integration.status = IntegrationStatus.ERROR
                    logger.warning(f"Integration {integration.name} is unhealthy")
                
                db.commit()
                
            except Exception as e:
                logger.error(f"Error checking health for {integration.name}: {e}")
                integration.is_healthy = False
                integration.status = IntegrationStatus.ERROR
                db.commit()
        
        logger.info(f"Health check completed for {len(integrations)} integrations")
        
    finally:
        db.close()

async def _send_sync_started(entity_type: str, task_id: str):
    """Отправка уведомления о начале синхронизации"""
    message = WebSocketMessage(
        type=WebSocketMessageType.SYNC_STARTED,
        data={
            "entity_type": entity_type,
            "task_id": task_id,
            "started_at": datetime.now().isoformat()
        },
        timestamp=datetime.now().isoformat()
    )
    await manager.broadcast(message, "sync_updates")

async def _send_sync_progress(entity_type: str, task_id: str, current: int, total: int):
    """Отправка уведомления о прогрессе синхронизации"""
    message = WebSocketMessage(
        type=WebSocketMessageType.SYNC_PROGRESS,
        data={
            "entity_type": entity_type,
            "task_id": task_id,
            "current": current,
            "total": total,
            "progress": (current / total * 100) if total > 0 else 0,
            "timestamp": datetime.now().isoformat()
        },
        timestamp=datetime.now().isoformat()
    )
    await manager.broadcast(message, "sync_updates")

async def _send_sync_completed(
    entity_type: str, 
    task_id: str, 
    processed: int, 
    created: int, 
    updated: int, 
    error: Optional[str] = None
):
    """Отправка уведомления о завершении синхронизации"""
    message = WebSocketMessage(
        type=WebSocketMessageType.SYNC_COMPLETED,
        data={
            "entity_type": entity_type,
            "task_id": task_id,
            "processed": processed,
            "created": created,
            "updated": updated,
            "error": error,
            "completed_at": datetime.now().isoformat()
        },
        timestamp=datetime.now().isoformat()
    )
    await manager.broadcast(message, "sync_updates")

async def _send_sync_error(entity_type: str, task_id: str, error: str):
    """Отправка уведомления об ошибке синхронизации"""
    message = WebSocketMessage(
        type=WebSocketMessageType.SYNC_ERROR,
        data={
            "entity_type": entity_type,
            "task_id": task_id,
            "error": error,
            "timestamp": datetime.now().isoformat()
        },
        timestamp=datetime.now().isoformat()
    )
    await manager.broadcast(message, "sync_updates")

async def _send_product_updated(product: Product):
    """Отправка уведомления об обновлении товара"""
    message = WebSocketMessage(
        type=WebSocketMessageType.PRODUCT_UPDATED,
        data={
            "product_id": product.id,
            "external_id": product.external_id,
            "name": product.name,
            "price": product.price,
            "quantity": product.quantity,
            "updated_at": datetime.now().isoformat()
        },
        timestamp=datetime.now().isoformat()
    )
    await manager.broadcast(message, "product_updates")