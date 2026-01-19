import httpx
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class OneCApiError(Exception):
    """Базовое исключение для ошибок API 1С"""
    pass

class OneCConnectionError(OneCApiError):
    """Ошибка подключения к 1С"""
    pass

class OneCAuthError(OneCApiError):
    """Ошибка аутентификации в 1С"""
    pass

class OneCResponseError(OneCApiError):
    """Ошибка в ответе от 1С"""
    def __init__(self, message: str, status_code: int, response: Optional[dict] = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)

@dataclass
class OneCProduct:
    """Модель товара из 1С"""
    id: str
    code: str
    name: str
    full_name: Optional[str] = None
    article: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[float] = None
    characteristics: Optional[Dict] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    updated_at: Optional[datetime] = None

@dataclass
class OneCStock:
    """Модель остатков из 1С"""
    product_id: str
    warehouse_id: str
    warehouse_name: str
    quantity: float
    reserved: float = 0.0
    available: float = 0.0
    updated_at: Optional[datetime] = None

class OneCClient:
    """Клиент для работы с API 1С"""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Сессия HTTP
        self._client: Optional[httpx.AsyncClient] = None
        
        # Кэш для повторных запросов
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}
        
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
    
    async def connect(self):
        """Создание HTTP сессии"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers=self._get_headers()
            )
            logger.info(f"Connected to 1C API at {self.base_url}")
    
    async def disconnect(self):
        """Закрытие HTTP сессии"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Disconnected from 1C API")
    
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для запросов"""
        headers = {
            "User-Agent": "TradeOS-Integration/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        elif self.username and self.password:
            # Для Basic Auth
            import base64
            auth = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {auth}"
        
        return headers
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Выполнение HTTP запроса с повторными попытками"""
        
        if self._client is None:
            await self.connect()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Request to 1C: {method} {url} (attempt {attempt + 1})")
                
                response = await self._client.request(
                    method=method,
                    url=url,
                    **kwargs
                )
                
                # Проверяем статус ответа
                if response.status_code >= 400:
                    error_msg = f"1C API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg = f"{error_msg} - {error_data}"
                    except:
                        error_msg = f"{error_msg} - {response.text[:200]}"
                    
                    if response.status_code == 401:
                        raise OneCAuthError(error_msg)
                    elif response.status_code in [502, 503, 504]:
                        raise OneCConnectionError(error_msg)
                    else:
                        raise OneCResponseError(
                            error_msg,
                            response.status_code,
                            response.json() if response.headers.get('content-type') == 'application/json' else None
                        )
                
                # Парсим JSON ответ
                if response.content:
                    return response.json()
                return {}
                
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to connect to 1C after {self.max_retries} attempts: {e}")
                    raise OneCConnectionError(f"Connection failed: {e}")
                
                # Экспоненциальная задержка
                wait_time = 2 ** attempt
                logger.warning(f"Retrying in {wait_time}s... (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Unexpected error during 1C request: {e}")
                raise OneCApiError(f"Unexpected error: {e}")
    
    async def health_check(self) -> bool:
        """Проверка доступности 1С API"""
        try:
            await self._request("GET", "/hs/api/health")
            return True
        except OneCApiError:
            return False
    
    async def get_nomenclature(
        self,
        updated_since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OneCProduct]:
        """Получение номенклатуры из 1С"""
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if updated_since:
            params["updated_since"] = updated_since.isoformat()
        
        try:
            response = await self._request(
                "GET",
                "/hs/api/nomenclature",
                params=params
            )
            
            products = []
            for item in response.get("items", []):
                product = OneCProduct(
                    id=item.get("id"),
                    code=item.get("code"),
                    name=item.get("name"),
                    full_name=item.get("full_name"),
                    article=item.get("article"),
                    unit=item.get("unit"),
                    price=float(item.get("price", 0)) if item.get("price") else None,
                    quantity=float(item.get("quantity", 0)) if item.get("quantity") else None,
                    characteristics=item.get("characteristics"),
                    category=item.get("category"),
                    manufacturer=item.get("manufacturer"),
                    updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None
                )
                products.append(product)
            
            logger.info(f"Retrieved {len(products)} products from 1C")
            return products
            
        except OneCApiError as e:
            logger.error(f"Error getting nomenclature from 1C: {e}")
            raise
    
    async def get_stock(
        self,
        product_ids: Optional[List[str]] = None,
        warehouse_ids: Optional[List[str]] = None
    ) -> List[OneCStock]:
        """Получение остатков из 1С"""
        params = {}
        
        if product_ids:
            params["product_ids"] = ",".join(product_ids)
        
        if warehouse_ids:
            params["warehouse_ids"] = ",".join(warehouse_ids)
        
        try:
            response = await self._request(
                "GET",
                "/hs/api/stock",
                params=params
            )
            
            stocks = []
            for item in response.get("items", []):
                stock = OneCStock(
                    product_id=item.get("product_id"),
                    warehouse_id=item.get("warehouse_id"),
                    warehouse_name=item.get("warehouse_name"),
                    quantity=float(item.get("quantity", 0)),
                    reserved=float(item.get("reserved", 0)),
                    available=float(item.get("available", 0)),
                    updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None
                )
                stocks.append(stock)
            
            logger.info(f"Retrieved {len(stocks)} stock items from 1C")
            return stocks
            
        except OneCApiError as e:
            logger.error(f"Error getting stock from 1C: {e}")
            raise
    
    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создание заказа в 1С"""
        try:
            response = await self._request(
                "POST",
                "/hs/api/orders",
                json=order_data
            )
            
            logger.info(f"Order created in 1C: {response.get('order_id')}")
            return response
            
        except OneCApiError as e:
            logger.error(f"Error creating order in 1C: {e}")
            raise
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Получение статуса заказа из 1С"""
        try:
            response = await self._request(
                "GET",
                f"/hs/api/orders/{order_id}/status"
            )
            
            return response
            
        except OneCApiError as e:
            logger.error(f"Error getting order status from 1C: {e}")
            raise
    
    async def test_connection(self) -> Dict[str, Any]:
        """Тестирование соединения с 1С"""
        try:
            start_time = datetime.now()
            
            # Проверяем доступность
            health = await self.health_check()
            
            # Пробуем получить немного данных
            products = await self.get_nomenclature(limit=1)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "success": True,
                "health": health,
                "can_fetch_data": len(products) > 0,
                "response_time": duration,
                "timestamp": datetime.now().isoformat()
            }
            
        except OneCApiError as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
