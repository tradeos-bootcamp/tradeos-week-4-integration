# scripts/test_integration_client.py
import asyncio
import json
import websocket
import threading
from datetime import datetime
import httpx

class IntegrationTestClient:
    """Клиент для тестирования интеграции"""
    
    def __init__(self, base_url="http://localhost:8000", ws_url="ws://localhost:8001"):
        self.base_url = base_url
        self.ws_url = ws_url
        self.ws = None
        
    async def test_http_api(self):
        """Тестирование HTTP API"""
        print("=" * 50)
        print("Testing HTTP API...")
        print("=" * 50)
        
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            # Тест эндпоинтов интеграции
            try:
                # Список интеграций
                response = await client.get("/api/v1/integrations")
                print(f"GET /integrations: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"  Found {len(data)} integrations")
                
                # Создание тестовой интеграции
                test_integration = {
                    "name": "Test 1C Integration",
                    "description": "Тестовая интеграция с 1С",
                    "integration_type": "onec",
                    "system_name": "1C:Торговля 11.5",
                    "base_url": "http://mock-1c:8080",
                    "api_key": "test-api-key-123",
                    "is_enabled": True
                }
                
                response = await client.post("/api/v1/integrations", json=test_integration)
                print(f"POST /integrations: {response.status_code}")
                if response.status_code == 201:
                    integration = response.json()
                    print(f"  Created integration: {integration['id']}")
                    return integration["id"]
                    
            except Exception as e:
                print(f"  Error: {e}")
                
        return None
    
    def on_websocket_message(self, ws, message):
        """Обработчик сообщений WebSocket"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            timestamp = data.get("timestamp", "")
            
            print(f"\n[WS] {timestamp} - {msg_type}")
            
            if msg_type == "sync_started":
                print(f"  Sync started: {data['data']['entity_type']}")
            elif msg_type == "sync_progress":
                progress = data["data"]["progress"]
                print(f"  Progress: {progress:.1f}%")
            elif msg_type == "product_updated":
                product = data["data"]
                print(f"  Product updated: {product['name']} - ${product['price']}")
            elif msg_type == "system_notification":
                print(f"  Notification: {data['data'].get('message', '')}")
                
        except json.JSONDecodeError:
            print(f"\n[WS] Raw message: {message}")
    
    def on_websocket_error(self, ws, error):
        """Обработчик ошибок WebSocket"""
        print(f"\n[WS Error] {error}")
    
    def on_websocket_close(self, ws, close_status_code, close_msg):
        """Обработчик закрытия WebSocket"""
        print(f"\n[WS Closed] Code: {close_status_code}, Message: {close_msg}")
    
    def on_websocket_open(self, ws):
        """Обработчик открытия WebSocket"""
        print("\n[WS Connected]")
        # Подписываемся на каналы
        subscribe_msg = {
            "type": "subscribe",
            "channels": ["sync_updates", "product_updates", "system_notifications"]
        }
        ws.send(json.dumps(subscribe_msg))
    
    def test_websocket(self):
        """Тестирование WebSocket"""
        print("\n" + "=" * 50)
        print("Testing WebSocket...")
        print("=" * 50)
        
        # Подключаемся к WebSocket
        websocket_url = f"{self.ws_url}/ws?channels=sync_updates,product_updates"
        
        self.ws = websocket.WebSocketApp(
            websocket_url,
            on_open=self.on_websocket_open,
            on_message=self.on_websocket_message,
            on_error=self.on_websocket_error,
            on_close=self.on_websocket_close
        )
        
        # Запускаем в отдельном потоке
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
        
        print("WebSocket client started. Press Ctrl+C to stop.")
        return wst
    
    async def trigger_sync(self, integration_id):
        """Запуск синхронизации"""
        print("\n" + "=" * 50)
        print("Triggering synchronization...")
        print("=" * 50)
        
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            try:
                response = await client.post(
                    f"/api/v1/integrations/{integration_id}/sync",
                    json={"sync_type": "full", "entity_type": "nomenclature"}
                )
                
                if response.status_code == 202:
                    task = response.json()
                    print(f"Sync task started: {task['task_id']}")
                    print(f"Status URL: {self.base_url}/api/v1/tasks/{task['task_id']}")
                    return task["task_id"]
                else:
                    print(f"Failed to start sync: {response.status_code}")
                    print(response.text)
                    
            except Exception as e:
                print(f"Error triggering sync: {e}")
        
        return None
    
    async def monitor_task(self, task_id):
        """Мониторинг задачи"""
        print("\nMonitoring task status...")
        
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            for i in range(10):  # Проверяем 10 раз
                await asyncio.sleep(3)
                
                try:
                    response = await client.get(f"/api/v1/tasks/{task_id}")
                    
                    if response.status_code == 200:
                        task = response.json()
                        status = task["status"]
                        print(f"  Task status: {status}")
                        
                        if status in ["completed", "failed"]:
                            print(f"  Result: {task.get('result', {})}")
                            break
                            
                except Exception as e:
                    print(f"  Error checking task: {e}")

async def main():
    """Основная функция тестирования"""
    client = IntegrationTestClient()
    
    # Тестируем HTTP API
    integration_id = await client.test_http_api()
    
    if integration_id:
        # Запускаем WebSocket клиент
        ws_thread = client.test_websocket()
        
        # Даем время на подключение WebSocket
        await asyncio.sleep(2)
        
        # Запускаем синхронизацию
        task_id = await client.trigger_sync(integration_id)
        
        if task_id:
            # Мониторим задачу
            await client.monitor_task(task_id)
        
        # Ждем завершения WebSocket
        try:
            while ws_thread.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
    
    print("\n" + "=" * 50)
    print("Integration test completed")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())