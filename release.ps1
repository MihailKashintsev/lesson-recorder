param(
    [string]$Version  = "",
    [string]$Changelog = ""
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  OK: $msg"   -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  FAIL: $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  LessonRecorder Release Tool" -ForegroundColor Yellow
Write-Host ""

Write-Step "Current version"
$currentVersion = python -c "from version import __version__; print(__version__)"
Write-Host "  Now: v$currentVersion" -ForegroundColor Gray

if (-not $Version) {
    $Version = Read-Host "`n  New version (e.g. 1.5.0)"
}
if ($Version -notmatch '^[0-9]+[.][0-9]+[.][0-9]+$') {
    Write-Fail "Wrong format. Use X.Y.Z e.g. 1.5.0"
}

# ── Changelog (multiline) ─────────────────────────────────────────────────────
if (-not $Changelog) {
    Write-Host "`n  What changed in v$Version?" -ForegroundColor Yellow
    Write-Host "  (Enter multiple lines. Empty line = done)" -ForegroundColor Gray
    $lines = @()
    while ($true) {
        $line = Read-Host "  > "
        if ($line -eq "") { break }
        $lines += $line
    }
    $Changelog = $lines -join "`n"
}

if (-not $Changelog) {
    Write-Fail "Changelog cannot be empty"
}

$tag = "v$Version"
Write-Host "`n  New version: $tag" -ForegroundColor Gray

# ── Git status ────────────────────────────────────────────────────────────────
Write-Step "Git status"
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "`n  Uncommitted changes:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Gray
    $answer = Read-Host "`n  Commit all? (y/n)"
    if ($answer -eq "y") {
        git add -A
        git commit -m "Release ${tag}"
        Write-Ok "Changes committed"
    } else {
        Write-Fail "Commit manually and run again"
    }
}

# ── Bump version ──────────────────────────────────────────────────────────────
Write-Step "Bumping version"
python bump_version.py $Version
if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to bump version" }
Write-Ok "Version updated to $Version"

Write-Step "Committing version bump"
git add version.py installer\version_info.txt 2>$null
git add version.py version_info.txt            2>$null
git commit -m "Bump version to $Version"
Write-Ok "Committed"

# ── Save changelog to file so release.yml can read it ────────────────────────
Write-Step "Saving changelog"
$changelogFile = "RELEASE_NOTES.md"

# Build markdown
$md  = "## Что изменилось`n`n"
foreach ($line in ($Changelog -split "`n")) {
    $trimmed = $line.Trim()
    if ($trimmed) {
        if ($trimmed -match '^[-*•]') {
            $md += "$trimmed`n"
        } else {
            $md += "- $trimmed`n"
        }
    }
}
$md | Out-File -FilePath $changelogFile -Encoding utf8 -NoNewline
Write-Ok "Changelog saved to $changelogFile"

git add $changelogFile
git commit -m "Add release notes for $tag"
Write-Ok "Release notes committed"

# ── Tag ───────────────────────────────────────────────────────────────────────
Write-Step "Creating tag $tag"
$existing = git tag -l $tag
if ($existing) { Write-Fail "Tag $tag already exists" }

# Tag message = first line of changelog
$tagMsg = ($Changelog -split "`n")[0]
git tag -a $tag -m $tagMsg
Write-Ok "Tag $tag created"

# ── Push ──────────────────────────────────────────────────────────────────────
Write-Step "Pushing to GitHub"
git push origin master
git push origin $tag
Write-Ok "Pushed"

$remote = git remote get-url origin
$repoUrl = $remote -replace "\.git$", ""

Write-Host ""
Write-Host "  DONE! Release $tag started" -ForegroundColor Green
Write-Host "  Watch: $repoUrl/actions"    -ForegroundColor Cyan
Write-Host "  Installer ready in ~7 min"  -ForegroundColor Green
Write-Host ""
