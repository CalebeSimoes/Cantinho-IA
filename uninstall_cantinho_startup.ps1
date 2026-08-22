$TaskName = "Cantinho Ghibli AI"

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($null -eq $Task) {
    Write-Host "A tarefa '$TaskName' nao existe."
    exit 0
}

Unregister-ScheduledTask `
    -TaskName $TaskName `
    -Confirm:$false

Write-Host "Tarefa '$TaskName' removida com sucesso."
