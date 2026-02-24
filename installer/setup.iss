; ════════════════════════════════════════════════════════════════════
;  LessonRecorder — Inno Setup Installer
;  Автоматически устанавливает Python 3.13 если не найден.
; ════════════════════════════════════════════════════════════════════

#define MyAppName      "LessonRecorder"
#define MyAppVersion   GetFileVersion('..\dist\LessonRecorder\LessonRecorder.exe')
#define MyAppPublisher "MihailKashintsev"
#define MyAppURL       "https://github.com/MihailKashintsev/lesson-recorder"
#define MyAppExeName   "LessonRecorder.exe"
#define PythonVersion  "3.13.2"
#define PythonURL      "https://www.python.org/ftp/python/3.13.2/python-3.13.2-amd64.exe"
#define PythonMinVer   "3.10"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=LessonRecorder_setup
SetupIconFile=..\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
DisableWelcomePage=no
LicenseFile=
InfoAfterFile=

[Languages]
Name: "russian";    MessagesFile: "compiler:Languages\Russian.isl"
Name: "english";    MessagesFile: "compiler:Default.isl"

[Messages]
russian.WelcomeLabel1=Добро пожаловать в мастер установки [name]
russian.WelcomeLabel2=Программа установит [name] {#MyAppVersion} на ваш компьютер.%n%nЕсли Python не установлен, он будет скачан и установлен автоматически (~25 МБ).%n%nНажмите Далее для продолжения.

[Tasks]
Name: "desktopicon"; Description: "Ярлык на Рабочем столе"; GroupDescription: "Дополнительные ярлыки:"
Name: "startupicon"; Description: "Запускать при входе в Windows"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
; Основной билд приложения
Source: "..\dist\LessonRecorder\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Скрипт установки зависимостей (извлекается во временную папку)
Source: "install_python.ps1";  DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}";            Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}";    Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}";    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}";      Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; ── Шаг 1: Установка Python (если нужно) ─────────────────────────────────────
Filename: "powershell.exe";                                      \
  Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden       \
               -File ""{tmp}\install_python.ps1""                \
               -PythonVersion ""{#PythonVersion}""               \
               -PythonURL ""{#PythonURL}""                       \
               -MinVersion ""{#PythonMinVer}""";                 \
  StatusMsg: "Проверка и установка Python...";                   \
  Flags: waituntilterminated runhidden;                           \
  Description: "Установить Python {#PythonVersion}"

; ── Шаг 2: Установка pip-пакетов ─────────────────────────────────────────────
Filename: "powershell.exe";                                      \
  Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -Command \
    $ErrorActionPreference='SilentlyContinue';                   \
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source; \
    if (-not $py) {                                              \
      $keys = @(                                                 \
        'HKCU:\Software\Python\PythonCore',                      \
        'HKLM:\Software\Python\PythonCore',                      \
        'HKLM:\Software\WOW6432Node\Python\PythonCore'          \
      );                                                         \
      foreach ($k in $keys) {                                    \
        if (Test-Path $k) {                                      \
          Get-ChildItem $k | ForEach-Object {                    \
            $ip = Join-Path $_.PSPath 'InstallPath';             \
            if (Test-Path $ip) {                                 \
              $ep = (Get-ItemProperty $ip).ExecutablePath;       \
              if ($ep -and (Test-Path $ep)) { $py = $ep }       \
            }                                                    \
          }                                                      \
        }                                                        \
      }                                                          \
    };                                                           \
    if ($py) {                                                   \
      & $py -m pip install --upgrade pip --quiet;               \
      & $py -m pip install openai-whisper --quiet;              \
      & $py -m pip install PyAudioWPatch sounddevice --quiet;   \
      & $py -m pip install pytesseract Pillow --quiet           \
    }";                                                          \
  StatusMsg: "Установка компонентов транскрипции (может занять 2-5 мин)..."; \
  Flags: waituntilterminated runhidden

; ── Запустить приложение ──────────────────────────────────────────────────────
Filename: "{app}\{#MyAppExeName}"; \
  Description: "Запустить {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "powershell.exe"; \
  Parameters: "-Command Remove-Item -Recurse -Force '$env:APPDATA\LessonRecorder' -ErrorAction SilentlyContinue"; \
  Flags: runhidden waituntilterminated; \
  RunOnceId: "CleanAppData"

[Registry]
; Автозапуск (если выбрана задача)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Code]
// ── Глобальные переменные ────────────────────────────────────────────────────
var
  PythonStatusPage: TWizardPage;
  PythonStatusLabel: TLabel;
  PythonFoundLabel: TLabel;

// ── Проверка версии Python в реестре ────────────────────────────────────────
function GetPythonFromRegistry(): String;
var
  i: Integer;
  Hives: array of Integer;
  Subs: array of String;
  VerKey, InstPath, ExePath: String;
begin
  Result := '';
  SetArrayLength(Hives, 2);
  Hives[0] := HKEY_CURRENT_USER;
  Hives[1] := HKEY_LOCAL_MACHINE;

  SetArrayLength(Subs, 2);
  Subs[0] := 'SOFTWARE\Python\PythonCore';
  Subs[1] := 'SOFTWARE\WOW6432Node\Python\PythonCore';

  for i := 0 to 1 do
  begin
    // Пробуем версии 3.13, 3.12, 3.11, 3.10 по порядку предпочтения
    for i := 0 to High(Subs) do
    begin
      if RegKeyExists(Hives[0], Subs[i] + '\3.13\InstallPath') then
      begin
        RegQueryStringValue(Hives[0], Subs[i] + '\3.13\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
      if RegKeyExists(Hives[1], Subs[i] + '\3.13\InstallPath') then
      begin
        RegQueryStringValue(Hives[1], Subs[i] + '\3.13\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
      if RegKeyExists(Hives[0], Subs[i] + '\3.12\InstallPath') then
      begin
        RegQueryStringValue(Hives[0], Subs[i] + '\3.12\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
      if RegKeyExists(Hives[1], Subs[i] + '\3.12\InstallPath') then
      begin
        RegQueryStringValue(Hives[1], Subs[i] + '\3.12\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
      if RegKeyExists(Hives[0], Subs[i] + '\3.11\InstallPath') then
      begin
        RegQueryStringValue(Hives[0], Subs[i] + '\3.11\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
      if RegKeyExists(Hives[1], Subs[i] + '\3.11\InstallPath') then
      begin
        RegQueryStringValue(Hives[1], Subs[i] + '\3.11\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
      if RegKeyExists(Hives[0], Subs[i] + '\3.10\InstallPath') then
      begin
        RegQueryStringValue(Hives[0], Subs[i] + '\3.10\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
      if RegKeyExists(Hives[1], Subs[i] + '\3.10\InstallPath') then
      begin
        RegQueryStringValue(Hives[1], Subs[i] + '\3.10\InstallPath', 'ExecutablePath', ExePath);
        if (ExePath <> '') and FileExists(ExePath) then begin Result := ExePath; Exit; end;
      end;
    end;
  end;
end;

// ── Создаём кастомную страницу с инфо о Python ───────────────────────────────
procedure CreatePythonStatusPage();
var
  PythonPath: String;
  StatusText: String;
begin
  PythonStatusPage := CreateCustomPage(wpSelectDir,
    'Проверка Python',
    'Анализ системы перед установкой');

  PythonPath := GetPythonFromRegistry();

  PythonFoundLabel := TLabel.Create(WizardForm);
  PythonFoundLabel.Parent := PythonStatusPage.Surface;
  PythonFoundLabel.Left := 0;
  PythonFoundLabel.Top := 0;
  PythonFoundLabel.Width := PythonStatusPage.SurfaceWidth;
  PythonFoundLabel.WordWrap := True;
  PythonFoundLabel.AutoSize := True;

  PythonStatusLabel := TLabel.Create(WizardForm);
  PythonStatusLabel.Parent := PythonStatusPage.Surface;
  PythonStatusLabel.Left := 0;
  PythonStatusLabel.Top := 40;
  PythonStatusLabel.Width := PythonStatusPage.SurfaceWidth;
  PythonStatusLabel.WordWrap := True;
  PythonStatusLabel.AutoSize := True;

  if PythonPath <> '' then
  begin
    PythonFoundLabel.Caption := '✅  Python найден';
    PythonFoundLabel.Font.Style := [fsBold];
    PythonStatusLabel.Caption :=
      'Путь: ' + PythonPath + #13#10#13#10 +
      'Дополнительная установка Python не потребуется.' + #13#10 +
      'Нажмите Далее для продолжения.';
  end else
  begin
    PythonFoundLabel.Caption := '⬇  Python не обнаружен';
    PythonFoundLabel.Font.Style := [fsBold];
    PythonStatusLabel.Caption :=
      'Python {#PythonMinVer}+ не найден на этом компьютере.' + #13#10#13#10 +
      'Во время установки будет автоматически скачан и установлен' + #13#10 +
      'Python {#PythonVersion} (~25 МБ). Потребуется подключение к интернету.' + #13#10#13#10 +
      'Также будут установлены компоненты транскрипции (openai-whisper и др.).' + #13#10 +
      'Это может занять 3-7 минут в зависимости от скорости интернета.';
  end;
end;

// ── Инициализация (вызывается при старте мастера) ────────────────────────────
procedure InitializeWizard();
begin
  CreatePythonStatusPage();
end;
