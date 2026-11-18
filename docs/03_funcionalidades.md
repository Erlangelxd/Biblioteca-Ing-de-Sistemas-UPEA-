# 3. Funcionalidades

Correspondencia entre los requisitos del Capítulo III, la ruta, el módulo y la prueba automática. Roles: **A** = administrador (encargada), **C** = consulta, **P** = público sin sesión. Todas las rutas que modifican datos son POST y llevan token CSRF.

## 3.1 Requisitos funcionales

| Req. | Funcionalidad | Ruta | Módulo | Rol | Prueba |
|---|---|---|---|---|---|
| RF01 | Iniciar / cerrar sesión | `/login`, `/logout` | `blueprints/auth/` | A, C | test_login_correcto_e_incorrecto, test_bloqueo_por_intentos |
| RF02 | Gestionar usuarios y roles | `/usuarios`, `/usuarios/nuevo`, `/usuarios/<id>/editar`, `/usuarios/<id>/estado` | `blueprints/auth/`, `services/usuarios.py` | A | test_crear_desactivar_usuario |
| RF03 | Registrar trabajo de grado con autores, tutor, área y ejemplares | `/trabajos/nuevo` | `blueprints/trabajos/`, `services/trabajos.py`, `domain/builders.py` | A | test_registro_con_ejemplares_sin_duplicados |
| RF04 | Modificar y dar de baja un trabajo | `/trabajos/<id>/editar`, `/trabajos/<id>/baja` | `blueprints/trabajos/`, `services/trabajos.py` | A | test_modificar_y_baja, test_no_baja_con_prestamo_vigente |
| RF05 | Agregar ejemplares | `/trabajos/<id>/ejemplar` | `blueprints/trabajos/`, `services/trabajos.py` | A | test_registro_con_ejemplares_sin_duplicados |
| RF06 | Buscar y filtrar trabajos (título, autor, área, gestión, modalidad) sin importar tildes | `/trabajos/` | `blueprints/trabajos/`, `services/trabajos.py`, `utilidades.py` | A, C | test_busqueda_sin_tildes_ni_mayusculas |
| RF07 | Ver ficha y estado (disponibilidad) | `/trabajos/<id>` | `blueprints/trabajos/` | A, C | test_seed_y_pantallas |
| RF08 | Registrar solicitantes | `/solicitantes/nuevo`, `/<id>/editar` | `blueprints/solicitantes/`, `services/solicitantes.py` | A | test_solicitante_inexistente |
| RF09 | Registrar préstamo interno o externo | `/prestamos/nuevo` | `blueprints/prestamos/`, `services/prestamos.py` | A | test_flujo_prestamo_y_devolucion, test_no_presta_ejemplar_no_disponible, test_limite_de_prestamos_externos, test_prestamo_interno_misma_fecha |
| RF10 | Registrar devolución y renovar | `/prestamos/<id>/devolver`, `/renovar` | `blueprints/prestamos/`, `services/prestamos.py` | A | test_flujo_prestamo_y_devolucion, test_renovacion_una_vez |
| RF11 | Reporte: préstamos activos | `/reportes/prestamos-activos` | `blueprints/reportes/`, `services/reportes.py` | A, C | test_todos_los_reportes_cargan |
| RF12 | Reporte: historial por usuario | `/reportes/historial-usuario` | `blueprints/reportes/`, `services/reportes.py` | A, C | ídem |
| RF13 | Reporte: trabajos más prestados | `/reportes/mas-prestados` | `blueprints/reportes/`, `services/reportes.py` | A, C | ídem |
| RF14 | Reporte: disponibilidad de ejemplares | `/reportes/disponibilidad` | `blueprints/reportes/`, `services/reportes.py` | A, C | ídem |
| RF15 | Reporte: trabajos por área temática | `/reportes/por-area` | `blueprints/reportes/`, `services/reportes.py` | A, C | ídem |
| RF16 | Reporte: estadísticas de uso | `/reportes/estadisticas` | `blueprints/reportes/`, `services/reportes.py` | A, C | ídem |
| RF17 | Reporte: alertas de retraso | `/reportes/alertas-retraso` | `blueprints/reportes/`, `services/reportes.py` | A, C | test_vencido_y_alerta |
| RF18 | Reporte: nuevas adquisiciones | `/reportes/nuevas-adquisiciones` | `blueprints/reportes/`, `services/reportes.py` | A, C | test_todos_los_reportes_cargan |
| RF19 | Reporte: comparativo anual | `/reportes/comparativo-anual` | `blueprints/reportes/`, `services/reportes.py` | A, C | ídem |
| RF20 | Imprimir reportes (botón Imprimir / guardar en PDF) y exportar a CSV | `/reportes/<clave>` (botón Imprimir) y `?formato=csv` | `blueprints/reportes/` | A, C | test_todos_los_reportes_cargan |

## 3.2 Requisitos no funcionales

| Req. | Cómo se cumple |
|---|---|
| Seguridad de acceso | Login obligatorio, roles con decoradores, redirección abierta bloqueada, bloqueo por intentos, `SameSite`/`HttpOnly` en cookies |
| Contraseñas | Hash Werkzeug (test_contrasena_guardada_cifrada) |
| CSRF | Token en sesión validado en cada POST (test_csrf_obligatorio) |
| Integridad | Claves foráneas activas, CHECK, índices únicos, transacciones de SQLAlchemy con `commit`/`rollback` |
| Sin duplicados | Índice único título+gestión y préstamo vigente único (test_no_dos_vigentes_mismo_ejemplar_en_bd) |
| Cabeceras de seguridad | X-Frame-Options, X-Content-Type-Options, Referrer-Policy (test_cabeceras_de_seguridad) |
| Acceso por internet | `wsgi.py` + variables de entorno; catálogo público sin datos personales (test_catalogo_publico_sin_datos_personales) |
| Respaldo | `flask --app wsgi backup` |
| Configuración | Variables de entorno (ver README) |
| Usabilidad | Interfaz en español, paginación de 15 filas, mensajes de error claros |

## 3.3 Otras funciones añadidas
Comprobante imprimible de préstamo (`/prestamos/<id>/comprobante`), catálogo público (`/catalogo`) y comandos CLI `init-db`, `crear-usuario`, `seed-demo`, `backup`.
