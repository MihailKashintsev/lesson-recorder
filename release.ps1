param(
    [string]$Version = "",
    [string]$Changelog = ""
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  FAIL: $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  LessonRecorder Release Tool" -ForegroundColor Yellow
Write-Host ""

Write-Step "Current version"
$currentVersion = python -c "from version import __version__; print(__version__)"
Write-Host "  Now: v$currentVersion" -ForegroundColor Gray

if (-not $Version) {
    $Version = Read-Host "`n  New version (e.g. 1.1.0)"
}

if ($Version -notmatch '^[0-9]+[.][0-9]+[.][0-9]+$') {
    Write-Fail "Wrong format. Use X.Y.Z e.g. 1.1.0"
}

if (-not $Changelog) {
    $Changelog = Read-Host "  What changed"
}

$tag = "v$Version"
Write-Host "  New version: $tag" -ForegroundColor Gray

Write-Step "Git status"
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "`n  Uncommitted changes:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Gray
    $answer = Read-Host "`n  Commit all? (y/n)"
    if ($answer -eq "y") {
        git add -A
        git commit -m "Release ${tag}: $Changelog"
        Write-Ok "Changes committed"
    } else {
        Write-Fail "Commit manually and run again"
    }
}

Write-Step "Bumping version"
python bump_version.py $Version
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Failed to bump version"
}
Write-Ok "Version updated"

Write-Step "Committing version"
git add version.py installer\version_info.txt
git commit -m "Bump version to $Version"
Write-Ok "Committed"

Write-Step "Creating tag $tag"
$existing = git tag -l $tag
if ($existing) {
    Write-Fail "Tag $tag already exists"
}
git tag -a $tag -m $Changelog
Write-Ok "Tag $tag created"

Write-Step "Pushing to GitHub"
git push origin master
git push origin $tag
Write-Ok "Pushed"

$remote = git remote get-url origin
$repoUrl = $remote -replace "\.git$", ""

Write-Host ""
Write-Host "  DONE! Release $tag started" -ForegroundColor Green
Write-Host "  Watch: $repoUrl/actions" -ForegroundColor Cyan
Write-Host "  Installer ready in ~7 minutes" -ForegroundColor Green
Write-Host ""