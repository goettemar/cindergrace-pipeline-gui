# Storyboard LLM Generator

**Tab:** 🤖 AI Storyboard
**Version:** 1.0
**Status:** Neu

## Beschreibung

Der Storyboard LLM Generator ermöglicht die automatische Erstellung von Storyboards aus natürlicher Sprache. Statt jeden Shot manuell zu definieren, beschreibst du einfach deine Video-Idee und ein LLM (Large Language Model) generiert ein vollständiges Storyboard-JSON.

## Voraussetzungen

1. **OpenRouter API Key** - Kostenlos registrieren auf [openrouter.ai](https://openrouter.ai/keys)
2. **Mindestens ein LLM-Modell konfiguriert** in Settings

## Setup

### 1. API Key hinterlegen

1. Öffne **⚙️ Settings**
2. Scrolle zum Abschnitt **🤖 OpenRouter (LLM)**
3. Trage deinen API Key ein (Format: `sk-or-v1-...`)
4. Klicke **💾 Save OpenRouter Settings**

### 2. Modelle konfigurieren

Standardmäßig sind 3 Modelle vorkonfiguriert:

| Modell | Beschreibung | Kosten* |
|--------|--------------|---------|
| `anthropic/claude-sonnet-4` | Beste Qualität für strukturiertes JSON | ~$3/1M tokens |
| `openai/gpt-4o` | Schnell und zuverlässig | ~$5/1M tokens |
| `meta-llama/llama-3.1-70b-instruct` | Open Source Alternative | ~$0.90/1M tokens |

*Kosten Stand Dezember 2024, ändern sich regelmäßig

Du kannst die Modelle in Settings anpassen. Weitere empfohlene Modelle:
- `openai/gpt-4o-mini` - Sehr günstig für Tests
- `google/gemini-pro-1.5` - Google Alternative
- `mistralai/mistral-large` - Europäische Alternative

### 3. Verbindung testen

Klicke **🧪 Test Connection** in Settings um die Verbindung zu prüfen.

## Verwendung

### Schritt 1: Idee eingeben

Beschreibe deine Video-Idee im Textfeld. Je detaillierter, desto besser:

**Einfach:**
```
Ein Werbespot für ein Café mit 3 Szenen
```

**Detailliert (empfohlen):**
```
Ein kurzer Werbespot für ein gemütliches Café in einer europäischen Altstadt.

Szene 1: Außenansicht des Cafés bei Sonnenaufgang, warmes goldenes Licht,
         leichter Morgennebel auf der Kopfsteinpflasterstraße

Szene 2: Nahaufnahme wie ein Barista Milch in einen Espresso gießt,
         Latte Art entsteht, professionelle Kaffeemaschine im Hintergrund

Szene 3: Zufriedener Kunde sitzt am Fenster mit Kaffeetasse in der Hand,
         sanftes Morgenlicht strömt durch das Glas
```

### Schritt 2: Modell wählen

Wähle ein LLM aus dem Dropdown. Für beste Ergebnisse:
- **Claude Sonnet 4** oder **GPT-4o** für komplexe Storyboards
- **GPT-4o-mini** oder **Llama 3.1** für schnelle Tests

### Schritt 3: Generieren

Klicke **✨ Storyboard generieren**. Die Generierung dauert 10-30 Sekunden.

### Schritt 4: Prüfen & Bearbeiten

Das generierte Storyboard erscheint rechts:
- **Shots Tab:** Übersicht aller Szenen
- **JSON Editor Tab:** Volle JSON-Ansicht (editierbar)

Die Validierung zeigt Fehler (rot) und Hinweise (gelb).

### Schritt 5: Importieren

Wenn das Storyboard valide ist, klicke **📥 In Projekt importieren**.
Das Storyboard wird unter `<Projekt>/storyboards/` gespeichert.

## Storyboard-Schema

Das generierte JSON folgt diesem Schema:

```json
{
  "project": "Projektname",
  "description": "Kurze Beschreibung",
  "version": "2.2",
  "shots": [
    {
      "shot_id": "001",
      "filename_base": "cafe-exterior-sunrise",
      "description": "Außenansicht bei Sonnenaufgang",
      "prompt": "cozy corner cafe exterior at sunrise, warm golden light...",
      "negative_prompt": "blurry, low quality, distorted",
      "width": 1024,
      "height": 576,
      "duration": 3.0,
      "presets": {
        "style": "cinematic",
        "lighting": "golden_hour",
        "mood": "peaceful",
        "camera": "slow_zoom_in"
      }
    }
  ],
  "video_settings": {
    "default_fps": 24,
    "max_duration": 3.0
  }
}
```

### Felder erklärt

| Feld | Beschreibung |
|------|--------------|
| `shot_id` | Eindeutige ID ("001", "002", ...) |
| `filename_base` | Dateiname-Basis (lowercase, keine Leerzeichen) |
| `description` | Kurze deutsche Beschreibung der Szene |
| `prompt` | Detaillierter englischer Prompt für Bildgenerierung |
| `negative_prompt` | Was vermieden werden soll |
| `width/height` | Auflösung (Standard: 1024x576 für 16:9) |
| `duration` | Dauer in Sekunden (Standard: 3.0) |
| `presets` | Stil-Voreinstellungen |

### Preset-Optionen

**style:** `cinematic`, `photorealistic`, `anime`, `artistic`, `documentary`

**lighting:** `natural`, `studio`, `dramatic`, `soft`, `golden_hour`, `neon`, `low_key`

**mood:** `peaceful`, `dramatic`, `mysterious`, `joyful`, `melancholic`, `tense`, `romantic`

**camera:** `static`, `pan_left`, `pan_right`, `zoom_in`, `zoom_out`, `tracking`, `dolly`

## Tipps

### Bessere Ergebnisse

1. **Sei spezifisch:** Beschreibe Lichtstimmung, Kamerawinkel, Details
2. **Struktur hilft:** Nummeriere deine Szenen (Szene 1, Szene 2, ...)
3. **Englische Prompts:** LLMs generieren bessere englische Bildprompts

### Kosten minimieren

- Nutze `gpt-4o-mini` für Entwürfe (~$0.15/1M tokens)
- Wechsle zu `claude-sonnet-4` nur für finale Version
- Ein Storyboard = ~500-1000 tokens = ~$0.003 pro Generation

### Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| "API Key nicht konfiguriert" | Key in Settings eintragen |
| "API Key ungültig" | Key auf openrouter.ai prüfen |
| Validierungsfehler | JSON im Editor manuell korrigieren |
| Leere Shots | Mehr Details in Idee-Beschreibung geben |

## Workflow-Integration

Nach dem Import kann das Storyboard direkt verwendet werden:

1. **Storyboard Editor:** Shots anpassen, Presets ändern
2. **Keyframe Generator:** Bilder aus Prompts generieren
3. **Keyframe Selector:** Beste Varianten auswählen
4. **Video Generator:** Videos aus Keyframes erstellen

## Technische Details

### Dateien

| Datei | Beschreibung |
|-------|--------------|
| `addons/storyboard_llm_generator.py` | Haupt-Addon |
| `services/storyboard_llm_service.py` | Service-Layer |
| `infrastructure/openrouter_client.py` | API-Client |
| `domain/validators.py` | Storyboard-Validierung |
| `data/templates/storyboard_prompt_template.txt` | LLM-Prompt |

### API

Der OpenRouter-Client nutzt die Standard Chat Completions API:
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Timeout: 120 Sekunden
- Temperature: 0.7 (Standard)

### Sicherheit

- API-Keys werden mit Fernet verschlüsselt in SQLite gespeichert
- Machine-spezifische Schlüsselableitung (PBKDF2, 100k Iterationen)
- Keys sind nicht auf andere Rechner übertragbar
