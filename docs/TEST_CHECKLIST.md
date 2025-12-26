# CINDERGRACE Test Checkliste

Diese Checkliste führt durch alle wichtigen Funktionen der App.

---

## Vorbereitung

- [ ] ComfyUI ist gestartet und erreichbar unter `http://127.0.0.1:8188`
- [ ] Erforderliche Modelle sind in ComfyUI installiert
- [ ] App starten mit `./start.sh` oder `python main.py`

---

## 1. Setup Wizard (Tab: Setup)

### 1.1 Erster Start
- [ ] App zeigt orangenen "Willkommen"-Banner beim ersten Start
- [ ] Banner verweist auf "Setup" Tab

### 1.2 Step 1: System Check
- [ ] System-Info wird korrekt angezeigt (OS, Architektur)
- [ ] Dependencies werden geprüft (Python, ffmpeg, etc.)
- [ ] "Check system again" Button funktioniert
- [ ] "Next" Button führt zu Step 2

### 1.3 Step 2: ComfyUI Status
- [ ] Radio-Buttons für "Ja/Nein" funktionieren
- [ ] "Next" Button wird nach Auswahl aktiviert
- [ ] Bei "Ja" wird Step 3 übersprungen

### 1.4 Step 3: Installation Guide (nur wenn "Nein" gewählt)
- [ ] Windows-Anleitung wird angezeigt
- [ ] Linux-Anleitung wird angezeigt
- [ ] Tabs wechseln funktioniert

### 1.5 Step 4: Configuration
- [ ] ComfyUI Path Eingabefeld funktioniert
- [ ] ComfyUI URL Eingabefeld zeigt Default `http://127.0.0.1:8188`
- [ ] "Test Connection" Button testet Verbindung
- [ ] Bei erfolgreicher Verbindung wird "Finish Setup" aktiviert
- [ ] API Key Felder sind sichtbar (Civitai, Huggingface, Google TTS)
- [ ] API Keys können eingegeben werden (optional)

### 1.6 Step 5: Complete
- [ ] Erfolgsmeldung wird angezeigt
- [ ] Hinweis auf Settings Tab für spätere Änderungen
- [ ] "Go to Project Tab" Button funktioniert

---

## 2. Settings (Tab: ⚙️ Settings)

### 2.1 ComfyUI Backend
- [ ] Aktives Backend wird angezeigt
- [ ] Backend-Dropdown zeigt verfügbare Backends
- [ ] "Switch" Button wechselt Backend
- [ ] "Test" Button testet Verbindung
- [ ] Aktuelle URL und Typ werden angezeigt

### 2.2 Add/Edit Backend
- [ ] Accordion öffnet sich
- [ ] Name-Feld funktioniert
- [ ] URL-Feld funktioniert
- [ ] Typ-Radio (Local/Remote) funktioniert
- [ ] ComfyUI Path erscheint nur bei "Local"
- [ ] "Add" Button fügt neues Backend hinzu
- [ ] "Remove Selected" Button entfernt Backend (außer "local")

### 2.3 Edit Local Backend
- [ ] Local URL kann geändert werden
- [ ] ComfyUI Path kann geändert werden
- [ ] "Save Local Backend" speichert Änderungen

### 2.4 Workflows
- [ ] Workflow-Status zeigt gefundene Workflows
- [ ] Kategorien werden angezeigt (Keyframe, Video, First-Last, Lipsync)
- [ ] "Rescan Workflows" Button aktualisiert Liste

### 2.5 API Keys
- [ ] Civitai API Key Feld (Password-Typ)
- [ ] Huggingface Token Feld (Password-Typ)
- [ ] Google TTS API Key Feld (Password-Typ)
- [ ] Status zeigt konfigurierte/nicht konfigurierte Keys
- [ ] "Save API Keys" speichert Keys (verschlüsselt)
- [ ] Gespeicherte Keys werden beim Neuladen angezeigt

### 2.6 Developer Tools
- [ ] Accordion "Developer Tools" öffnet sich
- [ ] Warnung wird angezeigt
- [ ] "Reset Setup Wizard" Button funktioniert
- [ ] "Reset All Settings" Button funktioniert
- [ ] Nach Reset und App-Neustart: Setup-Banner erscheint wieder

---

## 3. Project (Tab: 📁 Project)

### 3.1 Projekt erstellen
- [ ] Projektname eingeben
- [ ] "Create Project" Button erstellt Projekt
- [ ] Projektverzeichnis wird angelegt
- [ ] Projekt wird als aktiv gesetzt

### 3.2 Projekt auswählen
- [ ] Dropdown zeigt verfügbare Projekte
- [ ] Projekt kann gewechselt werden
- [ ] Aktives Projekt wird in Header angezeigt

### 3.3 Projektinfo
- [ ] Projektpfad wird angezeigt
- [ ] Storyboard-Info wird angezeigt

---

## 4. Storyboard Manager (Tab: 📚 Boards)

### 4.1 Storyboard erstellen
- [ ] Name eingeben
- [ ] "Create Storyboard" Button funktioniert
- [ ] Storyboard-Datei wird erstellt

### 4.2 Storyboard auswählen
- [ ] Dropdown zeigt verfügbare Storyboards
- [ ] Storyboard kann gewechselt werden

---

## 5. Storyboard Editor (Tab: 📝 Editor)

### 5.1 Shots hinzufügen
- [ ] "Add Shot" Button fügt neuen Shot hinzu
- [ ] Shot-Nummer wird automatisch vergeben
- [ ] Prompt-Feld funktioniert
- [ ] Duration-Feld funktioniert

### 5.2 Shots bearbeiten
- [ ] Prompt kann geändert werden
- [ ] Duration kann geändert werden
- [ ] Änderungen werden gespeichert

### 5.3 Shots löschen
- [ ] Shot kann gelöscht werden
- [ ] Nummerierung wird aktualisiert

---

## 6. Image Import (Tab: 📥 Import)

### 6.1 Bilder importieren
- [ ] Bild-Upload funktioniert
- [ ] Mehrere Bilder können importiert werden
- [ ] Bilder werden in Projekt-Verzeichnis kopiert

### 6.2 Bilder zuordnen
- [ ] Bilder können Shots zugeordnet werden
- [ ] Zuordnung wird gespeichert

---

## 7. Keyframe Generator (Tab: 🎬 Keyframes)

### 7.1 Workflow auswählen
- [ ] Dropdown zeigt verfügbare Workflows (gcp_*)
- [ ] Workflow kann gewechselt werden
- [ ] LoRA-Variante wird automatisch erkannt (🎭)

### 7.2 Generation Settings
- [ ] Shot-Auswahl funktioniert
- [ ] Anzahl Varianten einstellbar
- [ ] Seed einstellbar
- [ ] Steps einstellbar
- [ ] CFG einstellbar

### 7.3 Generation starten
- [ ] "Generate" Button startet Generation
- [ ] Progress wird angezeigt
- [ ] Generierte Bilder erscheinen in Galerie
- [ ] Bilder werden in Projekt gespeichert

### 7.4 LoRA Support
- [ ] LoRA kann ausgewählt werden (falls verfügbar)
- [ ] LoRA-Stärke einstellbar
- [ ] Generation mit LoRA funktioniert

---

## 8. Keyframe Selector (Tab: ✅ Select)

### 8.1 Varianten anzeigen
- [ ] Generierte Varianten werden angezeigt
- [ ] Shots sind gruppiert

### 8.2 Auswahl treffen
- [ ] Variante kann ausgewählt werden
- [ ] Ausgewählte Variante wird markiert
- [ ] Auswahl wird gespeichert

### 8.3 Finalisieren
- [ ] "Finalize Selection" speichert finale Keyframes

---

## 9. Video Generator (Tab: 🎥 Video)

### 9.1 Workflow auswählen
- [ ] Dropdown zeigt verfügbare Workflows (gcv_*)
- [ ] Workflow kann gewechselt werden

### 9.2 Video Settings
- [ ] Resolution einstellbar
- [ ] FPS einstellbar
- [ ] Steps einstellbar
- [ ] CFG einstellbar

### 9.3 Generation starten
- [ ] "Generate Video" Button startet Generation
- [ ] Progress wird angezeigt
- [ ] Video erscheint nach Fertigstellung
- [ ] Video kann abgespielt werden

### 9.4 Batch Generation
- [ ] Mehrere Shots können generiert werden
- [ ] Videos werden nacheinander generiert

---

## 10. First/Last Video (Tab: 🎞️ Transition)

### 10.1 Bilder auswählen
- [ ] Erstes Bild kann hochgeladen werden
- [ ] Letztes Bild kann hochgeladen werden
- [ ] Oder: Bilder aus Projekt auswählen

### 10.2 Transition Settings
- [ ] Workflow auswählbar (gcvfl_*)
- [ ] Duration einstellbar
- [ ] Steps einstellbar

### 10.3 Generation
- [ ] "Generate Transition" startet Generation
- [ ] Transition-Video wird erstellt
- [ ] Video kann abgespielt werden

---

## 11. Lipsync (Tab: 🎤 Lipsync)

### 11.1 Character Image
- [ ] Bild kann hochgeladen werden
- [ ] Bild-Preview wird angezeigt

### 11.2 Audio
- [ ] Audio kann hochgeladen werden (MP3/WAV)
- [ ] Audio-Info wird angezeigt (Duration, Format)
- [ ] Audio kann getrimmt werden
- [ ] Trimmed Audio kann angehört werden

### 11.3 Generation
- [ ] Prompt für Bewegung/Emotion einstellbar
- [ ] Resolution einstellbar
- [ ] Steps/CFG/FPS einstellbar
- [ ] "Generate" startet Lipsync-Generation
- [ ] Video wird erstellt

---

## 12. Text-to-Speech (Tab: 🎙️ TTS)

### 12.1 Konfiguration prüfen
- [ ] Status zeigt ob API Key konfiguriert ist
- [ ] Falls nicht: Hinweis auf Settings Tab

### 12.2 Settings
- [ ] Sprache auswählbar (Deutsch/Englisch)
- [ ] Stimme auswählbar
- [ ] Geschwindigkeit einstellbar
- [ ] Tonhöhe einstellbar
- [ ] Format auswählbar (MP3/WAV)

### 12.3 Text eingeben
- [ ] Text-Feld funktioniert
- [ ] Zeichenzähler wird aktualisiert
- [ ] Kostenvoranschlag wird angezeigt

### 12.4 Generation
- [ ] "Preview" generiert kurze Vorschau
- [ ] "Generate Audio" erstellt vollständige Datei
- [ ] Audio kann abgespielt werden
- [ ] Datei wird im Projekt gespeichert

---

## 13. Dataset Generator (Tab: 📸 Dataset)

### 13.1 Input
- [ ] Character Name eingeben
- [ ] Base Image hochladen

### 13.2 Settings
- [ ] Steps einstellbar
- [ ] CFG einstellbar

### 13.3 Generation
- [ ] "Generate 15 Views" startet Generation
- [ ] Progress wird angezeigt
- [ ] Generierte Views erscheinen in Galerie
- [ ] Dataset-Pfad wird angezeigt
- [ ] Caption-Dateien werden erstellt

---

## 14. Character Trainer (Tab: 🎭 LoRA)

### 14.1 Dataset auswählen
- [ ] Dataset-Ordner kann ausgewählt werden
- [ ] Oder: Pfad aus Dataset Generator übernehmen

### 14.2 Training Settings
- [ ] Model auswählbar (FLUX/SDXL/SD3)
- [ ] Optimizer auswählbar
- [ ] Learning Rate einstellbar
- [ ] Epochs einstellbar

### 14.3 Training starten
- [ ] "Start Training" startet Training
- [ ] Progress wird angezeigt
- [ ] LoRA wird in output gespeichert

---

## 15. Model Manager (Tab: 🗂️ Models)

### 15.1 Konfiguration
- [ ] Pfade werden aus Settings übernommen
- [ ] Workflows-Verzeichnis einstellbar
- [ ] Archive-Verzeichnis einstellbar

### 15.2 Analyse
- [ ] "Analyze" scannt Workflows und Models
- [ ] Statistiken werden angezeigt
- [ ] Verwendete/ungenutzte Models werden klassifiziert

### 15.3 Duplikate
- [ ] Duplikate werden erkannt
- [ ] Duplikate können archiviert werden

### 15.4 Downloads
- [ ] Fehlende Models können heruntergeladen werden
- [ ] Civitai/Huggingface Downloads funktionieren

---

## 16. ComfyUI Test (Tab: 🧪 Test)

### 16.1 Connection Test
- [ ] URL wird aus Settings übernommen
- [ ] "Test Connection" testet Verbindung
- [ ] System Info wird bei Erfolg angezeigt

### 16.2 Image Generation Test
- [ ] Prompt eingeben
- [ ] Anzahl Bilder einstellbar
- [ ] Seed einstellbar
- [ ] Workflow auswählbar
- [ ] "Generate Test Images" startet Generation
- [ ] Bilder erscheinen in Galerie

---

## 17. Help (Tab: ❓ Help)

- [ ] Hilfe-Inhalte werden angezeigt
- [ ] Navigation funktioniert
- [ ] Workflow-Übersicht ist vorhanden

---

## Abschluss

### Cleanup
- [ ] Test-Projekte können gelöscht werden
- [ ] "Reset All Settings" setzt App zurück (⚙️ Settings → Developer Tools)

### Bekannte Einschränkungen
- [ ] Dokumentiert in docs/BACKLOG.md

---

**Datum:** _______________
**Tester:** _______________
**Version:** 0.6.1
**Ergebnis:** _____ / _____ Tests bestanden
