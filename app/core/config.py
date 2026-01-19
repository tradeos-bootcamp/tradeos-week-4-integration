from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, PostgresDsn, RedisDsn, validator
import secrets

class Settings(BaseSettings):
    # Существующие настройки...
    PROJECT_NAME: str = "TradeOS API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Безопасность
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "ws://localhost:3000",  # Для WebSocket
    ]
    
    # База данных
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "tradeos_user"
    POSTGRES_PASSWORD: str = "tradeos_password"
    POSTGRES_DB: str = "tradeos_db"
    DATABASE_URL: Optional[PostgresDsn] = None
    
    # НОВЫЕ НАСТРОЙКИ для недели 4
    
    # Redis для Celery и кэша
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[RedisDsn] = None
    
    @validator("REDIS_URL", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: dict) -> str:
        if isinstance(v, str):
            return v
        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST", "localhost"),
            port=values.get("REDIS_PORT", 6379),
            path=f"/{values.get('REDIS_DB', 0)}",
        )
    
    # Настройки 1С интеграции
    ONEC_BASE_URL: str = "http://localhost:8080"
    ONEC_API_KEY: str = "your-1c-api-key"
    ONEC_TIMEOUT: int = 30
    ONEC_MAX_RETRIES: int = 3
    
    # Настройки синхронизации
    SYNC_NOMENCLATURE_INTERVAL: int = 3600  # секунды
    SYNC_STOCK_INTERVAL: int = 900          # 15 минут
    SYNC_ORDERS_INTERVAL: int = 300         # 5 минут
    
    # WebSocket
    WEBSOCKET_PORT: int = 8001
    WEBSOCKET_PING_INTERVAL: int = 20
    WEBSOCKET_PING_TIMEOUT: int = 20
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "Europe/Moscow"
    CELERY_ENABLE_UTC: bool = True
    
    @validator("CELERY_BROKER_URL", pre=True)
    def assemble_celery_broker_url(cls, v: Optional[str], values: dict) -> str:
        if isinstance(v, str):
            return v
        return str(values.get("REDIS_URL")) + "/0"
    
    @validator("CELERY_RESULT_BACKEND", pre=True)
    def assemble_celery_result_backend(cls, v: Optional[str], values: dict) -> str:
        if isinstance(v, str):
            return v
        return str(values.get("REDIS_URL")) + "/1"
    
    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/tradeos.log"
    
    # Настройки файлов
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()