# app/api/v1/endpoints/auth.py
from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import (
    create_access_token, 
    create_refresh_token,
    verify_token,
    get_password_hash
)
from app.db.session import get_db
from app.models.user import UserRole
from app.api.deps import get_current_active_user, require_admin
from app.crud.user import (
    authenticate_user, 
    create_user, 
    get_user_by_username,
    get_users,
    change_user_role,
    verify_user
)
from app.schemas.user import (
    UserCreate, 
    UserResponse, 
    Token,
    LoginRequest,
    RefreshTokenRequest,
    UserUpdate
)

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate
) -> Any:
    """
    Регистрация нового пользователя.
    """
    try:
        user = create_user(db, user_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return user

@router.post("/login", response_model=Token)
def login(
    db: Session = Depends(get_db),
    form_data: LoginRequest = Body(...)
) -> Any:
    """
    OAuth2 аутентификация с получением JWT токенов.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаем access токен
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    # Создаем refresh токен
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
def refresh_token(
    db: Session = Depends(get_db),
    token_data: RefreshTokenRequest = Body(...)
) -> Any:
    """
    Обновление access токена с помощью refresh токена.
    """
    payload = verify_token(token_data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user = get_user_by_username(db, username=username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Создаем новый access токен
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "refresh_token": token_data.refresh_token,  # Тот же refresh токен
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Получить информацию о текущем пользователе.
    """
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user_me(
    *,
    db: Session = Depends(get_db),
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Обновить информацию о текущем пользователе.
    """
    from app.crud.user import update_user
    
    user = update_user(db, current_user.id, user_update)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.post("/me/change-password")
def change_password_me(
    *,
    db: Session = Depends(get_db),
    current_password: str = Body(...),
    new_password: str = Body(..., min_length=8),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Изменить пароль текущего пользователя.
    """
    from app.core.security import verify_password
    from app.crud.user import update_user
    
    # Проверяем текущий пароль
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Обновляем пароль
    update_data = UserUpdate(password=new_password)
    user = update_user(db, current_user.id, update_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "Password changed successfully"}

# Административные endpoints
@router.get("/users", response_model=list[UserResponse])
def read_all_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Получить список всех пользователей (только для админов).
    """
    users = get_users(db, skip=skip, limit=limit)
    return users

@router.put("/users/{user_id}/role")
def change_user_role_admin(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    new_role: UserRole,
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Изменить роль пользователя (только для админов).
    """
    user = change_user_role(db, user_id, new_role)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": f"User role changed to {new_role}"}

@router.post("/users/{user_id}/verify")
def verify_user_admin(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Подтвердить пользователя (только для админов).
    """
    user = verify_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "User verified successfully"}