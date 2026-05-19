[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Version,
    [string]$Remote = "origin"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$PyProject = Join-Path $RepoRoot "pyproject.toml"

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

function Get-ProjectVersion {
    $content = Get-Content -Raw -Path $PyProject
    $match = [regex]::Match($content, '(?m)^version\s*=\s*"(?<version>[^"]+)"')
    if (-not $match.Success) {
        throw "Could not find project.version in pyproject.toml."
    }

    return $match.Groups['version'].Value
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Get-ProjectVersion
}

$tag = "v$Version"
$status = git -C $RepoRoot status --porcelain
if (-not [string]::IsNullOrWhiteSpace($status)) {
    throw "Working tree is not clean. Commit release changes before creating $tag."
}

$existingLocal = git -C $RepoRoot tag --list $tag
if (-not [string]::IsNullOrWhiteSpace($existingLocal)) {
    throw "Local tag $tag already exists."
}

$existingRemote = git -C $RepoRoot ls-remote --tags $Remote "refs/tags/$tag"
if (-not [string]::IsNullOrWhiteSpace($existingRemote)) {
    throw "Remote tag $tag already exists on $Remote."
}

if ($PSCmdlet.ShouldProcess($tag, "Create and push GitHub release tag")) {
    Invoke-RepoCommand @("git", "tag", "-a", $tag, "-m", "Release $tag")
    Invoke-RepoCommand @("git", "push", $Remote, $tag)
}