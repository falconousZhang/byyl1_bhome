param(
  [string]$Name = 'rust_like_compiler'
)

$ErrorActionPreference = 'Stop'

$venv = Join-Path $PSScriptRoot '.build-venv'
$python = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
  python -m venv --without-pip $venv
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create build environment' }
}

$sitePackages = Join-Path $venv 'Lib\site-packages'
if (-not (Test-Path -LiteralPath (Join-Path $sitePackages 'PyInstaller'))) {
  python -m pip install `
    --disable-pip-version-check `
    --target $sitePackages `
    -r requirements-build.txt
  if ($LASTEXITCODE -ne 0) { throw 'Failed to install build dependencies' }
}

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name $Name `
  --add-data 'templates;templates' `
  --add-data 'static;static' `
  --add-data 'examples;examples' `
  src/main.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }

Write-Host "Built dist\$Name.exe"
