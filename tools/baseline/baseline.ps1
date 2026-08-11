[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Prepare', 'Capture', 'Verify')]
    [string]$Action,

    [ValidateSet('B01', 'B02', 'B03', 'B04', 'B05', 'B06')]
    [string]$Case,

    [switch]$All,

    [string]$NodePath,

    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$tool = Join-Path $toolRoot 'baseline_tool.py'

if ($Action -eq 'Verify') {
    if (-not $All) {
        throw 'Verify requires -All.'
    }
} elseif ([string]::IsNullOrWhiteSpace($Case)) {
    throw "$Action requires -Case."
}

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw 'Python was not found. Pass -PythonPath explicitly.'
    }
    $PythonPath = $pythonCommand.Source
}

$arguments = @($tool, $Action.ToLowerInvariant())
if ($Action -ne 'Verify') {
    $arguments += @('--case', $Case)
}
if ($Action -eq 'Prepare') {
    if (-not [string]::IsNullOrWhiteSpace($NodePath)) {
        $arguments += @('--node-path', $NodePath)
    }
    $arguments += @('--python-path', $PythonPath)
}

& $PythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
