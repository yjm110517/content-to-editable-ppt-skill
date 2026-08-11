param(
    [ValidateSet('Focused', 'Milestone', 'FinalGate')]
    [string]$Tier = 'Focused',
    [ValidateSet('D03', 'D05', 'D08')]
    [string]$Case,
    [switch]$All,
    [switch]$RunP05Regression,
    [string]$PythonPath = 'python',
    [string]$NodePath
)

$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'p1_content_planning_eval.py'
$arguments = @($scriptPath, '--tier', $Tier, '--python-path', $PythonPath)
if ($Case) { $arguments += @('--case', $Case) }
if ($All) { $arguments += '--all' }
if ($RunP05Regression) { $arguments += '--run-p05-regression' }
if ($NodePath) { $arguments += @('--node-path', $NodePath) }
& $PythonPath @arguments
exit $LASTEXITCODE
