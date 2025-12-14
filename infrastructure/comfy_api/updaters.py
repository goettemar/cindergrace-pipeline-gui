from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from infrastructure.comfy_api.base import NodeUpdater


def _merge_params(*candidates: Optional[Any]) -> Optional[Any]:
    """Return the first non-None candidate."""
    for value in candidates:
        if value is not None:
            return value
    return None


class CLIPTextEncodeUpdater(NodeUpdater):
    target_types = ("CLIPTextEncode",)

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        prompt = params.get("prompt")
        if prompt is None:
            return
        inputs = node_data.setdefault("inputs", {})
        inputs["text"] = prompt


class SaveImageUpdater(NodeUpdater):
    target_types = ("SaveImage",)

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        filename_prefix = params.get("filename_prefix")
        if filename_prefix is None:
            return
        inputs = node_data.setdefault("inputs", {})
        inputs["filename_prefix"] = filename_prefix


class SaveVideoUpdater(NodeUpdater):
    target_types = ("SaveVideo",)

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        filename_prefix = params.get("filename_prefix")
        if filename_prefix is None:
            return
        inputs = node_data.setdefault("inputs", {})
        inputs["filename_prefix"] = filename_prefix


class RandomNoiseUpdater(NodeUpdater):
    target_types = ("RandomNoise",)

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        seed = params.get("seed")
        if seed is None:
            return
        inputs = node_data.setdefault("inputs", {})
        if "noise_seed" in inputs:
            inputs["noise_seed"] = seed
        if "seed" in inputs:
            inputs["seed"] = seed


class KSamplerUpdater(NodeUpdater):
    target_types = ("KSampler",)

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        inputs = node_data.setdefault("inputs", {})
        seed = params.get("seed")
        steps = params.get("steps")
        cfg = params.get("cfg")

        if seed is not None and "seed" in inputs:
            inputs["seed"] = seed
        if steps is not None and "steps" in inputs:
            inputs["steps"] = steps
        if cfg is not None and "cfg" in inputs:
            inputs["cfg"] = cfg


class BasicSchedulerUpdater(NodeUpdater):
    target_types = ("BasicScheduler",)

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        steps = params.get("steps")
        if steps is None:
            return
        inputs = node_data.setdefault("inputs", {})
        if "steps" in inputs:
            inputs["steps"] = steps


class EmptyLatentImageUpdater(NodeUpdater):
    target_types = ("EmptyLatentImage", "ImageResize", "ImageResizeAndScale")

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        width = params.get("width")
        height = params.get("height")
        if width is None and height is None:
            return
        inputs = node_data.setdefault("inputs", {})
        if width is not None and "width" in inputs:
            inputs["width"] = width
        if height is not None and "height" in inputs:
            inputs["height"] = height
        # Some nodes use capitalized keys
        if width is not None and "W" in inputs:
            inputs["W"] = width
        if height is not None and "H" in inputs:
            inputs["H"] = height


class WanImageToVideoUpdater(NodeUpdater):
    """Update Wan image-to-video latent nodes (both WanImageToVideo and Wan22ImageToVideoLatent)."""
    target_types = ("WanImageToVideo", "Wan22ImageToVideoLatent")

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        width = params.get("width")
        height = params.get("height")
        frames = _merge_params(
            params.get("frames"),
            params.get("num_frames"),
            params.get("frame_count"),
            params.get("length"),
        )
        inputs = node_data.setdefault("inputs", {})
        if width is not None and "width" in inputs:
            inputs["width"] = width
        if height is not None and "height" in inputs:
            inputs["height"] = height
        if frames is not None and "length" in inputs:
            inputs["length"] = frames


class LoadImageUpdater(NodeUpdater):
    target_types = ("LoadImage", "LoadImageForVideo", "ImageInput")

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        startframe = _merge_params(
            params.get("startframe_path"),
            params.get("start_frame_path"),
            params.get("image_path"),
        )
        if startframe is None:
            return
        inputs = node_data.setdefault("inputs", {})
        for key in ("image", "filename", "path"):
            if key in inputs:
                inputs[key] = startframe


class HunyuanVideoSamplerUpdater(NodeUpdater):
    target_types = ("HunyuanVideoSampler",)

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        inputs = node_data.setdefault("inputs", {})
        seed = params.get("seed")
        steps = params.get("steps")
        frames = _merge_params(
            params.get("frames"),
            params.get("num_frames"),
            params.get("frame_count"),
        )

        if seed is not None and "seed" in inputs:
            inputs["seed"] = seed
        if steps is not None and "steps" in inputs:
            inputs["steps"] = steps
        if frames is not None:
            for key in ("num_frames", "frame_count", "frames"):
                if key in inputs:
                    inputs[key] = frames


class GenericSeedUpdater(NodeUpdater):
    """Safety net to push seed into any node exposing seed/noise_seed."""

    target_types: tuple[str, ...] = ()

    def applies_to(self, node_type: str) -> bool:
        return True

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:
        seed = params.get("seed")
        if seed is None:
            return
        inputs = node_data.setdefault("inputs", {})
        for key in ("seed", "noise_seed"):
            if key in inputs:
                inputs[key] = seed


def default_updaters() -> Iterable[NodeUpdater]:
    """Factory returning the default updater set."""
    return (
        CLIPTextEncodeUpdater(),
        SaveImageUpdater(),
        SaveVideoUpdater(),
        RandomNoiseUpdater(),
        KSamplerUpdater(),
        BasicSchedulerUpdater(),
        EmptyLatentImageUpdater(),
        WanImageToVideoUpdater(),
        LoadImageUpdater(),
        HunyuanVideoSamplerUpdater(),
        GenericSeedUpdater(),
    )
