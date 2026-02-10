"""Local configuration management (.tsweb_py.local)."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class LocalConfig:
    """
    Local configuration for contest-specific settings.
    Stored at .tsweb_py.local in project directory.
    Stores only the default compiler index.
    """

    default_lang: int = 0

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Optional["LocalConfig"]:
        """
        Load local config from file.
        If path is not specified, searches upward from current directory.
        """
        if path is None:
            path = cls.find_config()

        if path is None or not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return cls(default_lang=data.get("default_lang", 0))
        except (json.JSONDecodeError, IOError, TypeError):
            return None

    def save(self, path: Optional[Path] = None) -> None:
        """Save local config to file."""
        if path is None:
            path = Path.cwd() / ".tsweb_py.local"

        data = {"default_lang": self.default_lang}

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def find_config() -> Optional[Path]:
        """
        Search for .tsweb_py.local starting from current directory,
        walking up to root.
        """
        current = Path.cwd()

        while True:
            config_path = current / ".tsweb_py.local"
            if config_path.exists():
                return config_path

            # Check if we've reached the root
            if current == current.parent:
                return None

            current = current.parent
