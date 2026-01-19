# scripts/check_dependencies.py
import importlib
import sys

required_packages = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "jose",
    "passlib",
    "pydantic",
    "python-dotenv"
]

missing_packages = []

for package in required_packages:
    try:
        importlib.import_module(package.split('[')[0] if '[' in package else package)
        print(f"✅ {package}")
    except ImportError:
        missing_packages.append(package)
        print(f"❌ {package}")

if missing_packages:
    print(f"\nОтсутствуют пакеты: {', '.join(missing_packages)}")
    print("Установите командой: pip install " + " ".join(missing_packages))
    sys.exit(1)
else:
    print("\n✅ Все зависимости установлены!")