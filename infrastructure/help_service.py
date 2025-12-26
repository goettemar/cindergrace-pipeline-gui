"""Help Service - SQLite-basierte Hilfetexte für alle Tabs."""
import sqlite3
from pathlib import Path
from typing import Optional

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class HelpService:
    """Service zum Laden und Bereitstellen von Hilfetexten aus SQLite."""

    def __init__(self, db_path: Optional[str] = None, language: str = "de"):
        """Initialisiert den HelpService.

        Args:
            db_path: Pfad zur SQLite-Datenbank (Standard: data/cindergrace.db)
            language: Sprache für Hilfetexte (Standard: de)
        """
        if db_path is None:
            # Relativ zum Projektverzeichnis
            base_dir = Path(__file__).parent.parent
            db_path = str(base_dir / "data" / "cindergrace.db")

        self.db_path = db_path
        self.language = language
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Erstellt Datenbank und Schema falls nicht vorhanden."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabelle für Hilfetexte
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS help_texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tab TEXT NOT NULL,
                field TEXT NOT NULL,
                text_type TEXT NOT NULL,
                language TEXT DEFAULT 'de',
                content TEXT NOT NULL,
                UNIQUE(tab, field, text_type, language)
            )
        """)

        # Tabelle für Tab-Informationen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tab_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tab TEXT NOT NULL,
                language TEXT DEFAULT 'de',
                title TEXT NOT NULL,
                description TEXT,
                UNIQUE(tab, language)
            )
        """)

        # Index für schnelle Abfragen
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_help_lookup
            ON help_texts(tab, field, language)
        """)

        conn.commit()
        conn.close()
        logger.debug(f"Help-Datenbank initialisiert: {self.db_path}")

    def get_tooltip(self, tab: str, field: str) -> str:
        """Holt Tooltip-Text für ein Feld.

        Args:
            tab: Tab-Bezeichner (z.B. 'project', 'keyframe_generator')
            field: Feld-Bezeichner (z.B. 'project_name', 'prompt')

        Returns:
            Tooltip-Text oder leerer String falls nicht gefunden
        """
        return self._get_text(tab, field, "tooltip")

    def get_modal(self, tab: str, field: str) -> str:
        """Holt Modal-Text für ein Feld.

        Args:
            tab: Tab-Bezeichner
            field: Feld-Bezeichner

        Returns:
            Modal-Text oder leerer String falls nicht gefunden
        """
        return self._get_text(tab, field, "modal")

    def _get_text(self, tab: str, field: str, text_type: str) -> str:
        """Interne Methode zum Abrufen von Texten.

        Args:
            tab: Tab-Bezeichner
            field: Feld-Bezeichner
            text_type: 'tooltip' oder 'modal'

        Returns:
            Text oder leerer String
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Erst in spezifischem Tab suchen
        cursor.execute(
            """
            SELECT content FROM help_texts
            WHERE tab = ? AND field = ? AND text_type = ? AND language = ?
            """,
            (tab, field, text_type, self.language),
        )
        result = cursor.fetchone()

        # Fallback auf 'common' Tab
        if not result:
            cursor.execute(
                """
                SELECT content FROM help_texts
                WHERE tab = 'common' AND field = ? AND text_type = ? AND language = ?
                """,
                (field, text_type, self.language),
            )
            result = cursor.fetchone()

        conn.close()
        return result[0] if result else ""

    def get_tab_info(self, tab: str) -> dict:
        """Holt Tab-Informationen (Titel, Beschreibung).

        Args:
            tab: Tab-Bezeichner

        Returns:
            Dict mit 'title' und 'description' oder leere Werte
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT title, description FROM tab_info
            WHERE tab = ? AND language = ?
            """,
            (tab, self.language),
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            return {"title": result[0], "description": result[1] or ""}
        return {"title": "", "description": ""}

    def get_common(self, key: str) -> dict:
        """Holt gemeinsame Hilfetexte (tooltip + modal).

        Args:
            key: Feld-Bezeichner im 'common' Tab

        Returns:
            Dict mit 'tooltip' und 'modal'
        """
        return {
            "tooltip": self._get_text("common", key, "tooltip"),
            "modal": self._get_text("common", key, "modal"),
        }

    def set_language(self, lang: str) -> None:
        """Setzt die Sprache für Hilfetexte.

        Args:
            lang: Sprachcode (z.B. 'de', 'en')
        """
        self.language = lang
        logger.info(f"Help-Sprache geändert auf: {lang}")

    def add_help_text(
        self,
        tab: str,
        field: str,
        text_type: str,
        content: str,
        language: Optional[str] = None,
    ) -> None:
        """Fügt einen Hilfetext hinzu oder aktualisiert ihn.

        Args:
            tab: Tab-Bezeichner
            field: Feld-Bezeichner
            text_type: 'tooltip' oder 'modal'
            content: Der Hilfetext
            language: Sprache (Standard: aktuelle Sprache)
        """
        lang = language or self.language
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO help_texts (tab, field, text_type, language, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tab, field, text_type, lang, content),
        )

        conn.commit()
        conn.close()
        logger.debug(f"Help-Text hinzugefügt: {tab}.{field}.{text_type} ({lang})")

    def add_tab_info(
        self,
        tab: str,
        title: str,
        description: str = "",
        language: Optional[str] = None,
    ) -> None:
        """Fügt Tab-Informationen hinzu oder aktualisiert sie.

        Args:
            tab: Tab-Bezeichner
            title: Tab-Titel
            description: Tab-Beschreibung
            language: Sprache (Standard: aktuelle Sprache)
        """
        lang = language or self.language
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tab_info (tab, language, title, description)
            VALUES (?, ?, ?, ?)
            """,
            (tab, lang, title, description),
        )

        conn.commit()
        conn.close()
        logger.debug(f"Tab-Info hinzugefügt: {tab} ({lang})")

    def get_all_fields(self, tab: str) -> list[str]:
        """Listet alle Felder eines Tabs auf.

        Args:
            tab: Tab-Bezeichner

        Returns:
            Liste der Feld-Bezeichner
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT DISTINCT field FROM help_texts
            WHERE tab = ? AND language = ?
            ORDER BY field
            """,
            (tab, self.language),
        )
        results = cursor.fetchall()
        conn.close()

        return [r[0] for r in results]


# Singleton-Instanz für einfachen Zugriff
_help_service: Optional[HelpService] = None


def get_help_service(language: str = "de") -> HelpService:
    """Gibt die Singleton-Instanz des HelpService zurück.

    Args:
        language: Sprache (nur beim ersten Aufruf relevant)

    Returns:
        HelpService-Instanz
    """
    global _help_service
    if _help_service is None:
        _help_service = HelpService(language=language)
    return _help_service
