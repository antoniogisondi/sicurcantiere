; Installatore Windows della famiglia SicurCantiere (Inno Setup 6: https://jrsoftware.org/isinfo.php)
; Compilare dopo Nuitka (scripts\build_windows.bat): iscc installer\sicurcantiere.iss
; I tre programmi sono copie dello stesso eseguibile compilato, nella stessa cartella con le librerie
; condivise: l'utente sceglie quali installare; ogni programma apre con un doppio clic i propri file:
; .scs (PSC), .spo (POS), .spm (PiMUS).

#define Versione "0.25.0"

[Setup]
AppId={{6B1F2C3E-5A7D-4E8B-9C0D-53C1CA171E20}
AppName=SicurCantiere
AppVersion={#Versione}
AppPublisher=SicurCantiere
DefaultDirName={autopf}\SicurCantiere
DefaultGroupName=SicurCantiere
OutputDir=..\dist
OutputBaseFilename=SicurCantiere-{#Versione}-setup
SetupIconFile=..\assets\sicurcantiere.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "italiano"; MessagesFile: "compiler:Languages\Italian.isl"

[Types]
Name: "completa"; Description: "Installazione completa (tutti i programmi)"
Name: "personalizzata"; Description: "Installazione personalizzata"; Flags: iscustom

[Components]
Name: "pos"; Description: "SicurCantiere POS - Piano operativo di sicurezza"; Types: completa personalizzata
Name: "psc"; Description: "SicurCantiere PSC - Piano di sicurezza e coordinamento"; Types: completa
Name: "pimus"; Description: "SicurCantiere PiMUS - Piano di montaggio, uso e smontaggio dei ponteggi"; Types: completa

[Tasks]
Name: "desktopicon"; Description: "Crea le icone sul desktop"; GroupDescription: "Icone aggiuntive:"
Name: "associa"; Description: "Apri i file dei cantieri con un doppio clic"; GroupDescription: "Associazione dei file:"

[InstallDelete]
; versioni fino alla 0.23 (PyInstaller): un programma per cartella, ognuno con le sue librerie
Type: filesandordirs; Name: "{app}\PSC"
Type: filesandordirs; Name: "{app}\POS"
Type: filesandordirs; Name: "{app}\PiMUS"

[Files]
; librerie e risorse comuni ai tre programmi
Source: "..\dist\SicurCantiere\*"; Excludes: "SicurCantiere PSC.exe,SicurCantiere POS.exe,SicurCantiere PiMUS.exe"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\SicurCantiere\SicurCantiere PSC.exe"; DestDir: "{app}"; Components: psc; Flags: ignoreversion
Source: "..\dist\SicurCantiere\SicurCantiere POS.exe"; DestDir: "{app}"; Components: pos; Flags: ignoreversion
Source: "..\dist\SicurCantiere\SicurCantiere PiMUS.exe"; DestDir: "{app}"; Components: pimus; Flags: ignoreversion
; Logo senza sigla: icona dei file dei cantieri (i programmi hanno la loro, con la sigla)
Source: "..\assets\sicurcantiere.ico"; DestDir: "{app}"; Flags: ignoreversion
; Icone dei programmi con la sigla, con un nome proprio: Windows non riusa l'icona che ricordava per l'eseguibile
Source: "..\assets\sicurcantiere-psc.ico"; DestDir: "{app}"; DestName: "icona-psc.ico"; Components: psc; Flags: ignoreversion
Source: "..\assets\sicurcantiere-pos.ico"; DestDir: "{app}"; DestName: "icona-pos.ico"; Components: pos; Flags: ignoreversion
Source: "..\assets\sicurcantiere-pimus.ico"; DestDir: "{app}"; DestName: "icona-pimus.ico"; Components: pimus; Flags: ignoreversion
; Caratteri Ubuntu (Ubuntu Font Licence) installati in Windows: servono a Word per i documenti generati.
Source: "..\sicurcantiere\risorse\font\Ubuntu-Regular.ttf"; DestDir: "{autofonts}"; FontInstall: "Ubuntu"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\sicurcantiere\risorse\font\Ubuntu-Italic.ttf"; DestDir: "{autofonts}"; FontInstall: "Ubuntu Italic"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\sicurcantiere\risorse\font\Ubuntu-Medium.ttf"; DestDir: "{autofonts}"; FontInstall: "Ubuntu Medium"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\sicurcantiere\risorse\font\Ubuntu-Bold.ttf"; DestDir: "{autofonts}"; FontInstall: "Ubuntu Bold"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\sicurcantiere\risorse\font\Ubuntu-BoldItalic.ttf"; DestDir: "{autofonts}"; FontInstall: "Ubuntu Bold Italic"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\sicurcantiere\risorse\font\UbuntuMono-Regular.ttf"; DestDir: "{autofonts}"; FontInstall: "Ubuntu Mono"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\sicurcantiere\risorse\font\UbuntuMono-Bold.ttf"; DestDir: "{autofonts}"; FontInstall: "Ubuntu Mono Bold"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\SicurCantiere PSC"; Filename: "{app}\SicurCantiere PSC.exe"; IconFilename: "{app}\icona-psc.ico"; Components: psc
Name: "{group}\SicurCantiere POS"; Filename: "{app}\SicurCantiere POS.exe"; IconFilename: "{app}\icona-pos.ico"; Components: pos
Name: "{group}\SicurCantiere PiMUS"; Filename: "{app}\SicurCantiere PiMUS.exe"; IconFilename: "{app}\icona-pimus.ico"; Components: pimus
Name: "{autodesktop}\SicurCantiere PSC"; Filename: "{app}\SicurCantiere PSC.exe"; IconFilename: "{app}\icona-psc.ico"; Components: psc; Tasks: desktopicon
Name: "{autodesktop}\SicurCantiere POS"; Filename: "{app}\SicurCantiere POS.exe"; IconFilename: "{app}\icona-pos.ico"; Components: pos; Tasks: desktopicon
Name: "{autodesktop}\SicurCantiere PiMUS"; Filename: "{app}\SicurCantiere PiMUS.exe"; IconFilename: "{app}\icona-pimus.ico"; Components: pimus; Tasks: desktopicon

[Registry]
; .scs -> PSC
Root: HKA; Subkey: "Software\Classes\.scs"; ValueType: string; ValueName: ""; ValueData: "SicurCantiere.PSC"; Flags: uninsdeletevalue; Components: psc; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.PSC"; ValueType: string; ValueName: ""; ValueData: "Cantiere PSC"; Flags: uninsdeletekey; Components: psc; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.PSC\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\sicurcantiere.ico"; Components: psc; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.PSC\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SicurCantiere PSC.exe"" ""%1"""; Components: psc; Tasks: associa
; .spo -> POS
Root: HKA; Subkey: "Software\Classes\.spo"; ValueType: string; ValueName: ""; ValueData: "SicurCantiere.POS"; Flags: uninsdeletevalue; Components: pos; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.POS"; ValueType: string; ValueName: ""; ValueData: "Cantiere POS"; Flags: uninsdeletekey; Components: pos; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.POS\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\sicurcantiere.ico"; Components: pos; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.POS\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SicurCantiere POS.exe"" ""%1"""; Components: pos; Tasks: associa
; .spm -> PiMUS
Root: HKA; Subkey: "Software\Classes\.spm"; ValueType: string; ValueName: ""; ValueData: "SicurCantiere.PiMUS"; Flags: uninsdeletevalue; Components: pimus; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.PiMUS"; ValueType: string; ValueName: ""; ValueData: "Ponteggi PiMUS"; Flags: uninsdeletekey; Components: pimus; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.PiMUS\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\sicurcantiere.ico"; Components: pimus; Tasks: associa
Root: HKA; Subkey: "Software\Classes\SicurCantiere.PiMUS\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SicurCantiere PiMUS.exe"" ""%1"""; Components: pimus; Tasks: associa

[Run]
; aggiorna le icone che Windows tiene in memoria (altrimenti i collegamenti possono mostrare quelle vecchie)
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden nowait skipifdoesntexist
Filename: "{app}\SicurCantiere POS.exe"; Description: "Avvia SicurCantiere POS"; Components: pos; Flags: nowait postinstall skipifsilent
; Aggiornamento avviato dal programma (/aggiornamento=si /programma=POS|PSC|PiMUS): lo riapre.
Filename: "{app}\SicurCantiere {param:programma|POS}.exe"; Flags: nowait runasoriginaluser; Check: RiavviaDopoAggiornamento

[Code]
function RiavviaDopoAggiornamento: Boolean;
begin
  Result := (ExpandConstant('{param:aggiornamento|no}') = 'si') and
    FileExists(ExpandConstant('{app}\SicurCantiere {param:programma|POS}.exe'));
end;
