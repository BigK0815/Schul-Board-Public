# Schul-Monitor (Beta)

<img src="schullogo.png" alt="Beispiel-Logo der Musterschule" width="96">

Schul-Monitor zeigt Stunden- und Vertretungspläne aus **beste.schule** zusammen mit Hinweisen und PDF-Aushängen. Die Einrichtung erfolgt in einer Windows-Anwendung, die Anzeige läuft im Browser.

## Installation unter Windows

1. Das Repository über **Code → Download ZIP** herunterladen und entpacken.
2. **Einmalig_installieren.bat** ausführen. Das Skript richtet die Python-Umgebung ein und bietet bei Bedarf die Installation von Python an.
3. **Starten.bat** öffnen. Unter **Allgemein** den Beispielnamen „Musterschule“ ersetzen und optional ein eigenes PNG-Logo wählen.
4. Unter **API & Server** den API-Token der eigenen Schule eintragen, die Verbindung testen und speichern. Für die automatische Klassenzuordnung benötigt der Token Zugriff auf die Gruppenmitgliedschaften.
5. **Schul-Monitor starten** und **Im Browser öffnen** wählen. Mit **F11** kann der Browser in den Vollbildmodus wechseln.

## Anzeige einrichten

- **Klassen & Gruppen** zeigt zuerst die Hauptklassen und danach die Gruppen. Jahrgänge lassen sich gesammelt ausblenden. Gruppen ohne Zuordnung können in der Tabelle ausgeblendet werden.
- In der Spalte **Anzeigen** schaltet ein Klick in die Zelle die Klasse oder Gruppe auf dem Board ein oder aus. Der **Eigene Anzeigename** ersetzt das Fachkürzel. Bei leerem Feld wird das Fachkürzel angezeigt.
- Das Board übernimmt das Zeitraster täglich aus beste.schule. Sobald eine Stunde endet, wechselt die grüne Markierung zur nächsten Stunde. Ohne Zeitraster zeigt das Board den Plan ohne Zeitmarkierung.
- Unter **Anzeige & PDFs** lassen sich die sichtbaren Stunden (0 bis 10, voreingestellt sind 1 bis 8), die Infobreite in Prozent der Bildschirmbreite und die Dauer der PDF-Anzeige einstellen. Die beiden Schultage stehen übereinander, ihre Jahrgänge nebeneinander. Ein Dateiname wie `01122026-18122026.pdf` begrenzt einen Aushang auf diesen Zeitraum einschließlich beider Tage.

## Datenabruf und lokale Speicherung

Der reguläre Stundenplan wird einmal pro Kalendertag geladen. Die API wird alle fünf Minuten gezielt nach Vertretungen für die beiden angezeigten Schultage abgefragt. Wochenenden und im Stundenplan hinterlegte schulfreie Tage werden übersprungen. Fehlt ein Vertretungsplan, erscheint der reguläre Stundenplan für den betreffenden Tag.

Die Gruppenzuordnung wird alle sieben Tage erneuert und kann unter **Klassen & Gruppen → Jetzt aktualisieren** manuell angestoßen werden. Schüler-IDs werden für den Abgleich im Arbeitsspeicher verwendet. Gespeichert werden die daraus ermittelten Zuordnungen und Jahrgangsangaben.

Schuleinstellungen und zwischengespeicherte Plandaten liegen lokal. Der Token wird über den Windows-Anmeldespeicher verwaltet. Die Beispielversion enthält den Namen „Musterschule“ und ein fiktives Schullogo. Zugangsdaten, echte Schulpläne und ausgefüllte Schuleinstellungen gehören nicht zum Download.

## Monitorprofile

Unter **Anzeige & PDFs → Monitorprofile** lassen sich 1 bis 10 Monitore einrichten. Pro Monitor werden Name, Port, Auflösung, Infobreite, sichtbare Stunden, Jahrgänge, Wechselzeiten und PDF-Ordner eingestellt. Die Standardports sind 5001 bis 5010. Eine bestehende Einzelmonitor-Einstellung wird als erstes Profil übernommen, einschließlich ihres Ports.

Nach dem Start zeigt die Verwaltung die Adressen an. Auf jedem Monitor wird die URL seines Profils im Vollbildbrowser geöffnet. Die Monitore verwenden denselben Datenabruf für den Stundenplan.

## Redaktion für Infos & Termine

1. Unter **API & Server → Redaktion** die Web-Redaktion aktivieren. Der voreingestellte Port ist **8081**. Board und Redaktion benötigen unterschiedliche Ports.
2. Ein gemeinsames Redaktionspasswort setzen. Die Vorschau verwendet Auflösung und Infobreite des gewählten Monitorprofils.
3. Speichern und den Schul-Monitor starten. **Redaktion öffnen** öffnet den Editor auf dem Server-PC. Bei aktivierter Schulnetzfreigabe ist die Redaktion über die IP des Server-PCs und den Redaktionsport erreichbar.
4. Eine Meldung mit Titel, formatiertem Text, Bildern und Anzeigezeitraum veröffentlichen. Bilder lassen sich an der unteren rechten Ecke proportional vergrößern und verkleinern. Meldungen können an einzelne, mehrere oder alle Monitore gesendet werden. Im Infoteil wechseln sie sich mit Tageshinweisen und PDFs ab. Aktive Vollbildmeldungen ersetzen auf ihren Zielmonitoren den Stundenplan und wechseln sich bei Überschneidungen ab. Nach Ablauf erscheint wieder das normale Board.

Das Redaktionspasswort wird im Windows-Anmeldespeicher gespeichert. Meldungen bleiben lokal in einer SQLite-Datei erhalten. Für den Netzwerkzugriff über eine verschlüsselte Verbindung kann die Schul-IT einen HTTPS-Reverse-Proxy vor die Redaktion setzen.

## Betrieb und Updates

Das Board ist standardmäßig nur auf dem eigenen Rechner erreichbar. Unter **API & Server → Im Schulnetz erreichbar** kann die Anzeige für Geräte im Schulnetz freigegeben werden. Diese Geräte können die dargestellten Pläne und Aushänge abrufen.

Für ein manuelles Update lässt sich die aktuelle Version in einen neuen Ordner entpacken. Dort einmal **Einmalig_installieren.bat** ausführen und anschließend **Starten.bat** öffnen. Die lokal gespeicherten Einstellungen können weiterverwendet werden. Aus Kompatibilitätsgründen bleibt der bisherige Windows-Datenordner `StundenplanBoard` erhalten; er darf bei einer Aktualisierung nicht gelöscht werden. **Auf Updates prüfen** prüft veröffentlichte [GitHub-Releases](https://github.com/BigK0815/Schul-Monitor/releases).

## Lizenz

Copyright (c) 2026 Robert Kettmann. Es gilt die [Lizenz](LICENSE).
