# Review - CINDERGRACE GUI

## Kontext und Scope
- Review basiert auf statischer Analyse des Repos, ohne Ausfuehrung.
- Fokus: Sicherheitsprobleme, Coding-Qualitaet, Architektur, plus Ideen zur Verbesserung.
- Einbezogen: Core-App (addons/services/infrastructure/domain), Updater, Model-Downloader, TTS, Comfy-API-Client, System-/Video-/Audio-Utilities. Externe Tools in `tools/sd-scripts` nur als Risiko-Note.

## Findings: Sicherheit

### Kritisch
1) Path Traversal bei Update/Rollback
- `tarfile.extractall()` wird ohne Pfadvalidierung verwendet. Ein manipulierter Tarball kann Dateien ausserhalb des App-Verzeichnisses schreiben/ueberschreiben.
- Stellen: `infrastructure/updater_service.py` (rollback + apply_update).

### Hoch
2) Keine Integritaets- oder Signaturpruefung fuer Updates
- Updates werden von GitHub geladen und direkt installiert. Es gibt keine Hash-/Signaturverifikation.
- Stelle: `infrastructure/updater_service.py`.

### Mittel
3) Pfad-Traversal im Model-Downloader moeglich
- Zielpfad baut direkt auf `filename` aus Workflow/Model-Listen. Ohne Normalisierung/`basename()` koennen `../` oder absolute Pfade ausserhalb des Model-Roots landen.
- Stellen: `services/model_manager/model_downloader.py` (get_target_path, add_to_queue, _download_task).

4) Shell-Injection Risiko bei `os.system` mit Benutzerpfaden
- `os.system(f'xdg-open "{path}"')` verwendet direkte String-Interpolation. Ein Pfad mit `"` oder Shell-Metazeichen kann Befehle einschleusen.
- Stellen: `addons/character_trainer.py`, `addons/dataset_generator.py`, `addons/keyframe_generator.py`, `addons/video_generator.py`, `addons/firstlast_video.py`.

### Niedrig
5) API-Key im Query-String (Google TTS)
- API Key wird in der URL uebergeben; kann in Logs/Proxies auftauchen.
- Stelle: `services/tts_service.py`.

6) Sensible Inhalte im Log
- LLM-Idee/Antwort werden geloggt; kann proprietaere oder personenbezogene Inhalte im Log persistieren.
- Stelle: `infrastructure/openrouter_client.py`.

7) Schluesselableitung aus Maschinen-ID
- Verschluesselung basiert auf Salt + Maschinen-ID. Bietet Schutz vor Kopieren, aber kein Nutzergeheimnis; bei Zugriff auf DB + Host-Infos ist Entschluesselung moeglich.
- Stelle: `infrastructure/settings_store.py`.

### Kontext-Risiko (Externe Tools)
8) `tools/sd-scripts` enthaelt `eval`/Shell-Calls
- Wird extern genutzt; potenzielle Angriffs- oder Supply-Chain-Risiken, falls untrusted Inputs oder veraltete Versionen.
- Stellen: `tools/sd-scripts/...`.

## Findings: Coding-Qualitaet

### Staerken
- Klare Schichtung (Domain/Services/Infrastructure/Addons) und solide Logging-Basis.
- Pydantic-Validierung fuer viele Eingaben (z.B. Settings, Video, Project).
- Testsuite vorhanden (laut README 253 Tests, Coverage 31%).
- Gute Utility-Aufteilung fuer wiederverwendbare UI-Komponenten.

### Risiken / Schwachstellen
- Grosse UI-Module mit gemischter UI- und Business-Logik erschweren Wartung und Tests.
  - Beispiele: `addons/storyboard_editor.py`, `addons/lipsync_addon.py`, `addons/video_generator.py`.
- Wiederholte UI-Patterns (Tab-Load/Refresh/Status) an vielen Stellen statt zentraler Abstraktion.
- Hintergrund-Threads fuer Downloads ohne zentralen Task-Controller (Monitoring/Cancel/Errors verteilt).
  - `addons/model_manager.py`, `services/model_manager/model_downloader.py`.
- Teilweise direkte Dateisystem-Operationen aus UI heraus (kopieren, loeschen, open), was Review und Testing erschwert.

## Findings: Architektur

### Positiv
- Saubere Trennung: UI (addons), Business-Services (services), Infrastruktur (infrastructure), Domain/Validatoren (domain).
- SQLite-basierte Settings und Projektverwaltung geben stabile Persistenz.

### Risiken
- Starke Kopplung UI <-> Services/Stores (Direktinstanzen statt Dependency Injection). Erschwert Tests/Swaps.
- Mehrere Singletons/Global-States (SettingsStore, ConfigManager) erhoehen Seiteneffekte bei parallelen Aktionen.
- Remote-Backend ist konfigurierbar, aber kein Auth/TLS-Handling im Client vorgesehen.
  - `infrastructure/config_manager.py`, `infrastructure/comfy_api/client.py`.

## Ideen zur Verbesserung (Prioritaet grob)

### P0 / P1 (Security)
- Safe-Tar-Extract (Pfadvalidierung; kein `..`/absolut) in `infrastructure/updater_service.py`.
- Signatur/Hash fuer Updates (z.B. SHA256 + Release-Asset, optional Signatur).
- Pfadnormalisierung fuer Downloader-Zielpfade (nur `basename`, Blocklist fuer Separatoren, optional allowlist fuer Endungen).
- `os.system` ersetzen durch `subprocess.run(["xdg-open", path])` ohne Shell.

### P1 / P2 (Privacy/Compliance)
- Log-Redaktion fuer LLM Inputs/Outputs und API Keys (z.B. truncation + opt-out Flag).
- Google TTS: Key in Header statt Query (sofern API dies erlaubt), oder least-privilege-Key.

### P2 (Qualitaet/Architektur)
- Langlaufende Tasks in zentralen Job-Manager (Status, Cancel, Retry, Log-Aggregation).
- UI entkoppeln: Services liefern reine Daten; UI macht Rendering. Tests werden einfacher.
- Gemeinsame UI-Patterns in BaseAddons/Helpers konsolidieren.
- Security-Guidelines fuer externe Tools (`tools/sd-scripts`): Versioning, pinning, minimaler Wrapper.

## Threat Model (Subsysteme)

### Updater (Release Download/Apply/Rollback)
- Assets/Trust: Release-Server (GitHub), lokale Installation, Backups.
- Entry Points: `download_update`, `apply_update`, `rollback`.
- Bedrohungen:
  - Supply-Chain (kompromittierter Release/Tarball).
  - Path Traversal im Tarball.
  - Downgrade/Replay (alte Versionen).
- Impact: Vollstaendige Code-Ausfuehrung im App-Kontext.
- Hauptrisiko: fehlende Signatur/Checksum + unsicheres Extract.

### Model-Downloader (Civitai/HF)
- Assets/Trust: Model-Ordner, Netzwerk, API-Tokens.
- Entry Points: Download-URL + Filename aus Workflows/Listen.
- Bedrohungen:
  - Pfad-Traversal ueber Filename.
  - Download von falschen/beschaedigten Modellen (Integritaet).
  - Token-Leak (Logs/Headers).
- Impact: Ueberschreiben von Dateien, untrusted Models.

### Community-Workflows (zukuenftig)
- Assets/Trust: Workflow-Dateien, lokale Pfade, Model-Auswahl.
- Entry Points: Import von JSON/Model-Referenzen.
- Bedrohungen:
  - Pfad-Referenzen auf sensitive Dateien.
  - Ueberlange/kaputte JSONs fuer DoS.
  - Workflow-Nodes mit externer Ausfuehrung (falls ComfyUI-Nodes Shell nutzen).
- Impact: Datenabfluss/DoS/Fehlkonfiguration.

### TTS/LLM Dienste
- Assets/Trust: API Keys, generierte Inhalte.
- Entry Points: HTTP Requests, Logging.
- Bedrohungen:
  - Key Leakage in URLs oder Logs.
  - Sensitive Inhalte in Logs.
- Impact: Kosten/Privacy.

## Hardening-Checkliste (priorisiert)

### P0
- Safe-Tar-Extract: Abbruch bei `..` oder absoluten Pfaden.
- Signatur/Hash fuer Updates (z.B. SHA256 + Release-Asset, optional Signatur).
- Downloader-Pfadnormalisierung (basename + allowlist fuer Endungen).

### P1
- `os.system` durch `subprocess.run([...])` ersetzen.
- Log-Redaktion fuer Secrets/LLM-Outputs (truncate, opt-in debug).
- TLS/Host-Validation fuer Remote-ComfyUI (mind. Hinweis/Warning).

### P2
- Update-Rollback mit Verify-Check (Dateiliste/Checksum).
- Modell-Downloads mit Hash-Check (falls Provider Hash liefert).
- Rate-Limits/Timeouts zentralisieren (Netzwerk-Client Wrapper).

## Policy-Vorschlag: Externe Tools & Community-Workflows

### Externe Tools (`tools/sd-scripts`)
- Version-Pinning im Repo (Commit-Hash dokumentieren).
- Periodischer Security-Review (z.B. alle 3-6 Monate).
- Wrapper-Script mit eingeschraenkten Pfaden/Inputs.
- Keine direkten User-Inputs an Shell/Eval weiterreichen.

### Community-Workflows
- Import nur aus vertrauenswuerdigen Quellen (allowlist).
- JSON-Schema-Validierung + Groessenlimits.
- Pfad-Referenzen normalisieren und auf Workspace begrenzen.
- Optionaler "Quarantine"-Status fuer neue Workflows.

## Security-Plan (Roadmap)

### Ziel
- Risiko fuer Supply-Chain und Pfad-Manipulationen minimieren.
- Secrets/Privacy besser schuetzen.
- Betriebssicherheit fuer Updates und Downloads erhoehen.

### Scope
- In: Updater, Model-Downloader, Workflow-Import, LLM/TTS, Shell-Opener.
- Out: Kern-ML-Modelle selbst, externe ComfyUI-Node-Implementierungen.

### Milestones
1) **M1: Kritische Hardening-Massnahmen (P0)**\n
   - Safe-Tar-Extract + Hash/Signatur fuer Updates.\n
   - Downloader-Pfade normalisieren.\n
   - Shell-Calls absichern (no shell).\n
2) **M2: Privacy & Logging (P1)**\n
   - Log-Redaktion fuer Secrets/LLM-Outputs.\n
   - TTS-API-Key aus Query entfernen (falls moeglich).\n
3) **M3: Community-Workflows (P2)**\n
   - JSON-Schema-Validierung, Groessenlimits.\n
   - Allowlist/Quarantine-Flow.\n
4) **M4: Governance & Audits (laufend)**\n
   - Externe Tools pinnen, regelmaessige Reviews.\n

### Risiken
- Aufwand fuer Signaturen/Release-Prozess.\n
- False Positives bei Pfad-Checks.\n
- User-Akzeptanz bei eingeschraenkten Imports.\n

## Jira-taugliche Tasks (Epics / Stories)

### Epic: Updater Hardening
- **Story:** Safe Tar Extraction\n
  - AC: Tarball mit `../` oder absolutem Pfad wird abgelehnt.\n
  - AC: Update/rollback funktioniert weiterhin mit gueltigem Tarball.\n
- **Story:** Release Hash/Signaturpruefung\n
  - AC: Update wird nur installiert, wenn Hash/Signatur passt.\n
  - AC: Fehlermeldung bei fehlender/verfaelschter Signatur.\n
  - AC: Release enthaelt `update_<version>.tar.gz`, `update_<version>.sha256`, `update_<version>.sig`.\n
  - AC: Signaturverfahren dokumentiert (z.B. minisign oder GPG), oeffentlicher Key wird gepinnt.\n

### Epic: Model-Downloader Sicherheit
- **Story:** Pfadnormalisierung fuer Downloads\n
  - AC: `filename` wird auf basename/allowlist begrenzt.\n
  - AC: Kein Schreiben ausserhalb `models_root`.\n
- **Story:** Optionaler Hash-Check\n
  - AC: Wenn Provider Hash liefert (API/Header), wird dieser validiert.\n
  - AC: Fehlende Hashes werden geloggt (Info), aber Download bleibt moeglich.\n

### Epic: Shell/Command Safety
- **Story:** `os.system` entfernen\n
  - AC: `xdg-open` wird via `subprocess.run([...])` gestartet.\n
  - AC: Pfade mit Sonderzeichen funktionieren.\n

### Epic: Privacy & Logging
- **Story:** Log-Redaktion fuer Secrets/LLM\n
  - AC: API-Keys werden nie im Log ausgegeben.\n
  - AC: LLM-Outputs sind per Default gekuerzt (z.B. 500 Zeichen) oder deaktiviert.\n
  - AC: Volles Debug-Logging nur per explizitem Opt-in.\n
- **Story:** TTS-Key nicht in Query\n
  - AC: OAuth/Bearer Token wird bevorzugt, falls konfiguriert.\n
  - AC: Falls API-Key im Query bleibt, wird URL niemals geloggt.\n

### Epic: Community-Workflow Governance
- **Story:** JSON-Schema + Groessenlimits\n
  - AC: Workflows > 2 MB (konfigurierbar) werden abgelehnt.\n
  - AC: Schema-Validierung blockiert ungueltige Workflows.\n
- **Story:** Allowlist/Quarantine\n
  - AC: Neue Workflows landen in Quarantaene.\n
  - AC: Explizite Freigabe noetig fuer Ausfuehrung.\n

### Epic: Externe Tools (sd-scripts)
- **Story:** Version Pinning & Review\n
  - AC: Commit-Hash dokumentiert und geprueft.\n
  - AC: Review-Intervall definiert (z.B. 6 Monate).\n

## Signatur/Release-Workflow Vorschlaege

### Option A: minisign (einfach, schnell)
- Maintainer generiert minisign Keypair (offline speichern).
- Release-Asset: `update_<version>.tar.gz` + `update_<version>.tar.gz.minisig`.
- App pinned den Public Key in Config/Code.
- Verifikation: `minisign -V -m <tar> -p <pubkey>`.

### Option B: GPG
- Release-Asset: `update_<version>.tar.gz` + `update_<version>.tar.gz.asc`.
- App pinned den Public Key (Fingerprint) und verifiziert lokal.
- Vorteil: weit verbreitet; Nachteil: schwerere UX.

### Option C: Sigstore (cosign)
- Signatur in Rekor Log; App verifiziert gegen pinned Fulcio/OIDC-Policy.
- Vorteil: moderne Supply-Chain, Nachteil: mehr Infrastruktur.

### Empfehlung (kurz)
- Start mit minisign (geringer Aufwand, klare UX), spaeter Optional Sigstore.

## Release-Checkliste (Kurzform)
- [ ] `VERSION` aktualisiert.\n
- [ ] Changelog/Release Notes gepflegt.\n
- [ ] `update_<version>.tar.gz` erstellt.\n
- [ ] SHA256 berechnet und veroeffentlicht.\n
- [ ] Signatur erstellt (minisign/GPG).\n
- [ ] Smoke-Test (Start, Update, Rollback) dokumentiert.\n

## Weitere Ideen / Optimierungsbedarf (Allgemein)

### Architektur/Qualitaet
- Gemeinsame UI-Patterns konsolidieren (Tab-Load/Status/Refresh).\n
- Zentraler Job-Manager fuer lange Tasks (Download/Render/Training).\n
- Service-APIs so gestalten, dass UI keine Dateisystem-Details braucht.\n

### Betrieb/Observability
- Einheitliche Struktur fuer Logs pro Feature (z.B. `component=...`).\n
- Ein optionales Debug-Panel, das nur technische Details zeigt.\n

### Sicherheit/Resilienz
- Feature-Flag fuer unsichere Operationen (z.B. externes Workflow-Import).\n
- Strengere Pfadvalidierung an allen Eingaben, die in FS schreiben.\n
- Optionaler Read-Only Modus fuer Workspace-Daten.\n

## Alpha-Checkliste (Kurz & Praktisch)

### Stabilitaet
- [ ] App startet reproduzierbar (ohne manuelle Schritte).\n
- [ ] Setup-Wizard laeuft komplett durch.\n
- [ ] Projekt anlegen, laden, wechseln funktioniert.\n
- [ ] Keyframe-Generation / Selection / Video-Generation jeweils mindestens 1x End-to-End.\n
- [ ] Fehlerfaelle zeigen klare Fehlermeldungen (kein Crash).\n

### UX & Onboarding
- [ ] Erststart-Flow erklaert naechste Schritte.\n
- [ ] Fehlende Abhaengigkeiten (ComfyUI/ffmpeg) werden gut kommuniziert.\n
- [ ] Wichtige Pfade sichtbar (Project/Output).\n

### Sicherheit (Minimal)
- [ ] Update-Tarball ist sicher extrahierbar (Path-Check).\n
- [ ] Keine `os.system`-Aufrufe im UI-Pfad.\n
- [ ] Keine API-Keys im Log.\n

### Release-Readiness
- [ ] Versionsnummer gesetzt.\n
- [ ] Kurze Alpha-Release-Notes (1-2 Seiten) mit Known Issues.\n
- [ ] Feedback-Kanal klar (Discord/GitHub/Email).\n

## Alpha-Testfaelle pro Tab (Vorschlag)

### Setup Wizard
- [ ] Disclaimer akzeptieren -> Next aktiv.\n
- [ ] System Check (OK/Fehlerfall) wird angezeigt.\n
- [ ] ComfyUI installed/not installed Pfad fuehrt korrekt weiter.\n
- [ ] Finish Setup speichert Werte und setzt Setup-Flag.\n

### Project
- [ ] Neues Projekt erstellen.\n
- [ ] Projekt wechseln (active Projekt aendert Statuszeile).\n
- [ ] Storyboard-Default setzen/wechseln.\n

### Keyframe Generator
- [ ] Storyboard laden + Workflow waehlen.\n
- [ ] Keyframes generieren (mind. 1 Shot).\n
- [ ] Output-Gallery zeigt Ergebnisse + Pfade.\n

### Keyframe Selector
- [ ] Varianten pro Shot laden.\n
- [ ] Auswahl speichern/exportieren.\n
- [ ] Fehlermeldung bei fehlendem Projekt/Storyboard.\n

### Video Generator
- [ ] Selections laden + Workflow.\n
- [ ] Plan erstellen + Starten.\n
- [ ] Ergebnis-Video erscheint + Pfad.\n

### Storyboard Editor / LLM Generator
- [ ] JSON laden/bearbeiten, Validierung funktioniert.\n
- [ ] LLM Draft erzeugen (wenn API-Key vorhanden).\n
- [ ] Fehlermeldung bei invalidem JSON.\n

### Model Manager
- [ ] Scan zeigt Modelle.\n
- [ ] Missing Models Detection.\n
- [ ] Download Queue Start/Stop.\n

### Lipsync Studio
- [ ] Audio laden, Analyse/Segmentation.\n
- [ ] Generate einzelnes Segment.\n
- [ ] Fehlerfall bei fehlendem Audio/Projekt.\n

### Settings
- [ ] ComfyUI URL/Root speichern + validieren.\n
- [ ] Backend-Switch (local/runpod) + persistiert.\n
- [ ] Setup Reset Button.\n

## Aufgabenaufteilung (Claude vs. Codex)

### Claude (Stark in)
- Produkt-/UX-Review, Text/Copy, Release Notes.\n
- Strukturiertes Feedback aus Alpha-Tester-Sicht.\n
- Risiko-/Bedrohungsmodell und Policies.\n

### Codex (Stark in)
- Code-Analyse, konkrete Code-Pfade, Refactoring-Ideen.\n
- Technische Hardening-Checks (Updater, Downloader, Pfade).\n
- Diff-basierte Umsetzungsvorschlaege + Testplaene.\n

### Zusammenarbeit (Empfehlung)
- Claude liefert Anforderungen/UX-Feedback; Codex setzt technische Umsetzung/Review.\n
- Gemeinsame Liste: Alpha-Issues priorisieren (P0/P1/P2).\n

## Offene Fragen / Klaerungsbedarf
- Wie soll Community-Workflow-Import abgesichert werden (Signaturen, Reviews, Trusted Sources)?
- Soll der Updater in Prod zwingend signierte Releases nutzen?
- Wird Remote-ComfyUI ohne Auth betrieben? Falls ja: VPN/Reverse Proxy geplant?

## Android-Spiel (Waldweg) - Arbeitsname
- Aktueller Arbeitsname: **Der Waldpfad**.\n
- Hinweis: es existiert ein Buch mit aehnlichem Titel (kein App-Konflikt erkannt).\n
- Empfehlung: vor Release finalen Store-Check machen und ggf. Namensvariante bereithalten.\n

## Kurzfazit
Die Basis ist solide (Schichtung, Validierung, Logging), aber Update-Pipeline und Download-/Shell-Pfade sind die groessten Sicherheitsrisiken. Eine Handvoll gezielter Hardening-Massnahmen wuerden das System deutlich robuster machen.
