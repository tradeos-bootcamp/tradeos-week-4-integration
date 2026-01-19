# scripts/check_environment.py
import sys
import os
import subprocess
import platform
from pathlib import Path

def check_python_version():
    """Проверка версии Python"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    print(f"  Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 9:
        print("  ✅ Python version OK")
        return True
    else:
        print("  ❌ Python 3.9+ required")
        return False

def check_docker():
    """Проверка установки Docker"""
    print("\n🔍 Checking Docker...")
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"  {result.stdout.strip()}")
        
        # Проверка Docker Compose
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"  {result.stdout.strip()}")
            print("  ✅ Docker and Docker Compose OK")
            return True
        else:
            print("  ⚠️ Docker Compose not found")
            return False
            
    except FileNotFoundError:
        print("  ❌ Docker not installed")
        return False

def check_env_file():
    """Проверка .env файла"""
    print("\n🔍 Checking environment configuration...")
    
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_example.exists():
        print("  ⚠️ .env.example not found")
        return False
    
    if env_file.exists():
        print("  ✅ .env file exists")
        
        # Проверяем обязательные переменные
        required_vars = [
            "SECRET_KEY",
            "POSTGRES_PASSWORD",
            "ONEC_API_KEY"
        ]
        
        missing = []
        with open(env_file) as f:
            content = f.read()
            for var in required_vars:
                if f"{var}=" in content:
                    # Проверяем, что значение не пустое
                    lines = content.split('\n')
                    for line in lines:
                        if line.startswith(f"{var}="):
                            if not line.split('=', 1)[1].strip():
                                missing.append(f"{var} (empty)")
                            break
                else:
                    missing.append(var)
        
        if missing:
            print(f"  ❌ Missing or empty variables: {', '.join(missing)}")
            return False
        else:
            print("  ✅ All required variables are set")
            return True
    else:
        print("  ❌ .env file not found. Copy from .env.example:")
        print("      cp .env.example .env")
        return False

def check_ports():
    """Проверка занятых портов"""
    print("\n🔍 Checking ports...")
    
    ports = {
        5432: "PostgreSQL",
        6379: "Redis",
        8000: "FastAPI",
        8001: "WebSocket",
        8080: "Mock 1C",
        5555: "Flower"
    }
    
    import socket
    
    available = True
    for port, service in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"  ⚠️ Port {port} ({service}) is in use")
            available = False
        else:
            print(f"  ✅ Port {port} ({service}) is available")
    
    return available

def check_dependencies():
    """Проверка зависимостей Python"""
    print("\n🔍 Checking Python dependencies...")
    
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import celery
        import redis
        import httpx
        import websockets
        
        print(f"  ✅ FastAPI {fastapi.__version__}")
        print(f"  ✅ SQLAlchemy {sqlalchemy.__version__}")
        print(f"  ✅ Celery {celery.__version__}")
        print(f"  ✅ Redis {redis.__version__}")
        print(f"  ✅ HTTPX {httpx.__version__}")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Missing dependency: {e.name}")
        print(f"  Install with: pip install -r requirements.txt")
        return False

def check_directory_structure():
    """Проверка структуры проекта"""
    print("\n🔍 Checking project structure...")
    
    required_dirs = [
        "app",
        "app/models",
        "app/schemas",
        "app/crud",
        "app/api/v1/endpoints",
        "app/services",
        "app/tasks",
        "tests",
        "logs",
        "uploads"
    ]
    
    required_files = [
        "requirements.txt",
        "docker-compose.yml",
        ".env.example",
        "app/main.py",
        "app/database.py"
    ]
    
    all_ok = True
    
    for directory in required_dirs:
        path = Path(directory)
        if path.exists():
            print(f"  ✅ Directory: {directory}")
        else:
            print(f"  ❌ Missing directory: {directory}")
            all_ok = False
    
    for file in required_files:
        path = Path(file)
        if path.exists():
            print(f"  ✅ File: {file}")
        else:
            print(f"  ❌ Missing file: {file}")
            all_ok = False
    
    return all_ok

def main():
    """Основная функция проверки"""
    print("=" * 60)
    print("TRADEOS INTEGRATION ENVIRONMENT CHECK")
    print("=" * 60)
    
    checks = [
        ("Python Version", check_python_version()),
        ("Docker", check_docker()),
        ("Environment", check_env_file()),
        ("Ports", check_ports()),
        ("Dependencies", check_dependencies()),
        ("Project Structure", check_directory_structure())
    ]
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All checks passed! You can start the project with:")
        print("  docker-compose up -d")
    else:
        print(f"\n⚠️  {total - passed} check(s) failed. Please fix them before starting.")
        sys.exit(1)

if __name__ == "__main__":
    main()