#!/usr/bin/env python3
from app.crud.user import create_user
#from app.db.session import SessionLocal
from app.db import SessionLocal
from app.schemas.user import UserCreate
# Создать админа
db = SessionLocal()
user_in = UserCreate(username="admin", email="admin@tradeos.ru", password="admin123", role="admin")
create_user(db, user_in)
db.close()
print("Admin created!")
