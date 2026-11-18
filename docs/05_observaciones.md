# 5. Observaciones respecto al documento (Capítulo III)

## 5.1 Cambios y adiciones al modelo
1. **Campo `activo`** en `trabajo_grado` y `usuario`: permite baja lógica sin perder el historial de préstamos.
2. **Índices únicos**: título+gestión (sin duplicados) y un solo préstamo vigente por ejemplar (índice parcial). Además, CHECK en estados, modalidades, rangos de fechas y longitudes.
3. **Estado «vencido» calculado**, no guardado: evita datos desactualizados. En la base solo existe `vigente`/`devuelto`.
4. **Catálogo público** (`/catalogo`): responde al acceso por internet; solo muestra trabajos activos que autorizan publicación, sin datos personales, y se puede apagar con `CATALOGO_PUBLICO=0`.
5. **Comprobante de préstamo** y **exportación CSV** de reportes: no estaban en el alcance; se añadieron por utilidad.
6. **Seguridad adicional**: CSRF, bloqueo por intentos, cabeceras de seguridad, hash de contraseñas.

## 5.2 Decisión técnica
Se usa **Flask con `sqlite3` de la biblioteca estándar** (sin ORM). Motivo: menos dependencias (solo Flask), consultas visibles y fáciles de explicar en la defensa. Si el docente exige ORM, el esquema se traslada directamente a Flask-SQLAlchemy.

## 5.3 Reglas supuestas (confirmar con la encargada)
Préstamo externo de 7 días, máximo 2 externos vigentes por solicitante, 1 renovación, garantía CI/matrícula. Se cambian con variables de entorno sin tocar el código.

## 5.4 Advertencias
- `seed-demo` crea usuarios de prueba (`bibliotecaria` / `consulta`) con contraseñas conocidas: **no usarlo en un servidor público**; crear usuarios reales con `crear-usuario`.
- En internet: usar HTTPS, `COOKIE_SEGURA=1`, `SECRET_KEY` propia y `DEBUG` apagado.
- SQLite basta para el volumen de una biblioteca de carrera; para varios cientos de usuarios simultáneos convendría PostgreSQL/MySQL.
- Hacer respaldos periódicos (la base es un solo archivo).
