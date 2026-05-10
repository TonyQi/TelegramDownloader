$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

Write-Host "Installing packaging dependencies..."
python -m pip install -r requirements.txt

Write-Host "Cleaning previous build output..."
if (Test-Path -LiteralPath "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}
if (Test-Path -LiteralPath "dist") {
    Remove-Item -LiteralPath "dist" -Recurse -Force
}

Write-Host "Building TelegramDownloader.exe..."
python -m PyInstaller --clean --noconfirm TelegramDownloader.spec

Write-Host ""
Write-Host "Build complete:"
Write-Host (Join-Path $PSScriptRoot "dist\TelegramDownloader\TelegramDownloader.exe")
