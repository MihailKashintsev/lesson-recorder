; ════════════════════════════════════════════════════════════════════
;  LessonRecorder — Inno Setup Installer
;  Python 3.13 устанавливается автоматически если не найден.
; ════════════════════════════════════════════════════════════════════

#define MyAppName      "LessonRecorder"
#define MyAppVersion   GetVersionNumbersString('..\dist\LessonRecorder\LessonRecorder.exe')
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

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
russian.WelcomeLabel1=Добро пожаловать в мастер установки [name]
russian.WelcomeLabel2=Программа установит [name] {#MyAppVersion} на ваш компьютер.%n%nЕсли Python не установлен, он будет скачан и установлен автоматически (~25 МБ).%n%nНажмите Далее для продолжения.

[Tasks]
Name: "desktopicon"; Description: "Ярлык на Рабочем столе";        GroupDescription: "Дополнительные ярлыки:"
Name: "startupicon"; Description: "Запускать при входе в Windows"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
; Основное приложение
Source: "..\dist\LessonRecorder\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; PS1-скрипты — извлекаются во временную папку во время установки
Source: "install_python.ps1";   DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "install_packages.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}";   Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}";   Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Шаг 1: Установка Python (если не установлен)
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -File ""{tmp}\install_python.ps1"" -PythonVersion ""{#PythonVersion}"" -PythonURL ""{#PythonURL}"" -MinVersion ""{#PythonMinVer}"""; \
  StatusMsg: "Проверка и установка Python..."; \
  Flags: waituntilterminated runhidden

; Шаг 2: Установка pip-пакетов
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -File ""{tmp}\install_packages.ps1"""; \
  StatusMsg: "Установка компонентов транскрипции (2-5 мин)..."; \
  Flags: waituntilterminated runhidden

; Запустить приложение
Filename: "{app}\{#MyAppExeName}"; \
  Description: "Запустить {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -Command ""Remove-Item -Recurse -Force $env:APPDATA\LessonRecorder -ErrorAction SilentlyContinue"""; \
  Flags: runhidden waituntilterminated; \
  RunOnceId: "CleanAppData"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Code]
var
  PythonStatusPage: TWizardPage;
  PythonFoundLabel: TLabel;
  PythonStatusLabel: TLabel;

function GetPythonFromRegistry(): String;
var
  Hives: array of Integer;
  Subs:  array of String;
  Vers:  array of String;
  h, s, v: Integer;
  ExePath: String;
begin
  Result := '';

  SetArrayLength(Hives, 2);
  Hives[0] := HKEY_CURRENT_USER;
  Hives[1] := HKEY_LOCAL_MACHINE;

  SetArrayLength(Subs, 2);
  Subs[0] := 'SOFTWARE\Python\PythonCore';
  Subs[1] := 'SOFTWARE\WOW6432Node\Python\PythonCore';

  SetArrayLength(Vers, 4);
  Vers[0] := '3.13';
  Vers[1] := '3.12';
  Vers[2] := '3.11';
  Vers[3] := '3.10';

  for v := 0 to High(Vers) do
    for h := 0 to High(Hives) do
      for s := 0 to High(Subs) do
      begin
        if RegKeyExists(Hives[h], Subs[s] + '\' + Vers[v] + '\InstallPath') then
        begin
          RegQueryStringValue(Hives[h], Subs[s] + '\' + Vers[v] + '\InstallPath',
                              'ExecutablePath', ExePath);
          if (ExePath <> '') and FileExists(ExePath) then
          begin
            Result := ExePath;
            Exit;
          end;
        end;
      end;
end;

procedure CreatePythonStatusPage();
var
  PythonPath: String;
begin
  PythonStatusPage := CreateCustomPage(wpSelectDir,
    'Проверка Python',
    'Анализ системы перед установкой');

  PythonFoundLabel := TLabel.Create(WizardForm);
  PythonFoundLabel.Parent    := PythonStatusPage.Surface;
  PythonFoundLabel.Left      := 0;
  PythonFoundLabel.Top       := 0;
  PythonFoundLabel.Width     := PythonStatusPage.SurfaceWidth;
  PythonFoundLabel.WordWrap  := True;
  PythonFoundLabel.AutoSize  := True;

  PythonStatusLabel := TLabel.Create(WizardForm);
  PythonStatusLabel.Parent   := PythonStatusPage.Surface;
  PythonStatusLabel.Left     := 0;
  PythonStatusLabel.Top      := 36;
  PythonStatusLabel.Width    := PythonStatusPage.SurfaceWidth;
  PythonStatusLabel.WordWrap := True;
  PythonStatusLabel.AutoSize := True;

  PythonPath := GetPythonFromRegistry();

  if PythonPath <> '' then
  begin
    PythonFoundLabel.Caption    := 'Python найден';
    PythonFoundLabel.Font.Style := [fsBold];
    PythonStatusLabel.Caption   :=
      'Путь: ' + PythonPath + #13#10#13#10 +
      'Дополнительная установка Python не потребуется.' + #13#10 +
      'Нажмите Далее для продолжения.';
  end else
  begin
    PythonFoundLabel.Caption    := 'Python не обнаружен';
    PythonFoundLabel.Font.Style := [fsBold];
    PythonStatusLabel.Caption   :=
      'Python 3.10+ не найден на этом компьютере.' + #13#10#13#10 +
      'Во время установки будет автоматически скачан Python {#PythonVersion} (~25 МБ).' + #13#10 +
      'Потребуется подключение к интернету.' + #13#10#13#10 +
      'Также будут установлены компоненты транскрипции (openai-whisper и др.).' + #13#10 +
      'Это займёт 3-7 минут в зависимости от скорости интернета.';
  end;
end;

procedure InitializeWizard();
begin
  CreatePythonStatusPage();
end;
