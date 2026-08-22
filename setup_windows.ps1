$ErrorActionPreference = "Stop"
Write-Host "🌿 Preparando Cantinho Ghibli AI v2..."
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "✅ Instalação concluída. Edite .env e depois rode .\testar_windows.ps1"
