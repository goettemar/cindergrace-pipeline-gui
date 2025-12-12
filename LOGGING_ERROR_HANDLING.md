# Logging und Error Handling Guide

Dieses Dokument erklärt, wie du das neue strukturierte Logging-System und Error Handling in der CINDERGRACE Pipeline nutzt.

## 📋 Übersicht

Das System besteht aus vier Komponenten:

1. **Strukturiertes Logging** (`infrastructure/logger.py`)
2. **Custom Exception Hierarchy** (`domain/exceptions.py`)
3. **Error Handler Decorators** (`infrastructure/error_handler.py`)
4. **Input Validation mit Pydantic** (`domain/validators.py`)

---

## 🪵 Logging

### Grundlegende Nutzung

```python
from infrastructure.logger import get_logger

logger = get_logger(__name__)

# Log-Levels
logger.debug("Detaillierte Debug-Information")
logger.info("Normaler Informations-Log")
logger.warning("Warnung - etwas ist ungewöhnlich")
logger.error("Fehler aufgetreten", exc_info=True)  # Mit Stacktrace
```

### Log-Levels

- **DEBUG**: Detaillierte Informationen für Debugging (nur in Log-Datei)
- **INFO**: Normale Prozess-Informationen (Konsole + Datei)
- **WARNING**: Warnungen - etwas ist ungewöhnlich, aber nicht kritisch
- **ERROR**: Fehler - etwas ist fehlgeschlagen

### Log-Ausgabe

**Konsole:**
```
14:32:15 [INFO] infrastructure.comfy_api: Testing connection to ComfyUI
14:32:15 [INFO] infrastructure.comfy_api: ✓ Connection successful
```

**Log-Datei** (`logs/pipeline.log`):
```
2024-12-10 14:32:15 [INFO] infrastructure.comfy_api:50 - Testing connection to ComfyUI
2024-12-10 14:32:15 [INFO] infrastructure.comfy_api:52 - ✓ Connection successful
```

### Log-Rotation

- Log-Dateien werden automatisch rotiert bei 10MB
- Es werden die letzten 5 Log-Dateien aufbewahrt
- Speicherort: `cindergrace_gui/logs/pipeline.log`

---

## 🚨 Exception Handling

### Custom Exceptions nutzen

Wirf spezifische Exceptions statt generischer `Exception`:

```python
from domain.exceptions import (
    ProjectCreationError,
    StoryboardLoadError,
    WorkflowExecutionError,
)

# ❌ Schlecht
if not os.path.exists(path):
    raise Exception("File not found")

# ✅ Gut
if not os.path.exists(path):
    raise StoryboardLoadError(f"Storyboard nicht gefunden: {path}")
```

### Exception Hierarchy

```
PipelineException (Base)
├── ProjectError
│   ├── ProjectNotFoundError
│   └── ProjectCreationError
├── StoryboardError
│   ├── StoryboardLoadError
│   └── StoryboardValidationError
├── ComfyUIError
│   ├── ComfyUIConnectionError
│   └── WorkflowError
│       ├── WorkflowLoadError
│       ├── WorkflowExecutionError
│       └── WorkflowTimeoutError
├── GenerationError
│   ├── KeyframeGenerationError
│   └── VideoGenerationError
└── ValidationError
    └── InputValidationError
```

Siehe `domain/exceptions.py` für vollständige Liste.

---

## 🎯 Error Handler Decorator

### Einfache Nutzung in Addons

Der `@handle_errors` Decorator fängt Exceptions und formatiert sie für die UI:

```python
from infrastructure.error_handler import handle_errors
from infrastructure.logger import get_logger
from domain.exceptions import ProjectCreationError

logger = get_logger(__name__)

@handle_errors("Konnte Projekt nicht erstellen")
def create_project(self, name: str):
    logger.info(f"Creating project: {name}")

    if not name:
        raise ProjectCreationError("Projektname darf nicht leer sein")

    project = self.project_manager.create_project(name)
    logger.info(f"✓ Project created: {project['name']}")

    return f"**✅ Erstellt:** {project['name']}"

# Bei Fehler wird automatisch returned:
# "**❌ Fehler:** Projektname darf nicht leer sein"
```

### Mit Tuple Return (für mehrere Outputs)

Wenn deine Funktion mehrere Gradio-Outputs zurückgibt:

```python
@handle_errors("Konnte Storyboard nicht laden", return_tuple=True)
def load_storyboard(self, file_path: str):
    logger.info(f"Loading storyboard: {file_path}")

    storyboard = storyboard_service.load_storyboard(file_path)
    shots = len(storyboard.shots)

    return (
        json.dumps(storyboard.raw, indent=2),  # Output 1
        f"**✅ Geladen:** {shots} Shots",      # Output 2
        gr.update(choices=self._get_shots())   # Output 3
    )

# Bei Fehler wird automatisch returned:
# (None, "**❌ Fehler:** ...", None)
```

### Alternative: safe_execute

Für explizitere Kontrolle:

```python
from infrastructure.error_handler import safe_execute

result, error = safe_execute(
    lambda: project_store.create_project(name),
    error_message="Konnte Projekt nicht erstellen"
)

if error:
    logger.warning(f"Project creation failed: {error}")
    return error

logger.info(f"✓ Project created: {result['name']}")
return f"**✅ Erstellt:** {result['name']}"
```

---

## ✅ Input Validation mit Pydantic

### Was ist Pydantic?

Pydantic ist eine Validierungs-Bibliothek, die Python Type Hints nutzt, um Eingabedaten automatisch zu validieren und zu konvertieren. Dies hilft dabei:

- **Ungültige Eingaben früh abzufangen** (bevor sie zu Fehlern führen)
- **Klare Fehlermeldungen** zu generieren
- **Type Safety** zu gewährleisten
- **Code selbst-dokumentierend** zu machen

### Verfügbare Validatoren

Alle Validatoren befinden sich in `domain/validators.py`:

#### KeyframeGeneratorInput
Validiert Eingaben für Keyframe-Generierung:
- `variants_per_shot`: 1-10 Varianten pro Shot
- `base_seed`: Positive Ganzzahl (0 bis 2147483647)

#### VideoGeneratorInput
Validiert Eingaben für Video-Generierung:
- `fps`: 12-30 Frames pro Sekunde
- `max_segment_seconds`: 0.1-10.0 Sekunden

#### ProjectCreateInput
Validiert Projektnamen:
- Nicht leer
- Max. 100 Zeichen
- Keine ungültigen Dateisystem-Zeichen (`< > : " / \ | ? *`)
- Keine Windows-reservierten Namen (`CON`, `PRN`, etc.)

#### SettingsInput
Validiert Einstellungen:
- `comfy_url`: Gültige HTTP/HTTPS URL
- `comfy_root`: Absoluter Pfad

#### Datei-Validatoren
- `StoryboardFileInput`: Validiert Storyboard-Datei-Auswahl
- `WorkflowFileInput`: Validiert Workflow-Datei-Auswahl
- `SelectionFileInput`: Validiert Selection-Datei-Auswahl

### Nutzung in Addons

**Beispiel: Projekt erstellen**

```python
from domain.validators import ProjectCreateInput

@handle_errors("Konnte Projekt nicht erstellen")
def _create_project(self, name: str):
    logger.info(f"Creating new project: {name}")

    # Validate input with Pydantic
    validated = ProjectCreateInput(name=name)
    validated_name = validated.name  # Garantiert gültig!

    project = self.project_manager.create_project(validated_name)
    logger.info(f"✓ Project created: {project['name']}")

    return f"**✅ Erstellt:** {project['name']}"
```

**Beispiel: Keyframe-Generierung**

```python
from domain.validators import KeyframeGeneratorInput, StoryboardFileInput

def start_generation(self, storyboard_file, workflow_file, variants_per_shot, base_seed):
    try:
        # Validate all inputs
        validated_inputs = KeyframeGeneratorInput(
            variants_per_shot=int(variants_per_shot),
            base_seed=int(base_seed)
        )
        StoryboardFileInput(storyboard_file=storyboard_file)

        logger.info(f"Starting generation: {validated_inputs.variants_per_shot} variants")

        # Use validated values
        checkpoint = {
            "variants_per_shot": validated_inputs.variants_per_shot,
            "base_seed": validated_inputs.base_seed,
            ...
        }
    except Exception as e:
        # ValidationError wird automatisch vom @handle_errors decorator gefangen
        logger.error(f"Validation failed: {e}")
        return [], f"**❌ Error:** {str(e)}", {}, "Error"
```

**Beispiel: Settings speichern**

```python
from domain.validators import SettingsInput

def save_settings(self, comfy_url: str, comfy_root: str) -> str:
    try:
        # Validate inputs
        validated = SettingsInput(
            comfy_url=comfy_url,
            comfy_root=comfy_root
        )

        logger.info(f"Saving settings: URL={validated.comfy_url}")

        self.config.set("comfy_url", validated.comfy_url)
        self.config.set("comfy_root", validated.comfy_root)

        return "**✅ Gespeichert:** Basiseinstellungen aktualisiert."
    except Exception as exc:
        logger.error(f"Failed to save settings: {exc}")
        return f"**❌ Fehler:** {exc}"
```

### Automatische Fehlerformatierung

Pydantic `ValidationError` Exceptions werden automatisch vom `@handle_errors` Decorator gefangen und formatiert:

**Single Error:**
```
**❌ Validierungsfehler:** Mindestens 1 Variante pro Shot erforderlich
```

**Multiple Errors:**
```
**❌ Validierungsfehler:**
- variants_per_shot: Mindestens 1 Variante pro Shot erforderlich
- base_seed: Seed muss eine positive Zahl sein
```

### Eigene Validatoren erstellen

Wenn du einen neuen Validator brauchst, füge ihn in `domain/validators.py` hinzu:

```python
from pydantic import BaseModel, Field, field_validator

class MyCustomInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    my_field: int = Field(
        ge=1,
        le=100,
        description="My custom field"
    )

    @field_validator('my_field')
    @classmethod
    def validate_my_field(cls, v: int) -> int:
        if v % 2 != 0:
            raise ValueError("Wert muss gerade sein")
        return v
```

### Vorteile

✅ **Frühe Fehlerkennung**: Fehler werden sofort beim Validieren erkannt, nicht später beim Ausführen

✅ **Klare Fehlermeldungen**: Deutsche Fehlermeldungen, die dem User direkt helfen

✅ **Type Safety**: Garantiert, dass Werte im richtigen Format sind

✅ **Weniger Code**: Keine manuellen if-Checks mehr

✅ **Selbst-dokumentierend**: Validierungsregeln sind im Code sichtbar

---

## 📝 Best Practices

### 1. **Logging in Services**

```python
from infrastructure.logger import get_logger

logger = get_logger(__name__)

class KeyframeService:
    def generate_keyframes(self, storyboard, variants=4):
        logger.info(f"Starting keyframe generation: {len(storyboard.shots)} shots")

        for idx, shot in enumerate(storyboard.shots):
            logger.debug(f"Processing shot {idx+1}/{len(storyboard.shots)}: {shot.shot_id}")

            # ... generation logic ...

            logger.info(f"✓ Generated {variants} variants for shot {shot.shot_id}")

        logger.info(f"✓ Keyframe generation complete: {total} images")
```

### 2. **Error Handling in Services**

Services sollten spezifische Exceptions werfen:

```python
from domain.exceptions import KeyframeGenerationError, WorkflowExecutionError

def generate_keyframes(self, shot):
    logger.info(f"Generating keyframes for shot {shot.shot_id}")

    try:
        result = self.comfy_api.queue_prompt(workflow)
    except WorkflowExecutionError as e:
        # Re-raise mit zusätzlichem Kontext
        raise KeyframeGenerationError(
            f"Keyframe-Generierung für Shot {shot.shot_id} fehlgeschlagen: {e}"
        )

    if not result["output_images"]:
        raise KeyframeGenerationError(
            f"Keine Bilder generiert für Shot {shot.shot_id}"
        )

    return result["output_images"]
```

### 3. **Error Handling in Addons**

Addons sollten Exceptions fangen und für die UI formatieren:

```python
@handle_errors("Konnte Keyframes nicht generieren")
def start_generation(self, storyboard_file, variants, seed):
    logger.info(f"Starting generation: {variants} variants, seed {seed}")

    # Load storyboard (kann StoryboardLoadError werfen)
    storyboard = storyboard_service.load_storyboard(storyboard_file)

    # Generate (kann KeyframeGenerationError werfen)
    images = self.service.generate_keyframes(storyboard, variants, seed)

    logger.info(f"✓ Generation complete: {len(images)} images")
    return f"**✅ Generiert:** {len(images)} Keyframes"
```

### 4. **Keine print() Statements**

❌ **Schlecht:**
```python
print(f"Starting generation...")
print(f"Error: {e}")
```

✅ **Gut:**
```python
logger.info("Starting generation...")
logger.error(f"Generation failed: {e}", exc_info=True)
```

### 5. **Exception Context beibehalten**

Wenn du Exceptions re-raises, füge Kontext hinzu:

```python
try:
    workflow = self.comfy_api.load_workflow(path)
except WorkflowLoadError as e:
    # Re-raise mit zusätzlichem Kontext
    raise KeyframeGenerationError(
        f"Konnte Workflow für Keyframe-Generierung nicht laden: {e}"
    )
```

---

## 🔧 Migration Guide

### Bestehenden Code migrieren

**Vorher:**
```python
def create_project(self, name):
    try:
        if not name:
            return "**❌ Fehler:** Projektname darf nicht leer sein"

        project = self.project_manager.create_project(name)
        return f"**✅ Erstellt:** {project['name']}"

    except Exception as e:
        print(f"Error creating project: {e}")
        return f"**❌ Fehler:** {e}"
```

**Nachher:**
```python
from infrastructure.error_handler import handle_errors
from infrastructure.logger import get_logger
from domain.exceptions import ProjectCreationError

logger = get_logger(__name__)

@handle_errors("Konnte Projekt nicht erstellen")
def create_project(self, name):
    logger.info(f"Creating project: {name}")

    if not name:
        raise ProjectCreationError("Projektname darf nicht leer sein")

    project = self.project_manager.create_project(name)
    logger.info(f"✓ Project created: {project['name']}")

    return f"**✅ Erstellt:** {project['name']}"
```

**Vorteile:**
- Automatisches Exception Handling
- Strukturiertes Logging
- Konsistente Error-Messages
- Stacktraces in Log-Datei
- Keine duplizierte Error-Handling-Logik

---

## 📊 Log-Level ändern

Während der Entwicklung kannst du den Log-Level dynamisch ändern:

```python
from infrastructure.logger import PipelineLogger
import logging

# DEBUG-Level aktivieren (sehr detailliert)
PipelineLogger.set_level(logging.DEBUG)

# INFO-Level (Standard)
PipelineLogger.set_level(logging.INFO)

# WARNING-Level (nur Warnungen und Fehler)
PipelineLogger.set_level(logging.WARNING)
```

---

## 🎯 Beispiele aus der Codebase

### Gutes Beispiel: project_panel.py

```python
@handle_errors("Konnte Projekt nicht erstellen")
def _create_project(self, name: str):
    logger.info(f"Creating new project: {name}")

    name = (name or "").strip()
    if not name:
        logger.warning("Project creation attempted with empty name")
        return (
            "**❌ Fehler:** Bitte einen Projektnamen eingeben.",
            self._project_overview(None),
            "{}",
            gr.update()
        )

    project = self.project_manager.create_project(name)
    logger.info(f"✓ Project created: {project['name']} ({project['slug']})")

    return (
        f"**✅ Erstellt:** {project['name']} (`{project['slug']}`)",
        self._project_overview(project),
        self._project_json(project),
        gr.update(value=project["slug"])
    )
```

### Gutes Beispiel: comfy_api.py

```python
def load_workflow(self, workflow_path: str) -> Dict[str, Any]:
    logger.debug(f"Loading workflow from {workflow_path}")

    if not os.path.exists(workflow_path):
        raise WorkflowLoadError(f"Workflow nicht gefunden: {workflow_path}")

    try:
        with open(workflow_path, 'r') as f:
            workflow = json.load(f)
        logger.debug(f"✓ Workflow loaded: {len(workflow)} nodes")
        return workflow
    except json.JSONDecodeError as e:
        raise WorkflowLoadError(f"Ungültiges Workflow-JSON: {e}")
```

---

## ❓ FAQ

**Q: Wann soll ich welchen Log-Level nutzen?**

- `DEBUG`: Detaillierte Informationen für Debugging (z.B. "Loading workflow node 5/20")
- `INFO`: Wichtige Meilensteine (z.B. "✓ Generation complete: 20 images")
- `WARNING`: Ungewöhnlich, aber nicht kritisch (z.B. "No variants found for shot")
- `ERROR`: Kritische Fehler (z.B. "Failed to connect to ComfyUI")

**Q: Muss ich überall `@handle_errors` nutzen?**

Nicht unbedingt. Nutze es hauptsächlich in:
- Addon-Callback-Funktionen (die mit Gradio UI verbunden sind)
- Top-Level Service-Methoden

Interne Hilfsfunktionen können einfach Exceptions werfen - sie werden vom Decorator gefangen.

**Q: Kann ich eigene Exceptions hinzufügen?**

Ja! Füge sie in `domain/exceptions.py` hinzu und leite sie von der passenden Base-Klasse ab.

**Q: Wo finde ich die Log-Dateien?**

`cindergrace_gui/logs/pipeline.log` (und pipeline.log.1, .2, ... für rotierte Logs)

---

**Last Updated:** 2025-12-10
**Version:** 1.1 (mit Pydantic Validation)
