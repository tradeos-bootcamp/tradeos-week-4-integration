# scripts/setup.ps1
# Скрипт настройки проекта для Windows

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   TradeOS Week 4 Setup Script" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Проверка версии PowerShell
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Host "❌ PowerShell 5.0 or higher required" -ForegroundColor Red
    exit 1
}

# Функция проверки команд
function Test-Command($cmdname) {
    return [bool](Get-Command -Name $cmdname -ErrorAction SilentlyContinue)
}

# Проверка Docker
Write-Host "`n[1/6] Checking Docker..." -ForegroundColor Yellow
if (Test-Command "docker") {
    $dockerVersion = docker --version
    Write-Host "✅ Docker installed: $dockerVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Docker not installed" -ForegroundColor Red
    Write-Host "   Download from: https://docs.docker.com/desktop/install/windows-install/" -ForegroundColor Yellow
    exit 1
}

# Проверка Docker Compose
if (Test-Command "docker-compose") {
    $composeVersion = docker-compose --version
    Write-Host "✅ Docker Compose: $composeVersion" -ForegroundColor Green
} else {
    Write-Host "⚠️ Docker Compose not found (using docker compose plugin)" -ForegroundColor Yellow
}

# Создание .env файла
Write-Host "`n[2/6] Setting up environment..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "✅ .env file already exists" -ForegroundColor Green
} else {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ Created .env file from .env.example" -ForegroundColor Green
        Write-Host "⚠️ Please edit .env file with your settings" -ForegroundColor Yellow
    } else {
        Write-Host "❌ .env.example not found" -ForegroundColor Red
    }
}

# Создание необходимых директорий
Write-Host "`n[3/6] Creating directories..." -ForegroundColor Yellow
$directories = @("logs", "uploads", "backups")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "✅ Created directory: $dir" -ForegroundColor Green
    } else {
        Write-Host "✅ Directory exists: $dir" -ForegroundColor Green
    }
}

# Проверка портов
Write-Host "`n[4/6] Checking ports..." -ForegroundColor Yellow
$ports = @(5432, 6379, 8000, 8001, 8080, 5555)
$services = @("PostgreSQL", "Redis", "FastAPI", "WebSocket", "Mock 1C", "Flower")

for ($i = 0; $i -lt $ports.Count; $i++) {
    $port = $ports[$i]
    $service = $services[$i]
    
    try {
        $socket = New-Object System.Net.Sockets.TcpClient
        $socket.Connect("localhost", $port)
        $socket.Close()
        Write-Host "⚠️ Port $port ($service) is in use" -ForegroundColor Yellow
    } catch {
        Write-Host "✅ Port $port ($service) is available" -ForegroundColor Green
    }
}

# Запуск Docker Compose
Write-Host "`n[5/6] Starting Docker Compose..." -ForegroundColor Yellow
Write-Host "Starting services..." -ForegroundColor Cyan
docker-compose up -d

# Ожидание запуска сервисов
Write-Host "`n[6/6] Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Проверка статуса
Write-Host "`nChecking service status..." -ForegroundColor Cyan
$services = @("postgres", "redis", "backend")

foreach ($service in $services) {
    $status = docker-compose ps $service --format "{{.Status}}"
    if ($status -like "*Up*") {
        Write-Host "✅ $service is running" -ForegroundColor Green
    } else {
        Write-Host "❌ $service is not running" -ForegroundColor Red
    }
}

# Показ информации
Write-Host "`n" + ("="*50) -ForegroundColor Cyan
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "="*50 -ForegroundColor Cyan
Write-Host "`n📊 Services available:" -ForegroundColor White
Write-Host "  • FastAPI:      http://localhost:8000" -ForegroundColor Yellow
Write-Host "  • WebSocket:    ws://localhost:8001" -ForegroundColor Yellow
Write-Host "  • Flower:       http://localhost:5555" -ForegroundColor Yellow
Write-Host "  • Mock 1C:      http://localhost:8080" -ForegroundColor Yellow
Write-Host "  • PostgreSQL:   localhost:5432" -ForegroundColor Yellow
Write-Host "  • Redis:        localhost:6379" -ForegroundColor Yellow

Write-Host "`n📚 Useful commands:" -ForegroundColor White
Write-Host "  • View logs:       docker-compose logs -f" -ForegroundColor Cyan
Write-Host "  • Stop services:   docker-compose down" -ForegroundColor Cyan
Write-Host "  • Restart:         docker-compose restart" -ForegroundColor Cyan
Write-Host "  • Run tests:       docker-compose exec backend pytest" -ForegroundColor Cyan

Write-Host "`n🚀 Next steps:" -ForegroundColor White
Write-Host "  1. Test the API: curl http://localhost:8000/api/v1/health" -ForegroundColor Green
Write-Host "  2. Create integration: Use test client script" -ForegroundColor Green
Write-Host "  3. Start sync: POST /api/v1/integrations/{id}/sync" -ForegroundColor Green

Write-Host "`n" + ("="*50) -ForegroundColor Cyan