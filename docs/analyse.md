# Analyse CINDERGRACE GUI (Beta-Vorbereitung)

## Kontext
- Codebasis: Python/Gradio GUI für CINDERGRACE Pipeline (Projekt-, Storyboard-, Keyframe- & Video-Management).
- Fokus: Fehlersuche & Verbesserungen vor Beta-Release. Keine Änderungen vorgenommen.

## Kritische Bugs / Blocker
- **Checkpoint-Dateiname inkonsistent (Resume unmöglich)**: `KeyframeGenerationService._save_checkpoint` speichert `checkpoints/checkpoint_<storyboard_filename>` (`services/keyframe_service.py`), während `KeyframeGeneratorAddon._load_checkpoint` nach `<basename>_checkpoint.json` sucht (`addons/keyframe_generator.py`). Ergebnis: Resume findet nie einen Checkpoint → jeder Lauf muss neu gestartet werden.
- **Automatisches Herunterladen aller ComfyUI-Outputs**: `ComfyUIAPI.get_output_images` lädt nach jedem Job sämtliche Bilder aus der History in `infrastructure/output/test` (`infrastructure/comfy_api/client.py`). Pfad liegt im Repo, wird nie aufgeräumt/konfiguriert und skaliert bei echten Jobs schlecht (Speicherverbrauch, Git-Verschmutzung). Für Produktion deaktivieren oder in Projekt-Output verschieben + optional machen.

## Weitere Risiken / Bugs
- **Fortschritts-/Statusverlust**: Keyframe-Stop/Resume im UI ist als „experimentell“ gekennzeichnet; `resume_btn` ist deaktiviert. Ohne funktionierenden Checkpoint ist Phase 1 nicht robust gegenüber Unterbrechungen.
- **Falsche Metadaten in Auswahl-Export**: `KeyframeSelectorAddon._build_preview_payload` setzt `total_shots` auf Anzahl gespeicherter Selektionen statt Storyboard-Shots (`addons/keyframe_selector.py`). Export wirkt vollständig, obwohl Shots fehlen – kann später im Video-Tab zu stillen Auslassungen führen.
- **Fehlende Modell-Prüfung wenn ComfyUI-Root fehlt**: `ModelValidator` deaktiviert sich komplett, wenn `comfy_root` nicht existiert (`infrastructure/model_validator.py`). Dadurch laufen Video-Jobs ohne Vorwarnung in fehlenden Modellen fest. Mindestens Warnung im UI, wenn Validation nicht läuft.
- **Log-Level aus Config wird ignoriert**: `ConfigManager.get_log_level` existiert, aber der Logger wird immer mit `INFO`-Konsole/`DEBUG`-File initialisiert (`infrastructure/logger.py`). Wunsch-Level aus Settings wird nie angewendet → erschwert Debugging/Support.
- **Pfadangaben für Storyboards in Projekt-Tab**: Auswahl kombiniert `config/` und Projektordner (`addons/project_panel.py`), nutzt aber absolute Pfade im Dropdown-Wert. Beim Umzug des Projekts greifen gespeicherte Pfade nicht mehr; relative Pfade oder Validierung beim Laden fehlen.

## Stabilität & UX-Verbesserungen
- **Robustes Job-Management**: Lange laufende Keyframe-/Video-Jobs benötigen klaren Lifecycle (Start/Stop/Resume), sichtbare Checkpoints, und Schutz vor Tab-Reload. Ein separater Worker/Queue-Service oder Hintergrund-Thread wäre stabiler als UI-gebundene Generatoren.
- **Timeout/Retry Tuning**: Video-Kopie wartet fix 60s + 20×30s (`services/video/video_generation_service.py`). Bei langen Encodes (WAN) kann das nicht reichen; Timeouts sollten konfigurierbar sein und Statusmeldungen in der UI landen.
- **ffmpeg-Abhängigkeit**: Last-Frame-Kette bricht still, wenn ffmpeg fehlt (`services/video/last_frame_extractor.py`). Frühzeitige Prüfung mit UI-Hinweis/Befehlspfad würde Fehlersuche beschleunigen.
- **Workflow-Preset-Fallback**: Wenn `config/workflow_presets.json` fehlt/beschädigt, wird nur der Ordner gescannt (`infrastructure/workflow_registry.py`), aber die UI meldet es nicht. Hinweis im Settings-Tab einblenden.
- **UI-Konsistenz**: Projekt-Tab Statusleisten/Warnings gut, aber Video-Tab zeigt „Noch kein Plan“ auch wenn Auto-Load fehlschlägt – sollte klar „Storyboards/Selections fehlen“ anzeigen.

## Tests / Release-Checks
- **Automatisierte Pfad-/Checkpoint-Tests**: Unit-Test für Checkpoint-Zyklus (save→resume) und für Auswahl-Export (alle Shots vs. exportierte Shots) würden die oben genannten Fehler sofort finden.
- **Integrationstest gegen lokale ComfyUI-Instanz**: Smoke-Test, der einen Mini-Workflow queued, Fortschritt über WebSocket bestätigt und sicherstellt, dass keine Downloads im Repo landen.
- **Logging-/Config-Test**: Sicherstellen, dass `log_level` aus `config/settings.json` angewendet wird und Logs in `logs/pipeline.log` rotieren.

## Vorschläge (Kurzfristig)
1) Checkpoint-Namensschema zwischen `KeyframeGenerationService` und `KeyframeGeneratorAddon` angleichen; Resume-Button aktivieren/testen.
2) `get_output_images` optional machen oder Pfad in Projekt-Output legen + Aufräum-Strategie.
3) Export-Payload im Keyframe-Selector mit echter Shot-Gesamtzahl anreichern und fehlende Shots markieren.
4) Log-Level aus Settings anwenden (oder Setting entfernen), klare Warnung wenn Model-Validator deaktiviert ist.
5) Frühprüfung ffmpeg + ComfyUI-Verbindung im Video-Tab anzeigen, bevor Jobs gestartet werden.
