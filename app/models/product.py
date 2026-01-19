class Product(Base):
    __tablename__ = "products"
    
    # Существующие поля...
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, default=0)
    category = Column(String(100), index=True)
    
    # НОВЫЕ ПОЛЯ для синхронизации с 1С
    external_id = Column(String(100), unique=True, index=True, nullable=True)  # ID из 1С
    external_code = Column(String(100), index=True, nullable=True)             # Код из 1С
    external_data = Column(JSON, nullable=True)                                # Доп. данные из 1С
    
    # Флаги синхронизации
    is_synced = Column(Boolean, default=False)
    sync_status = Column(String(20), default="pending")  # pending, synced, error
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)
    
    # Версионирование
    sync_version = Column(Integer, default=0)
    external_version = Column(Integer, default=0)  # Версия в 1С
    
    # Даты
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    external_updated_at = Column(DateTime(timezone=True), nullable=True)  # Когда обновили в 1С
    
    # Связи
    integration_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    def __repr__(self):
        return f"<Product {self.name} (ID: {self.external_id})>"