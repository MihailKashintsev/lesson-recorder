# release.ps1 - LessonRecorder Release Tool
param(
    [string]$Version   = "",
    [string]$Changelog = ""
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  OK: $msg"   -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  FAIL: $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  LessonRecorder Release Tool" -ForegroundColor Yellow
Write-Host ""

# Version
Write-Step "Current version"
$currentVersion = python -c "from version import __version__; print(__version__)"
Write-Host "  Now: v$currentVersion" -ForegroundColor Gray

if (-not $Version) {
    $Version = Read-Host "`n  New version (e.g. 1.5.0)"
}
if ($Version -notmatch '^[0-9]+[.][0-9]+[.][0-9]+$') {
    Write-Fail "Wrong format. Use X.Y.Z e.g. 1.5.0"
}
$tag = "v$Version"

# Changelog
if (-not $Changelog) {
    Write-Host ""
    Write-Host "  What changed in $tag?" -ForegroundColor Yellow
    Write-Host "  Enter each item on a new line." -ForegroundColor Gray
    Write-Host "  Empty line = done." -ForegroundColor Gray
    Write-Host ""
    $lines = @()
    while ($true) {
        $line = Read-Host "  + "
        if ($line -eq "") { break }
        $lines += $line
    }
    $Changelog = $lines -join "`n"
}
if (-not $Changelog.Trim()) {
    Write-Fail "Changelog cannot be empty"
}

Write-Host ""
Write-Host "  Version:  $tag" -ForegroundColor White
Write-Host "  Changes:" -ForegroundColor White
foreach ($line in ($Changelog -split "`n")) {
    if ($line.Trim()) { Write-Host "    - $($line.Trim())" -ForegroundColor Gray }
}

# Sync .github/workflows/release.yml
Write-Step "Checking GitHub Actions workflow"
$workflowDir  = ".github\\workflows"
$workflowFile = "$workflowDir\\release.yml"
if (-not (Test-Path $workflowDir)) {
    New-Item -ItemType Directory -Path $workflowDir -Force | Out-Null
}
if (Test-Path "release.yml") {
    Copy-Item "release.yml" $workflowFile -Force
    Write-Ok "Workflow synced to $workflowFile"
} elseif (-not (Test-Path $workflowFile)) {
    Write-Fail "release.yml not found"
} else {
    Write-Ok "Workflow OK"
}

# Git status
Write-Step "Git status"
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host ""
    Write-Host "  Uncommitted changes:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Gray
    $answer = Read-Host "`n  Commit all? (y/n)"
    if ($answer -eq "y") {
        git add -A
        git commit -m "Release ${tag}"
        Write-Ok "Committed"
    } else {
        Write-Fail "Commit manually and run again"
    }
}

# Bump version
Write-Step "Bumping version"
python bump_version.py $Version
if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to bump version" }
Write-Ok "Version updated to $Version"

git add version.py
@("installer\\version_info.txt", "version_info.txt") | ForEach-Object {
    if (Test-Path $_) { git add $_ }
}
git commit -m "Bump version to $Version"
Write-Ok "Committed"

# Save RELEASE_NOTES.md
Write-Step "Saving release notes"
$md = "## What's new in $tag`n`n"
foreach ($line in ($Changelog -split "`n")) {
    $t = $line.Trim()
    if ($t) {
        if ($t -match '^[-*]') { $md += "$t`n" }
        else                    { $md += "- $t`n" }
    }
}
$md | Out-File -FilePath "RELEASE_NOTES.md" -Encoding utf8 -NoNewline
Write-Ok "RELEASE_NOTES.md saved"

git add RELEASE_NOTES.md
git commit -m "Release notes for $tag"
Write-Ok "Notes committed"

# Tag
Write-Step "Creating tag $tag"
$existing = git tag -l $tag
if ($existing) { Write-Fail "Tag $tag already exists" }

$tagMsg = ($Changelog -split "`n")[0]
git tag -a $tag -m $tagMsg
Write-Ok "Tag $tag created"

# Push
Write-Step "Pushing to GitHub"
git push origin master 2>$null
if ($LASTEXITCODE -ne 0) { git push origin main }
git push origin $tag
Write-Ok "Pushed"

$remote  = git remote get-url origin
$repoUrl = $remote -replace "\.git$", ""

Write-Host ""
Write-Host "  DONE! Release $tag started" -ForegroundColor Green
Write-Host "  Watch: $repoUrl/actions"    -ForegroundColor Cyan
Write-Host "  Installer ready in ~7 min"  -ForegroundColor Green
Write-Host ""
