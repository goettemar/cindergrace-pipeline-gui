"""Kohya Config Builder - TOML configuration generation for LoRA training.

This module handles the generation of TOML configuration files for Kohya sd-scripts.
Supports FLUX, SDXL, and SD3 model types.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List

from infrastructure.logger import get_logger
from .models import (
    KohyaTrainingConfig,
    KohyaModelType,
    KohyaVRAMPreset,
    KOHYA_NETWORK_MODULES,
    get_vram_preset,
)

logger = get_logger(__name__)


class KohyaConfigBuilder:
    """Builds TOML configuration files for Kohya training.

    Supports multiple model types: FLUX, SDXL, SD3.
    """

    def __init__(self, config_dir: str, comfy_root: str):
        """Initialize the config builder.

        Args:
            config_dir: Directory to store generated configs
            comfy_root: ComfyUI root directory for model paths
        """
        self.config_dir = Path(config_dir)
        self.comfy_root = comfy_root

    def get_vram_preset_config(
        self,
        preset: KohyaVRAMPreset,
        model_type: KohyaModelType = KohyaModelType.FLUX
    ) -> Dict[str, Any]:
        """Get configuration for a VRAM preset.

        Args:
            preset: The VRAM preset to get config for
            model_type: The model type (FLUX, SDXL, SD3)

        Returns:
            Dictionary with preset configuration
        """
        return get_vram_preset(model_type, preset).copy()

    def generate_training_config(
        self,
        character_name: str,
        images_dir: str,
        trigger_word: str,
        output_dir: Optional[str],
        model_paths: Dict[str, str],
        model_type: KohyaModelType = KohyaModelType.FLUX,
        vram_preset: KohyaVRAMPreset = KohyaVRAMPreset.VRAM_16GB,
        **overrides
    ) -> str:
        """Generate TOML configuration for training.

        Args:
            character_name: Name for the character (used in output filename)
            images_dir: Directory containing training images
            trigger_word: Trigger word for the LoRA (without cg_ prefix)
            output_dir: Output directory for trained LoRA
            model_paths: Dict with model, vae, clip_l, t5xxl, clip_g paths
            model_type: Model type (FLUX, SDXL, SD3)
            vram_preset: VRAM optimization preset
            **overrides: Override any default parameters

        Returns:
            Path to generated TOML config file
        """
        # Get preset config for specific model type
        preset_config = self.get_vram_preset_config(vram_preset, model_type)
        preset_config.pop("description", None)
        preset_config.update(overrides)

        # Default output to ComfyUI loras folder
        if not output_dir:
            output_dir = str(Path(self.comfy_root) / "models" / "loras") if self.comfy_root else "/tmp/lora_output"

        # Build config
        config = KohyaTrainingConfig(
            character_name=character_name,
            images_dir=images_dir,
            trigger_word=trigger_word,
            output_dir=output_dir,
            model_type=model_type,
            model_path=model_paths.get("model", ""),
            vae_path=model_paths.get("vae", ""),
            clip_l_path=model_paths.get("clip_l", ""),
            t5xxl_path=model_paths.get("t5xxl", ""),
            clip_g_path=model_paths.get("clip_g", ""),
            resolution=preset_config.get("resolution", 512),
            batch_size=preset_config.get("batch_size", 1),
            gradient_accumulation=preset_config.get("gradient_accumulation", 4),
            gradient_checkpointing=preset_config.get("gradient_checkpointing", True),
            mixed_precision=preset_config.get("mixed_precision", "bf16"),
            optimizer=preset_config.get("optimizer", "prodigy"),
            network_dim=preset_config.get("network_dim", 16),
            network_alpha=preset_config.get("network_alpha", 8),
            learning_rate=preset_config.get("learning_rate", 1.0),
            max_train_steps=preset_config.get("max_train_steps", 1500),
            save_every_n_steps=preset_config.get("save_every_n_steps", 500),
            sample_every_n_steps=preset_config.get("sample_every_n_steps", 0),
            sample_prompt=preset_config.get("sample_prompt", ""),
            sample_sampler=preset_config.get("sample_sampler", "euler"),
        )

        # Create config directory
        config_dir = self.config_dir / "training_configs"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Generate dataset TOML
        dataset_path = config_dir / f"{character_name}_dataset.toml"
        dataset_content = self._build_dataset_toml(config)
        with open(dataset_path, "w") as f:
            f.write(dataset_content)
        logger.info(f"Generated dataset config: {dataset_path}")

        # Generate sample prompts file if sampling is enabled
        sample_prompts_path = None
        if config.sample_every_n_steps > 0:
            sample_prompts_path = config_dir / f"{character_name}_sample_prompts.txt"
            sample_content = self._build_sample_prompts(config)
            with open(sample_prompts_path, "w") as f:
                f.write(sample_content)
            logger.info(f"Generated sample prompts: {sample_prompts_path}")

        # Generate training TOML based on model type
        config_path = config_dir / f"{character_name}_kohya_training.toml"
        toml_content = self._build_toml(
            config, preset_config, str(dataset_path),
            str(sample_prompts_path) if sample_prompts_path else None
        )
        with open(config_path, "w") as f:
            f.write(toml_content)

        logger.info(f"Generated Kohya {model_type.value.upper()} training config: {config_path}")
        return str(config_path.resolve())

    def _build_dataset_toml(self, config: KohyaTrainingConfig) -> str:
        """Build dataset TOML configuration string."""
        model_name = config.model_type.value.upper()
        lines = [
            f"# Kohya {model_name} Dataset Configuration",
            f"# Character: {config.character_name}",
            "",
            "[general]",
            f'caption_extension = "{config.caption_extension}"',
            "",
            "[[datasets]]",
            f"batch_size = {config.batch_size}",
            f"resolution = [{config.resolution}, {config.resolution}]",
            "enable_bucket = true",
            "bucket_no_upscale = true",
            "",
            "  [[datasets.subsets]]",
            f'  image_dir = "{config.images_dir}"',
            f"  num_repeats = {config.num_repeats}",
            "",
        ]
        return "\n".join(lines)

    def _build_sample_prompts(self, config: KohyaTrainingConfig) -> str:
        """Build sample prompts file content.

        Args:
            config: Training configuration

        Returns:
            Sample prompts file content (one prompt per line)
        """
        # Use custom prompt or default to trigger word with simple description
        if config.sample_prompt:
            prompt = config.sample_prompt
        else:
            prompt = f"{config.trigger_word}, portrait, high quality"

        # Can add multiple prompts, one per line
        return prompt

    def _build_sample_section(
        self,
        config: KohyaTrainingConfig,
        sample_prompts_path: Optional[str]
    ) -> list:
        """Build sample generation section for TOML.

        Args:
            config: Training configuration
            sample_prompts_path: Path to sample prompts file

        Returns:
            List of TOML lines for sample section
        """
        if config.sample_every_n_steps <= 0 or not sample_prompts_path:
            return []

        return [
            "",
            "[sample_arguments]",
            f"sample_every_n_steps = {config.sample_every_n_steps}",
            f'sample_prompts = "{sample_prompts_path}"',
            f'sample_sampler = "{config.sample_sampler}"',
        ]

    def _build_toml(
        self,
        config: KohyaTrainingConfig,
        preset_config: Dict[str, Any],
        dataset_config_path: str = "",
        sample_prompts_path: Optional[str] = None
    ) -> str:
        """Build TOML configuration string based on model type.

        Args:
            config: Training configuration
            preset_config: VRAM preset configuration dict
            dataset_config_path: Path to dataset config file
            sample_prompts_path: Path to sample prompts file (optional)

        Returns:
            TOML configuration string
        """
        if config.model_type == KohyaModelType.FLUX:
            return self._build_flux_toml(config, preset_config, dataset_config_path, sample_prompts_path)
        elif config.model_type == KohyaModelType.SDXL:
            return self._build_sdxl_toml(config, preset_config, dataset_config_path, sample_prompts_path)
        elif config.model_type == KohyaModelType.SD3:
            return self._build_sd3_toml(config, preset_config, dataset_config_path, sample_prompts_path)
        else:
            raise ValueError(f"Unknown model type: {config.model_type}")

    def _build_flux_toml(
        self,
        config: KohyaTrainingConfig,
        preset_config: Dict[str, Any],
        dataset_config_path: str,
        sample_prompts_path: Optional[str] = None
    ) -> str:
        """Build TOML for FLUX LoRA training."""
        output_name = f"cg_{config.character_name}"
        blocks_to_swap = preset_config.get("blocks_to_swap", 20)
        t5xxl_max_token_length = preset_config.get("t5xxl_max_token_length", 512)

        lines = [
            "# Kohya FLUX LoRA Training Configuration",
            f"# Generated for: {config.character_name}",
            f"# Trigger word: {config.trigger_word}",
            "",
            "[model_arguments]",
            f'pretrained_model_name_or_path = "{config.model_path}"',
            f'ae = "{config.vae_path}"',
            f'clip_l = "{config.clip_l_path}"',
            f't5xxl = "{config.t5xxl_path}"',
            "",
            "[network_arguments]",
            f'network_module = "{KOHYA_NETWORK_MODULES[KohyaModelType.FLUX]}"',
            f"network_dim = {config.network_dim}",
            f"network_alpha = {config.network_alpha}",
            "",
            "[optimizer_arguments]",
            f'optimizer_type = "{config.optimizer}"',
            f"learning_rate = {config.learning_rate}",
            "",
            "[training_arguments]",
            f'output_dir = "{config.output_dir}"',
            f'output_name = "{output_name}"',
            'save_model_as = "safetensors"',
            f"max_train_steps = {config.max_train_steps}",
            f'mixed_precision = "{config.mixed_precision}"',
            f"gradient_checkpointing = {str(config.gradient_checkpointing).lower()}",
            f"gradient_accumulation_steps = {config.gradient_accumulation}",
            f"seed = {config.seed}",
            f"save_every_n_steps = {config.save_every_n_steps}",
            "cache_latents = true",
            "cache_latents_to_disk = true",
            "cache_text_encoder_outputs = true",
            "cache_text_encoder_outputs_to_disk = true",
            "fp8_base = true",
            "",
            "[flux_arguments]",
            f"blocks_to_swap = {blocks_to_swap}",
            f"t5xxl_max_token_length = {t5xxl_max_token_length}",
            "guidance_scale = 1.0",
            "",
            "[dataset]",
            f'dataset_config = "{dataset_config_path}"',
        ]

        # Add sample section if enabled
        lines.extend(self._build_sample_section(config, sample_prompts_path))
        lines.append("")

        return "\n".join(lines)

    def _build_sdxl_toml(
        self,
        config: KohyaTrainingConfig,
        preset_config: Dict[str, Any],
        dataset_config_path: str,
        sample_prompts_path: Optional[str] = None
    ) -> str:
        """Build TOML for SDXL LoRA training."""
        output_name = f"cg_{config.character_name}"

        lines = [
            "# Kohya SDXL LoRA Training Configuration",
            f"# Generated for: {config.character_name}",
            f"# Trigger word: {config.trigger_word}",
            "",
            "[model_arguments]",
            f'pretrained_model_name_or_path = "{config.model_path}"',
        ]

        # VAE is optional for SDXL (often embedded in checkpoint)
        if config.vae_path:
            lines.append(f'vae = "{config.vae_path}"')

        lines += [
            "",
            "[network_arguments]",
            f'network_module = "{KOHYA_NETWORK_MODULES[KohyaModelType.SDXL]}"',
            f"network_dim = {config.network_dim}",
            f"network_alpha = {config.network_alpha}",
            "network_train_unet_only = true",  # Required when caching text encoder outputs
            "",
            "[optimizer_arguments]",
            f'optimizer_type = "{config.optimizer}"',
            f"learning_rate = {config.learning_rate}",
            "",
            "[training_arguments]",
            f'output_dir = "{config.output_dir}"',
            f'output_name = "{output_name}"',
            'save_model_as = "safetensors"',
            f"max_train_steps = {config.max_train_steps}",
            f'mixed_precision = "{config.mixed_precision}"',
            f"gradient_checkpointing = {str(config.gradient_checkpointing).lower()}",
            f"gradient_accumulation_steps = {config.gradient_accumulation}",
            f"seed = {config.seed}",
            f"save_every_n_steps = {config.save_every_n_steps}",
            "cache_latents = true",
            "cache_latents_to_disk = true",
            "cache_text_encoder_outputs = true",
            "cache_text_encoder_outputs_to_disk = true",
            "",
            "[dataset]",
            f'dataset_config = "{dataset_config_path}"',
        ]

        # Add sample section if enabled
        lines.extend(self._build_sample_section(config, sample_prompts_path))
        lines.append("")

        return "\n".join(lines)

    def _build_sd3_toml(
        self,
        config: KohyaTrainingConfig,
        preset_config: Dict[str, Any],
        dataset_config_path: str,
        sample_prompts_path: Optional[str] = None
    ) -> str:
        """Build TOML for SD3 LoRA training."""
        output_name = f"cg_{config.character_name}"
        blocks_to_swap = preset_config.get("blocks_to_swap", 10)
        t5xxl_max_token_length = preset_config.get("t5xxl_max_token_length", 256)

        lines = [
            "# Kohya SD3 LoRA Training Configuration",
            f"# Generated for: {config.character_name}",
            f"# Trigger word: {config.trigger_word}",
            "",
            "[model_arguments]",
            f'pretrained_model_name_or_path = "{config.model_path}"',
        ]

        # SD3 has optional separate text encoders (can be in checkpoint)
        if config.clip_l_path:
            lines.append(f'clip_l = "{config.clip_l_path}"')
        if config.clip_g_path:
            lines.append(f'clip_g = "{config.clip_g_path}"')
        if config.t5xxl_path:
            lines.append(f't5xxl = "{config.t5xxl_path}"')
        if config.vae_path:
            lines.append(f'vae = "{config.vae_path}"')

        lines += [
            "",
            "[network_arguments]",
            f'network_module = "{KOHYA_NETWORK_MODULES[KohyaModelType.SD3]}"',
            f"network_dim = {config.network_dim}",
            f"network_alpha = {config.network_alpha}",
            "network_train_unet_only = true",  # Required when caching text encoder outputs
            "",
            "[optimizer_arguments]",
            f'optimizer_type = "{config.optimizer}"',
            f"learning_rate = {config.learning_rate}",
            "",
            "[training_arguments]",
            f'output_dir = "{config.output_dir}"',
            f'output_name = "{output_name}"',
            'save_model_as = "safetensors"',
            f"max_train_steps = {config.max_train_steps}",
            f'mixed_precision = "{config.mixed_precision}"',
            f"gradient_checkpointing = {str(config.gradient_checkpointing).lower()}",
            f"gradient_accumulation_steps = {config.gradient_accumulation}",
            f"seed = {config.seed}",
            f"save_every_n_steps = {config.save_every_n_steps}",
            "cache_latents = true",
            "cache_latents_to_disk = true",
            "cache_text_encoder_outputs = true",
            "cache_text_encoder_outputs_to_disk = true",
            "fp8_base = true",
            "",
            "[sd3_arguments]",
            f"blocks_to_swap = {blocks_to_swap}",
            f"t5xxl_max_token_length = {t5xxl_max_token_length}",
            "",
            "[dataset]",
            f'dataset_config = "{dataset_config_path}"',
        ]

        # Add sample section if enabled
        lines.extend(self._build_sample_section(config, sample_prompts_path))
        lines.append("")

        return "\n".join(lines)
