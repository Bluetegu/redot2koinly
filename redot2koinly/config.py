"""Configuration loader and defaults."""
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    input_path: str = "data"
    output_file: str = "redotpay.csv"
    timezone: str = "Asia/Jerusalem"
    year: int = 2025
    # logging
    debug_level: str = "DEBUG"
    log_file: str = "redot2koinly.log"
    log_max_bytes: int = 1000000
    log_backup_count: int = 5


def load_config(path: Optional[str] = None) -> Config:
    cfg = Config()
    if not path:
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
    except Exception:
        # Fail softly; caller may override via CLI
        pass
    return cfg
