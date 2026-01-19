# app/crud/user.py
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from datetime import datetime

def get_user(db: Session, user_id: int) -> Optional[User]:
    """Получить пользователя по ID"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Получить пользователя по email"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Получить пользователя по username"""
    return db.query(User).filter(User.username == username).first()

def get_users(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None
) -> List[User]:
    """Получить список пользователей с фильтрами"""
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

def create_user(db: Session, user_in: UserCreate) -> User:
    """Создать нового пользователя"""
    # Проверяем, нет ли уже пользователя с таким email или username
    existing_user = db.query(User).filter(
        or_(User.email == user_in.email, User.username == user_in.username)
    ).first()
    
    if existing_user:
        if existing_user.email == user_in.email:
            raise ValueError("User with this email already exists")
        else:
            raise ValueError("User with this username already exists")
    
    # Хешируем пароль
    hashed_password = get_password_hash(user_in.password)
    
    # Создаем пользователя
    db_user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        phone=user_in.phone,
        hashed_password=hashed_password,
        role=UserRole.USER  # По умолчанию обычный пользователь
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
    """Обновить пользователя"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.dict(exclude_unset=True)
    
    # Если обновляем пароль, хешируем его
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    # Обновляем поля
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int) -> bool:
    """Удалить пользователя (мягкое удаление)"""
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    
    db_user.is_active = False
    db.commit()
    return True

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Аутентификация пользователя"""
    user = get_user_by_username(db, username)
    if not user:
        # Попробуем найти по email
        user = get_user_by_email(db, username)
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    if not user.is_active:
        return None
    
    # Обновляем время последнего входа
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user

def change_user_role(db: Session, user_id: int, new_role: UserRole) -> Optional[User]:
    """Изменить роль пользователя"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    db_user.role = new_role
    db.commit()
    db.refresh(db_user)
    return db_user

def verify_user(db: Session, user_id: int) -> Optional[User]:
    """Подтвердить пользователя"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    db_user.is_verified = True
    db.commit()
    db.refresh(db_user)
    return db_user