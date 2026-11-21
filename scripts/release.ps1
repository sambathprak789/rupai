<#
.SYNOPSIS
  Publish a RupAI release from this computer (same result as the CI "release" job).

.DESCRIPTION
  1. Checks that the working tree is clean and HEAD is pushed (the notebook clones the repo at the release tag).
  2. Runs the same checks as CI: Ruff + pytest (backend), typecheck + oxlint + Prettier (frontend).
  3. Builds the frontend and zips frontend/dist into dist.zip (forward-slash paths, so Linux/Colab can unzip it).
  4. Creates GitHub release "build-YYYYMMDD-HHmm" with dist.zip, targeting HEAD.
  5. Keeps only the 10 newest "build-*" releases.

  Works in Windows PowerShell 5.1 and PowerShell 7. Needs: git, gh (logged in), Python venv in backend/.venv, Node.

.EXAMPLE
  .\scripts\release.ps1
.EXAMPLE
  .\scripts\release.ps1 -SkipChecks   # only build and publish
#>
param(
    [switch]$SkipChecks,
    [int]$Keep = 10
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

function Invoke-Native {
    param([string]$What, [scriptblock]$Command)
    Write-Host "==> $What" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

foreach ($tool in 'git', 'gh', 'npm') {
    if (-not (Test-Command $tool)) { throw "'$tool' was not found. Install it first (gh: winget install GitHub.cli)." }
}

Push-Location $Root
try {
    # --- 1. Git state ------------------------------------------------------------
    gh auth status *> $null
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not logged in. Run: gh auth login" }

    $dirty = git status --porcelain
    if ($dirty) { throw "Uncommitted changes. Commit and push first:`n$dirty" }

    Invoke-Native 'git fetch' { git fetch --quiet origin }
    $sha = (git rev-parse HEAD).Trim()
    $onRemote = git branch -r --contains $sha
    if (-not $onRemote) { throw "Commit $($sha.Substring(0, 7)) is not on GitHub yet. Run: git push" }

    $repo = (gh repo view --json nameWithOwner -q .nameWithOwner).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $repo) { throw "Could not read the GitHub repository from 'origin'." }
    Write-Host "Repository: $repo  Commit: $($sha.Substring(0, 7))"

    # --- 2. Checks ---------------------------------------------------------------
    $python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { $python = Join-Path $Root 'backend/.venv/bin/python' }
    if (-not (Test-Path $python)) { throw "backend/.venv not found. Create it first (see backend/README.md)." }

    if (-not $SkipChecks) {
        Push-Location (Join-Path $Root 'backend')
        try {
            Invoke-Native 'ruff check' { & $python -m ruff check . }
            Invoke-Native 'ruff format --check' { & $python -m ruff format --check . }
            Invoke-Native 'pytest' { & $python -m pytest -q }
        }
        finally { Pop-Location }
    }

    Push-Location (Join-Path $Root 'frontend')
    try {
        if (-not (Test-Path 'node_modules')) { Invoke-Native 'npm ci' { npm ci } }
        if (-not $SkipChecks) {
            Invoke-Native 'typecheck' { npm run typecheck }
            Invoke-Native 'lint' { npm run lint }
            Invoke-Native 'format:check' { npm run format:check }
        }
        Invoke-Native 'build' { npm run build }
    }
    finally { Pop-Location }

    # --- 3. dist.zip (entries always use '/') -----------------------------------
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $dist = (Resolve-Path (Join-Path $Root 'frontend/dist')).Path
    $zipPath = Join-Path ([System.IO.Path]::GetTempPath()) 'rupai-dist.zip'
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        Get-ChildItem -Path $dist -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($dist.Length).TrimStart('\', '/').Replace('\', '/')
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $_.FullName, $relative, [System.IO.Compression.CompressionLevel]::Optimal)
        }
    }
    finally { $zip.Dispose() }

    # The asset must be called dist.zip (the notebook looks for that name)
    $asset = Join-Path ([System.IO.Path]::GetTempPath()) 'dist.zip'
    Move-Item -Force $zipPath $asset
    Write-Host ("dist.zip: {0:N1} KB" -f ((Get-Item $asset).Length / 1KB))

    # --- 4. Release ----------------------------------------------------------------
    $tag = 'build-' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmm')
    $notes = "Frontend build of $($sha.Substring(0, 7)), published from a local machine. The notebook clones the repo at this tag."
    Invoke-Native "gh release create $tag" {
        gh release create $tag $asset --repo $repo --target $sha --title $tag --notes $notes
    }

    # --- 5. Keep the newest releases -----------------------------------------------
    # Filtered in PowerShell: Windows PowerShell 5.1 strips quotes inside native arguments (no --jq here)
    $releases = (gh release list --repo $repo --limit 100 --json tagName,createdAt) | Out-String | ConvertFrom-Json
    $old = @($releases | Where-Object { $_.tagName -like 'build-*' } |
        Sort-Object { [datetime]$_.createdAt } -Descending |
        Select-Object -Skip $Keep | ForEach-Object { $_.tagName })
    foreach ($t in $old) {
        Invoke-Native "delete old release $t" { gh release delete $t --repo $repo --yes --cleanup-tag }
    }

    Write-Host ""
    Write-Host "Published $tag for $repo. Run the notebook with RELEASE_TAG = `"latest`"." -ForegroundColor Green
}
finally {
    Pop-Location
}
