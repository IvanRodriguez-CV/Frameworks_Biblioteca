import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(int(default))).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


DEBUG = env_bool("DEBUG", False)
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("SECRET_KEY debe configurarse cuando DEBUG está desactivado.")
    SECRET_KEY = "development-only-not-for-production-change-this-key"
if not DEBUG and (
    len(SECRET_KEY) < 32
    or SECRET_KEY
    in {
        "development-only-change-before-production",
        "development-only-not-for-production-change-this-key",
    }
):
    raise RuntimeError(
        "SECRET_KEY debe ser único, no usar la clave de ejemplo y tener al menos 32 caracteres."
    )

ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.environ.get("REFRESH_TOKEN_DAYS", "1"))
if ACCESS_TOKEN_MINUTES < 1 or REFRESH_TOKEN_DAYS < 1:
    raise RuntimeError("La duración de los tokens debe ser mayor que cero.")

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").strip().lower()
if DB_ENGINE == "sqlite":
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'biblioteca.db').as_posix()}"
    )
    CONNECT_ARGS = {"check_same_thread": False}
elif DB_ENGINE in {"mysql", "mariadb"}:
    database = os.environ.get("DB_NAME", "").strip()
    username = os.environ.get("DB_USER", "").strip()
    password = os.environ.get("DB_PASSWORD", "")
    host = os.environ.get("DB_HOST", "").strip()
    port = os.environ.get("DB_PORT", "3306").strip()
    if not all((database, username, host)):
        raise RuntimeError("DB_NAME, DB_USER y DB_HOST son obligatorios para MySQL.")
    DATABASE_URL = (
        f"mysql+pymysql://{quote_plus(username)}:{quote_plus(password)}@"
        f"{host}:{port}/{quote_plus(database)}?charset=utf8mb4"
    )
    ssl_ca = os.environ.get("DB_SSL_CA", "").strip()
    CONNECT_ARGS = {"ssl": {"ca": ssl_ca}} if ssl_ca else {}
else:
    raise RuntimeError("DB_ENGINE debe ser sqlite, mysql o mariadb.")

configured_database_url = os.environ.get("DATABASE_URL", "").strip()
if configured_database_url:
    DATABASE_URL = configured_database_url

PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
