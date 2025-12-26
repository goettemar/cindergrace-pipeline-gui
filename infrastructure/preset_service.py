"""Preset management service for prompt building."""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from infrastructure.logger import get_logger

logger = get_logger(__name__)


def get_preset_db_path() -> str:
    """Return path to presets database."""
    base_dir = Path(__file__).parent.parent
    return str(base_dir / "data" / "presets.db")


class PresetService:
    """Manage prompt presets for different generation phases."""

    # Preset categories and their phases
    CATEGORIES = {
        # Universal (apply to all models)
        "style": "universal",
        "lighting": "universal",
        "mood": "universal",
        "time_of_day": "universal",
        # Keyframe/Image specific (Flux)
        "composition": "keyframe",
        "color_grade": "keyframe",
        # Video specific (Wan)
        "camera": "video",
        "motion": "video",
    }

    def __init__(self, db_path: Optional[str] = None, auto_seed: bool = True):
        self.db_path = db_path or get_preset_db_path()
        self._ensure_db()
        # Auto-seed default presets if database is empty
        if auto_seed and self.get_preset_count() == 0:
            self.seed_default_presets()

    def _ensure_db(self) -> None:
        """Create database and tables if not exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Presets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                name_de TEXT NOT NULL,
                name_en TEXT,
                prompt_text TEXT NOT NULL,
                phase TEXT NOT NULL DEFAULT 'universal',
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                UNIQUE(category, key)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_presets_category
            ON prompt_presets(category, phase, is_active)
        """)

        # Model profiles table (for future model-specific settings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT UNIQUE NOT NULL,
                model_type TEXT NOT NULL,
                workflow_category TEXT,
                supports_negative_prompt INTEGER DEFAULT 1,
                supports_camera_control INTEGER DEFAULT 0,
                supports_motion INTEGER DEFAULT 0,
                cfg_default REAL DEFAULT 7.0,
                steps_default INTEGER DEFAULT 20,
                max_duration REAL,
                notes TEXT
            )
        """)

        conn.commit()
        conn.close()
        logger.debug(f"Preset-Datenbank initialisiert: {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_presets_by_category(self, category: str) -> List[Dict]:
        """Get all active presets for a category."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT key, name_de, name_en, prompt_text, phase
            FROM prompt_presets
            WHERE category = ? AND is_active = 1
            ORDER BY sort_order, name_de
        """, (category,))

        presets = []
        for row in cursor.fetchall():
            presets.append({
                "key": row["key"],
                "name_de": row["name_de"],
                "name_en": row["name_en"],
                "prompt_text": row["prompt_text"],
                "phase": row["phase"],
            })

        conn.close()
        return presets

    def get_presets_by_phase(self, phase: str) -> Dict[str, List[Dict]]:
        """Get all presets for a phase, grouped by category."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT category, key, name_de, name_en, prompt_text
            FROM prompt_presets
            WHERE phase = ? AND is_active = 1
            ORDER BY category, sort_order, name_de
        """, (phase,))

        result = {}
        for row in cursor.fetchall():
            category = row["category"]
            if category not in result:
                result[category] = []
            result[category].append({
                "key": row["key"],
                "name_de": row["name_de"],
                "name_en": row["name_en"],
                "prompt_text": row["prompt_text"],
            })

        conn.close()
        return result

    def get_dropdown_choices(self, category: str, include_none: bool = True) -> List[tuple]:
        """Get presets as dropdown choices (label, value) tuples."""
        presets = self.get_presets_by_category(category)
        choices = []

        if include_none:
            choices.append(("-- Keine --", "none"))

        for preset in presets:
            choices.append((preset["name_de"], preset["key"]))

        return choices

    def get_prompt_text(self, category: str, key: str) -> Optional[str]:
        """Get the prompt text for a specific preset."""
        if not key or key == "none":
            return None

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT prompt_text
            FROM prompt_presets
            WHERE category = ? AND key = ? AND is_active = 1
        """, (category, key))

        row = cursor.fetchone()
        conn.close()

        return row["prompt_text"] if row else None

    def build_prompt(
        self,
        base_prompt: str,
        style: Optional[str] = None,
        lighting: Optional[str] = None,
        mood: Optional[str] = None,
        time_of_day: Optional[str] = None,
        camera: Optional[str] = None,
        motion: Optional[str] = None,
    ) -> str:
        """Build a complete prompt from base + presets."""
        parts = [base_prompt.strip()]

        # Add universal presets
        for category, key in [
            ("style", style),
            ("lighting", lighting),
            ("mood", mood),
            ("time_of_day", time_of_day),
        ]:
            text = self.get_prompt_text(category, key)
            if text:
                parts.append(text)

        # Add video-specific presets
        for category, key in [
            ("camera", camera),
            ("motion", motion),
        ]:
            text = self.get_prompt_text(category, key)
            if text:
                parts.append(text)

        return ", ".join(parts)

    def add_preset(
        self,
        category: str,
        key: str,
        name_de: str,
        prompt_text: str,
        phase: str = "universal",
        name_en: Optional[str] = None,
        sort_order: int = 0,
    ) -> bool:
        """Add or update a preset."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO prompt_presets
                (category, key, name_de, name_en, prompt_text, phase, sort_order, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (category, key, name_de, name_en, prompt_text, phase, sort_order))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to add preset: {e}")
            conn.close()
            return False

    def seed_default_presets(self) -> int:
        """Seed the database with default presets. Returns count of added presets."""
        presets = [
            # === STYLE (Universal) ===
            ("style", "cinematic", "Filmisch", "cinematic composition, film grain, anamorphic bokeh, movie still", "universal", 1),
            ("style", "photorealistic", "Fotorealistisch", "photorealistic, hyperrealistic, 8k detailed, sharp focus", "universal", 2),
            ("style", "anime", "Anime", "anime style, cel shaded, vibrant colors, japanese animation", "universal", 3),
            ("style", "oil_painting", "Ölgemälde", "oil painting style, visible brushstrokes, artistic, classical", "universal", 4),
            ("style", "watercolor", "Aquarell", "watercolor painting, soft edges, artistic, delicate", "universal", 5),
            ("style", "3d_render", "3D Render", "3D render, octane render, unreal engine, CGI", "universal", 6),
            ("style", "vintage", "Vintage", "vintage film, 1970s aesthetic, film grain, nostalgic", "universal", 7),
            ("style", "noir", "Film Noir", "film noir style, black and white, high contrast, dramatic shadows", "universal", 8),

            # === LIGHTING (Universal) ===
            ("lighting", "golden_hour", "Goldene Stunde", "golden hour lighting, warm sunset tones, soft shadows", "universal", 1),
            ("lighting", "blue_hour", "Blaue Stunde", "blue hour lighting, twilight, cool tones, serene", "universal", 2),
            ("lighting", "dramatic", "Dramatisch", "dramatic lighting, chiaroscuro, high contrast, deep shadows", "universal", 3),
            ("lighting", "soft", "Weich", "soft diffused lighting, even illumination, gentle", "universal", 4),
            ("lighting", "neon", "Neon", "neon lighting, cyberpunk, colorful rim lights, urban night", "universal", 5),
            ("lighting", "natural", "Natürlich", "natural daylight, realistic lighting, outdoor", "universal", 6),
            ("lighting", "studio", "Studio", "studio lighting, professional, three-point lighting", "universal", 7),
            ("lighting", "backlit", "Gegenlicht", "backlit, silhouette, rim light, atmospheric", "universal", 8),
            ("lighting", "volumetric", "Volumetrisch", "volumetric lighting, god rays, atmospheric fog, ethereal", "universal", 9),

            # === MOOD (Universal) ===
            ("mood", "peaceful", "Friedlich", "peaceful atmosphere, calm, serene, tranquil", "universal", 1),
            ("mood", "dramatic", "Dramatisch", "dramatic mood, intense, powerful, emotional", "universal", 2),
            ("mood", "mysterious", "Mysteriös", "mysterious atmosphere, enigmatic, intriguing, foggy", "universal", 3),
            ("mood", "joyful", "Fröhlich", "joyful mood, happy, bright, cheerful", "universal", 4),
            ("mood", "melancholic", "Melancholisch", "melancholic mood, sad, thoughtful, nostalgic", "universal", 5),
            ("mood", "tense", "Angespannt", "tense atmosphere, suspenseful, anxious, thriller", "universal", 6),
            ("mood", "romantic", "Romantisch", "romantic mood, intimate, warm, loving", "universal", 7),
            ("mood", "epic", "Episch", "epic atmosphere, grand, majestic, awe-inspiring", "universal", 8),

            # === TIME OF DAY (Universal) ===
            ("time_of_day", "sunrise", "Sonnenaufgang", "sunrise, early morning, dawn light, fresh", "universal", 1),
            ("time_of_day", "morning", "Morgen", "morning light, bright, clear, fresh start", "universal", 2),
            ("time_of_day", "noon", "Mittag", "midday sun, harsh light, clear sky", "universal", 3),
            ("time_of_day", "afternoon", "Nachmittag", "afternoon light, warm, relaxed", "universal", 4),
            ("time_of_day", "sunset", "Sonnenuntergang", "sunset, dusk, orange sky, warm colors", "universal", 5),
            ("time_of_day", "night", "Nacht", "nighttime, dark, moonlight, stars", "universal", 6),
            ("time_of_day", "overcast", "Bewölkt", "overcast sky, diffused light, cloudy, soft shadows", "universal", 7),

            # === COMPOSITION (Keyframe/Flux) ===
            ("composition", "rule_of_thirds", "Drittel-Regel", "rule of thirds composition, balanced framing", "keyframe", 1),
            ("composition", "centered", "Zentriert", "centered composition, symmetrical, balanced", "keyframe", 2),
            ("composition", "wide_shot", "Totale", "wide shot, establishing shot, full scene visible", "keyframe", 3),
            ("composition", "close_up", "Nahaufnahme", "close-up shot, detailed, intimate framing", "keyframe", 4),
            ("composition", "low_angle", "Froschperspektive", "low angle shot, looking up, powerful, imposing", "keyframe", 5),
            ("composition", "high_angle", "Vogelperspektive", "high angle shot, looking down, overview", "keyframe", 6),
            ("composition", "dutch_angle", "Schräge", "dutch angle, tilted frame, dynamic, unsettling", "keyframe", 7),

            # === COLOR GRADE (Keyframe/Flux) ===
            ("color_grade", "teal_orange", "Teal & Orange", "teal and orange color grading, cinematic look", "keyframe", 1),
            ("color_grade", "desaturated", "Entsättigt", "desaturated colors, muted tones, subtle", "keyframe", 2),
            ("color_grade", "vibrant", "Lebendig", "vibrant colors, saturated, bold, colorful", "keyframe", 3),
            ("color_grade", "warm", "Warm", "warm color grading, orange tones, cozy", "keyframe", 4),
            ("color_grade", "cool", "Kühl", "cool color grading, blue tones, cold", "keyframe", 5),
            ("color_grade", "bleach_bypass", "Bleach Bypass", "bleach bypass look, high contrast, desaturated highlights", "keyframe", 6),
            ("color_grade", "sepia", "Sepia", "sepia tones, vintage look, brownish", "keyframe", 7),

            # === CAMERA (Video/Wan) ===
            ("camera", "static", "Statisch", "static shot, fixed camera, stable", "video", 1),
            ("camera", "pan_left", "Schwenk links", "smooth pan left, horizontal camera movement", "video", 2),
            ("camera", "pan_right", "Schwenk rechts", "smooth pan right, horizontal camera movement", "video", 3),
            ("camera", "tilt_up", "Neigung hoch", "tilt up, vertical camera movement upward", "video", 4),
            ("camera", "tilt_down", "Neigung runter", "tilt down, vertical camera movement downward", "video", 5),
            ("camera", "dolly_in", "Dolly vor", "slow dolly in, gradual approach, push in", "video", 6),
            ("camera", "dolly_out", "Dolly zurück", "dolly out, pull back, reveal shot", "video", 7),
            ("camera", "tracking", "Tracking", "tracking shot, following subject, lateral movement", "video", 8),
            ("camera", "crane_up", "Kran hoch", "crane shot up, ascending, reveal", "video", 9),
            ("camera", "crane_down", "Kran runter", "crane shot down, descending", "video", 10),
            ("camera", "orbit", "Orbit", "orbital shot, circling around subject, 360 movement", "video", 11),
            ("camera", "handheld", "Handkamera", "handheld camera, slight shake, documentary feel", "video", 12),

            # === MOTION (Video/Wan) ===
            ("motion", "slow_motion", "Zeitlupe", "slow motion, slowed down, dramatic timing", "video", 1),
            ("motion", "normal", "Normal", "normal speed, real-time motion", "video", 2),
            ("motion", "fast_motion", "Zeitraffer", "fast motion, sped up, time-lapse feel", "video", 3),
            ("motion", "subtle", "Subtil", "subtle motion, minimal movement, calm", "video", 4),
            ("motion", "dynamic", "Dynamisch", "dynamic motion, energetic movement, action", "video", 5),
            ("motion", "flowing", "Fließend", "flowing motion, smooth, graceful movement", "video", 6),
        ]

        count = 0
        for preset in presets:
            if self.add_preset(
                category=preset[0],
                key=preset[1],
                name_de=preset[2],
                prompt_text=preset[3],
                phase=preset[4],
                sort_order=preset[5],
            ):
                count += 1

        logger.info(f"{count} Presets in Datenbank eingefügt")
        return count

    def get_preset_count(self) -> int:
        """Get total number of presets in database."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prompt_presets WHERE is_active = 1")
        count = cursor.fetchone()[0]
        conn.close()
        return count


__all__ = ["PresetService", "get_preset_db_path"]
