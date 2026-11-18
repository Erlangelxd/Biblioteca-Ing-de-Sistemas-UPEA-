"""Configuración por entornos. Lo sensible se lee de variables de entorno."""
import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INSTANCE = RAIZ / "instance"


def _clave_secreta():
    """SECRET_KEY del entorno; si no existe, se genera una vez en instance/."""
    clave = os.environ.get("SECRET_KEY")
    if clave:
        return clave
    INSTANCE.mkdir(exist_ok=True)
    archivo = INSTANCE / "secret_key"
    if not archivo.exists():
        archivo.write_text(secrets.token_hex(32))
    return archivo.read_text().strip()


def _bool(nombre, defecto="0"):
    return os.environ.get(nombre, defecto).lower() in ("1", "true", "si", "sí", "yes")


def _uri_base_datos():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    ruta = os.environ.get("BIBLIOTECA_DB", str(INSTANCE / "biblioteca.sqlite3"))
    return "sqlite:///" + ruta


class Config:
    SECRET_KEY = _clave_secreta()
    SQLALCHEMY_DATABASE_URI = _uri_base_datos()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"connect_args": {"check_same_thread": False}}
        if SQLALCHEMY_DATABASE_URI.startswith("sqlite")
        else {}
    )

    DEBUG = _bool("FLASK_DEBUG")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("COOKIE_SEGURA")  # poner 1 al publicar con HTTPS

    # Reglas de la biblioteca (supuestas: confirmar con la encargada).
    DIAS_PRESTAMO_EXTERNO = int(os.environ.get("DIAS_PRESTAMO_EXTERNO", 7))
    MAX_PRESTAMOS_EXTERNOS = int(os.environ.get("MAX_PRESTAMOS_EXTERNOS", 2))
    MAX_RENOVACIONES = int(os.environ.get("MAX_RENOVACIONES", 1))

    CATALOGO_PUBLICO = _bool("CATALOGO_PUBLICO", "1")
    MAX_INTENTOS = 5
    MINUTOS_BLOQUEO = 5
    POR_PAGINA = 15


class DevelopmentConfig(Config):
    DEBUG = _bool("FLASK_DEBUG", "1")


class TestingConfig(Config):
    TESTING = True
    DEBUG = False


class ProductionConfig(Config):
    DEBUG = False


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
