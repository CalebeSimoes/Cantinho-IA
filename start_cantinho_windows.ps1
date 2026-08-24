$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$WatchdogStart = Join-Path $ProjectDir "start_watchdog_background.ps1"

Write-Host "🌿 Iniciando Cantinho Ghibli..."
& $WatchdogStart

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] O Watchdog nao iniciou." -ForegroundColor Red
    exit 1
}

Start-Process `
    -FilePath "powershell" `
    -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Set-Location '$ProjectDir'; .\run_api_windows.ps1"
    )

Write-Host "✅ Watchdog + Worker + Ollama supervisionados; API iniciada."
