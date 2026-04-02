; Meetily (ZennoCall) - Inno Setup Script
; Builds a Windows installer from the PyInstaller dist/Meetily/ output.
;
; Prerequisites:
;   1. Run `build.bat` first to produce dist\Meetily\
;   2. Install Inno Setup 6.x  (https://jrsoftware.org/isinfo.php)
;   3. Compile this script:  iscc installer\meetily.iss
;
; The installer will:
;   - Copy the app to Program Files
;   - Create Start Menu and optional Desktop shortcuts
;   - Register an uninstaller
;   - Install VC++ Redistributable if missing

#define MyAppName      "Meetily"
#define MyAppVersion   "0.1.0"
#define MyAppPublisher "Meetily"
#define MyAppExeName   "Meetily.exe"
#define MyAppURL       "https://github.com/grk717/meeting-minutes"

[Setup]
AppId={{B3F7A1D2-8E4C-4F6A-9D1B-2C5E8F0A3D7E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Allow user to toggle desktop icon in the wizard
AllowNoIcons=yes
; Output location and filename
OutputDir=..\dist
OutputBaseFilename=Meetily-{#MyAppVersion}-Setup
; Compression
Compression=lzma2/max
SolidCompression=yes
; Modern wizard style
WizardStyle=modern
; Require Windows 10+
MinVersion=10.0
; Request admin rights (needed for Program Files + VC++ redist)
PrivilegesRequired=admin
; Uninstall info
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; Use the app icon if available
SetupIconFile=..\meetily\resources\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application files from PyInstaller output
Source: "..\dist\Meetily\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; VC++ Redistributable (x64) - downloaded separately, see README
; If you place vc_redist.x64.exe next to this .iss file, it will be bundled.
; Otherwise the installer skips it gracefully.
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Install VC++ Redistributable silently if the file was bundled
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; \
    StatusMsg: "Installing Visual C++ Redistributable..."; \
    Flags: waituntilterminated skipifdoesntexist

; Offer to launch the app after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up any app-generated files in the install directory
Type: filesandordirs; Name: "{app}"

[Code]
// Check if VC++ Redistributable (2015-2022, x64) is already installed
function VCRedistInstalled: Boolean;
var
  Version: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64',
    'Installed', Version) and (Version = 1);
end;

// Skip VC++ install if already present
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // If VC++ is already installed, delete the bundled installer so [Run] skips it
  if VCRedistInstalled then
    DeleteFile(ExpandConstant('{tmp}\vc_redist.x64.exe'));
end;
