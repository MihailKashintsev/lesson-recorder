# install_packages.ps1
# Finds Python and installs required pip packages for LessonRecorder.
# Called from Inno Setup [Run] section after install_python.ps1.
# Runs HIDDEN — no console windows shown to user.

$ErrorActionPreference = "SilentlyContinue"
$LogFile = "$env:TEMP\LessonRecorder_install.log"

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    "$ts  $msg" | Add-Content -Path $LogFile -Encoding UTF8
}

Log "=== install_packages.ps1 started ==="

function Find-Python {
    # 1. PATH
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($py -and (Test-Path $py) -and $py -match "python") {
        Log "Found in PATH: $py"; return $py
    }

    # 2. Registry
    $regBases = @(
        "HKCU:\Software\Python\PythonCore",
        "HKLM:\Software\Python\PythonCore",
        "HKLM:\Software\WOW6432Node\Python\PythonCore"
    )
    foreach ($ver in @("3.13","3.12","3.11","3.10")) {
        foreach ($base in $regBases) {
            $key = "$base\$ver\InstallPath"
            if (Test-Path $key) {
                $exe = (Get-ItemProperty $key -ErrorAction SilentlyContinue).ExecutablePath
                if ($exe -and (Test-Path $exe) -and $exe -match "python") {
                    Log "Found in registry [$ver]: $exe"
                    return $exe
                }
            }
        }
    }

    # 3. Standard install folders
    $localApp = $env:LOCALAPPDATA
    $candidates = @(
        "$localApp\Programs\Python\Python313\python.exe",
        "$localApp\Programs\Python\Python312\python.exe",
        "$localApp\Programs\Python\Python311\python.exe",
        "$localApp\Programs\Python\Python310\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python313\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { Log "Found at: $c"; return $c }
    }

    Log "Python not found"
    return $null
}

$py = Find-Python
if (-not $py) {
    Log "ERROR: No Python found, skipping package install"
    exit 0
}

Log "Using Python: $py"
Log "Installing packages (hidden)..."

# Все pip-команды запускаются скрыто — без окон консоли
$pipFlags = @(
    "-m", "pip", "install",
    "--quiet", "--quiet",
    "--disable-pip-version-check",
    "--no-warn-script-location"
)

$packages = @(
    "openai-whisper",
    "sounddevice",
    "pytesseract",
    "Pillow",
    "requests",
    "packaging"
)

foreach ($pkg in $packages) {
    Log "Installing: $pkg"
    $proc = Start-Process -FilePath $py `
        -ArgumentList ($pipFlags + @($pkg)) `
        -WindowStyle Hidden `
        -Wait -PassThru `
        -RedirectStandardOutput "$env:TEMP\lr_pip_out.txt" `
        -RedirectStandardError  "$env:TEMP\lr_pip_err.txt"
    
    $out = Get-Content "$env:TEMP\lr_pip_out.txt" -ErrorAction SilentlyContinue
    $err = Get-Content "$env:TEMP\lr_pip_err.txt" -ErrorAction SilentlyContinue
    if ($out) { Log "OUT: $out" }
    if ($err) { Log "ERR: $err" }
    Log "Exit code for ${pkg}: $($proc.ExitCode)"
}

# PyAudioWPatch только на Windows
Log "Installing PyAudioWPatch..."
$proc = Start-Process -FilePath $py `
    -ArgumentList ($pipFlags + @("PyAudioWPatch")) `
    -WindowStyle Hidden `
    -Wait -PassThru `
    -RedirectStandardOutput "$env:TEMP\lr_pip_out.txt" `
    -RedirectStandardError  "$env:TEMP\lr_pip_err.txt"
Log "PyAudioWPatch exit: $($proc.ExitCode)"

Log "=== install_packages.ps1 done ==="
exit 0
