# Arquitectura del sistema

El sistema es un **monolito modular** construido con Flask. Un solo proceso y una sola base de datos, pero con responsabilidades separadas en capas y módulos independientes. La intención es que cada proceso del Capítulo III (usuarios, trabajos, solicitantes, préstamos, reportes) se pueda leer, probar y modificar sin tocar los demás.

## 1. Capas

```
Petición HTTP
     │
     ▼
blueprints/          Rutas, permisos, formularios y respuestas
     │
     ▼
services/            Reglas de negocio y consultas
     │
     ▼
models/  +  domain/  Entidades ORM y construcción de agregados
     │
     ▼
extensions.db        SQLAlchemy / SQLite
```

| Capa | Responsabilidad | No debe hacer |
|---|---|---|
| `app/blueprints/` | Recibir la petición, validar permisos, leer el formulario, llamar al servicio y renderizar o redirigir. | Consultas SQL complejas ni reglas de negocio. |
| `app/services/` | Aplicar las reglas del negocio, abrir transacciones y lanzar `ErrorNegocio` cuando algo no se cumple. | Conocer `request`, `flash` o plantillas. |
| `app/models/` | Definir tablas, columnas, relaciones, restricciones e índices. | Decidir reglas de préstamo o de baja. |
| `app/domain/` | Objetos de dominio que no son tablas; en este proyecto, el Builder del trabajo de grado. | Acceder a la base de datos. |
| `app/validacion.py` | Validar la forma de los formularios y normalizar sus datos. | Consultar la base. |
| `app/utilidades.py` | Paginación, estado calculado y adaptadores para las plantillas. | Persistir cambios. |
| `app/seguridad.py` | Sesión, roles, CSRF y bloqueo por intentos fallidos. | Reglas de la biblioteca. |

La dependencia siempre apunta hacia abajo: los blueprints pueden importar servicios, los servicios pueden importar modelos y dominio, y los modelos solo dependen de `extensions.py`. Ningún modelo importa un blueprint.

## 2. Estructura de carpetas

```
app/
├── __init__.py          # create_app(): Factory Method
├── extensions.py        # db, Base, norm() y PRAGMA foreign_keys
├── config.py            # Config, Development, Testing, Production y CONFIGS
├── seguridad.py
├── validacion.py
├── utilidades.py
├── cli.py
├── seed.py
├── domain/
│   └── builders.py
├── models/
│   ├── usuario.py
│   ├── catalogo.py      # AreaTematica, Tutor, Autor
│   ├── trabajo.py       # TrabajoGrado, Ejemplar, trabajo_autor
│   ├── solicitante.py
│   └── prestamo.py
├── services/
│   ├── base.py          # ErrorNegocio, transaccion()
│   ├── usuarios.py
│   ├── trabajos.py
│   ├── solicitantes.py
│   ├── prestamos.py
│   └── reportes.py
└── blueprints/
    ├── main/
    ├── auth/
    ├── trabajos/
    ├── solicitantes/
    ├── prestamos/
    └── reportes/
```

Cada blueprint vive en su propia carpeta con un `__init__.py` que exporta `bp` y un `routes.py` con las vistas. Todos se registran en `app/blueprints/__init__.py`.

## 3. Factory Method: `create_app`

`app/__init__.py` expone:

```python
create_app(config_name=None, overrides=None)
```

La función:

1. Crea la instancia de `Flask`.
2. Elige la clase de configuración (`development`, `testing` o `production`) según `config_name` o la variable `APP_ENV`.
3. Aplica `overrides`, lo que permite a las pruebas usar una base temporal sin tocar el entorno.
4. Inicializa `db` con `db.init_app(app)`.
5. Registra los blueprints y los comandos CLI.
6. Instala los ganchos: carga del usuario, verificación CSRF, cabeceras de seguridad, contexto de plantillas, filtro de fechas y páginas de error.

Ventajas del patrón en este proyecto:

- Las pruebas construyen una aplicación aislada con su propia base SQLite.
- Producción y desarrollo comparten el mismo código y cambian solo la configuración.
- El registro de módulos queda en un único lugar.

Ejemplo:

```python
from app import create_app

app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": "sqlite:////tmp/prueba.sqlite3"})
```

## 4. Builder: `TrabajoGradoBuilder`

Registrar un trabajo de grado combina datos simples (título, gestión, modalidad) con relaciones (área, tutor, autores) y una colección de ejemplares cuyos códigos dependen del identificador del trabajo. El Builder separa esa construcción del guardado:

```python
constructor = (
    TrabajoGradoBuilder(titulo, gestion, modalidad, fecha_recepcion)
    .con_resumen(resumen)
    .con_cd(True)
    .con_autorizacion(True)
    .con_area(area)
    .con_tutor(tutor)
    .con_autores(autores)
    .con_ejemplares(2, "Estante 1")
)

trabajo = constructor.construir()          # objeto aún no persistido
db.session.add(trabajo)
db.session.flush()                         # asigna id_trabajo
trabajo.ejemplares.extend(constructor.crear_ejemplares(trabajo.id_trabajo))
```

El servicio `registrar_trabajo` es el único que usa el Builder. La vista no conoce ni el orden de construcción ni la generación de códigos.

## 5. Transacciones y errores de negocio

Los servicios usan un contexto común:

```python
from .base import ErrorNegocio, transaccion

with transaccion():
    ...
```

- `transaccion()` hace `commit` al salir y `rollback` ante cualquier excepción.
- `ErrorNegocio` representa un rechazo esperado (por ejemplo, «ese ejemplar no está disponible») y los blueprints lo convierten en un mensaje para la persona usuaria.
- Las restricciones de la base siguen actuando como última defensa: el índice único parcial `ux_prestamo_ejemplar_vigente` impide dos préstamos vigentes del mismo ejemplar aunque falle la validación de la aplicación.

## 6. Flujo de una petición

Ejemplo: registrar un préstamo.

```
POST /prestamos/nuevo
  └─ before_request: cargar_usuario() + verificar_csrf()
  └─ blueprints/prestamos/routes.py::nuevo()
       └─ services/prestamos.py::registrar_prestamo()
            ├─ buscar_por_documento()      (services/solicitantes.py)
            ├─ valida límite de externos
            ├─ verifica disponibilidad del ejemplar
            ├─ crea Prestamo y cambia estado del Ejemplar
            └─ transaccion() → commit
       └─ redirect → /prestamos/<id>/comprobante
```

## 7. Base de datos

- Los modelos de `app/models/` son la **única fuente del esquema**. `flask --app wsgi init-db` ejecuta `db.create_all()`.
- `app/extensions.py` registra la función SQLite `norm()` (minúsculas y sin tildes) y activa `PRAGMA foreign_keys = ON` en cada conexión.
- Los índices y restricciones viven junto al modelo que protegen: `CheckConstraint`, `unique=True` e `Index`, incluidos los índices por expresión y el índice único parcial de préstamos.

## 8. Nombres y compatibilidad

- Se mantienen los nombres de endpoints (`auth.login`, `trabajos.lista`, `prestamos.nuevo`, `reportes.ver`, etc.) y las rutas originales para no romper plantillas ni enlaces.
- El dominio y los mensajes están en español; las capas técnicas usan nombres en inglés cuando son términos estándar (`services`, `blueprints`, `models`).
- Los procesos nuevos deben crear su carpeta en `blueprints/`, su servicio en `services/` y, si necesita tablas, sus modelos en `models/`.
