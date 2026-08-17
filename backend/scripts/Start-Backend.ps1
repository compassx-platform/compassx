param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000
)

$backendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = & (Join-Path $PSScriptRoot "Get-BackendPython.ps1") -RepoBackendPath $backendRoot

Write-Host "Using Python: $python"
Write-Host "Backend root: $backendRoot"

& $python -m uvicorn app.main:app --host $Host --port $Port
