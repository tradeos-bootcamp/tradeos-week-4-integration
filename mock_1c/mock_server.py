# mock_1c/mock_server.py
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uvicorn
import json
import random
from pydantic import BaseModel
import hashlib

app = FastAPI(title="Mock 1C API", version="1.0")

# Хранилище данных в памяти
products_db = []
stock_db = []
orders_db = []
api_keys = ["test-api-key-123", "demo-1c-key-456"]

class Product(BaseModel):
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
    updated_at: Optional[str] = None

class Order(BaseModel):
    id: str
    number: str
    customer: Dict[str, Any]
    items: List[Dict[str, Any]]
    status: str
    total_amount: float
    created_at: str
    updated_at: str

# Инициализация тестовых данных
def init_test_data():
    categories = ["Электроника", "Одежда", "Продукты", "Книги", "Спорт"]
    manufacturers = ["Samsung", "Apple", "Nike", "Adidas", "Bosch"]
    
    for i in range(1, 101):
        product = {
            "id": f"PROD-{i:04d}",
            "code": f"CODE-{i:04d}",
            "name": f"Товар {i}",
            "full_name": f"Товар {i} - полное наименование",
            "article": f"ART-{i:04d}",
            "unit": "шт",
            "price": round(random.uniform(100, 10000), 2),
            "quantity": random.randint(0, 1000),
            "characteristics": {
                "weight": random.uniform(0.1, 50),
                "color": random.choice(["красный", "синий", "зеленый", "черный", "белый"]),
                "material": random.choice(["пластик", "металл", "дерево", "ткань"])
            },
            "category": random.choice(categories),
            "manufacturer": random.choice(manufacturers),
            "updated_at": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
        }
        products_db.append(product)
        
        # Создаем остатки
        for warehouse_id in ["WH-001", "WH-002", "WH-003"]:
            stock = {
                "product_id": product["id"],
                "warehouse_id": warehouse_id,
                "warehouse_name": f"Склад {warehouse_id[-3:]}",
                "quantity": random.randint(0, 500),
                "reserved": random.randint(0, 50),
                "available": random.randint(0, 450),
                "updated_at": datetime.now().isoformat()
            }
            stock_db.append(stock)

# Dependency для проверки API ключа
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not x_api_key or x_api_key not in api_keys:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key

@app.on_event("startup")
async def startup_event():
    init_test_data()
    print("Mock 1C server started with 100 test products")

@app.get("/hs/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/hs/api/nomenclature")
async def get_nomenclature(
    updated_since: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(verify_api_key)
):
    """Получение номенклатуры (мок)"""
    
    # Фильтрация по дате обновления
    filtered_products = products_db
    if updated_since:
        try:
            updated_date = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
            filtered_products = [
                p for p in products_db 
                if datetime.fromisoformat(p["updated_at"].replace('Z', '+00:00')) > updated_date
            ]
        except:
            pass
    
    # Пагинация
    start = offset
    end = start + limit
    paginated_products = filtered_products[start:end]
    
    return {
        "items": paginated_products,
        "total": len(filtered_products),
        "limit": limit,
        "offset": offset,
        "has_more": end < len(filtered_products)
    }

@app.get("/hs/api/stock")
async def get_stock(
    product_ids: Optional[str] = Query(None),
    warehouse_ids: Optional[str] = Query(None),
    api_key: str = Depends(verify_api_key)
):
    """Получение остатков (мок)"""
    
    filtered_stock = stock_db
    
    if product_ids:
        product_list = product_ids.split(",")
        filtered_stock = [s for s in filtered_stock if s["product_id"] in product_list]
    
    if warehouse_ids:
        warehouse_list = warehouse_ids.split(",")
        filtered_stock = [s for s in filtered_stock if s["warehouse_id"] in warehouse_list]
    
    return {
        "items": filtered_stock,
        "total": len(filtered_stock),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/hs/api/orders")
async def create_order(
    order_data: Dict[str, Any],
    api_key: str = Depends(verify_api_key)
):
    """Создание заказа (мок)"""
    
    order_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:10].upper()
    
    order = {
        "id": order_id,
        "number": f"ORDER-{order_id}",
        "customer": order_data.get("customer", {}),
        "items": order_data.get("items", []),
        "status": "created",
        "total_amount": sum(item.get("price", 0) * item.get("quantity", 0) for item in order_data.get("items", [])),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    orders_db.append(order)
    
    return {
        "success": True,
        "order_id": order_id,
        "order_number": order["number"],
        "message": "Order created successfully"
    }

@app.get("/hs/api/orders/{order_id}/status")
async def get_order_status(order_id: str, api_key: str = Depends(verify_api_key)):
    """Получение статуса заказа (мок)"""
    
    order = next((o for o in orders_db if o["id"] == order_id), None)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order_id,
        "status": order["status"],
        "updated_at": order["updated_at"]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)