# RunPod Integration - Implementierungsplan

**Erstellt:** 2024-12-26
**Status:** ✅ Complete
**Ziel:** CINDERGRACE GUI mit RunPod ComfyUI Backend verbinden

---

## Übersicht

### Problem
- Output-Dateien liegen auf RunPod Server (`/workspace/ComfyUI/output/`)
- CINDERGRACE erwartet Dateien lokal (`ComfyUI/output/` oder konfigurierter Pfad)
- Workflows wie Last Frame, First Frame, Move to Project benötigen lokale Dateien

### Lösung
1. Nach jedem ComfyUI Job: Output-Dateien via API herunterladen
2. Lokal im erwarteten Pfad speichern
3. Rest des Workflows funktioniert unverändert

---

## Implementierungsreihenfolge

### Phase 1: Settings Panel Anpassung ✅
**Dateien:** `addons/settings_panel.py`, `infrastructure/config_manager.py`

- [x] 1.1 Connection Mode Dropdown hinzufügen: `Local URL` | `RunPod`
- [x] 1.2 Bei RunPod: Nur Pod-ID Eingabefeld (statt voller URL)
- [x] 1.3 URL automatisch bauen: `https://{pod_id}-8188.proxy.runpod.net`
- [x] 1.4 Settings speichern: `connection_mode`, `runpod_pod_id`
- [x] 1.5 Test Connection für beide Modi

### Phase 2: ComfyAPI Client Erweiterung ✅
**Dateien:** `infrastructure/comfy_api/client.py`

- [x] 2.1 `get_history(prompt_id)` Methode (bereits vorhanden)
- [x] 2.2 `download_file(filename, local_path, subfolder, file_type)` Methode hinzugefügt
- [x] 2.3 `download_job_outputs(prompt_id, local_dir)` Convenience-Methode hinzugefügt
- [x] 2.4 `upload_image(local_path, subfolder)` für Keyframe-Upload hinzugefügt

### Phase 3: Output Download Integration ✅
**Dateien:** `services/keyframe_service.py`, `services/video/video_generation_service.py`

- [x] 3.1 Nach erfolgreicher Generation: Outputs herunterladen (via `download_job_outputs`)
- [x] 3.2 Dateien in korrekten lokalen Pfad speichern (output_dir für keyframes, comfy_output für video)
- [x] 3.3 Bestehende Logik (move, last_frame) arbeitet mit lokalen Dateien weiter

### Phase 4: Test Panel Konsolidierung ✅
**Dateien:** `addons/test_comfy_flux.py`, `addons/settings_panel.py`

- [x] 4.1 Test-Konfiguration nur in Settings (kein Duplicate)
- [x] 4.2 Tests nutzen Settings-Konfiguration (URL aus active backend)
- [x] 4.3 Connection Test in Settings (bereits vorhanden)
- [x] 4.4 Image Generation Tests im Test Panel (vereinfacht)

### Phase 5: Input File Upload (für RunPod) ✅
**Dateien:** `infrastructure/comfy_api/client.py`, `services/video/video_generation_service.py`

- [x] 5.1 `upload_image(local_path)` Methode für Keyframe Upload (Phase 2)
- [x] 5.2 Automatischer Upload vor Job-Start wenn RunPod Modus
- [x] 5.3 Uploaded Filename in Workflow eintragen (automatisch via LoadImage nodes)

---

## API Endpoints (ComfyUI)

### History abrufen
```
GET /history/{prompt_id}
Response: {
  "{prompt_id}": {
    "outputs": {
      "node_id": {
        "images": [{"filename": "xxx.png", "subfolder": "", "type": "output"}]
      }
    }
  }
}
```

### Datei herunterladen
```
GET /view?filename={filename}&subfolder={subfolder}&type={type}
Response: Binary image/video data
```

### Datei hochladen
```
POST /upload/image
Body: multipart/form-data with file
Response: {"name": "uploaded_filename.png", ...}
```

---

## Settings Schema (Erweiterung)

```json
{
  "comfyui": {
    "connection_mode": "local",  // "local" | "runpod"
    "url": "http://127.0.0.1:8188",  // für local mode
    "runpod_pod_id": "",  // für runpod mode
    "output_dir": "output"
  }
}
```

---

## Offene Fragen

1. ✅ URL-Format für RunPod: `https://{pod_id}-8188.proxy.runpod.net`
2. ⏳ Sollen Downloads in ComfyUI/output oder direkt ins Projekt?
   - Vorschlag: Wie lokal - erst in output, dann move_to_project
3. ⏳ Upload-Pfad für Keyframes auf RunPod?
   - ComfyUI `/upload/image` speichert in `input/` Ordner

---

## Backlog Items (später)

- [ ] #031: OpenRouter End-to-End Test im Test Panel
- [ ] #032: TTS End-to-End Test im Test Panel

---

## Fortschritt

| Phase | Status | Notizen |
|-------|--------|---------|
| 1. Settings Panel | ✅ Done | Connection Mode, Pod-ID Input, URL Auto-Build |
| 2. ComfyAPI Client | ✅ Done | download_file, download_job_outputs, upload_image |
| 3. Output Download | ✅ Done | Keyframe + Video Service Integration |
| 4. Test Konsolidierung | ✅ Done | URL aus Settings, Connection Test in Settings |
| 5. Input Upload | ✅ Done | Auto-Upload vor Job, Filename in Workflow |
