# Installation im Benutzerkontext; keine Administratorrechte erzwingen.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Test-Python([string]$Executable, [string[]]$PrefixArgs) {
    try {
        $code = "import sys,tkinter,venv;print('BOARD_PY_OK' if (3,10) <= sys.version_info[:2] < (3,15) else 'BOARD_PY_NO')"
        $result = & $Executable @PrefixArgs -c $code 2>$null
        if ($LASTEXITCODE -eq 0 -and "$result" -match 'BOARD_PY_OK') {
            return @{ Exe = $Executable; Args = $PrefixArgs }
        }
    } catch { }
    return $null
}

function Find-Python {
    $local = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    $candidates = @(
        @{Exe='py';Args=@('-3.13')},
        @{Exe='py';Args=@('-3')},
        @{Exe='python';Args=@()},
        @{Exe=(Join-Path $local 'Python313\python.exe');Args=@()},
        @{Exe=(Join-Path $local 'Python314\python.exe');Args=@()},
        @{Exe=(Join-Path $local 'Python312\python.exe');Args=@()}
    )
    foreach ($candidate in $candidates) {
        $found = Test-Python $candidate.Exe $candidate.Args
        if ($found) { return $found }
    }
    return $null
}

Write-Host 'Pruefe Python (mindestens 3.10, mit tkinter und venv) ...'
$python = Find-Python
if (-not $python) {
    Write-Host 'Keine geeignete Python-Installation gefunden.' -ForegroundColor Yellow
    $answer = Read-Host 'Python 3.13 ueber den Windows-Paketmanager winget installieren? [J/N]'
    if ($answer -notmatch '^[JjYy]$') {
        Write-Host 'Abgebrochen: Python wurde nicht installiert.'
        exit 2
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host 'winget ist auf diesem Windows-PC nicht verfuegbar.' -ForegroundColor Yellow
        Write-Host 'Bitte Python von https://www.python.org/downloads/windows/ installieren und danach diese Datei erneut starten.'
        $browser = Read-Host 'Offizielle Python-Downloadseite jetzt oeffnen? [J/N]'
        if ($browser -match '^[JjYy]$') { Start-Process 'https://www.python.org/downloads/windows/' }
        exit 3
    }
    Write-Host 'Starte die offizielle Python-Installation mit winget ...'
    & winget install --id Python.Python.3.13 --exact --source winget --scope user --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Python-Installation fehlgeschlagen oder abgebrochen.' -ForegroundColor Red
        exit 4
    }
    $python = Find-Python
    if (-not $python) {
        Write-Host 'Python wurde noch nicht gefunden. Bitte Windows-Anmeldung/Terminal neu starten und die BAT erneut ausfuehren.'
        exit 5
    }
}
Write-Host ('Python gefunden: ' + $python.Exe + ' ' + ($python.Args -join ' ')) -ForegroundColor Green

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host 'Erstelle isolierte Python-Umgebung im Programmordner ...'
    $pythonExe = $python.Exe
    $pythonArgs = @($python.Args)
    & $pythonExe @pythonArgs -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { Write-Host 'Fehler beim Erstellen der Umgebung.'; exit 6 }
}
Write-Host 'Installiere/aktualisiere die benoetigten Bibliotheken ...'
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Write-Host 'Fehler beim Installieren der Python-Pakete.'; exit 7 }
Write-Host 'Pruefe alle Programm-Abhaengigkeiten ...'
$checkCode = 'import flask, requests, waitress, keyring, fitz, tkinter; import board_engine; print(12345)'
& $venvPython -c $checkCode
if ($LASTEXITCODE -ne 0) { Write-Host 'Modulpruefung fehlgeschlagen.'; exit 8 }
Write-Host 'Einrichtung erfolgreich! Bestehende API-Zugangsdaten und Einstellungen bleiben erhalten.' -ForegroundColor Green
exit 0
