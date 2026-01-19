# app/api/v1/endpoints/integration.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.db.session import get_db
from app.api.deps import get_current_user, require_admin
from app.schemas.integration import (
    IntegrationCreate, IntegrationUpdate, IntegrationResponse,
    SyncRequest, SyncLogResponse, IntegrationStats
)
from app.crud.integration import (
    create_integration, get_integration, get_integrations,
    update_integration, delete_integration, get_sync_logs,
    get_integration_stats, test_integration_connection
)
from app.tasks.sync_tasks import sync_nomenclature, sync_stock
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/integrations", response_model=List[IntegrationResponse])
async def list_integrations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    is_enabled: Optional[bool] = Query(None),
    integration_type: Optional[str] = Query(None),
    current_user = Depends(get_current_user)
):
    """Получение списка интеграций"""
    integrations = get_integrations(
        db, skip=skip, limit=limit,
        is_enabled=is_enabled,
        integration_type=integration_type
    )
    return integrations

@router.post("/integrations", response_model=IntegrationResponse, status_code=201)
async def create_new_integration(
    integration_in: IntegrationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Создание новой интеграции"""
    # Проверяем, что нет интеграции с таким именем
    existing = get_integrations(db, name=integration_in.name)
    if existing:
        raise HTTPException(status_code=400, detail="Integration with this name already exists")
    
    integration = create_integration(db, integration_in)
    
    # Тестируем соединение
    try:
        test_result = test_integration_connection(db, integration.id)
        if not test_result["success"]:
            logger.warning(f"Integration {integration.name} connection test failed")
    except Exception as e:
        logger.error(f"Error testing connection for {integration.name}: {e}")
    
    return integration

@router.get("/integrations/{integration_id}", response_model=IntegrationResponse)
async def get_integration_by_id(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получение интеграции по ID"""
    integration = get_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration

@router.put("/integrations/{integration_id}", response_model=IntegrationResponse)
async def update_integration_by_id(
    integration_id: UUID,
    integration_in: IntegrationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Обновление интеграции"""
    integration = get_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    updated_integration = update_integration(db, integration, integration_in)
    
    # Перетестируем соединение после обновления
    try:
        test_integration_connection(db, integration_id)
    except Exception as e:
        logger.error(f"Error testing connection after update: {e}")
    
    return updated_integration

@router.delete("/integrations/{integration_id}", status_code=204)
async def delete_integration_by_id(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Удаление интеграции"""
    integration = get_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Не удаляем, а отключаем
    integration.is_enabled = False
    db.commit()
    
    return

@router.post("/integrations/{integration_id}/sync", status_code=202)
async def trigger_sync(
    integration_id: UUID,
    sync_request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Запуск синхронизации для интеграции"""
    integration = get_integration(db, integration_id)
    if not integration or not integration.is_enabled:
        raise HTTPException(status_code=404, detail="Integration not found or disabled")
    
    # Выбираем задачу в зависимости от типа сущности
    if sync_request.entity_type == "nomenclature":
        task = sync_nomenclature.apply_async(
            args=[str(integration_id)],
            task_id=f"sync_nomenclature_{integration_id}_{sync_request.sync_type}"
        )
    elif sync_request.entity_type == "stock":
        task = sync_stock.apply_async(
            args=[str(integration_id)],
            task_id=f"sync_stock_{integration_id}_{sync_request.sync_type}"
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported entity type")
    
    return {
        "task_id": task.id,
        "status": "started",
        "message": f"Sync task started for {sync_request.entity_type}"
    }

@router.get("/integrations/{integration_id}/sync-logs", response_model=List[SyncLogResponse])
async def get_integration_sync_logs(
    integration_id: UUID,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    current_user = Depends(get_current_user)
):
    """Получение логов синхронизации для интеграции"""
    logs = get_sync_logs(
        db, integration_id,
        skip=skip, limit=limit,
        status=status, entity_type=entity_type
    )
    return logs

@router.get("/integrations/{integration_id}/stats", response_model=IntegrationStats)
async def get_integration_stats(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получение статистики по интеграции"""
    stats = get_integration_stats(db, integration_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Integration not found")
    return stats

@router.post("/integrations/{integration_id}/test-connection")
async def test_connection(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Тестирование соединения с интеграцией"""
    integration = get_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    result = test_integration_connection(db, integration_id)
    
    return {
        "integration_id": integration_id,
        "integration_name": integration.name,
        **result
    }

@router.post("/integrations/{integration_id}/enable")
async def enable_integration(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Включение интеграции"""
    integration = get_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    integration.is_enabled = True
    db.commit()
    
    return {"message": "Integration enabled"}

@router.post("/integrations/{integration_id}/disable")
async def disable_integration(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Отключение интеграции"""
    integration = get_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    integration.is_enabled = False
    db.commit()
    
    return {"message": "Integration disabled"}

@router.get("/sync-status")
async def get_sync_status(
    db: Session = Depends(get_db),
    last_hours: int = Query(24, ge=1, le=168),
    current_user = Depends(get_current_user)
):
    """Получение статуса синхронизаций за последние N часов"""
    from sqlalchemy import func, and_
    from datetime import datetime, timedelta
    from app.models.integration import SyncLog
    
    time_threshold = datetime.utcnow() - timedelta(hours=last_hours)
    
    # Общая статистика
    total_syncs = db.query(func.count(SyncLog.id)).filter(
        SyncLog.started_at >= time_threshold
    ).scalar()
    
    completed_syncs = db.query(func.count(SyncLog.id)).filter(
        and_(
            SyncLog.started_at >= time_threshold,
            SyncLog.status == "completed"
        )
    ).scalar()
    
    failed_syncs = db.query(func.count(SyncLog.id)).filter(
        and_(
            SyncLog.started_at >= time_threshold,
            SyncLog.status == "failed"
        )
    ).scalar()
    
    # Статистика по типам сущностей
    entity_stats = {}
    entity_types = db.query(SyncLog.entity_type).distinct().all()
    
    for (entity_type,) in entity_types:
        stats = db.query(
            func.count(SyncLog.id),
            func.sum(SyncLog.processed_items),
            func.sum(SyncLog.created_items),
            func.sum(SyncLog.updated_items)
        ).filter(
            and_(
                SyncLog.started_at >= time_threshold,
                SyncLog.entity_type == entity_type,
                SyncLog.status == "completed"
            )
        ).first()
        
        entity_stats[entity_type] = {
            "syncs": stats[0] or 0,
            "processed": stats[1] or 0,
            "created": stats[2] or 0,
            "updated": stats[3] or 0
        }
    
    return {
        "period_hours": last_hours,
        "total_syncs": total_syncs,
        "completed_syncs": completed_syncs,
        "failed_syncs": failed_syncs,
        "success_rate": (completed_syncs / total_syncs * 100) if total_syncs > 0 else 0,
        "entity_statistics": entity_stats,
        "last_sync_time": time_threshold.isoformat()
    }