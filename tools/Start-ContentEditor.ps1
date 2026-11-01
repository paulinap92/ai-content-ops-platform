$ErrorActionPreference = 'Stop'
$ccEditorRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ccEditorRoot
$ccEnvPath = Join-Path $ccEditorRoot 'content-agent-api\.env'

function Get-CcEnvValue([string]$Name) {
    if (!(Test-Path -LiteralPath $ccEnvPath)) { return '' }
    $ccLine = Get-Content -LiteralPath $ccEnvPath | Where-Object { $_ -match ('^\s*' + [regex]::Escape($Name) + '\s*=') } | Select-Object -Last 1
    if (!$ccLine) { return '' }
    return ($ccLine -replace '^\s*[^=]+=', '').Trim().Trim('"').Trim("'")
}
function Set-CcEnvValue([string]$Name, [string]$Value) {
    if ($Value -match '[\r\n]') { throw 'Nieprawidlowa wartosc konfiguracji.' }
    $ccExisting = if (Test-Path -LiteralPath $ccEnvPath) { [string[]](Get-Content -LiteralPath $ccEnvPath) } else { @() }
    $ccKept = @($ccExisting | Where-Object { $_ -notmatch ('^\s*' + [regex]::Escape($Name) + '\s*=') })
    $ccKept += ($Name + '=' + $Value)
    [IO.File]::WriteAllLines($ccEnvPath, $ccKept, [Text.UTF8Encoding]::new($false))
}

& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Uruchom Docker Desktop z Docker Compose.' }
if (!(Get-CcEnvValue 'EDITOR_STORAGE')) { Set-CcEnvValue 'EDITOR_STORAGE' 'postgres' }
$ccKey = Get-CcEnvValue 'EDITOR_TOKEN'
if ($ccKey.Length -lt 32) {
    $ccBytes = New-Object byte[] 48
    $ccGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $ccGenerator.GetBytes($ccBytes) } finally { $ccGenerator.Dispose() }
    $ccKey = [Convert]::ToBase64String($ccBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    Set-CcEnvValue 'EDITOR_TOKEN' $ccKey
}

if (!(Get-CcEnvValue 'SITE_DATABASE_URL')) {
    $ccCandidate = ''
    # Read only a known Canarias preview's configured URL; never print secrets.
    $ccContainers = @(& docker ps --format '{{.Names}}')
    foreach ($ccName in $ccContainers) {
        if ($ccName -notmatch '^(cc-neon-readonly-|cc-preview-.*-api-|canarias-backend-orm-test-api-)') { continue }
        $ccInspection = @(& docker inspect $ccName | ConvertFrom-Json)
        foreach ($ccItem in $ccInspection) {
            foreach ($ccSetting in $ccItem.Config.Env) {
                if ($ccSetting -match '^DATABASE_URL=(.+)$') {
                    $ccValue = $Matches[1]
                    if ($ccValue -match 'ep-bold-wind-ba3u0dkc\.c-8\.eu-central-1\.aws\.neon\.tech') { $ccCandidate = $ccValue }
                }
            }
        }
    }
    if (!$ccCandidate) {
        Read-Host 'Skopiuj adres z Neon > Connect do schowka, potem nacisnij ENTER (nie wklejaj go tutaj)' | Out-Null
        $ccClipboard = Get-Clipboard -Raw
        $ccMatch = [regex]::Match($ccClipboard, 'postgres(?:ql)?(?:\+[^:]+)?://[^\s''"]+')
        if (!$ccMatch.Success) { throw 'W schowku nie ma adresu PostgreSQL.' }
        $ccCandidate = $ccMatch.Value
        if ($ccCandidate -notmatch 'ep-bold-wind-ba3u0dkc\.c-8\.eu-central-1\.aws\.neon\.tech') { throw 'To nie jest oczekiwana baza Canarias Cerca w Neon.' }
    }
    Set-CcEnvValue 'SITE_DATABASE_URL' $ccCandidate
}

$ccEditorPort = 8004
while (Get-NetTCPConnection -LocalPort $ccEditorPort -State Listen -ErrorAction SilentlyContinue) {
    $ccEditorPort++
    if ($ccEditorPort -gt 8014) { throw 'Brak wolnego portu w zakresie 8004-8014.' }
}
$ccOldPort = $env:EDITOR_LOCAL_PORT
try {
    $env:EDITOR_LOCAL_PORT = [string]$ccEditorPort
    & docker compose -p cc-content-editor-local -f compose.editor.yml up --build -d
    if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie uruchomic osobnego Content Editora.' }
    $ccAddress = 'http://127.0.0.1:' + $ccEditorPort + '/login'
    $ccStarted = $false
    for ($ccAttempt = 0; $ccAttempt -lt 30; $ccAttempt++) {
        try {
            $ccReply = Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:' + $ccEditorPort + '/health/live') -TimeoutSec 3
            if ($ccReply.StatusCode -eq 200) { $ccStarted = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (!$ccStarted) { throw 'Editor jeszcze nie odpowiada. Sprawdz logi tylko projektu cc-content-editor-local.' }
    Set-Clipboard -Value $ccKey
    Write-Host 'Content Editor dziala osobno. Klucz logowania skopiowano do schowka.' -ForegroundColor Green
    Write-Host $ccAddress
    Start-Process $ccAddress
} finally {
    $env:EDITOR_LOCAL_PORT = $ccOldPort
}
