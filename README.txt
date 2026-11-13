# Schul-Board

Schul-Board zeigt Stunden- und Vertretungspläne aus **beste.schule** sowie Hinweise und PDF-Aushänge auf einem Bildschirm an. Die Verwaltung läuft unter Windows, die Anzeige im Browser.

## Installation und Einrichtung

1. Dieses Repository über **Code → Download ZIP** herunterladen und entpacken.
2. `Einmalig_installieren.bat` ausführen. Das Skript richtet die Python-Umgebung für Schul-Board ein und bietet bei Bedarf an, Python zu installieren.
3. `Starten.bat` öffnen. Unter **Allgemein → Schule** den Schulnamen eintragen und optional ein eigenes PNG-Logo auswählen. Für die fiktive Musterschule ist ein [Beispiel-Logo](schullogo.png) enthalten.
4. Unter **API & Server** einen berechtigten API-Token für die eigene Schule eintragen und die Verbindung testen. Beim Speichern wird der Token im Windows-Anmeldespeicher abgelegt.
5. Unter **Klassen & Gruppen** die Hauptklassen übernehmen oder eintragen und bei Bedarf ihre Unterrichtsgruppen zuordnen. Für jede zugeordnete Gruppe lässt sich wählen, ob der Gruppenname oder das Fachkürzel angezeigt wird.
6. **Board starten** wählen und anschließend **Im Browser öffnen**. Mit **F11** lässt sich der Browser in den Vollbildmodus schalten.

## Anzeige anpassen

- Unter **Allgemein → Unterrichtszeiten** die Stundenlänge eingeben und die Startzeiten der Stunden auswählen. Das Ende berechnet Schul-Board automatisch. Die Markierung springt beim Stundenende zur nächsten eingetragenen Stunde.
- Unter **Anzeige & PDFs** lassen sich der Wechsel zwischen Jahrgängen, der Aktualisierungsabstand und die Anzeigedauer der PDFs einstellen.
- Unter **Lehrer** und **Räume** können die Kürzel aus der API durch eigene Anzeigebezeichnungen ersetzt werden.
- Für PDF-Aushänge unter **Anzeige & PDFs** einen Ordner auswählen und die gewünschten PDFs dort ablegen. Ein Dateiname wie `01122026-18122026.pdf` begrenzt die Anzeige auf diesen Zeitraum einschließlich beider Tage.

## Betrieb und Updates

Standardmäßig ist die Anzeige nur auf dem Rechner erreichbar, auf dem Schul-Board läuft. Für einen separaten Anzeigerechner kann der Zugriff unter **API & Server** für das Schulnetz aktiviert werden. In diesem Modus können Geräte, die den Server erreichen, die angezeigten Pläne und Aushänge abrufen.

Schuleinstellungen und Zugangsdaten werden lokal gespeichert. Beim Aktualisieren können die vorhandenen Einstellungen weiterverwendet werden. **Auf Updates prüfen** sucht nach neueren [GitHub-Releases](https://github.com/BigK0815/Schul-Board-Public/releases). Die Installation erfolgt manuell.

## Lizenz

Copyright (c) 2026 Robert Kettmann. Nichtkommerzielle Nutzung, Bearbeitung und Weitergabe sind gemäß der [Lizenz](LICENSE) möglich.
