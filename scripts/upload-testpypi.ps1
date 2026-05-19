[CmdletBinding()]
param(
    [switch]$SkipTwineCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Pypirc = Join-Path $RepoRoot ".pypirc"
$DistPattern = Join-Path $RepoRoot "dist\*"

function Invoke-RepoCommand {
    param([Parameter(Mandatory = $true)][string[]]$Command)

    Push-Location $RepoRoot
    try {
        $executable = $Command[0]
        $arguments = @()
        if ($Command.Count -gt 1) {
            $arguments = $Command[1..($Command.Count - 1)]
        }
        & $executable @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $($Command -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $Python)) {
    throw "Local Python was not found at $Python. Create .venv and install requirements-dev.txt first."
}

if (-not (Test-Path $Pypirc)) {
    throw "Repo-local .pypirc was not found. Create it with [distutils], [testpypi], and token credentials."
}

if (-not (Get-ChildItem -Path $DistPattern -File -ErrorAction SilentlyContinue)) {
    throw "No distribution artifacts found in dist. Build first with .\.venv\Scripts\python.exe -m build."
}

if (-not $SkipTwineCheck) {
    Invoke-RepoCommand @($Python, "-m", "twine", "check", "dist/*")
}

Invoke-RepoCommand @(
    $Python,
    "-m",
    "twine",
    "upload",
    "--config-file",
    $Pypirc,
    "--repository",
    "testpypi",
    "dist/*"
)