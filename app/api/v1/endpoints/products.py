# app/api/v1/endpoints/products.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_active_user, require_manager, optional_auth
from app.models.user import UserRole
from app.schemas.product import Product, ProductCreate, ProductUpdate
from app.crud.product import (
    get_product, 
    get_products, 
    create_product, 
    update_product, 
    delete_product,
    get_products_by_category,
    search_products
)

router = APIRouter()

@router.get("/", response_model=List[Product])
def read_products(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    current_user = Depends(optional_auth)
) -> Any:
    """
    Получить список товаров.
    Доступно всем (даже неаутентифицированным).
    """
    if category:
        products = get_products_by_category(db, category=category, skip=skip, limit=limit)
    else:
        products = get_products(db, skip=skip, limit=limit)
    
    # Фильтрация по цене
    if min_price is not None:
        products = [p for p in products if p.price >= min_price]
    if max_price is not None:
        products = [p for p in products if p.price <= max_price]
    
    return products

@router.get("/search")
def search_products_endpoint(
    db: Session = Depends(get_db),
    q: str = Query(..., min_length=2, description="Search query"),
    skip: int = 0,
    limit: int = 50,
    current_user = Depends(optional_auth)
) -> Any:
    """
    Поиск товаров.
    Доступно всем.
    """
    products = search_products(db, query=q, skip=skip, limit=limit)
    return products

@router.get("/{product_id}", response_model=Product)
def read_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(optional_auth)
) -> Any:
    """
    Получить товар по ID.
    Доступно всем.
    """
    product = get_product(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return product

@router.post("/", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_new_product(
    *,
    db: Session = Depends(get_db),
    product_in: ProductCreate,
    current_user = Depends(require_manager)  # Только менеджеры и админы
) -> Any:
    """
    Создать новый товар.
    Требуется роль менеджера или администратора.
    """
    return create_product(db=db, product=product_in)

@router.put("/{product_id}", response_model=Product)
def update_existing_product(
    *,
    db: Session = Depends(get_db),
    product_id: int,
    product_in: ProductUpdate,
    current_user = Depends(require_manager)  # Только менеджеры и админы
) -> Any:
    """
    Обновить существующий товар.
    Требуется роль менеджера или администратора.
    """
    product = get_product(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return update_product(db=db, product=product, product_update=product_in)

@router.delete("/{product_id}")
def delete_existing_product(
    *,
    db: Session = Depends(get_db),
    product_id: int,
    current_user = Depends(require_admin)  # Только админы
) -> Any:
    """
    Удалить товар.
    Требуется роль администратора.
    """
    product = get_product(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    delete_product(db=db, product_id=product_id)
    return {"message": "Product deleted successfully"}