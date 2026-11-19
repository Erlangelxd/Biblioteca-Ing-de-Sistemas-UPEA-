"""Migraciones ligeras para bases SQLite existentes.

`db.create_all()` crea tablas nuevas, pero no modifica las ya existentes. Este
módulo aplica los cambios mínimos de esquema que no requieren Alembic.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def migrar_modalidad_libro(ruta: str | Path) -> bool:
    """Permite la modalidad «libro» en trabajo_grado conservando los datos.

    SQLite no permite alterar un CHECK con ALTER TABLE, por lo que se
    reconstruye la tabla siguiendo el procedimiento recomendado: crear la nueva,
    copiar las filas, reemplazar la antigua y recrear sus índices.
    Devuelve True si aplicó algún cambio.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return False

    conexion = sqlite3.connect(ruta)
    conexion.isolation_level = None  # control manual de BEGIN/COMMIT
    try:
        fila = conexion.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='trabajo_grado'"
        ).fetchone()
        if not fila or not fila[0]:
            return False

        ddl = fila[0]
        if "'libro'" in ddl:
            return False  # ya migrada

        indices = [
            registro[0]
            for registro in conexion.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name='trabajo_grado' AND sql IS NOT NULL"
            )
            if registro[0]
        ]
        columnas = [
            registro[1] for registro in conexion.execute("PRAGMA table_info(trabajo_grado)")
        ]
        lista_columnas = ", ".join(f'"{columna}"' for columna in columnas)

        nuevo_ddl = ddl.replace(
            "CREATE TABLE trabajo_grado", "CREATE TABLE trabajo_grado_nuevo", 1
        ).replace("'dirigido'", "'dirigido','libro'", 1)
        if "'libro'" not in nuevo_ddl or "trabajo_grado_nuevo" not in nuevo_ddl:
            raise RuntimeError("No se pudo adaptar el esquema de trabajo_grado.")

        conexion.execute("PRAGMA foreign_keys=OFF")
        try:
            conexion.execute("BEGIN")
            conexion.execute(nuevo_ddl)
            conexion.execute(
                f"INSERT INTO trabajo_grado_nuevo ({lista_columnas}) "
                f"SELECT {lista_columnas} FROM trabajo_grado"
            )
            conexion.execute("DROP TABLE trabajo_grado")
            conexion.execute("ALTER TABLE trabajo_grado_nuevo RENAME TO trabajo_grado")
            for sql in indices:
                conexion.execute(sql)
            conexion.execute("COMMIT")
        except Exception:
            try:
                conexion.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conexion.execute("PRAGMA foreign_keys=ON")

        return True
    finally:
        conexion.close()
