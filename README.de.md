# ExactSplice

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Українська](README.uk.md)

**Bildgenauer Videoschnitt mit minimaler Neukodierung.**

ExactSplice ist ein quelloffener, lokal arbeitender Videoeditor auf FFmpeg-Basis. Er entstand als Video Hide zum Unkenntlichmachen vertraulicher Abschnitte von Aufzeichnungen. Browser und Python-Server laufen auf demselben Gerät; Cloud-Dienste sind nicht erforderlich.

## Projektstatus

Die Referenzversion ist [Video Hide v0.3.1](https://github.com/l3chat/ExactSplice/releases/tag/v0.3.1). Der erweiterte Editor 0.4 ist in Entwicklung. Portable Pakete für Windows, Linux und macOS sind geplant, aber noch nicht verfügbar.

## Installation

Unter Android Termux installieren und die folgenden Befehle ausführen. Unter Linux Python 3 und FFmpeg (einschließlich ffprobe, libx264 und drawtext) installieren, das Repository klonen und den Server starten.

### Android / Termux

```sh
pkg install python ffmpeg git
termux-setup-storage
git clone --branch v0.3.1 https://github.com/l3chat/ExactSplice.git
cd ExactSplice
python gui.py
```

### Linux

```sh
git clone --branch v0.3.1 https://github.com/l3chat/ExactSplice.git
cd ExactSplice
python3 gui.py /path/to/videos
```

Im Browser http://127.0.0.1:8765 öffnen. Die bisherige Oberfläche ist derzeit russischsprachig. Ein lokaler Medienordner kann als Kommandozeilenargument übergeben werden.

## Bedienung

1. Quelldatei auswählen; die Wiedergabe hängt von der Codec-Unterstützung des Browsers ab.
2. Für Smart-Modi Schlüsselbilder suchen. Anfang und Ende mit zoombarer Zeitleiste, Schlüsselbildnavigation und Einzelbildschritten festlegen.
3. Jedes Intervall hinzufügen. Überlappende und angrenzende Intervalle werden zusammengeführt; auch eine gültige noch nicht hinzugefügte Auswahl wird exportiert.
4. Hintergrundfarbe, Timerfarbe und -größe einstellen und Vorschau aktivieren. Der Export enthält den Countdown, nicht den Vorschautext.
5. JSON-Projekt speichern oder öffnen; es enthält Pfade und Einstellungen, keine Videodaten. Projekte aus 0.2 können geladen werden; Smart Exact bei Bedarf manuell wählen.
6. Modus, Audio, CRF und neuen MP4-Dateinamen wählen. Fortschritt und Protokoll verfolgen; Server bis zum Abschluss laufen lassen.

## Exportmodi

- **Full:** kodiert das gesamte Video als H.264 neu; Standard-CRF 18.
- **Smart:** erweitert die Intervalle nach außen bis zu vorhandenen Schlüsselbildern und kopiert unveränderte GOPs ohne Neukodierung.
- **Smart Exact (experimentell):** kodiert nur betroffene GOPs neu, maskiert anhand der Bildnummer und erzeugt IDR-Bilder an inneren Intervallgrenzen. Übrige GOPs werden kopiert. Grenzen zwischen Bildern werden auf das nächste Anzeigebild aufgerundet; der Timer zählt bis zum tatsächlichen Ende.

## Kompatibilität und Vertraulichkeit

Smart erfordert gewöhnliches H.264 yuv420p mit konstanter Bildrate (CFR), quadratischen Pixeln, Startzeit null und geeigneten inneren Schlüsselbildern beiderseits der Intervalle. Andernfalls Full verwenden. Paketanzahl, Anzeigezeitstempel und dekodierte Bilder an Schnittstellen werden geprüft; Fehler verhindern die Veröffentlichung. Die optionale vollständige Prüfung vergleicht dekodierte Ausgabebilder mit vorbereiteten Segmenten; bei Full prüft sie nur die Dekodierung. Das garantiert keine Vertraulichkeit: alle verdeckten Intervalle ansehen und Ton vor Weitergabe anhören.

Nur die erste Tonspur bleibt erhalten. Stummschaltung kodiert sie als AAC neu, mit 0,25 s Sicherheitsabstand auf beiden Seiten; Ergebnis prüfen. Untertitel, Kapitel und ursprüngliche Metadaten werden nicht kopiert. Quelldateien bleiben unverändert. Die Dateigröße ist nicht garantiert; Schätzungen berücksichtigen weder variable Bitrate noch neue Daten.

## Fortschritt und Abbruch

Die Anzeige ist ungefähr und zeigt Phase, FFmpeg-Geschwindigkeit, verstrichene und geschätzte Restzeit sowie Datenmenge des aktuellen Vorgangs, sofern verfügbar. Die Schlüsselbildsuche hat keine genaue Prozentanzeige. Abbrechen sendet SIGTERM an die Prozessgruppe; normalerweise werden temporäre Dateien ohne Veröffentlichung gelöscht. Erzwungenes Beenden kann .video-hide-*-Ordner mit vertraulichen Bildern neben der Ausgabe hinterlassen. Erst nach Ende der Verarbeitung löschen.

## Tests und DTS-Korrektur

0.3.1 normalisiert DTS bei unveränderten PTS. Für synthetische Linux-Videos wurden erfolgreiche Tests mit null, einem und zwei B-Bildern sowie Smart-Exact-Prüfung und Abbruch berichtet. Ein Anwender bestätigte auch die Bearbeitung einer langen Zoom-Aufzeichnung unter Android. Umfassende Geräte-, Codec- und Audiotests fehlen noch.

## Lizenz

Siehe [LICENSE](LICENSE). FFmpeg und weitere Abhängigkeiten haben eigene Lizenzen.
