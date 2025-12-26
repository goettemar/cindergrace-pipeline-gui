"""Targeted helper tests for addon modules (no full UI)."""

import os
import importlib

import pytest


def _stub_video_addon(monkeypatch, tmp_path, project_data=None):
    pytest.importorskip("gradio")
    import addons.video_generator as vg

    class DummyConfig:
        def __init__(self, *args, **kwargs):
            self.config_dir = str(tmp_path)
            self.refreshed = False

        def refresh(self):
            self.refreshed = True

        def get_comfy_root(self):
            return "/tmp"

        def get_comfy_url(self):
            return "http://localhost:8188"

    class DummyProjectStore:
        def __init__(self, cfg):
            self.cfg = cfg
            self.project = project_data

        def get_active_project(self, refresh=False):
            return self.project

        def project_path(self, project, subdir=None):
            if not project:
                return None
            base = project.get("path")
            return os.path.join(base, subdir) if subdir else base

    class DummyStateStore:
        def __init__(self):
            self.configured = []

        def configure(self, path):
            self.configured.append(path)

        def update(self, **kwargs):
            return None

        def load(self):
            return {}

    monkeypatch.setattr(vg, "ConfigManager", DummyConfig)
    monkeypatch.setattr(vg, "WorkflowRegistry", lambda: type("WR", (), {
        "get_files": lambda self=None, category=None: [],
        "get_default": lambda self=None, category=None: None,
    })())
    monkeypatch.setattr(vg, "ModelValidator", lambda root: object())
    monkeypatch.setattr(vg, "ProjectStore", DummyProjectStore)
    monkeypatch.setattr(vg, "VideoGeneratorStateStore", lambda: DummyStateStore())
    monkeypatch.setattr(
        vg,
        "VideoPlanBuilder",
        lambda max_segment_seconds=3.0: type("PB", (), {"build": staticmethod(lambda *a, **k: type("Plan", (), {"to_dict_list": lambda self: []})())})(),
    )
    monkeypatch.setattr(
        vg,
        "VideoGenerationService",
        lambda project_store, model_validator, state_store, plan_builder=None: type("VS", (), {"run_generation": lambda *a, **k: []})(),
    )

    addon = vg.VideoGeneratorAddon()
    return addon


@pytest.mark.unit
def test_video_generator_lists_selection_json(monkeypatch, tmp_path):
    selected_dir = tmp_path / "proj" / "selected"
    selected_dir.mkdir(parents=True)
    (selected_dir / "keep.json").write_text("{}", encoding="utf-8")
    (selected_dir / "ignore.txt").write_text("", encoding="utf-8")
    (selected_dir / "second.json").write_text("{}", encoding="utf-8")

    addon = _stub_video_addon(
        monkeypatch,
        tmp_path,
        project_data={"path": str(tmp_path / "proj"), "slug": "proj", "name": "Demo"},
    )

    files = addon._get_available_selection_files()
    assert set(files) == {"keep.json", "second.json"}
    assert addon.config.refreshed is True


@pytest.mark.unit
def test_video_generator_project_status(monkeypatch, tmp_path):
    addon = _stub_video_addon(monkeypatch, tmp_path, project_data=None)
    missing = addon._project_status_md()
    assert "No active project" in missing

    project_addon = _stub_video_addon(
        monkeypatch,
        tmp_path,
        project_data={"name": "Demo", "slug": "demo", "path": "/tmp/demo"},
    )
    status = project_addon._project_status_md()
    assert "Demo" in status and "demo" in status and "/tmp/demo" in status


@pytest.mark.unit
def test_video_generator_state_store_configured(monkeypatch, tmp_path):
    addon = _stub_video_addon(
        monkeypatch,
        tmp_path,
        project_data={"path": "/tmp/demo"},
    )
    addon._configure_state_store({"path": "/tmp/demo"})
    addon._configure_state_store(None)

    # First call uses project path, second resets to None
    assert addon.state_store.configured[0].endswith("/video/_state.json")
    assert addon.state_store.configured[1] is None


def _stub_keyframe_addon(monkeypatch, tmp_path, project_data=None):
    pytest.importorskip("gradio")
    import addons.keyframe_generator as kg

    class DummyConfig:
        def __init__(self, *args, **kwargs):
            self.config_dir = str(tmp_path)

        def get_comfy_url(self):
            return "http://localhost:8188"

        def get_current_storyboard(self):
            return "sb.json"

        def refresh(self):
            return None

        def get_resolution_tuple(self):
            return (640, 480)

    class DummyProjectStore:
        def __init__(self, cfg):
            self.cfg = cfg
            self.project = project_data

        def get_active_project(self, refresh=False):
            return self.project

    monkeypatch.setattr(kg, "ConfigManager", DummyConfig)
    monkeypatch.setattr(kg, "WorkflowRegistry", lambda: type("WR", (), {
        "get_files": lambda self=None, category=None: [],
        "get_default": lambda self=None, category=None: None,
    })())
    monkeypatch.setattr(kg, "ProjectStore", DummyProjectStore)
    monkeypatch.setattr(kg, "KeyframeGenerationService", lambda config=None, project_store=None: type("KGS", (), {"run_generation": lambda self, *args, **kwargs: iter([])})())
    monkeypatch.setattr(kg, "KeyframeService", lambda project_store=None, config=None, workflow_registry=None: type("KS", (), {"prepare_checkpoint": lambda *a, **k: {}, "is_running": False})())

    return kg.KeyframeGeneratorAddon()


@pytest.mark.skip(reason="Method _get_available_storyboards() removed during addon refactoring - test obsolete")
@pytest.mark.unit
def test_keyframe_generator_storyboard_paths(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    project_dir = tmp_path / "project"
    storyboards_dir = project_dir / "storyboards"
    config_dir.mkdir()
    project_dir.mkdir()
    storyboards_dir.mkdir()

    (config_dir / "storyboard_main.json").write_text("{}", encoding="utf-8")
    (storyboards_dir / "storyboard_extra.json").write_text("{}", encoding="utf-8")
    (project_dir / "not_storyboard.json").write_text("{}", encoding="utf-8")

    addon = _stub_keyframe_addon(
        monkeypatch,
        tmp_path=config_dir,
        project_data={"path": str(project_dir)},
    )

    available = addon._get_available_storyboards()
    assert any("storyboard_main.json" in entry for entry in available)
    assert any("storyboard_extra.json" in entry for entry in available)
    # Non-storyboard file should be ignored
    assert all("not_storyboard" not in entry for entry in available)


@pytest.mark.unit
def test_keyframe_generator_project_status(monkeypatch, tmp_path):
    addon = _stub_keyframe_addon(monkeypatch, tmp_path, project_data=None)
    assert "No active project" in addon._project_status_md()

    addon_with_project = _stub_keyframe_addon(
        monkeypatch,
        tmp_path,
        project_data={"name": "Project", "slug": "p", "path": "/tmp/p"},
    )
    status = addon_with_project._project_status_md()
    assert "Project" in status and "p" in status and "/tmp/p" in status


def _stub_selector_addon(monkeypatch, tmp_path, project_data=None):
    pytest.importorskip("gradio")
    import addons.keyframe_selector as ks

    class DummyConfig:
        def __init__(self, *args, **kwargs):
            self.config_dir = str(tmp_path)

        def refresh(self):
            return None

        def get_current_storyboard(self):
            return "sb.json"

    class DummyProjectStore:
        def __init__(self, cfg):
            self.cfg = cfg
            self.project = project_data

        def get_active_project(self, refresh=False):
            return self.project

    monkeypatch.setattr(ks, "ConfigManager", DummyConfig)
    monkeypatch.setattr(ks, "ProjectStore", DummyProjectStore)
    monkeypatch.setattr(ks, "SelectionService", lambda store: type("Sel", (), {
        "collect_keyframes": staticmethod(lambda *args, **kwargs: []),
        "export_selections": staticmethod(lambda *args, **kwargs: ("", {})),
    })())

    return ks.KeyframeSelectorAddon()


@pytest.mark.unit
def test_keyframe_selector_storyboards(monkeypatch, tmp_path):
    cfg_dir = tmp_path / "cfg"
    project_dir = tmp_path / "proj"
    sb_dir = project_dir / "storyboards"
    cfg_dir.mkdir()
    project_dir.mkdir()
    sb_dir.mkdir()

    (cfg_dir / "storyboard_a.json").write_text("{}", encoding="utf-8")
    (sb_dir / "storyboard_b.json").write_text("{}", encoding="utf-8")

    addon = _stub_selector_addon(
        monkeypatch,
        tmp_path=cfg_dir,
        project_data={"path": str(project_dir)},
    )

    storyboards = addon._get_available_storyboards()
    assert any("storyboard_a.json" in s for s in storyboards)
    assert any("storyboard_b.json" in s for s in storyboards)


@pytest.mark.unit
def test_keyframe_selector_selection_summary(monkeypatch, tmp_path):
    addon = _stub_selector_addon(monkeypatch, tmp_path, project_data=None)

    empty_summary = addon._format_selection_summary({}, {"shots": [{"shot_id": "1"}]})
    assert "No keyframes selected" in empty_summary

    selections = {"1": {"selected_file": "shot1.png", "selected_variant": 2}}
    storyboard = {"shots": [{"shot_id": "1"}]}
    filled_summary = addon._format_selection_summary(selections, storyboard)
    assert "shot1.png" in filled_summary


@pytest.mark.unit
def test_keyframe_generator_validation_error(monkeypatch):
    pytest.importorskip("gradio")
    import addons.keyframe_generator as kg

    addon = kg.KeyframeGeneratorAddon()
    validated, error = addon._validate_generation_inputs(0, -5, "workflow.txt")
    assert validated is None
    assert error and "Validierungsfehler" in error


@pytest.mark.unit
def test_video_generator_validation_and_workflow_errors(monkeypatch, tmp_path):
    pytest.importorskip("gradio")
    import addons.video_generator as vg

    addon = _stub_video_addon(
        monkeypatch,
        tmp_path,
        project_data={"path": str(tmp_path / "proj"), "slug": "proj", "name": "Demo"},
    )

    _, sel_error = addon._validate_selection_file("bad.txt")
    assert sel_error and "Auswahl-Datei" in sel_error

    class DummyAPI:
        def load_workflow(self, path):
            raise RuntimeError("boom")

    workflow, wf_error = addon._load_workflow_template(DummyAPI(), "missing.json")
    assert workflow is None
    assert wf_error and "Failed to load workflow" in wf_error


@pytest.mark.unit
def test_selector_storyboard_load_error(monkeypatch, tmp_path):
    pytest.importorskip("gradio")
    import addons.keyframe_selector as ks

    addon = _stub_selector_addon(monkeypatch, tmp_path)
    monkeypatch.setattr(ks.StoryboardService, "load_from_config", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("kaputt")))

    model, error = addon._load_storyboard_model("bad.json")
    assert model is None
    assert error and "Failed to load storyboard" in error


@pytest.mark.unit
def test_settings_addon_save_settings(monkeypatch):
    import addons.settings_panel as sp

    class DummyConfig:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def set(self, key, value):
            self.calls.append((key, value))

    monkeypatch.setattr(sp, "ConfigManager", DummyConfig)
    monkeypatch.setattr(sp, "WorkflowRegistry", lambda: object())

    addon = sp.SettingsAddon()

    ok = addon.save_settings("http://localhost:8188", "/tmp/root")
    assert "Saved" in ok
    assert addon.config.calls == [("comfy_url", "http://localhost:8188"), ("comfy_root", "/tmp/root")]

    error = addon.save_settings("invalid-url", "")
    assert "Error" in error


@pytest.mark.unit
def test_settings_addon_save_presets(monkeypatch):
    import addons.settings_panel as sp

    class DummyRegistry:
        def __init__(self):
            self.saved = None

        def save_raw(self, content):
            self.saved = content
            return "ok"

    monkeypatch.setattr(sp, "ConfigManager", lambda *a, **k: object())
    registry = DummyRegistry()
    monkeypatch.setattr(sp, "WorkflowRegistry", lambda: registry)

    addon = sp.SettingsAddon()
    assert addon.save_presets("{}") == "ok"
    assert registry.saved == "{}"
