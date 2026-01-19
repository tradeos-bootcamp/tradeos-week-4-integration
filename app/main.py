# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_tables, engine
from app.api.v1.api import api_router

# Создаем app
app = FastAPI(
    title="TradeOS API",
    description="TradeOS Bootcamp Week 4 - 1C Integration",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "TradeOS API v1.0", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok", "database": "connected", "service": "tradeos-api"}

# Инициализация БД
create_tables()
