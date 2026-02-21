; LessonRecorder Installer — Inno Setup 6
; Скачать Inno Setup: https://jrsoftware.org/isdl.php

#define MyAppName "LessonRecorder"
#define MyAppVersion GetVersionNumbersString("{#SourcePath}\..\dist\LessonRecorder\LessonRecorder.exe")
#define MyAppPublisher "YOUR-GITHUB-USERNAME"
#define MyAppURL "https://github.com/YOUR-GITHUB-USERNAME/lesson-recorder"
#define MyAppExeName "LessonRecorder.exe"
#define MyOutputName "LessonRecorder_" + MyAppVersion + "_setup"

[Setup]
; Уникальный GUID — НЕ менять после первого релиза!
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Иконка установщика
;SetupIconFile=icon.ico
OutputDir={#SourcePath}\..\dist\installer
OutputBaseFilename={#MyOutputName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Без запроса UAC если можно
PrivilegesRequiredOverridesAllowed=dialog
; Автозакрытие приложения перед установкой
CloseApplications=yes
CloseApplicationsFilter=LessonRecorder.exe
RestartApplications=yes
; Версионирование для silent install (/SILENT флаг)
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Запускать при старте Windows"; GroupDescription: "Дополнительно:"; Flags: unchecked

[Files]
; Вся папка dist\LessonRecorder\ (PyInstaller вывод)
Source: "{#SourcePath}\..\dist\LessonRecorder\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Удалять пользовательские данные только если пользователь согласился
Type: dirifempty; Name: "{app}"

[Code]
// Убиваем запущенный процесс перед обновлением (для silent install)
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
