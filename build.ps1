# Genera dist\DiarioTrading.exe (un solo archivo). Los datos se guardan en dist\datos\ junto al .exe.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install -q -r requirements.txt pyinstaller
.\.venv\Scripts\python -m PyInstaller --noconfirm --onefile --noconsole --name DiarioTrading --add-data "app\static;app\static" run.py
Write-Host "Listo: dist\DiarioTrading.exe"
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) { $p = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"; if (Test-Path $p) { $iscc = $p } }
if ($iscc) {
    $ver = (Select-String -Path app\__init__.py -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
    & $iscc "/DAppVersion=$ver" installer\DiarioTrading.iss
    Write-Host "Instalador: dist\DiarioTrading-Setup-$ver.exe"
} else { Write-Host "Inno Setup no está instalado: se omite el instalador (https://jrsoftware.org/isinfo.php)" }
