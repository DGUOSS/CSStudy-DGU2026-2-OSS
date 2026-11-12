$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot 'backend\.venv\demo-pids.json'
if (-not (Test-Path -LiteralPath $pidFile)) { throw '실행 중인 데모 기록이 없습니다.' }
$demoPids = Get-Content -LiteralPath $pidFile -Raw -Encoding utf8 | ConvertFrom-Json
$expectedPython = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'backend\.venv\Scripts\python.exe')).Path
$expectedNode = (Get-Command node -ErrorAction Stop).Source

foreach ($entry in @(@{ id = $demoPids.api; started = $demoPids.apiStart; path = $expectedPython }, @{ id = $demoPids.web; started = $demoPids.webStart; path = $expectedNode })) {
    $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    if ($process) {
        if ($process.Path -ne $entry.path -or $process.StartTime.ToString('o') -ne $entry.started) {
            throw "PID $($entry.id)가 데모 프로세스와 일치하지 않아 종료하지 않았습니다."
        }
        Stop-Process -Id $entry.id -Force
    }
}
Remove-Item -LiteralPath $pidFile
Write-Host '데모 서버를 종료했습니다.'
