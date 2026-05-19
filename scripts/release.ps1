[CmdletBinding()]
param(
    [string]$PackageName = "endlessdb"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PyProject = Join-Path $RepoRoot "pyproject.toml"

function Ask-YesNo {
    param(
        [Parameter(Mandatory = $true)][string]$Question,
        [bool]$Default = $true
    )

    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    while ($true) {
        $answer = Read-Host "$Question $suffix"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        switch -Regex ($answer.Trim()) {
            '^(y|yes)$' { return $true }
            '^(n|no)$' { return $false }
        }
        Write-Host "Please answer yes or no."
    }
}

function Ask-Menu {
    param(
        [Parameter(Mandatory = $true)][string]$Question,
        [Parameter(Mandatory = $true)][string[]]$Options,
        [int]$DefaultIndex = 0
    )

    Write-Host ""
    Write-Host $Question
    for ($index = 0; $index -lt $Options.Count; $index++) {
        $marker = if ($index -eq $DefaultIndex) { "*" } else { " " }
        Write-Host ("{0} {1}. {2}" -f $marker, ($index + 1), $Options[$index])
    }

    while ($true) {
        $answer = Read-Host "Choose 1-$($Options.Count)"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Options[$DefaultIndex] }
        $number = 0
        if ([int]::TryParse($answer, [ref]$number) -and $number -ge 1 -and $number -le $Options.Count) {
            return $Options[$number - 1]
        }
        Write-Host "Please choose a number from the list."
    }
}

function Invoke-Stage {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action,
        [bool]$Default = $true
    )

    if (-not (Ask-YesNo "Run stage: $Name?" $Default)) {
        Write-Host "Skipped: $Name"
        return
    }

    Write-Host ""
    Write-Host "== $Name =="
    & $Action
}

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
    if (-not $match.Success) { throw "Could not find project.version in pyproject.toml." }
    return $match.Groups['version'].Value
}

function Set-ProjectVersion {
    param([Parameter(Mandatory = $true)][string]$Version)

    $content = Get-Content -Raw -Path $PyProject
    $updated = [regex]::Replace($content, '(?m)^version\s*=\s*"[^"]+"', "version = `"$Version`"", 1)
    Set-Content -Path $PyProject -Value $updated -NoNewline
}

function Get-BumpedVersion {
    param([Parameter(Mandatory = $true)][string]$CurrentVersion)

    $match = [regex]::Match($CurrentVersion, '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)(?<suffix>.*)$')
    if (-not $match.Success) {
        $custom = Read-Host "Current version is not simple semver. Enter new PEP 440 version"
        if ([string]::IsNullOrWhiteSpace($custom)) { throw "Version bump cancelled." }
        return $custom.Trim()
    }

    $major = [int]$match.Groups['major'].Value
    $minor = [int]$match.Groups['minor'].Value
    $patch = [int]$match.Groups['patch'].Value
    $choice = Ask-Menu "Current version is $CurrentVersion. How should it be incremented?" @(
        "patch -> $major.$minor.$($patch + 1)",
        "minor -> $major.$($minor + 1).0",
        "major -> $($major + 1).0.0",
        "dev -> $major.$minor.$($patch + 1).dev1",
        "rc -> $major.$minor.$($patch + 1)rc1",
        "custom"
    ) 0

    switch -Regex ($choice) {
        '^patch' { return "$major.$minor.$($patch + 1)" }
        '^minor' { return "$major.$($minor + 1).0" }
        '^major' { return "$($major + 1).0.0" }
        '^dev' { return "$major.$minor.$($patch + 1).dev1" }
        '^rc' { return "$major.$minor.$($patch + 1)rc1" }
        '^custom' {
            $custom = Read-Host "Enter new PEP 440 version"
            if ([string]::IsNullOrWhiteSpace($custom)) { throw "Version bump cancelled." }
            return $custom.Trim()
        }
    }
}

function Test-PublishedVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$Version
    )

    $baseUrl = if ($Repository -eq "testpypi") { "https://test.pypi.org/pypi" } else { "https://pypi.org/pypi" }
    $url = "$baseUrl/$PackageName/json"
    try {
        $response = Invoke-RestMethod -Uri $url -Method Get -ErrorAction Stop
        return $null -ne $response.releases.$Version
    }
    catch {
        Write-Host ("Could not query {0} for {1}: {2}" -f $Repository, $PackageName, $_.Exception.Message)
        return $false
    }
}

Write-Host "EndlessDB release assistant"
Write-Host "Repository: $RepoRoot"

if (-not (Test-Path $Python)) {
    if (Ask-YesNo "Local .venv was not found. Create it with Python 3.13?" $true) {
        Push-Location $RepoRoot
        try { py -3.13 -m venv .venv }
        finally { Pop-Location }
    }
    else {
        throw "Cannot continue without .venv."
    }
}

Invoke-Stage "upgrade pip" { Invoke-RepoCommand @($Python, "-m", "pip", "install", "--upgrade", "pip") }
Invoke-Stage "install development dependencies" { Invoke-RepoCommand @($Python, "-m", "pip", "install", "--upgrade", "-r", "requirements-dev.txt") }
Invoke-Stage "show outdated packages" { Invoke-RepoCommand @($Python, "-m", "pip", "list", "--outdated", "--format=json") }
Invoke-Stage "check installed dependencies" { Invoke-RepoCommand @($Python, "-m", "pip", "check") }
Invoke-Stage "start integration MongoDB with Docker Compose" { Invoke-RepoCommand @("docker", "compose", "-f", "tests/docker-compose.yml", "up", "-d") }
Invoke-Stage "run pytest" { Invoke-RepoCommand @($Python, "-m", "pytest", "tests", "-q") }
Invoke-Stage "compile Python sources" { Invoke-RepoCommand @($Python, "-m", "compileall", "samples", "tests", "src") }

$currentVersion = Get-ProjectVersion
if (Ask-YesNo "Increment project version before building? Current version is $currentVersion." $true) {
    $newVersion = Get-BumpedVersion $currentVersion
    if (Test-PublishedVersion "testpypi" $newVersion) { throw "Version $newVersion already exists on TestPyPI." }
    if (Test-PublishedVersion "pypi" $newVersion) { throw "Version $newVersion already exists on PyPI." }
    Set-ProjectVersion $newVersion
    Write-Host "Updated pyproject.toml: $currentVersion -> $newVersion"
}
else {
    Write-Host "Version was not changed. Upload stages will be blocked unless you confirm a manual exception."
}

Invoke-Stage "clean build artifacts" {
    Push-Location $RepoRoot
    try { Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue }
    finally { Pop-Location }
}
Invoke-Stage "build source and wheel distributions" { Invoke-RepoCommand @($Python, "-m", "build") }
Invoke-Stage "validate distributions with twine" { Invoke-RepoCommand @($Python, "-m", "twine", "check", "dist/*") }

$uploadChoice = Ask-Menu "Upload built distributions?" @(
    "no upload",
    "TestPyPI only",
    "PyPI production only",
    "TestPyPI then PyPI production"
) 0

switch ($uploadChoice) {
    "no upload" { Write-Host "Upload skipped." }
    "TestPyPI only" {
        if (Ask-YesNo "Upload to TestPyPI now? Twine may prompt for credentials." $false) {
            Invoke-RepoCommand @(Join-Path $ScriptRoot "upload-testpypi.ps1")
        }
    }
    "PyPI production only" {
        if (Ask-YesNo "Upload to public PyPI now? Twine may prompt for credentials." $false) {
            Invoke-RepoCommand @(Join-Path $ScriptRoot "upload-pypi.ps1")
        }
    }
    "TestPyPI then PyPI production" {
        if (Ask-YesNo "Upload to TestPyPI now? Twine may prompt for credentials." $false) {
            Invoke-RepoCommand @(Join-Path $ScriptRoot "upload-testpypi.ps1")
        }
        if (Ask-YesNo "Upload the same artifacts to public PyPI now?" $false) {
            Invoke-RepoCommand @(Join-Path $ScriptRoot "upload-pypi.ps1")
        }
    }
}

Write-Host "Release assistant finished. Review git diff before committing."