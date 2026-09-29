param(
    [string]$Target = "C:\projects\canary project\content editor"
)

$ErrorActionPreference = "Stop"
$source = $PSScriptRoot

Write-Host "Updating Canarias Cerca Content Studio -> v0.9.0" -ForegroundColor Cyan
Write-Host "Source: $source"
Write-Host "Target: $Target"

if (-not (Test-Path $Target)) {
    throw "Target folder does not exist: $Target"
}

# Preserve local/runtime data: .env, virtual env, generated output and photo inbox.
$excludeDirs = @(".venv", "output", "photo_inbox", "__pycache__")
$excludeFiles = @(".env")

$robocopyArgs = @($source, $Target, "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD") + $excludeDirs + @("/XF") + $excludeFiles
& robocopy @robocopyArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}

Write-Host "Updated. Your existing .env, .venv, photo_inbox and output were preserved." -ForegroundColor Green
Write-Host "Restart FastAPI, then press Ctrl+F5 in the browser." -ForegroundColor Yellow
Write-Host "The first 'uv run' after this update may install the new Trafilatura/BeautifulSoup dependencies." -ForegroundColor Yellow
Write-Host "You should see: v0.9.0, Events grouped by island with editable source links, and the updated Graph tab."
