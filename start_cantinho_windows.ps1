$ErrorActionPreference = "Stop"
Write-Host "🌿 Iniciando Cantinho Ghibli..."
$ok=$false
try { $null=Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2; $ok=$true } catch { $ok=$false }
if (-not $ok) { Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized; Start-Sleep -Seconds 4 }
$project=Split-Path -Parent $MyInvocation.MyCommand.Path
Start-Process powershell -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-Command","Set-Location '$project'; .\run_worker_windows.ps1")
Start-Process powershell -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-Command","Set-Location '$project'; .\run_api_windows.ps1")
Write-Host "✅ Worker + API iniciados."
