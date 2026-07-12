[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoReload
)

$backendDir = Join-Path $PSScriptRoot "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

if (-not (Test-Path $backendDir)) {
    throw "Backend directory not found: $backendDir"
}

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $Port)
if (-not $NoReload) {
    $uvicornArgs += "--reload"
}

Push-Location $backendDir
try {
    & $python @uvicornArgs
} finally {
    Pop-Location
}
