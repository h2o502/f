"""配置管理"""
import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "watch_folder": "",
    "api_url": "https://acmwork.cloud/tokenfactory/v1",
    "api_key": "sk-cs27k7SZJOqGIUBJB46a852c717e4332B5C939078b0c834b",
    "model": "qwen3.6-flash",
    "deep_model": "qwen3.6-plus",
    "auto_rename": False,
    "supported_extensions": [
        ".txt", ".md", ".pdf", ".docx", ".doc", ".xlsx", ".xls",
        ".pptx", ".ppt", ".csv", ".json", ".xml", ".html", ".htm",
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".go",
        ".rs", ".rb", ".php", ".sh", ".bat", ".ps1",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
        ".zip", ".rar", ".7z",
    ],
    "index_db_name": "blackhole_index.db",
}


class Config:
    def __init__(self):
        self.config_dir = Path.home() / ".blackhole"
        self.config_file = self.config_dir / "config.json"
        self._config = {}
        self.load()

    def load(self):
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def update(self, data: dict):
        self._config.update(data)
        self.save()

    @property
    def watch_folder(self) -> str:
        return self._config.get("watch_folder", "")

    @watch_folder.setter
    def watch_folder(self, value: str):
        self._config["watch_folder"] = value
        self.save()

    @property
    def db_path(self) -> Path:
        return self.config_dir / self._config.get("index_db_name", "blackhole_index.db")

    @property
    def all(self) -> dict:
        return self._config.copy()


config = Config()
