import os

from dotenv import load_dotenv

DEFAULT_PASSWORD = "cable2026"


def get_app_password() -> str:
    load_dotenv()
    return os.getenv("APP_PASSWORD") or DEFAULT_PASSWORD


def password_ok(entered: str) -> bool:
    return (entered or "") == get_app_password()
