[CmdletBinding()]
param(
    [string]$Source = ".vendor-sources/tabler-icons",
    [string]$Destination = "content-to-editable-ppt/runtime/vendor/tabler-icons/3.46.0"
)

$ErrorActionPreference = "Stop"
$expectedCommit = "8ac7d81b72ece11072ef25ea9fd92e80c6f3c9fc"
$expectedTag = "v3.46.0"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$sourceRoot = (Resolve-Path (Join-Path $repoRoot $Source)).Path
$destinationRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Destination))
$allowedDestinationRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "content-to-editable-ppt/runtime/vendor/"))

if (-not $destinationRoot.StartsWith($allowedDestinationRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must remain inside the managed Runtime vendor directory."
}
if ((git -C $sourceRoot rev-parse HEAD).Trim() -ne $expectedCommit) { throw "Unexpected Tabler commit." }
if ((git -C $sourceRoot describe --tags --exact-match).Trim() -ne $expectedTag) { throw "Unexpected Tabler tag." }
if (git -C $sourceRoot status --porcelain) { throw "Tabler research mirror must be clean." }

$whitelist = @(
    (Join-Path $sourceRoot "LICENSE"),
    (Join-Path $sourceRoot "aliases.json"),
    (Join-Path $sourceRoot "icons/outline")
)
foreach ($item in $whitelist) {
    if (-not (Test-Path -LiteralPath $item)) { throw "Missing required vendor input: $item" }
}
$unsafe = Get-ChildItem -LiteralPath $sourceRoot -Recurse -Force | Where-Object {
    ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
}
if ($unsafe) { throw "Symlink or reparse point found in Tabler research mirror." }

$staging = "$destinationRoot.staging"
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $staging "icons/outline") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceRoot "LICENSE") -Destination (Join-Path $staging "LICENSE")
Copy-Item -LiteralPath (Join-Path $sourceRoot "aliases.json") -Destination (Join-Path $staging "aliases.json")
Get-ChildItem -LiteralPath (Join-Path $sourceRoot "icons/outline") -Filter *.svg | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $staging "icons/outline")
}
if (Test-Path -LiteralPath $destinationRoot) { Remove-Item -LiteralPath $destinationRoot -Recurse -Force }
Move-Item -LiteralPath $staging -Destination $destinationRoot

$iconCount = (Get-ChildItem -LiteralPath (Join-Path $destinationRoot "icons/outline") -Filter *.svg).Count
if ($iconCount -ne 5130) { throw "Unexpected managed icon count: $iconCount" }
Write-Output "Synced Tabler $expectedTag ($expectedCommit): $iconCount outline icons"
