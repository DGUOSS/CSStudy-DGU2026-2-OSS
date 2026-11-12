$ErrorActionPreference = 'Stop'

$backendDir = Join-Path $PSScriptRoot 'backend'
$frontendDir = Join-Path $PSScriptRoot 'frontend'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'
$vite = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
$node = (Get-Command node -ErrorAction Stop).Source
$pidFile = Join-Path $backendDir '.venv\demo-pids.json'
$demoEnvFile = Join-Path $backendDir '.venv\demo.env'

if (-not (Test-Path -LiteralPath $python)) { throw 'backend/.venv가 없습니다. 먼저 uv sync를 실행하세요.' }
if (-not (Test-Path -LiteralPath $vite)) { throw 'frontend/node_modules가 없습니다. 먼저 pnpm install을 실행하세요.' }
$apiStatus = & curl.exe --silent --output NUL --write-out '%{http_code}' --max-time 1 'http://127.0.0.1:8000/api/v1/health' 2>$null
$apiInUse = $LASTEXITCODE -eq 0
$webStatus = & curl.exe --silent --output NUL --write-out '%{http_code}' --max-time 1 'http://127.0.0.1:5173/' 2>$null
$webInUse = $LASTEXITCODE -eq 0
if ($apiInUse -or $webInUse) {
    throw '8000 또는 5173 포트가 이미 사용 중입니다. 기존 서버를 종료한 뒤 다시 실행하세요.'
}

$env:DATABASE_URL = 'sqlite:///./.venv/demo.db'
$env:DATABASE_URL_UNPOOLED = $env:DATABASE_URL
$env:COOKIE_SECURE = 'false'
@('DATABASE_URL=sqlite:///./.venv/demo.db', 'DATABASE_URL_UNPOOLED=sqlite:///./.venv/demo.db', 'COOKIE_SECURE=false') | Set-Content -LiteralPath $demoEnvFile -Encoding ascii

Push-Location $backendDir
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw '데모 DB 마이그레이션 실패' }
    & $python scripts/prepare_demo.py
    if ($LASTEXITCODE -ne 0) { throw '데모 데이터 준비 실패' }
} finally {
    Pop-Location
}

function Start-HiddenDemoProcess($file, $arguments, $workingDirectory) {
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $file
    $startInfo.Arguments = $arguments
    $startInfo.WorkingDirectory = $workingDirectory
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    return [System.Diagnostics.Process]::Start($startInfo)
}

$api = Start-HiddenDemoProcess $python "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file `"$demoEnvFile`"" $backendDir
$web = Start-HiddenDemoProcess $node "`"$vite`" --host 127.0.0.1 --port 5173" $frontendDir
@{ api = $api.Id; apiStart = $api.StartTime.ToString('o'); web = $web.Id; webStart = $web.StartTime.ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding utf8

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $health = & curl.exe --silent --max-time 2 'http://127.0.0.1:8000/api/v1/health' 2>$null
    $apiReady = $LASTEXITCODE -eq 0 -and $health -match '"status":"ok"'
    $frontStatus = & curl.exe --silent --output NUL --write-out '%{http_code}' --max-time 2 'http://127.0.0.1:5173/' 2>$null
    $webReady = $LASTEXITCODE -eq 0 -and $frontStatus -eq '200'
    if ($apiReady -and $webReady) {
        Write-Host '데모 서버가 준비됐습니다. 종료: .\stop_demo.ps1'
        exit 0
    }
    Start-Sleep -Milliseconds 500
}
throw '데모 서버가 시작되지 않았습니다. 포트와 실행 환경을 확인하세요.'
