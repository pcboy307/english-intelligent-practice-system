param(
  [switch]$SkipFrontendBuild,
  [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $root "dist\windows"
$stage = Join-Path $distRoot "package"
$nodeHome = "C:\Users\Administrator\node24"
$pythonHome = "C:\Users\Administrator\AppData\Local\Programs\Python\Python312"
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$postgresHome = "C:\pgsql"
$npm = Join-Path $nodeHome "npm.cmd"
$npx = Join-Path $nodeHome "npx.cmd"
$installerScript = Join-Path $root "installer\gaoer-english-practice.iss"
$installerPath = Join-Path $distRoot "GaoerEnglishPractice-Setup.exe"

function Assert-File([string]$Path, [string]$Label) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "$Label not found: $Path"
  }
}

function Assert-Directory([string]$Path, [string]$Label) {
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    throw "$Label not found: $Path"
  }
}

function Safe-RemoveTree([string]$Path, [string]$ExpectedParent) {
  $target = [IO.Path]::GetFullPath($Path)
  $parent = [IO.Path]::GetFullPath($ExpectedParent).TrimEnd('\') + '\'
  if (-not $target.StartsWith($parent, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove path outside expected parent: $target"
  }
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
}

function Copy-Directory([string]$Source, [string]$Destination) {
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

Assert-File $npm "Node npm"
Assert-File $npx "Node npx"
Assert-File $pythonExe "Project Python"
Assert-Directory $pythonHome "Portable Python source"
Assert-Directory $postgresHome "PostgreSQL source"

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
Safe-RemoveTree $stage $distRoot
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$mobileRoot = Join-Path $root "apps\mobile"
$webExport = Join-Path $mobileRoot "dist"
if (-not $SkipFrontendBuild) {
  Push-Location $mobileRoot
  try {
    & $npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "TypeScript check failed" }
    Safe-RemoveTree $webExport $mobileRoot
    & $npx expo export --platform web
    if ($LASTEXITCODE -ne 0) { throw "Expo Web export failed" }
  } finally {
    Pop-Location
  }
}
Assert-Directory $webExport "Expo Web export"
Copy-Directory $webExport (Join-Path $stage "web")

foreach ($name in @("backend", "config", "contracts", "db", "desktop")) {
  Copy-Directory (Join-Path $root $name) (Join-Path $stage $name)
}
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination $stage -Force
Copy-Item -LiteralPath (Join-Path $root "CHANGELOG.md") -Destination $stage -Force

$runtimeRoot = Join-Path $stage "runtime"
$portablePython = Join-Path $runtimeRoot "python"
New-Item -ItemType Directory -Force -Path $portablePython | Out-Null
foreach ($item in @(
  "DLLs",
  "Lib",
  "LICENSE.txt",
  "NEWS.txt",
  "python.exe",
  "python3.dll",
  "python312.dll",
  "pythonw.exe",
  "vcruntime140.dll",
  "vcruntime140_1.dll"
)) {
  $source = Join-Path $pythonHome $item
  if (Test-Path -LiteralPath $source) {
    Copy-Item -LiteralPath $source -Destination $portablePython -Recurse -Force
  }
}

$portablePythonExe = Join-Path $portablePython "python.exe"
$portableSitePackages = Join-Path $portablePython "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $portableSitePackages | Out-Null
Copy-Item -Path (Join-Path $root ".venv\Lib\site-packages\*") `
  -Destination $portableSitePackages -Recurse -Force
& $portablePythonExe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Portable Python dependency check failed" }

$portablePostgres = Join-Path $runtimeRoot "pgsql"
New-Item -ItemType Directory -Force -Path $portablePostgres | Out-Null
foreach ($name in @("bin", "lib", "share")) {
  Copy-Directory (Join-Path $postgresHome $name) (Join-Path $portablePostgres $name)
}
foreach ($license in @(
  "server_license.txt",
  "commandlinetools_3rd_party_licenses.txt"
)) {
  $source = Join-Path $postgresHome $license
  if (Test-Path -LiteralPath $source) {
    Copy-Item -LiteralPath $source -Destination $portablePostgres -Force
  }
}

# App-local MSVC runtime files are required when the target PC has no VC++ runtime.
foreach ($dll in @(
  "concrt140.dll",
  "msvcp140.dll",
  "vcruntime140.dll",
  "vcruntime140_1.dll"
)) {
  $source = Join-Path $env:WINDIR "System32\$dll"
  if (Test-Path -LiteralPath $source) {
    Copy-Item -LiteralPath $source -Destination (Join-Path $portablePostgres "bin") -Force
  }
}

$seedPath = Join-Path $stage "seed\bank.json"
& $pythonExe (Join-Path $root "scripts\export-active-bank.py") --output $seedPath
if ($LASTEXITCODE -ne 0) { throw "Active bank export failed" }

$version = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root "contracts\VERSION")).Trim()
$manifest = [ordered]@{
  product = "高二英语智能练习"
  app_version = "0.1.0"
  requirement_version = $version
  built_at = (Get-Date).ToString("o")
  stage = $stage
  frontend = $webExport
  seed = $seedPath
}
$manifestJson = $manifest | ConvertTo-Json -Depth 4
[IO.File]::WriteAllText(
  (Join-Path $distRoot "build-manifest.json"),
  $manifestJson,
  [Text.UTF8Encoding]::new($false)
)

if ($SkipInstaller) {
  Write-Output "STAGE_READY=$stage"
  exit 0
}

$isccCandidates = @(
  (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
  "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) {
  throw "ISCC_NOT_FOUND. Install with: winget install --id JRSoftware.InnoSetup -e"
}
& $iscc /Qp "/DMyAppVersion=$version" $installerScript
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }
Assert-File $installerPath "Installer"
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installerPath).Hash
$sizeMb = [math]::Round((Get-Item -LiteralPath $installerPath).Length / 1MB, 1)
"$hash  GaoerEnglishPractice-Setup.exe" | Set-Content -Encoding ASCII -LiteralPath "$installerPath.sha256"
"INSTALLER=$installerPath"
"SIZE_MB=$sizeMb"
"SHA256=$hash"
