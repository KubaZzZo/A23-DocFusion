param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$mode = if ($OneFile) { "--onefile" } else { "--onedir" }

$apiDefaults = if (Test-Path "frontend\api.private.json") { "frontend\api.private.json" } else { "frontend\api.defaults.json" }
$toolkitDefaults = if (Test-Path "frontend\server_task.private.json") { "frontend\server_task.private.json" } else { "frontend\server_task.defaults.json" }

$args = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--windowed",
    $mode,
    "--name", "DocFusion",
    "--icon", "frontend\assets\docfusion_icon.ico",
    "--add-data", "frontend\assets;assets",
    "--add-data", "$toolkitDefaults;.",
    "--paths", "frontend"
)

if (Test-Path $apiDefaults) {
    $args += @("--add-data", "$apiDefaults;.")
}

$args += "frontend\main.py"

python @args
