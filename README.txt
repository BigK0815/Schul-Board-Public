# Schul-Board (Beta)


Schul-Board zeigt Stunden- und Vertretungspläne aus **beste.schule** zusammen mit Hinweisen und PDF-Aushängen. Die Einrichtung erfolgt in einer Windows-Anwendung, die Anzeige läuft im Browser.

## Installation unter Windows

1. Das Repository über **Code → Download ZIP** herunterladen und entpacken.
2. **Einmalig_installieren.bat** ausführen. Das Skript richtet die Python-Umgebung ein und bietet bei Bedarf die Installation von Python an.
3. **Starten.bat** öffnen. Unter **Allgemein → Schule** den Beispielnamen „Musterschule“ ersetzen und optional ein eigenes PNG-Logo wählen.
4. Unter **API & Server** den API-Token der eigenen Schule eintragen, die Verbindung testen und speichern. Für die automatische Klassenzuordnung benötigt der Token Zugriff auf die Gruppenmitgliedschaften.
5. **Board starten** und **Im Browser öffnen** wählen. Mit **F11** kann der Browser in den Vollbildmodus wechseln.

## Anzeige einrichten

- **Klassen & Gruppen** zeigt zuerst die Hauptklassen und danach die Gruppen. Jahrgänge lassen sich gesammelt ausblenden. Gruppen ohne Zuordnung können in der Tabelle ausgeblendet werden.
- In der Spalte **Anzeigen** schaltet ein Klick in die Zelle die Klasse oder Gruppe auf dem Board ein oder aus. Der **Eigene Anzeigename** ersetzt das Fachkürzel. Bei leerem Feld wird das Fachkürzel angezeigt.
- Unter **Allgemein → Unterrichtszeiten** zeigt das Programm das täglich aus beste.schule geladene Zeitraster. Sobald eine Stunde endet, wechselt die grüne Markierung zur nächsten Stunde. Ohne Zeitraster zeigt das Board den Plan ohne Zeitmarkierung.
- Unter **Anzeige & PDFs** lassen sich der Wechsel zwischen Jahrgängen und die Dauer der PDF-Anzeige einstellen. Ein Dateiname wie `01122026-18122026.pdf` begrenzt einen Aushang auf diesen Zeitraum einschließlich beider Tage.

## Datenabruf und lokale Speicherung

Der reguläre Stundenplan wird einmal pro Kalendertag geladen. Die API wird alle fünf Minuten gezielt nach Vertretungen für die beiden angezeigten Schultage abgefragt. Wochenenden und im Stundenplan hinterlegte schulfreie Tage werden übersprungen. Fehlt ein Vertretungsplan, erscheint der reguläre Stundenplan für den betreffenden Tag.

Die Gruppenzuordnung wird alle sieben Tage erneuert und kann unter **Klassen & Gruppen → Jetzt aktualisieren** manuell angestoßen werden. Schüler-IDs werden für den Abgleich im Arbeitsspeicher verwendet. Gespeichert werden die daraus ermittelten Zuordnungen und Jahrgangsangaben.

Schuleinstellungen und zwischengespeicherte Plandaten liegen lokal. Der Token wird über den Windows-Anmeldespeicher verwaltet. Die Beispielversion enthält den Namen „Musterschule“ und ein fiktives Schullogo. Zugangsdaten, echte Schulpläne und ausgefüllte Schuleinstellungen gehören nicht zum Download.

## Betrieb und Updates

Das Board ist standardmäßig nur auf dem eigenen Rechner erreichbar. Unter **API & Server → Im Schulnetz erreichbar** kann die Anzeige für Geräte im Schulnetz freigegeben werden. Diese Geräte können die dargestellten Pläne und Aushänge abrufen.

Für ein manuelles Update lässt sich die aktuelle Version in einen neuen Ordner entpacken. Dort einmal **Einmalig_installieren.bat** ausführen und anschließend **Starten.bat** öffnen. Die lokal gespeicherten Einstellungen können weiterverwendet werden. **Auf Updates prüfen** prüft veröffentlichte [GitHub-Releases](https://github.com/BigK0815/Schul-Board-Public/releases).

## Lizenz

Copyright (c) 2026 Robert Kettmann. Es gilt die [Lizenz](LICENSE).
