import os
from dataclasses import dataclass

try:
    from _secrets import get_embedded_credentials
except ImportError:
    def get_embedded_credentials() -> tuple[str, str]:
        return (
            os.environ.get("TOTVS_USER", ""),
            os.environ.get("TOTVS_PASSWORD", ""),
        )


@dataclass
class AppConfig:
    login_url: str = "https://tec.totvshospitalidade.com/"
    username: str = ""
    password: str = ""
    headless: bool = True
    timeout_ms: int = 30000


def load_config() -> AppConfig:
    user, pwd = get_embedded_credentials()
    return AppConfig(
        username=user,
        password=pwd,
        headless=True,
    )
