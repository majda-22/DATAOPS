param(
    [string]$ContainerName = 'dataops-postgres-test'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
}

$inspection = docker inspect $ContainerName
if ($LASTEXITCODE -ne 0) {
    throw "Cannot inspect $ContainerName. Start Docker and the PostgreSQL test container."
}
$containerInfo = ($inspection | ConvertFrom-Json)[0]
$databaseSettings = @{}
foreach ($entry in $containerInfo.Config.Env) {
    $pair = $entry -split '=', 2
    $databaseSettings[$pair[0]] = $pair[1]
}
$binding = $containerInfo.NetworkSettings.Ports.'5432/tcp' | Select-Object -First 1
if (-not $binding -or -not $containerInfo.State.Running) {
    throw 'The test PostgreSQL container must be running with a published port.'
}
foreach ($key in 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB') {
    if (-not $databaseSettings[$key]) {
        throw "The test container is missing $key. Configure TEST_DATABASE_URL manually."
    }
}
$databaseUser = [uri]::EscapeDataString($databaseSettings['POSTGRES_USER'])
$databasePassword = [uri]::EscapeDataString($databaseSettings['POSTGRES_PASSWORD'])
$databaseName = [uri]::EscapeDataString($databaseSettings['POSTGRES_DB'])
$env:TEST_DATABASE_URL = "postgresql+psycopg://${databaseUser}:${databasePassword}@127.0.0.1:$($binding.HostPort)/${databaseName}"

Push-Location $projectRoot
try {
    & $pythonPath -m pytest -v tests/integration/test_metadata_queries.py
    $testExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($testExitCode -ne 0) {
    throw "Metadata integration tests failed (exit code $testExitCode)."
}
