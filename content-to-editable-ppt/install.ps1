param(
    [string]$PythonPath = 'python',
    [string]$NodePath,
    [string]$ManifestPath = (Join-Path $PSScriptRoot 'runtime-manifest.json'),
    [switch]$InstallDependencies
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Content to Editable PPT P0.5 supports Windows only.' }
$bootstrap = Join-Path $PSScriptRoot 'scripts\bootstrap_runtime.py'
$arguments = @($bootstrap, '--python', $PythonPath, '--manifest', $ManifestPath)
if ($NodePath) { $arguments += @('--node', $NodePath) }
if ($InstallDependencies) { $arguments += '--install-dependencies' }
& $PythonPath @arguments
exit $LASTEXITCODE
