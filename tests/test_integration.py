import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
from app.services.onec_client import OneCClient, OneCApiError
from app.services.websocket_manager import ConnectionManager, WebSocketMessage
from app.tasks.sync_tasks import sync_nomenclature

@pytest.mark.asyncio
async def test_onec_client_connection():
    """Тест подключения к 1С"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        
        mock_client_instance = AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = OneCClient(base_url="http://localhost:8080", api_key="test-key")
        
        # Тестируем health check
        result = await client.health_check()
        assert result == True
        
        # Тестируем получение номенклатуры
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "123",
                    "code": "TEST001",
                    "name": "Test Product",
                    "price": 100.0,
                    "quantity": 10,
                    "updated_at": "2024-01-20T10:00:00Z"
                }
            ]
        }
        
        products = await client.get_nomenclature()
        assert len(products) == 1
        assert products[0].id == "123"
        assert products[0].name == "Test Product"

@pytest.mark.asyncio
async def test_websocket_manager():
    """Тест WebSocket менеджера"""
    manager = ConnectionManager()
    
    # Тест подключения
    mock_websocket = AsyncMock()
    await manager.connect(mock_websocket, ["test_channel"])
    
    assert mock_websocket in manager.active_connections["test_channel"]
    assert mock_websocket in manager.active_connections["all"]
    
    # Тест отправки сообщения
    message = WebSocketMessage(
        type="test_message",
        data={"test": "data"},
        timestamp=datetime.now().isoformat()
    )
    
    await manager.send_personal_message(message, mock_websocket)
    mock_websocket.send_json.assert_called_once()
    
    # Тест отключения
    manager.disconnect(mock_websocket)
    assert mock_websocket not in manager.active_connections["test_channel"]

def test_sync_nomenclature_task():
    """Тест задачи синхронизации"""
    with patch('app.tasks.sync_tasks.SessionLocal') as mock_session_local, \
         patch('app.tasks.sync_tasks._get_integrations_for_sync') as mock_get_integrations, \
         patch('app.tasks.sync_tasks.OneCClient') as mock_client_class, \
         patch('app.tasks.sync_tasks.create_or_update_product') as mock_create_product:
        
        # Настраиваем моки
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_integration = Mock()
        mock_integration.id = "test-uuid"
        mock_integration.name = "Test Integration"
        mock_integration.base_url = "http://localhost:8080"
        mock_integration.api_key = "test-key"
        mock_integration.settings = {}
        mock_get_integrations.return_value = [mock_integration]
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Мокируем получение товаров из 1С
        mock_product = Mock()
        mock_product.id = "123"
        mock_product.code = "TEST001"
        mock_product.name = "Test Product"
        mock_product.price = 100.0
        mock_product.quantity = 10
        mock_product.updated_at = datetime.now()
        mock_client.get_nomenclature.return_value = [mock_product]
        
        # Запускаем задачу
        result = sync_nomenclature()
        
        # Проверяем результаты
        assert result["status"] == "completed"
        assert result["processed"] > 0
        
        # Проверяем, что товар был создан/обновлен
        mock_create_product.assert_called()

@pytest.mark.asyncio
async def test_integration_error_handling():
    """Тест обработки ошибок интеграции"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client_instance = AsyncMock()
        
        # Симулируем ошибку соединения
        mock_client_instance.request.side_effect = Exception("Connection failed")
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = OneCClient(base_url="http://localhost:8080")
        
        with pytest.raises(OneCApiError):
            await client.get_nomenclature()

def test_websocket_message_structure():
    """Тест структуры WebSocket сообщений"""
    message = WebSocketMessage(
        type="test_type",
        data={"key": "value"},
        timestamp="2024-01-20T10:00:00Z"
    )
    
    message_dict = message.to_dict()
    
    assert message_dict["type"] == "test_type"
    assert message_dict["data"] == {"key": "value"}
    assert message_dict["timestamp"] == "2024-01-20T10:00:00Z"
    assert "message_id" in message_dict