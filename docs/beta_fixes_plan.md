# Beta-Fixes Plan (14.12.2024)

Basierend auf der Codex-Analyse und Verifizierung.

---

## WICHTIG (vor Beta-Release)

### 3. total_shots in Export korrigieren
**Problem:** `_build_preview_payload` zeigt `len(selections)` als total_shots - irreführend wenn nicht alle Shots ausgewählt.

**Lösung:**
- `total_shots` aus `storyboard.get("shots", [])` nehmen
- Zusätzlich `selected_shots` und `missing_shots` anzeigen

**Aufwand:** Klein (3-4 Zeilen)

---

### 4. ModelValidator-Warnung im UI
**Problem:** Wenn ComfyUI-Root fehlt, deaktiviert sich der Validator stillschweigend - Jobs scheitern dann an fehlenden Modellen ohne Vorwarnung.

**Lösung:**
- Warnung im Video-Tab anzeigen wenn `model_validator.enabled == False`
- Oder: Im Settings-Tab den Status anzeigen

**Aufwand:** Klein (UI-Element hinzufügen)

---

### 5. Log-Level aus Config anwenden
**Problem:** `config_manager.get_log_level()` existiert, wird aber vom Logger ignoriert.

**Lösung:**
- Logger beim Start den Level aus Config lesen lassen
- Oder: Setting aus UI entfernen wenn nicht verwendet

**Aufwand:** Klein

---

### 6. Pfadangaben für Storyboards validieren
**Problem:** Absolute Pfade in Dropdowns - beim Projekt-Umzug ungültig.

**Lösung:**
- Relative Pfade speichern
- Oder: Beim Laden validieren und Warnung zeigen

**Aufwand:** Mittel

---

### 7. Timeout/Retry konfigurierbar machen
**Problem:** Feste Werte (60s + 20×30s) für Video-Kopie - bei langen Encodes evtl. nicht genug.

**Lösung:**
- In Settings konfigurierbar machen
- Status-Updates in UI während des Wartens

**Aufwand:** Mittel

---

### 8. Workflow-Preset Fallback Warnung
**Problem:** Wenn `workflow_presets.json` fehlt, wird nur gescannt ohne UI-Hinweis.

**Lösung:**
- Hinweis im Settings-Tab wenn Preset-Datei fehlt

**Aufwand:** Klein

---

## BACKLOG (nach Beta)

### 1. Checkpoint-Dateiname angleichen
**Problem:** Resume funktioniert nie, weil Save und Load unterschiedliche Dateinamen verwenden.
- `keyframe_service.py:539` speichert: `checkpoint_{filename}`
- `keyframe_generator.py:431` sucht: `{basename}_checkpoint.json`

**Hinweis:** Stop/Resume ist noch nicht implementiert, kommt in nächster Version.

**Aufwand:** Klein (2 Zeilen Code + Test)

---

### 2. Auto-Download in Repo abstellen
**Problem:** `get_output_images()` lädt alle Bilder nach `infrastructure/output/test` - verschmutzt Repo, skaliert nicht.

**Lösung:**
- Funktion optional machen (nur bei Bedarf aufrufen)
- Oder: In Projekt-Output verschieben mit Cleanup-Strategie

**Aufwand:** Mittel

---

### 9. UI-Konsistenz verbessern
**Problem:** "Noch kein Plan" auch wenn Auto-Load fehlschlägt - sollte spezifischere Meldung zeigen.

**Lösung:**
- Fehlermeldungen präzisieren
- "Storyboard fehlt" vs "Selection fehlt" unterscheiden

**Aufwand:** Klein

---

## Tests hinzufügen (Backlog)

- [ ] Unit-Test: Checkpoint save → load Zyklus
- [ ] Unit-Test: Export total_shots vs selected_shots
- [ ] Integration: Mini-Workflow gegen lokale ComfyUI
- [ ] Config-Test: Log-Level wird angewendet

---

## Zusammenfassung

### WICHTIG
| # | Problem | Aufwand |
|---|---------|---------|
| 3 | total_shots falsch im Export | Klein |
| 4 | ModelValidator-Warnung fehlt | Klein |
| 5 | Log-Level aus Config ignoriert | Klein |
| 6 | Pfad-Validierung Storyboards | Mittel |
| 7 | Timeout konfigurierbar | Mittel |
| 8 | Preset-Warnung | Klein |

### BACKLOG
| # | Problem | Aufwand |
|---|---------|---------|
| 1 | Checkpoint-Namen (Stop/Resume) | Klein |
| 2 | Auto-Download in Repo | Mittel |
| 9 | UI-Konsistenz | Klein |
