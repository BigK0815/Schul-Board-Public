Schul-Board – Schul-Board
================================================

INSTALLATION / UPDATE
1. Vorherigen Server und die Verwaltung beenden.
2. Diesen Ordner komplett entpacken und die alten Programmdateien ersetzen.
   Wichtig: schullogo.png muss neben board_engine.py liegen.
3. Einmalig_installieren.bat per Doppelklick ausführen. Sie prüft Python,
   fragt vor einer fehlenden Python-Installation um Erlaubnis und installiert
   die Python-Bibliotheken in einer eigenen .venv im Programmordner.
   Internetzugang ist für die Erstinstallation erforderlich.
   Python-Installation über winget (Windows App Installer) im Benutzerkontext.
   Falls winget fehlt, wird die offizielle Python-Downloadseite angeboten.
   Bei Schul-PCs können Richtlinien die Installation untersagen.
   Bei Updates die BAT erneut ausführen, damit Pakete aktualisiert werden.
4. Starten.bat öffnen und in der Verwaltung den Server starten.
5. Browser auf http://127.0.0.1:5000 (oder eingestellten Port) öffnen,
   mit Strg+F5 neu laden.

ANZEIGE
- Oben: Schullogo, Schul-Board, lokale Uhrzeit.
- Links: gemeinsamer Kopf für HEUTE und MORGEN, darunter ganze Jahrgänge
  mit allen Klassen nebeneinander. Standard: zwei Jahrgänge übereinander.
- Fach, Lehrerkürzel und Raum pro Stunde, acht Stunden je Schultag.
- Kurskopplungen werden wie bisher automatisch durchgeblättert.
- Gelb = Änderung, Rot = Ausfall, gekoppelte Kurse = etwas kräftigeres Blau.
- Jede zweite Stunde wird sehr hellblau eingefärbt, inklusive Stundennummer.
- Fach fett linksbündig, danach nur die aktuell unterrichtende Lehrkraft
  und der Raum; ursprüngliche Lehrkräfte werden nicht angezeigt.
- Nach der konfigurierten Uhrzeit (Standard 15 Uhr) wechseln die Tage.
  Wochenenden werden übersprungen; Ferien/Feiertage noch nicht automatisch.
- Rechts: etwa ein Drittel des Bildschirms für PDF-Informationen.
- Alle PDFs aus dem in der Verwaltung gewählten Ordner werden alphabetisch
  angezeigt, bei mehreren Seiten nacheinander.
- PDF-Ordner wird etwa alle 20 Sekunden neu geprüft.
- Die Darstellung skaliert mit der Bildschirmgröße (16:9 empfohlen).

EINSTELLUNGEN
- Die Windows-Verwaltung behält die bestehenden Einstellungen bei.
- Bei einem Update bleibt eine bereits gespeicherte Zeilenanzahl erhalten.
  Bitte ggf. 'Klassenstufen übereinander (Zeilen)' auf 2 einstellen.
- Start-Jahrgang z.B. 9 für die Anzeige 9 und 10.
- Die Daten kommen weiterhin von beste.schule; der API-Token bleibt
  ausschließlich im Windows-Anmeldespeicher.

HINWEIS
Keine vertraulichen PDFs in den öffentlichen Info-Ordner legen.
Die Python-Dateien sind syntaktisch geprüft; die Anzeige mit der echten
Schul-API muss vor Ort im Browser getestet werden.

NEU: TAGESINFORMATIONEN
- Unter den Datumsueberschriften HEUTE und MORGEN erscheint je ein schmaler
  hellblauer Hinweisstreifen mit den Tagesinformationen aus day.notes.
- Mehrere Hinweise wechseln alle 8 Sekunden, getrennt je Tag.
- Wenn beide Tage keine Hinweise haben, entfaellt die komplette Zeile.
- Die Stundenplaene und das rechte PDF-Infoboard bleiben unveraendert.
- Hinweise aendern nicht automatisch den Status von Unterrichtsstunden.

NEU: GRUPPENZUORDNUNG (Version mit Klassen-Zuordnung)
----------------------------------------------------
In der Verwaltung auf „Gruppen Klassen zuordnen …“ klicken.
„Gruppen aus API laden“ zeigt die verfügbaren Gruppenbezeichnungen.
Eine Gruppe markieren, im Feld „Klassen“ die Zielklassen eingeben
(z. B. 5/1, 5/2) und „Übernehmen“ klicken.
Danach „Zuordnungen speichern“ klicken und den Server neu starten.

Manuelle Zuordnungen haben Vorrang vor der bisherigen automatischen
Erkennung. Ohne manuellen Eintrag bleiben die bisherigen Schulregeln
aktiv. Gruppen mit NGS im Namen gehören zu den Klassenstufen 5 und 6.
Da NGS allein die genaue Klasse nicht angibt, bitte unklare NGS-Gruppen
manuell zuordnen. Die Einstellungen werden in
%APPDATA%\Schul-Board\einstellungen.json gespeichert.

WICHTIG: Eine Zuordnung beeinflusst nur die Anzeige. Es werden keine
Änderungen in beste.schule vorgenommen. Zum Test zuerst die Gruppen
prüfen und erst danach das Board im Schulbetrieb einsetzen.


SCHULSPEZIFISCHE ZUORDNUNGEN (NEU)
In der Verwaltung gibt es drei Schaltflächen für Räume, Lehrer sowie Hauptklassen/Gruppen.
Zwei Excel-Spalten markieren und kopieren (Strg+C), anschließend im jeweiligen
Editor auf „Aus Excel einfügen“ klicken oder in der Tabelle Strg+V drücken.
Beispiel Räume/Lehrer: API-Bezeichnung [TAB] gewünschte Anzeige
Beispiel Gruppen: API-Gruppe [TAB] 5/1, 5/2
Mehrere Zeilen mit derselben API-Gruppe ergänzen die Hauptklassen.
Mit „Bezeichnungen aus API übernehmen“ werden unbekannte Bezeichnungen ergänzt,
ohne bestehende Anpassungen zu überschreiben.
„Zuordnungen speichern“ speichert die Listen in der bisherigen Einstellungen-Datei
unter APPDATA/Schul-Board/einstellungen.json. Diese Datei bei Updates erhalten.
Einträge ohne angepasste Anzeige werden unverändert ausgegeben.
Die Raum-/Lehrer-Übersetzung erfolgt erst nach der Auswahl der aktuell gültigen
Vertretungsdaten. Änderungen sind nach dem nächsten Datenabruf sichtbar.
\n\nKLASSEN- UND GRUPPENZUORDNUNG (16 SPALTEN)\nIn der Verwaltung „Hauptklassen und Gruppen“ öffnen.\nSpalte A = Hauptklasse, Spalten B bis Q = Gruppe 1 bis Gruppe 16.\nAus Excel kopieren (Strg+C) und im Editor einfügen (Strg+V).\nAlternativ mehrere Gruppen mit Semikolon in eine Zelle schreiben.\nDie Hauptklasse selbst wird automatisch berücksichtigt.\nEine Gruppe kann mehreren Hauptklassen zugeordnet sein.\nDie Zuordnungen werden weiterhin in einstellungen.json gespeichert.\n
SCHULUNABHÄNGIGE KONFIGURATION (Testversion)
------------------------------------------
In der Verwaltung unter "Schule" können Schulname und ein eigenes PNG-Logo
festgelegt werden. Die Logo-Datei muss am gewählten Ort verfügbar bleiben.
Für andere Schulen die automatische Gruppenzuordnung ausschalten.
Unter "Hauptklassen und Gruppen" jede Hauptklasse (z. B. 5a, 9b, 10c)
als eigene Zeile erfassen. Die Hauptklasse wird beim Speichern automatisch
als API-Gruppe hinterlegt, auch wenn keine weiteren Gruppen angegeben sind.
Bis zu 16 Gruppen pro Klasse, Excel-Import und Semikolon-Eingaben bleiben erhalten.
Der Board-Rhythmus gruppiert Klassen nach führender Jahrgangszahl 5–10.
Die automatische Erkennung aus der API erkennt bisher 5/1 bzw. 5a;
abweichende Namen sind über die Tabelle manuell einzutragen.
Die schulspezifischen Einstellungen liegen im bisherigen Windows-Benutzerprofil.
Bestehende Einstellungen werden beim Update weiterverwendet.
