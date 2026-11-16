$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$AppName = "l4d2-mod-manager"
$Version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
$Out = "dist/$AppName-$Version-windows-x64.zip"

Write-Host "==> Building $AppName $Version (Windows)"

Write-Host "==> Cleaning previous output"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path dist | Out-Null

Write-Host "==> Generating icons"
$env:QT_QPA_PLATFORM = "offscreen"
poetry run python scripts/make_icon.py

Write-Host "==> Running PyInstaller"
poetry run pyinstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $AppName `
    --distpath dist `
    --workpath build/pyinstaller `
    --paths src `
    --icon packaging/icon.ico `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtWebEngineQuick `
    --exclude-module PySide6.QtWebChannel `
    --exclude-module PySide6.QtPdf `
    --exclude-module PySide6.QtPdfWidgets `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtQuickWidgets `
    --exclude-module PySide6.QtQuick3D `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.Qt3DRender `
    --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtDataVisualization `
    --exclude-module tkinter `
    packaging/entry.py

Write-Host "==> Zipping app folder"
Compress-Archive -Path "dist/$AppName" -DestinationPath $Out -Force

Write-Host "==> Self-test (offscreen, killed after check = healthy launch)"
$env:QT_QPA_PLATFORM = "offscreen"
$proc = Start-Process -FilePath (Join-Path "dist/$AppName" "$AppName.exe") -PassThru
Start-Sleep -Seconds 6
if ($proc.HasExited) {
    throw "Self-test failed: app exited with code $($proc.ExitCode)"
}
Stop-Process -Id $proc.Id -Force
Write-Host "Self-test OK (app stayed running)"

$artifact = Get-Item $Out
Write-Host ("==> Done: {0} ({1:N1} MB)" -f $artifact.Name, ($artifact.Length / 1MB))
