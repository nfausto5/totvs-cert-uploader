import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"


@dataclass
class AppConfig:
    login_url: str = "https://tec.totvshospitalidade.com/"
    username: str = ""
    password: str = ""
    headless: bool = False
    persist_session: bool = False
    timeout_ms: int = 30000


def load_config() -> AppConfig:
    if CONFIG_PATH.is_file():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            valid_keys = {f for f in AppConfig.__dataclass_fields__}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            return AppConfig(**filtered)
        except Exception:
            pass
    cfg = AppConfig()
    save_config(cfg)
    return cfg


def save_config(cfg: AppConfig) -> None:
    CONFIG_PATH.write_text(
        json.dumps(asdict(cfg), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
