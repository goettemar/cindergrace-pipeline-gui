# Codecov Integration Setup

Diese Anleitung führt Sie durch die Einrichtung von Codecov für dieses Projekt.

## ✅ Bereits erledigt

Die technische Integration ist bereits vorbereitet:

- ✅ CI/CD Pipeline erstellt (`.github/workflows/ci.yml`)
- ✅ Coverage-Reports werden generiert (`coverage.xml`)
- ✅ Codecov Upload-Action konfiguriert
- ✅ README Badges hinzugefügt

## 🚀 Was Sie noch tun müssen

### Schritt 1: Codecov-Account erstellen (5 Minuten)

1. **Gehen Sie zu:** https://codecov.io/
2. **Klicken Sie auf:** "Sign up with GitHub"
3. **Autorisieren Sie:** Codecov den Zugriff auf Ihre Repositories
4. **Wählen Sie aus:** Welche Repositories Codecov sehen darf

### Schritt 2: Repository verbinden (2 Minuten)

1. **Im Codecov Dashboard:** Klicken Sie auf "Add new repository"
2. **Suchen Sie:** "cindergrace-pipeline-gui" (oder Ihr Repo-Name)
3. **Klicken Sie:** "Set up repo"
4. **Optional:** Kopieren Sie das Upload-Token (wird automatisch von GitHub Actions verwendet)

### Schritt 3: Ersten CI-Run triggern (1 Minute)

```bash
# Commit und Push Ihrer Änderungen
git add .
git commit -m "feat: add comprehensive test suite and codecov integration"
git push origin main
```

Die GitHub Action läuft automatisch und sendet Coverage-Daten zu Codecov.

### Schritt 4: Badges verifizieren (1 Minute)

Nach dem ersten erfolgreichen CI-Run:

1. **Gehen Sie zu:** Codecov Dashboard → Ihr Repository
2. **Klicken Sie:** Settings → Badge
3. **Kopieren Sie:** Den Badge-Code
4. **Vergleichen Sie:** Mit dem bereits im README vorhandenen Badge

Der Badge im README sollte automatisch funktionieren:
```markdown
[![codecov](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/USERNAME/REPO)
```

Ersetzen Sie `USERNAME/REPO` mit Ihrem tatsächlichen GitHub Username und Repository-Namen.

---

## 📊 Was Sie dann sehen werden

### Codecov Dashboard

**Übersicht:**
- Gesamte Coverage: 23%
- Trend-Grafiken über Zeit
- Coverage per Datei

**Interaktive File-Ansicht:**
```python
# ✅ GRÜN = Getestet
def export_selections(self, project, storyboard, selections):
    export_payload = self._build_payload(storyboard, selections)  # ✅
    return export_payload  # ✅

# ❌ ROT = Nicht getestet
def complex_method_without_tests(self):
    if condition:  # ❌ Nie getestet
        return result  # ❌ Nie getestet
```

### Pull Request Comments

Bei jedem Pull Request kommentiert Codecov automatisch:

```
## Codecov Report
Coverage: 23.16% (+0.12%) ✅
Files changed: 3
- services/selection_service.py: 96% (+2%)
- domain/models.py: 89% (+10%)
- tests/unit/test_selection_service.py: new file
```

---

## 🎯 Coverage-Ziele

| Modul | Aktuell | Ziel |
|-------|---------|------|
| **services/** | 44% avg | 80%+ |
| **domain/** | 91% | 95%+ |
| **infrastructure/** | 62% avg | 70%+ |
| **GESAMT** | 29% | 75%+ |

**Kürzlich verbessert:**
- ProjectStore: 25% → 98% ✅
- WorkflowRegistry: 17% → 100% ✅
- StateStore: 28% → 100% ✅

---

## 🔧 Troubleshooting

### Badge zeigt "unknown" an

**Problem:** Badge wird nicht aktualisiert

**Lösung:**
1. Warten Sie 5-10 Minuten nach dem ersten CI-Run
2. Leeren Sie Browser-Cache (Strg+F5)
3. Prüfen Sie, ob der CI-Run erfolgreich war

### Coverage wird nicht hochgeladen

**Problem:** Codecov erhält keine Daten

**Lösung:**
1. Prüfen Sie GitHub Actions Logs: `Actions` → `CI` → Neuester Run
2. Suchen Sie nach "Upload coverage to Codecov"
3. Wenn Fehler: Token in Repository Secrets hinzufügen
   - GitHub: Settings → Secrets → New repository secret
   - Name: `CODECOV_TOKEN`
   - Value: [Token von Codecov Dashboard]

### Codecov findet coverage.xml nicht

**Problem:** "Coverage file not found"

**Lösung:**
Verifizieren Sie, dass Tests Coverage generieren:
```bash
pytest tests/unit/ --cov=services --cov-report=xml
ls -la coverage.xml  # Sollte existieren
```

---

## 📚 Weitere Ressourcen

- **Codecov Dokumentation:** https://docs.codecov.com/
- **GitHub Actions Integration:** https://docs.codecov.com/docs/github-actions-integration
- **Badge-Anpassung:** https://docs.codecov.com/docs/status-badges

---

## ✅ Checkliste

- [ ] Codecov-Account erstellt
- [ ] Repository zu Codecov hinzugefügt
- [ ] Ersten Commit gepusht
- [ ] CI-Run erfolgreich (GitHub Actions)
- [ ] Coverage in Codecov Dashboard sichtbar
- [ ] Badge im README funktioniert
- [ ] (Optional) Codecov-Token in GitHub Secrets hinzugefügt

---

**Nach Abschluss:** Sie haben eine vollständige Codecov-Integration mit automatischem Coverage-Tracking bei jedem Commit! 🎉
