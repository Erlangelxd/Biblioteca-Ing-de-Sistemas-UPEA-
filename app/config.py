"""Configuración. Todo lo sensible se lee de variables de entorno (RNF10)."""
import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INSTANCE = RAIZ / "instance"


def _clave_secreta():
    """SECRET_KEY del entorno; si no existe, se genera una vez y se guarda en instance/ (no en el código)."""
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


class Config:
    SECRET_KEY = _clave_secreta()
    DATABASE = os.environ.get("BIBLIOTECA_DB", str(INSTANCE / "biblioteca.sqlite3"))
    DEBUG = _bool("FLASK_DEBUG")                          # RNF11: apagado por defecto
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("COOKIE_SEGURA")        # RNF09: poner 1 cuando se publique con HTTPS
    # Reglas de la biblioteca (supuestas: confirmarlas con la encargada)
    DIAS_PRESTAMO_EXTERNO = int(os.environ.get("DIAS_PRESTAMO_EXTERNO", 7))
    MAX_PRESTAMOS_EXTERNOS = int(os.environ.get("MAX_PRESTAMOS_EXTERNOS", 2))
    MAX_RENOVACIONES = int(os.environ.get("MAX_RENOVACIONES", 1))
    # Consulta pública de solo lectura (mejora opcional del anexo de acceso por internet)
    CATALOGO_PUBLICO = _bool("CATALOGO_PUBLICO", "1")
    # Bloqueo temporal tras intentos fallidos de ingreso
    MAX_INTENTOS = 5
    MINUTOS_BLOQUEO = 5
    POR_PAGINA = 15
