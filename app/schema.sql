-- Esquema de la base de datos (SQLite).
-- Corresponde al modelo relacional final del Capítulo III (Tabla 13) y al diccionario de datos.
-- Las diferencias con el documento (campo "activo", índices y restricciones) están en docs/05_observaciones.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_usuario  TEXT    NOT NULL UNIQUE CHECK (length(nombre_usuario) BETWEEN 3 AND 30),
    contrasena      TEXT    NOT NULL,                      -- hash (werkzeug), nunca texto simple (RNF02)
    rol             TEXT    NOT NULL DEFAULT 'consulta' CHECK (rol IN ('administrador','consulta')),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1))
);

CREATE TABLE IF NOT EXISTS area_tematica (
    id_area   INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL UNIQUE CHECK (length(nombre) <= 60)
);

CREATE TABLE IF NOT EXISTS tutor (
    id_tutor  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL UNIQUE CHECK (length(nombre) <= 80)
);

CREATE TABLE IF NOT EXISTS autor (
    id_autor  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL CHECK (length(nombre) <= 80),
    ci        TEXT NOT NULL DEFAULT '' CHECK (length(ci) <= 15)
);

CREATE TABLE IF NOT EXISTS trabajo_grado (
    id_trabajo            INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo                TEXT    NOT NULL CHECK (length(titulo) <= 250),
    resumen               TEXT    NOT NULL DEFAULT '',
    gestion               INTEGER NOT NULL CHECK (gestion BETWEEN 1980 AND 2100),
    modalidad             TEXT    NOT NULL CHECK (modalidad IN ('tesis','proyecto','dirigido')),
    fecha_recepcion       TEXT    NOT NULL,                -- AAAA-MM-DD
    cd_entregado          INTEGER NOT NULL DEFAULT 0 CHECK (cd_entregado IN (0,1)),
    autoriza_publicacion  INTEGER NOT NULL DEFAULT 0 CHECK (autoriza_publicacion IN (0,1)),
    id_area               INTEGER REFERENCES area_tematica(id_area) ON DELETE SET NULL,
    id_tutor              INTEGER REFERENCES tutor(id_tutor) ON DELETE SET NULL,
    activo                INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1))   -- baja lógica (RF04)
);
-- RNF05: no se permiten trabajos duplicados (mismo título y gestión)
CREATE UNIQUE INDEX IF NOT EXISTS ux_trabajo_titulo_gestion ON trabajo_grado (lower(titulo), gestion);
CREATE INDEX IF NOT EXISTS ix_trabajo_area ON trabajo_grado (id_area);
CREATE INDEX IF NOT EXISTS ix_trabajo_gestion ON trabajo_grado (gestion);

CREATE TABLE IF NOT EXISTS trabajo_autor (
    id_trabajo  INTEGER NOT NULL REFERENCES trabajo_grado(id_trabajo) ON DELETE CASCADE,
    id_autor    INTEGER NOT NULL REFERENCES autor(id_autor) ON DELETE CASCADE,
    PRIMARY KEY (id_trabajo, id_autor)
);

CREATE TABLE IF NOT EXISTS ejemplar (
    id_ejemplar  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_trabajo   INTEGER NOT NULL REFERENCES trabajo_grado(id_trabajo) ON DELETE CASCADE,
    codigo       TEXT NOT NULL UNIQUE CHECK (length(codigo) <= 20),
    ubicacion    TEXT NOT NULL CHECK (length(ubicacion) <= 60),
    estado       TEXT NOT NULL DEFAULT 'disponible'
                 CHECK (estado IN ('disponible','en_consulta','en_prestamo','baja'))
);
CREATE INDEX IF NOT EXISTS ix_ejemplar_trabajo ON ejemplar (id_trabajo);

CREATE TABLE IF NOT EXISTS solicitante (
    id_solicitante  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL CHECK (length(nombre) <= 80),
    ci              TEXT NOT NULL UNIQUE CHECK (length(ci) <= 15),
    matricula       TEXT NOT NULL DEFAULT '' CHECK (length(matricula) <= 15),
    tipo            TEXT NOT NULL DEFAULT 'estudiante' CHECK (tipo IN ('estudiante','docente')),
    telefono        TEXT NOT NULL DEFAULT '' CHECK (length(telefono) <= 15)
);
CREATE INDEX IF NOT EXISTS ix_solicitante_matricula ON solicitante (matricula);

CREATE TABLE IF NOT EXISTS prestamo (
    id_prestamo                INTEGER PRIMARY KEY AUTOINCREMENT,
    id_ejemplar                INTEGER NOT NULL REFERENCES ejemplar(id_ejemplar),
    id_solicitante             INTEGER NOT NULL REFERENCES solicitante(id_solicitante),
    id_usuario                 INTEGER NOT NULL REFERENCES usuario(id_usuario),
    tipo                       TEXT NOT NULL DEFAULT 'interno' CHECK (tipo IN ('interno','externo')),
    garantia                   TEXT NOT NULL DEFAULT 'ci' CHECK (garantia IN ('ci','matricula','ninguna')),
    fecha_prestamo             TEXT NOT NULL,
    fecha_devolucion_prevista  TEXT NOT NULL,
    fecha_devolucion_real      TEXT,
    renovaciones               INTEGER NOT NULL DEFAULT 0 CHECK (renovaciones >= 0),
    estado                     TEXT NOT NULL DEFAULT 'vigente' CHECK (estado IN ('vigente','devuelto'))
                               -- "vencido" no se guarda: se calcula (vigente y fecha prevista pasada)
);
CREATE INDEX IF NOT EXISTS ix_prestamo_estado ON prestamo (estado, fecha_devolucion_prevista);
CREATE INDEX IF NOT EXISTS ix_prestamo_solicitante ON prestamo (id_solicitante);
CREATE INDEX IF NOT EXISTS ix_prestamo_ejemplar ON prestamo (id_ejemplar);
-- Un ejemplar no puede tener dos préstamos vigentes a la vez (RNF05)
CREATE UNIQUE INDEX IF NOT EXISTS ux_prestamo_ejemplar_vigente ON prestamo (id_ejemplar) WHERE estado = 'vigente';
