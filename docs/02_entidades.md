# 2. Entidades

Cada entidad corresponde a un modelo ORM de [`app/models/`](../app/models/) y a una tabla de [01_esquema_base_datos.md](01_esquema_base_datos.md). Las reglas de negocio se aplican en los servicios de [`app/services/`](../app/services/).

| Entidad | Descripción | Atributos principales | Relaciones | Reglas de negocio |
|---|---|---|---|---|
| **Usuario** | Persona que opera el sistema (encargada de la biblioteca o personal de consulta). | nombre_usuario, contrasena (hash), rol, activo | Registra N préstamos | Nombre único; clave mínima validada; no puede desactivarse a sí mismo; usuario inactivo no ingresa; 5 intentos fallidos bloquean 5 min. |
| **Área temática** | Clasificación del material (p. ej. Redes, Ingeniería de software). | nombre | 1 área → N trabajos | Nombre único; se crea al registrar un material si no existe. |
| **Tutor** | Docente guía del trabajo. | nombre | 1 tutor → N trabajos | Nombre único; se reutiliza si ya existe. |
| **Autor** | Estudiante autor de un trabajo. | nombre, ci | N autores ↔ N trabajos | Un trabajo puede tener varios autores. |
| **Trabajo de grado / Libro** | Material bibliográfico: tesis, proyecto de grado, trabajo dirigido o libro. | título, resumen, gestión, modalidad, fecha de recepción, cd_entregado, autoriza_publicación, activo | Tiene 1 área, 1 tutor, N autores, N ejemplares | No se duplica (mismo título y gestión); la baja es lógica y **no se permite con préstamos vigentes**; solo los que autorizan publicación y están activos aparecen en el catálogo público. |
| **Ejemplar** | Copia física identificable con código y ubicación. | código, ubicación, estado | Pertenece a 1 trabajo; tiene N préstamos | Código único; estados: disponible, en_consulta, en_prestamo, baja; solo un ejemplar *disponible* se presta. |
| **Solicitante** | Estudiante o docente que consulta o se lleva un trabajo. | nombre, ci, matrícula, tipo, teléfono | Tiene N préstamos | CI única; se busca por CI o matrícula al prestar. |
| **Préstamo** | Registro de una consulta en sala o préstamo a domicilio. | tipo, garantía, fecha de préstamo, fecha prevista, fecha real, renovaciones, estado | 1 ejemplar, 1 solicitante, 1 usuario | Interno: se devuelve el mismo día. Externo: 7 días, máx. 2 externos vigentes por solicitante, 1 renovación. Vencido = vigente con fecha prevista pasada (se calcula). Un ejemplar no tiene dos préstamos vigentes. |

Los parámetros de plazo y límites (7 días, 2 préstamos, 1 renovación) se cambian con variables de entorno (`DIAS_PRESTAMO_EXTERNO`, `MAX_PRESTAMOS_EXTERNOS`, `MAX_RENOVACIONES`). **Son reglas supuestas: deben confirmarse con la encargada de la biblioteca.**

## Ciclo de vida del ejemplar
`disponible` → (préstamo interno) `en_consulta` → (devolución) `disponible`
`disponible` → (préstamo externo) `en_prestamo` → (devolución) `disponible`
`baja` es terminal (se asigna al dar de baja el trabajo).
