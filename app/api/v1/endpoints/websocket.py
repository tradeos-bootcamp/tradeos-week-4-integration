from typing import List
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import asyncio
from app.db.session import get_db
from app.api.deps import get_current_user_optional
from app.services.websocket_manager import manager, WebSocketMessage, WebSocketMessageType
from datetime import datetime

router = APIRouter()
security = HTTPBearer()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    channels: str = Query("sync_updates,product_updates", description="Каналы для подписки"),
    token: str = Query(None, description="JWT токен для аутентификации")
):
    """
    WebSocket endpoint для real-time уведомлений.
    
    Поддерживаемые каналы:
    - sync_updates: обновления синхронизации
    - product_updates: обновления товаров
    - order_updates: обновления заказов
    - system_notifications: системные уведомления
    - all: все сообщения
    """
    
    # Разбираем каналы
    channel_list = [ch.strip() for ch in channels.split(",")]
    
    # Получаем информацию о пользователе (если есть токен)
    user_info = None
    db = None
    
    try:
        # Получаем сессию БД
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        # Если есть токен, пытаемся аутентифицировать пользователя
        if token:
            try:
                current_user = await get_current_user_optional(db, token)
                if current_user:
                    user_info = {
                        "id": current_user.id,
                        "username": current_user.username,
                        "email": current_user.email,
                        "role": current_user.role
                    }
            except Exception as e:
                # Если токен невалидный, продолжаем без аутентификации
                pass
        
        # Подключаем клиента
        await manager.connect(websocket, channel_list, user_info)
        
        # Бесконечный цикл для получения сообщений
        while True:
            try:
                # Ожидаем сообщение от клиента
                data = await websocket.receive_text()
                
                # Обновляем статистику
                manager.stats["messages_received"] += 1
                
                # Парсим сообщение
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type")
                    
                    # Обработка PONG
                    if message_type == "pong":
                        # Просто обновляем время активности
                        if websocket in manager.connection_info:
                            manager.connection_info[websocket]["last_activity"] = datetime.now().isoformat()
                    
                    # Обработка подписки/отписки от каналов
                    elif message_type == "subscribe":
                        new_channels = message_data.get("channels", [])
                        await _handle_subscribe(websocket, new_channels)
                    
                    elif message_type == "unsubscribe":
                        channels_to_remove = message_data.get("channels", [])
                        await _handle_unsubscribe(websocket, channels_to_remove)
                    
                    # Обработка запроса статистики
                    elif message_type == "get_stats":
                        stats = await manager.get_connection_stats()
                        response = WebSocketMessage(
                            type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                            data={"stats": stats},
                            timestamp=datetime.now().isoformat()
                        )
                        await manager.send_personal_message(response, websocket)
                    
                except json.JSONDecodeError:
                    # Невалидный JSON
                    error_msg = WebSocketMessage(
                        type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                        data={"error": "Invalid JSON format"},
                        timestamp=datetime.now().isoformat()
                    )
                    await manager.send_personal_message(error_msg, websocket)
                
                except Exception as e:
                    logger.error(f"Error processing client message: {e}")
                    
            except WebSocketDisconnect:
                # Клиент отключился
                manager.disconnect(websocket)
                break
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                # Отправляем сообщение об ошибке
                error_msg = WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                    data={"error": "Internal server error"},
                    timestamp=datetime.now().isoformat()
                )
                try:
                    await manager.send_personal_message(error_msg, websocket)
                except:
                    pass
                break
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Закрываем соединение с БД
        if db:
            try:
                await db_gen.aclose()
            except:
                pass

async def _handle_subscribe(websocket: WebSocket, channels: List[str]):
    """Обработка подписки на каналы"""
    if websocket not in manager.connection_info:
        return
    
    connection_info = manager.connection_info[websocket]
    current_channels = set(connection_info["channels"])
    
    for channel in channels:
        if channel in manager.active_connections:
            manager.active_connections[channel].add(websocket)
            current_channels.add(channel)
    
    # Обновляем информацию
    connection_info["channels"] = list(current_channels)
    
    # Отправляем подтверждение
    response = WebSocketMessage(
        type=WebSocketMessageType.SYSTEM_NOTIFICATION,
        data={
            "message": f"Subscribed to channels: {channels}",
            "current_channels": list(current_channels)
        },
        timestamp=datetime.now().isoformat()
    )
    await manager.send_personal_message(response, websocket)

async def _handle_unsubscribe(websocket: WebSocket, channels: List[str]):
    """Обработка отписки от каналов"""
    if websocket not in manager.connection_info:
        return
    
    connection_info = manager.connection_info[websocket]
    current_channels = set(connection_info["channels"])
    
    for channel in channels:
        if channel in manager.active_connections:
            manager.active_connections[channel].discard(websocket)
            current_channels.discard(channel)
    
    # Обновляем информацию
    connection_info["channels"] = list(current_channels)
    
    # Отправляем подтверждение
    response = WebSocketMessage(
        type=WebSocketMessageType.SYSTEM_NOTIFICATION,
        data={
            "message": f"Unsubscribed from channels: {channels}",
            "current_channels": list(current_channels)
        },
        timestamp=datetime.now().isoformat()
    )
    await manager.send_personal_message(response, websocket)

@router.get("/ws/stats")
async def get_websocket_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """
    Получение статистики WebSocket соединений.
    Только для администраторов.
    """
    from app.api.deps import require_admin
    
    # Проверяем права
    if current_user:
        await require_admin(current_user)
    
    stats = await manager.get_connection_stats()
    return stats