param(
    [ValidateSet('Focused', 'Milestone', 'LiveSmoke', 'FinalGate')]
    [string]$Tier = 'Focused',
    [ValidateSet('B01', 'B02', 'B03', 'B04', 'B05', 'B06')]
    [string]$Case,
    [switch]$All,
    [switch]$AllowLiveAgent,
    [int]$AgentCallBudget = 0,
    [string]$PythonPath = 'python',
    [string]$NodePath,
    [string]$LiveEvidence
)

$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'p05_runtime_eval.py'
$arguments = @($scriptPath, '--tier', $Tier, '--agent-call-budget', $AgentCallBudget, '--python-path', $PythonPath)
if ($NodePath) { $arguments += @('--node-path', $NodePath) }
if ($LiveEvidence) { $arguments += @('--live-evidence', $LiveEvidence) }
if ($Case) { $arguments += @('--case', $Case) }
if ($All) { $arguments += '--all' }
if ($AllowLiveAgent) { $arguments += '--allow-live-agent' }
& $PythonPath @arguments
exit $LASTEXITCODE
