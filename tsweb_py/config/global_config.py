"""Global configuration management (~/.tsweb_py.global)."""

import json
import pickle
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class GlobalConfig:
    """
    Global configuration storing user credentials and session cookies.
    Stored at ~/.tsweb_py.global
    """

    user: str = ""
    password: str = ""

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "GlobalConfig":
        """Load global config from file."""
        if path is None:
            path = Path.home() / ".tsweb_py.global"

        if not path.exists():
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return cls(user=data.get("user", ""), password=data.get("password", ""))
        except (json.JSONDecodeError, IOError):
            return cls()

    def save(self, path: Optional[Path] = None) -> None:
        """Save global config to file."""
        if path is None:
            path = Path.home() / ".tsweb_py.global"

        data = {"user": self.user, "password": self.password}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def has_credentials(self) -> bool:
        """Check if credentials are stored."""
        return bool(self.user and self.password)

    @staticmethod
    def save_cookies(cookies, path: Optional[Path] = None) -> None:
        """Save cookies using pickle."""
        if path is None:
            path = Path.home() / ".tsweb_py.cookies"

        with open(path, "wb") as f:
            pickle.dump(cookies, f)

    @staticmethod
    def load_cookies(path: Optional[Path] = None):
        """Load cookies using pickle."""
        if path is None:
            path = Path.home() / ".tsweb_py.cookies"

        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError):
            return None
