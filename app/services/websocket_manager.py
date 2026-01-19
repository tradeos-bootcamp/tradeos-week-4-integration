import asyncio
import json
import logging
from typing import Dict, Set, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketMessageType(str, Enum):
    """Типы WebSocket сообщений"""
    SYNC_STARTED = "sync_started"
    SYNC_PROGRESS = "sync_progress"
    SYNC_COMPLETED = "sync_completed"
    SYNC_ERROR = "sync_error"
    PRODUCT_UPDATED = "product_updated"
    STOCK_UPDATED = "stock_updated"
    ORDER_CREATED = "order_created"
    ORDER_UPDATED = "order_updated"
    SYSTEM_NOTIFICATION = "system_notification"
    PING = "ping"
    PONG = "pong"

@dataclass
class WebSocketMessage:
    """Структура WebSocket сообщения"""
    type: WebSocketMessageType
    data: Dict[str, Any]
    timestamp: str
    message_id: str = None
    
    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

class ConnectionManager:
    """Менеджер WebSocket соединений"""
    
    def __init__(self):
        # Активные соединения по каналам
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "sync_updates": set(),
            "product_updates": set(),
            "order_updates": set(),
            "system_notifications": set(),
            "all": set()  # Все сообщения
        }
        
        # Информация о подключениях
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
        
        # Статистика
        self.stats = {
            "total_connections": 0,
            "current_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0
        }
        
        # Очередь сообщений для отложенной отправки
        self.message_queue: asyncio.Queue = asyncio.Queue()
        
        # Фоновая задача для обработки очереди
        self._queue_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запуск менеджера"""
        if self._queue_task is None:
            self._queue_task = asyncio.create_task(self._process_message_queue())
            logger.info("WebSocket manager started")
    
    async def stop(self):
        """Остановка менеджера"""
        if self._queue_task:
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass
            self._queue_task = None
            logger.info("WebSocket manager stopped")
    
    async def _process_message_queue(self):
        """Обработка очереди сообщений"""
        while True:
            try:
                message, channel = await self.message_queue.get()
                await self._broadcast_internal(message, channel)
                self.message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message queue: {e}")
                self.stats["errors"] += 1
    
    async def connect(
        self,
        websocket: WebSocket,
        channels: List[str],
        user_info: Optional[Dict[str, Any]] = None
    ):
        """Подключение клиента"""
        await websocket.accept()
        
        # Регистрируем соединение
        for channel in channels:
            if channel in self.active_connections:
                self.active_connections[channel].add(websocket)
        
        self.active_connections["all"].add(websocket)
        
        # Сохраняем информацию о подключении
        connection_id = str(uuid.uuid4())
        self.connection_info[websocket] = {
            "id": connection_id,
            "channels": channels,
            "connected_at": datetime.now().isoformat(),
            "user": user_info or {},
            "last_activity": datetime.now().isoformat()
        }
        
        # Обновляем статистику
        self.stats["total_connections"] += 1
        self.stats["current_connections"] += 1
        
        logger.info(f"WebSocket connected: {connection_id} on channels: {channels}")
        
        # Отправляем приветственное сообщение
        welcome_msg = WebSocketMessage(
            type=WebSocketMessageType.SYSTEM_NOTIFICATION,
            data={
                "message": "Connected to TradeOS WebSocket",
                "connection_id": connection_id,
                "channels": channels
            },
            timestamp=datetime.now().isoformat()
        )
        
        await websocket.send_json(welcome_msg.to_dict())
    
    def disconnect(self, websocket: WebSocket):
        """Отключение клиента"""
        connection_info = self.connection_info.get(websocket)
        
        if connection_info:
            # Удаляем из всех каналов
            for channel in connection_info["channels"]:
                if channel in self.active_connections:
                    self.active_connections[channel].discard(websocket)
            
            self.active_connections["all"].discard(websocket)
            
            # Удаляем информацию
            del self.connection_info[websocket]
            
            # Обновляем статистику
            self.stats["current_connections"] -= 1
            
            logger.info(f"WebSocket disconnected: {connection_info['id']}")
    
    async def send_personal_message(
        self,
        message: WebSocketMessage,
        websocket: WebSocket
    ):
        """Отправка личного сообщения"""
        try:
            await websocket.send_json(message.to_dict())
            self.stats["messages_sent"] += 1
            
            # Обновляем время последней активности
            if websocket in self.connection_info:
                self.connection_info[websocket]["last_activity"] = datetime.now().isoformat()
                
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.stats["errors"] += 1
    
    async def broadcast(
        self,
        message: WebSocketMessage,
        channel: str = "all"
    ):
        """Асинхронная широковещательная рассылка"""
        await self.message_queue.put((message, channel))
    
    async def _broadcast_internal(
        self,
        message: WebSocketMessage,
        channel: str = "all"
    ):
        """Внутренняя реализация широковещательной рассылки"""
        if channel not in self.active_connections:
            logger.warning(f"Unknown channel: {channel}")
            return
        
        disconnected = set()
        
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message.to_dict())
                self.stats["messages_sent"] += 1
                
                # Обновляем время последней активности
                if connection in self.connection_info:
                    self.connection_info[connection]["last_activity"] = datetime.now().isoformat()
                    
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.add(connection)
                self.stats["errors"] += 1
        
        # Удаляем отключенные соединения
        for connection in disconnected:
            self.disconnect(connection)
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Получение статистики соединений"""
        active_by_channel = {
            channel: len(connections)
            for channel, connections in self.active_connections.items()
        }
        
        return {
            **self.stats,
            "active_by_channel": active_by_channel,
            "total_active_connections": len(self.active_connections["all"]),
            "timestamp": datetime.now().isoformat()
        }
    
    async def ping_all(self):
        """Ping всех активных соединений"""
        ping_msg = WebSocketMessage(
            type=WebSocketMessageType.PING,
            data={"timestamp": datetime.now().isoformat()},
            timestamp=datetime.now().isoformat()
        )
        
        await self.broadcast(ping_msg, "all")
        logger.debug("Sent ping to all connections")

# Глобальный экземпляр менеджера
manager = ConnectionManager()