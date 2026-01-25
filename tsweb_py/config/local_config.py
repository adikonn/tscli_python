"""Local configuration management (.tsweb_py.local)."""

import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict, field

from ..client.models import Problem, Compiler


@dataclass
class LocalConfig:
    """
    Local configuration for contest-specific settings.
    Stored at .tsweb_py.local in project directory.
    Note: Contest ID is stored in session cookies, not here.
    """

    default_lang: int = 0
    problems: List[Problem] = field(default_factory=list)
    compilers: List[Compiler] = field(default_factory=list)

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
                # Convert problem and compiler dicts to objects
                if "problems" in data:
                    data["problems"] = [Problem(**p) for p in data["problems"]]
                if "compilers" in data:
                    data["compilers"] = [Compiler(**c) for c in data["compilers"]]
                return cls(**data)
        except (json.JSONDecodeError, IOError, TypeError):
            return None

    def save(self, path: Optional[Path] = None) -> None:
        """Save local config to file."""
        if path is None:
            path = Path.cwd() / ".tsweb_py.local"

        # Convert to dict and handle nested dataclasses
        data = {
            "default_lang": self.default_lang,
            "problems": [asdict(p) for p in self.problems],
            "compilers": [asdict(c) for c in self.compilers],
        }

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

    def get_compiler(self) -> Optional[Compiler]:
        """Get the default compiler."""
        if 0 <= self.default_lang < len(self.compilers):
            return self.compilers[self.default_lang]
        return None
