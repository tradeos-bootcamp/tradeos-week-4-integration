# app/database.py - Полная рабочая версия
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

# URL базы данных
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://tradeosuser:tradeospassword@localhost:5432/tradeosdb"
)

# Создание движка SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Проверка соединения
    pool_recycle=300,        # Пересоздание каждые 5 мин
    echo=False               # Логи SQL (True для debug)
)

# Фабрика сессий
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Базовый класс для моделей
Base = declarative_base()

def get_db():
    """FastAPI dependency для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Создание таблиц при старте (dev)
def create_tables():
    Base.metadata.create_all(bind=engine)
