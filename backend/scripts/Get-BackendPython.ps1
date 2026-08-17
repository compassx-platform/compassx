param(
    [string]$RepoBackendPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$candidates = @()

if ($env:BACKEND_VENV_PATH) {
    $candidates += (Join-Path $env:BACKEND_VENV_PATH "Scripts\python.exe")
    $candidates += (Join-Path $env:BACKEND_VENV_PATH "bin/python")
}

$candidates += (Join-Path $RepoBackendPath ".venv\Scripts\python.exe")
$candidates += (Join-Path $RepoBackendPath ".venv\bin\python")

foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
        Write-Output (Resolve-Path $candidate).Path
        exit 0
    }
}

Write-Error "Could not find a backend Python interpreter. Set BACKEND_VENV_PATH to a short external venv path or create backend\.venv."
exit 1
