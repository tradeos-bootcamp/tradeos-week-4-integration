from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, Enum, Text, Float
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import enum
import uuid
from app.database import Base

class IntegrationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    SYNCING = "syncing"

class SyncType(str, enum.Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    MANUAL = "manual"

class IntegrationLogLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"

class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Тип интеграции
    integration_type = Column(String(50), nullable=False)  # "onec", "erp", "api"
    system_name = Column(String(100), nullable=False)      # "1C:Торговля 11.5"
    system_version = Column(String(50), nullable=True)
    
    # Настройки подключения
    base_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=True)
    username = Column(String(100), nullable=True)
    password = Column(String(500), nullable=True)  # Зашифрованное поле
    
    # Дополнительные настройки
    settings = Column(JSON, default={})
    
    # Состояние
    status = Column(Enum(IntegrationStatus), default=IntegrationStatus.INACTIVE)
    is_enabled = Column(Boolean, default=True)
    is_healthy = Column(Boolean, default=False)
    
    # Время синхронизации
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    next_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_interval = Column(Integer, default=3600)  # секунды
    
    # Статистика
    total_syncs = Column(Integer, default=0)
    successful_syncs = Column(Integer, default=0)
    failed_syncs = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    # Метрики
    avg_response_time = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    
    # Даты
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Integration {self.name} ({self.integration_type})>"

class SyncLog(Base):
    __tablename__ = "sync_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Детали синхронизации
    sync_type = Column(Enum(SyncType), nullable=False)
    entity_type = Column(String(50), nullable=False)  # "nomenclature", "stock", "orders"
    
    # Статус
    status = Column(String(20), nullable=False)  # "pending", "running", "completed", "failed"
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Результаты
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    created_items = Column(Integer, default=0)
    updated_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    # Ошибки
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Длительность
    duration_seconds = Column(Float, nullable=True)
    
    # Метаданные
    metadata = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<SyncLog {self.entity_type} ({self.status})>"

class IntegrationLog(Base):
    __tablename__ = "integration_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Логирование
    level = Column(Enum(IntegrationLogLevel), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    
    # Контекст
    operation = Column(String(100), nullable=True)
    endpoint = Column(String(500), nullable=True)
    http_method = Column(String(10), nullable=True)
    status_code = Column(Integer, nullable=True)
    
    # Время
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<IntegrationLog {self.level}: {self.message[:50]}...>"
