from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

def make_celery():
    """Создание и настройка Celery приложения"""
    
    celery_app = Celery(
        "tradeos",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "app.tasks.sync_tasks",
            "app.tasks.notification_tasks",
            "app.tasks.import_tasks"
        ]
    )
    
    # Конфигурация
    celery_app.conf.update(
        task_serializer=settings.CELERY_TASK_SERIALIZER,
        result_serializer=settings.CELERY_RESULT_SERIALIZER,
        accept_content=settings.CELERY_ACCEPT_CONTENT,
        timezone=settings.CELERY_TIMEZONE,
        enable_utc=settings.CELERY_ENABLE_UTC,
        
        # Настройки задач
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 минут
        task_soft_time_limit=25 * 60,  # 25 минут
        
        # Настройки брокера
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=10,
        
        # Результаты
        result_expires=3600,  # 1 час
        
        # Сериализация
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        
        # Расписание задач
        beat_schedule={
            # Синхронизация номенклатуры каждый час
            'sync-nomenclature-hourly': {
                'task': 'app.tasks.sync_tasks.sync_nomenclature',
                'schedule': crontab(minute=0, hour='*/1'),
                'args': (),
                'options': {'queue': 'sync'}
            },
            
            # Синхронизация остатков каждые 15 минут
            'sync-stock-quarterly': {
                'task': 'app.tasks.sync_tasks.sync_stock',
                'schedule': crontab(minute='*/15'),
                'args': (),
                'options': {'queue': 'sync'}
            },
            
            # Проверка статуса интеграций каждые 5 минут
            'check-integrations': {
                'task': 'app.tasks.sync_tasks.check_integrations_health',
                'schedule': crontab(minute='*/5'),
                'args': (),
                'options': {'queue': 'monitoring'}
            },
            
            # Очистка старых логов каждый день в 2:00
            'cleanup-old-logs': {
                'task': 'app.tasks.sync_tasks.cleanup_old_logs',
                'schedule': crontab(minute=0, hour=2),
                'args': (30,),  # Удалять логи старше 30 дней
                'options': {'queue': 'maintenance'}
            },
            
            # Резервное копирование каждый день в 3:00
            'backup-database': {
                'task': 'app.tasks.sync_tasks.backup_database',
                'schedule': crontab(minute=0, hour=3),
                'args': (),
                'options': {'queue': 'maintenance'}
            }
        },
        
        # Очереди
        task_routes={
            'app.tasks.sync_tasks.*': {'queue': 'sync'},
            'app.tasks.notification_tasks.*': {'queue': 'notifications'},
            'app.tasks.import_tasks.*': {'queue': 'import'},
            'app.tasks.sync_tasks.cleanup_old_logs': {'queue': 'maintenance'},
            'app.tasks.sync_tasks.backup_database': {'queue': 'maintenance'},
        },
        
        # Работники
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        worker_concurrency=4
    )
    
    return celery_app

# Создаем экземпляр Celery
celery_app = make_celery()