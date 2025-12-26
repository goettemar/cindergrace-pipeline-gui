"""Kohya Model Scanner - Scans for available models in ComfyUI.

This module handles detection of FLUX, SDXL, SD3 and text encoder models
for training configuration.
"""

from pathlib import Path
from typing import List, Tuple, Optional, Dict

from infrastructure.logger import get_logger
from .models import KohyaModelType

logger = get_logger(__name__)


class KohyaModelScanner:
    """Scans for models and text encoders in ComfyUI models directory.

    Supports FLUX, SDXL, and SD3 model types.
    """

    # Default model filenames (FP8 preferred for lower VRAM usage)
    # FLUX defaults
    DEFAULT_FLUX_MODEL = "flux1-dev-fp8.safetensors"
    DEFAULT_FLUX_AE = "ae.safetensors"  # FLUX uses AutoEncoder, not VAE

    # SDXL defaults
    DEFAULT_SDXL_MODEL = "sd_xl_base_1.0.safetensors"
    DEFAULT_SDXL_VAE = "sdxl_vae.safetensors"

    # SD3 defaults
    DEFAULT_SD3_MODEL = "sd3_medium.safetensors"
    DEFAULT_SD3_VAE = "sd3_vae.safetensors"

    # Shared text encoder defaults
    DEFAULT_CLIP_L = "clip_l.safetensors"
    DEFAULT_CLIP_G = "clip_g.safetensors"
    DEFAULT_T5XXL = "t5xxl_fp8_e4m3fn.safetensors"

    def __init__(self, comfy_root: str):
        """Initialize the model scanner.

        Args:
            comfy_root: Path to the ComfyUI installation
        """
        self.comfy_root = comfy_root
        self.models_dir = Path(comfy_root) / "models" if comfy_root else None

    def scan_flux_models(self) -> List[Tuple[str, str]]:
        """Scan for available FLUX models.

        Returns:
            List of tuples (display_name, full_path) for each found model
        """
        models = []
        if not self.models_dir:
            return models

        # Check diffusion_models and unet folders
        for subdir in ["diffusion_models", "unet", "checkpoints"]:
            search_dir = self.models_dir / subdir
            if not search_dir.exists():
                continue

            for f in search_dir.iterdir():
                if f.is_file() and f.suffix == ".safetensors":
                    name = f.name.lower()
                    # Filter for FLUX models
                    if "flux" in name:
                        # Create display name with size info
                        size_mb = f.stat().st_size / (1024 * 1024)
                        size_str = f"{size_mb / 1024:.1f}GB" if size_mb > 1024 else f"{size_mb:.0f}MB"
                        display = f"{f.name} ({size_str})"
                        models.append((display, str(f)))

        # Sort by name
        models.sort(key=lambda x: x[0])
        return models

    def scan_t5xxl_models(self) -> List[Tuple[str, str]]:
        """Scan for available T5XXL text encoder models.

        Returns:
            List of tuples (display_name, full_path) for each found model
        """
        models = []
        if not self.models_dir:
            return models

        # Check text_encoders and clip folders
        for subdir in ["text_encoders", "clip"]:
            search_dir = self.models_dir / subdir
            if not search_dir.exists():
                continue

            for f in search_dir.iterdir():
                if f.is_file() and f.suffix in [".safetensors", ".gguf"]:
                    name = f.name.lower()
                    # Filter for T5XXL models
                    if "t5" in name and ("xxl" in name or "xl" in name):
                        # Create display name with size and type info
                        size_mb = f.stat().st_size / (1024 * 1024)
                        size_str = f"{size_mb / 1024:.1f}GB" if size_mb > 1024 else f"{size_mb:.0f}MB"

                        # Add FP8/FP16 indicator
                        precision = "FP8" if "fp8" in name else "FP16" if "fp16" in name else "BF16" if "bf16" in name else ""
                        precision_str = f" [{precision}]" if precision else ""

                        display = f"{f.name} ({size_str}){precision_str}"
                        models.append((display, str(f)))

        # Sort: FP8 first (smaller), then by name
        def sort_key(x):
            name = x[0].lower()
            # FP8 models first (more VRAM friendly)
            if "fp8" in name:
                return (0, name)
            return (1, name)

        models.sort(key=sort_key)
        return models

    def scan_sdxl_models(self) -> List[Tuple[str, str]]:
        """Scan for available SDXL models.

        Returns:
            List of tuples (display_name, full_path) for each found model
        """
        models = []
        if not self.models_dir:
            return models

        # Check checkpoints folder (SDXL models are typically full checkpoints)
        for subdir in ["checkpoints", "unet"]:
            search_dir = self.models_dir / subdir
            if not search_dir.exists():
                continue

            for f in search_dir.iterdir():
                if f.is_file() and f.suffix == ".safetensors":
                    name = f.name.lower()
                    # Filter for SDXL models (exclude FLUX and SD3)
                    if ("sdxl" in name or "sd_xl" in name or "xl_base" in name) and \
                       "flux" not in name and "sd3" not in name:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        size_str = f"{size_mb / 1024:.1f}GB" if size_mb > 1024 else f"{size_mb:.0f}MB"
                        display = f"{f.name} ({size_str})"
                        models.append((display, str(f)))

        models.sort(key=lambda x: x[0])
        return models

    def scan_sd3_models(self) -> List[Tuple[str, str]]:
        """Scan for available SD3 models.

        Returns:
            List of tuples (display_name, full_path) for each found model
        """
        models = []
        if not self.models_dir:
            return models

        # Check checkpoints and diffusion_models folders
        for subdir in ["checkpoints", "diffusion_models", "unet"]:
            search_dir = self.models_dir / subdir
            if not search_dir.exists():
                continue

            for f in search_dir.iterdir():
                if f.is_file() and f.suffix == ".safetensors":
                    name = f.name.lower()
                    # Filter for SD3 models
                    if "sd3" in name and "flux" not in name:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        size_str = f"{size_mb / 1024:.1f}GB" if size_mb > 1024 else f"{size_mb:.0f}MB"
                        display = f"{f.name} ({size_str})"
                        models.append((display, str(f)))

        models.sort(key=lambda x: x[0])
        return models

    def scan_models(self, model_type: KohyaModelType) -> List[Tuple[str, str]]:
        """Scan for models of a specific type.

        Args:
            model_type: The model type to scan for

        Returns:
            List of tuples (display_name, full_path) for each found model
        """
        if model_type == KohyaModelType.FLUX:
            return self.scan_flux_models()
        elif model_type == KohyaModelType.SDXL:
            return self.scan_sdxl_models()
        elif model_type == KohyaModelType.SD3:
            return self.scan_sd3_models()
        else:
            return []

    def scan_clip_g_models(self) -> List[Tuple[str, str]]:
        """Scan for available CLIP-G text encoder models (SD3 only).

        Returns:
            List of tuples (display_name, full_path) for each found model
        """
        models = []
        if not self.models_dir:
            return models

        for subdir in ["text_encoders", "clip"]:
            search_dir = self.models_dir / subdir
            if not search_dir.exists():
                continue

            for f in search_dir.iterdir():
                if f.is_file() and f.suffix in [".safetensors", ".gguf"]:
                    name = f.name.lower()
                    # Filter for CLIP-G models
                    if "clip_g" in name or "clip-g" in name or "openclip" in name:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        size_str = f"{size_mb / 1024:.1f}GB" if size_mb > 1024 else f"{size_mb:.0f}MB"
                        display = f"{f.name} ({size_str})"
                        models.append((display, str(f)))

        models.sort(key=lambda x: x[0])
        return models

    def get_default_model_paths(
        self,
        model_type: KohyaModelType = KohyaModelType.FLUX
    ) -> Dict[str, str]:
        """Get default model paths from ComfyUI installation.

        Args:
            model_type: The model type to get paths for

        Returns:
            Dictionary with model paths. Keys depend on model type:
            - FLUX: model, vae (ae), clip_l, t5xxl
            - SDXL: model, vae (optional)
            - SD3: model, vae, clip_l, clip_g, t5xxl (all optional except model)
        """
        if not self.models_dir:
            logger.warning("ComfyUI root not configured")
            return {}

        if model_type == KohyaModelType.FLUX:
            return self._get_flux_default_paths()
        elif model_type == KohyaModelType.SDXL:
            return self._get_sdxl_default_paths()
        elif model_type == KohyaModelType.SD3:
            return self._get_sd3_default_paths()
        else:
            return {}

    def _get_flux_default_paths(self) -> Dict[str, str]:
        """Get default FLUX model paths."""
        paths = {}

        # FLUX model (diffusion_models or unet)
        for model_subdir in ["diffusion_models", "unet"]:
            model_dir = self.models_dir / model_subdir
            if model_dir.exists():
                for model in [self.DEFAULT_FLUX_MODEL, "flux1-dev.safetensors"]:
                    model_path = model_dir / model
                    if model_path.exists():
                        paths["model"] = str(model_path)
                        break
            if "model" in paths:
                break

        # VAE (AutoEncoder for FLUX)
        vae_dir = self.models_dir / "vae"
        vae_path = vae_dir / self.DEFAULT_FLUX_AE
        if vae_path.exists():
            paths["vae"] = str(vae_path)

        # CLIP-L
        paths.update(self._find_clip_l())

        # T5XXL
        paths.update(self._find_t5xxl())

        return paths

    def _get_sdxl_default_paths(self) -> Dict[str, str]:
        """Get default SDXL model paths."""
        paths = {}

        # SDXL model (checkpoints)
        for model_subdir in ["checkpoints", "unet"]:
            model_dir = self.models_dir / model_subdir
            if model_dir.exists():
                for model in [
                    self.DEFAULT_SDXL_MODEL,
                    "sd_xl_base_1.0.safetensors",
                    "sdxl_base.safetensors",
                ]:
                    model_path = model_dir / model
                    if model_path.exists():
                        paths["model"] = str(model_path)
                        break
                # Also search for any SDXL model
                if "model" not in paths:
                    for f in model_dir.iterdir():
                        if f.suffix == ".safetensors":
                            name = f.name.lower()
                            if ("sdxl" in name or "sd_xl" in name) and "flux" not in name:
                                paths["model"] = str(f)
                                break
            if "model" in paths:
                break

        # VAE (optional for SDXL, usually embedded)
        vae_dir = self.models_dir / "vae"
        for vae_name in [self.DEFAULT_SDXL_VAE, "sdxl_vae.safetensors", "sdxl-vae-fp16-fix.safetensors"]:
            vae_path = vae_dir / vae_name
            if vae_path.exists():
                paths["vae"] = str(vae_path)
                break

        return paths

    def _get_sd3_default_paths(self) -> Dict[str, str]:
        """Get default SD3 model paths."""
        paths = {}

        # SD3 model (checkpoints or diffusion_models)
        for model_subdir in ["checkpoints", "diffusion_models", "unet"]:
            model_dir = self.models_dir / model_subdir
            if model_dir.exists():
                for model in [
                    self.DEFAULT_SD3_MODEL,
                    "sd3_medium.safetensors",
                    "sd3.5_medium.safetensors",
                    "sd3.5_large.safetensors",
                ]:
                    model_path = model_dir / model
                    if model_path.exists():
                        paths["model"] = str(model_path)
                        break
                # Also search for any SD3 model
                if "model" not in paths:
                    for f in model_dir.iterdir():
                        if f.suffix == ".safetensors" and "sd3" in f.name.lower():
                            paths["model"] = str(f)
                            break
            if "model" in paths:
                break

        # VAE (optional, usually in checkpoint)
        vae_dir = self.models_dir / "vae"
        for vae_name in [self.DEFAULT_SD3_VAE, "sd3_vae.safetensors"]:
            vae_path = vae_dir / vae_name
            if vae_path.exists():
                paths["vae"] = str(vae_path)
                break

        # Text encoders (optional, can be in checkpoint)
        paths.update(self._find_clip_l())
        paths.update(self._find_clip_g())
        paths.update(self._find_t5xxl())

        return paths

    def _find_clip_l(self) -> Dict[str, str]:
        """Find CLIP-L text encoder."""
        for clip_dir_name in ["clip", "text_encoders"]:
            clip_dir = self.models_dir / clip_dir_name
            clip_path = clip_dir / self.DEFAULT_CLIP_L
            if clip_path.exists():
                return {"clip_l": str(clip_path)}
        return {}

    def _find_clip_g(self) -> Dict[str, str]:
        """Find CLIP-G text encoder (for SD3)."""
        for clip_dir_name in ["clip", "text_encoders"]:
            clip_dir = self.models_dir / clip_dir_name
            for clip_name in [self.DEFAULT_CLIP_G, "clip_g.safetensors", "open_clip_g.safetensors"]:
                clip_path = clip_dir / clip_name
                if clip_path.exists():
                    return {"clip_g": str(clip_path)}
        return {}

    def _find_t5xxl(self) -> Dict[str, str]:
        """Find T5XXL text encoder."""
        for encoder_dir_name in ["clip", "text_encoders"]:
            encoder_dir = self.models_dir / encoder_dir_name
            for t5_name in [
                self.DEFAULT_T5XXL,
                "google_t5-v1_1-xxl_encoderonly-fp8_e4m3fn.safetensors",
                "t5xxl_fp16.safetensors",
            ]:
                t5_path = encoder_dir / t5_name
                if t5_path.exists():
                    return {"t5xxl": str(t5_path)}
                # Also check in t5 subfolder
                t5_path = encoder_dir / "t5" / t5_name
                if t5_path.exists():
                    return {"t5xxl": str(t5_path)}
        return {}

    def find_trained_lora(self, character_name: str) -> Optional[str]:
        """Find a trained LoRA file.

        Args:
            character_name: Character name used during training

        Returns:
            Path to LoRA file or None
        """
        if not self.models_dir:
            return None

        import glob
        import os

        loras_dir = self.models_dir / "loras"
        output_name = f"cg_{character_name}"

        # Look for the LoRA file
        for pattern in [f"{output_name}.safetensors", f"{output_name}*.safetensors"]:
            matches = glob.glob(str(loras_dir / pattern))
            if matches:
                # Return most recent
                return max(matches, key=os.path.getmtime)

        return None
