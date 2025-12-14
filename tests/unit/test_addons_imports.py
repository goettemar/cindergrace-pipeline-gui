"""Lightweight import smoke tests for addon modules."""
import importlib
import pytest
from addons.base_addon import BaseAddon


@pytest.mark.unit
@pytest.mark.parametrize(
    "module_name",
    [
        "addons.keyframe_generator",
        "addons.keyframe_selector",
        "addons.project_panel",
        "addons.settings_panel",
        "addons.video_generator",
        "addons.test_comfy_flux",
    ],
)
def test_addon_imports(module_name):
    """Ensure addon modules import (skipped if gradio not installed)."""
    pytest.importorskip("gradio")
    importlib.import_module(module_name)


def test_base_addon_repr_and_flags():
    """BaseAddon default flags, category, and repr."""
    class DummyAddon(BaseAddon):
        def render(self):
            return []

        def get_tab_name(self):
            return "Dummy"

    # Test default category
    addon = DummyAddon("Name", "Desc")
    assert addon.enabled is True
    assert addon.category == "pipeline"
    assert "DummyAddon" in repr(addon)

    # Test custom category
    tool_addon = DummyAddon("Tool", "ToolDesc", category="tools")
    assert tool_addon.category == "tools"


def test_video_generator_addon_init(monkeypatch):
    """VideoGeneratorAddon should construct with stubbed dependencies."""
    import addons.video_generator as vg

    class DummyConfig:
        def __init__(self):
            self.calls = []

        def get_comfy_root(self):
            return "/tmp"

        def get_comfy_url(self):
            return "http://localhost:8188"

    class DummyProjectStore:
        def __init__(self, cfg):
            self.cfg = cfg

    monkeypatch.setattr(vg, "ConfigManager", DummyConfig)
    monkeypatch.setattr(vg, "WorkflowRegistry", lambda: object())
    monkeypatch.setattr(vg, "ModelValidator", lambda root: type("MV", (), {"enabled": True})())
    monkeypatch.setattr(vg, "ProjectStore", DummyProjectStore)
    monkeypatch.setattr(vg, "VideoGeneratorStateStore", lambda: object())
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
    assert addon.get_tab_name() == "🎥 Video Generator"
    assert addon.max_clip_duration == 3.0


def test_keyframe_generator_addon_init(monkeypatch):
    """KeyframeGeneratorAddon should construct with stubbed dependencies."""
    import addons.keyframe_generator as kg

    class DummyConfig:
        pass

    class DummyProjectStore:
        def __init__(self, cfg):
            self.cfg = cfg

    monkeypatch.setattr(kg, "ConfigManager", DummyConfig)
    monkeypatch.setattr(kg, "WorkflowRegistry", lambda: object())
    monkeypatch.setattr(kg, "ProjectStore", DummyProjectStore)

    addon = kg.KeyframeGeneratorAddon()
    assert addon.get_tab_name() == "🎬 Keyframe Generator"
    assert addon.project_manager.cfg is addon.config


def test_keyframe_selector_addon_init(monkeypatch):
    """KeyframeSelectorAddon should construct with stubbed dependencies."""
    import addons.keyframe_selector as ks

    class DummyConfig:
        pass

    class DummyProjectStore:
        def __init__(self, cfg):
            self.cfg = cfg

    monkeypatch.setattr(ks, "ConfigManager", DummyConfig)
    monkeypatch.setattr(ks, "ProjectStore", DummyProjectStore)
    monkeypatch.setattr(ks, "SelectionService", lambda store: object())

    addon = ks.KeyframeSelectorAddon()
    assert addon.get_tab_name() == "✅ Keyframe Selector"
    assert addon.selection_service is not None


def test_project_and_settings_addon_init(monkeypatch):
    """Project/Settings addons construct with stubbed config/store/registry."""
    import addons.project_panel as pp
    import addons.settings_panel as sp

    class DummyConfig:
        pass

    class DummyProjectStore:
        def __init__(self, cfg):
            self.cfg = cfg

    monkeypatch.setattr(pp, "ConfigManager", DummyConfig)
    monkeypatch.setattr(pp, "ProjectStore", DummyProjectStore)
    proj_addon = pp.ProjectAddon()
    assert proj_addon.get_tab_name() == "📁 Projekt"

    monkeypatch.setattr(sp, "ConfigManager", DummyConfig)
    monkeypatch.setattr(sp, "WorkflowRegistry", lambda: object())
    settings_addon = sp.SettingsAddon()
    assert settings_addon.get_tab_name() == "⚙️ Settings"


def test_video_generator_render_minimal(monkeypatch):
    """Render should build interface even with stubbed dependencies."""
    pytest.importorskip("gradio")
    import addons.video_generator as vg

    class DummyConfig:
        def __init__(self):
            self.data = {"project": "demo"}

        def get_comfy_root(self):
            return "/tmp"

        def get_current_storyboard(self):
            return "sb.json"

        def get_current_project(self):
            return {"path": "/tmp/project"}

        def refresh(self):
            return None

        def get_comfy_url(self):
            return "http://localhost:8188"

        @property
        def config_dir(self):
            return "/tmp/config"

    class DummyModelValidator:
        enabled = True

    class DummyStore:
        def __init__(self, cfg):
            self.cfg = cfg

        def get_active_project(self, refresh=False):
            return {"path": "/tmp/project"}

        def ensure_dir(self, project, subdir=None):
            return "/tmp/project"

        def project_path(self, project, subdir=None):
            return "/tmp/project"

    monkeypatch.setattr(vg, "ConfigManager", DummyConfig)
    monkeypatch.setattr(
        vg,
        "WorkflowRegistry",
        lambda: type(
            "WR",
            (),
            {
                "list_presets": lambda self=None, category=None: [],
                "get_files": lambda self=None, category=None: [],
                "get_default": lambda self=None, category=None: None,
            },
        )(),
    )
    monkeypatch.setattr(vg, "ModelValidator", lambda root: DummyModelValidator())
    monkeypatch.setattr(vg, "ProjectStore", DummyStore)
    class DummyStateStore:
        def configure(self, *args, **kwargs):
            return None

        def load(self):
            return {}

        def save(self, *args, **kwargs):
            return None

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
    ui = addon.render()
    assert ui is not None


def test_keyframe_generator_render_smoke(monkeypatch):
    """Keyframe render should initialize without hitting real filesystem."""
    pytest.importorskip("gradio")
    import addons.keyframe_generator as kg

    class DummyConfig:
        def get_comfy_url(self):
            return "http://localhost:8188"

        def get_current_storyboard(self):
            return "sb.json"

        def get_resolution_tuple(self):
            return (640, 480)

        def refresh(self):
            return None

        def get_comfy_root(self):
            return "/tmp"

    class DummyStore:
        def __init__(self, cfg):
            self.cfg = cfg

        def get_active_project(self, refresh=False):
            return {"path": "/tmp/project"}

    monkeypatch.setattr(kg, "ConfigManager", DummyConfig)
    monkeypatch.setattr(
        kg,
        "WorkflowRegistry",
        lambda: type(
            "WR",
            (),
            {
                "list_presets": lambda self=None, category=None: [],
                "get_files": lambda self=None, category=None: [],
                "get_default": lambda self=None, category=None: None,
            },
        )(),
    )
    monkeypatch.setattr(kg, "ProjectStore", DummyStore)
    monkeypatch.setattr(kg, "StoryboardService", type("SS", (), {"load_from_config": staticmethod(lambda cfg: type("SB", (), {"shots": [], "project": "p", "raw": {"shots": []}})())}))
    monkeypatch.setattr(kg, "KeyframeGenerationService", lambda config=None, project_store=None: type("KGS", (), {"run_generation": lambda self, *args, **kwargs: iter([])})(), raising=False)
    monkeypatch.setattr(kg, "KeyframeService", lambda project_store=None, config=None, workflow_registry=None: type("KS", (), {"prepare_checkpoint": lambda *a, **k: {}, "is_running": False})(), raising=False)

    addon = kg.KeyframeGeneratorAddon()
    ui = addon.render()
    assert ui is not None
