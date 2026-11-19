"""Pruebas automáticas:  python -m unittest discover -s tests -v"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func, select, text

from app import create_app, seguridad
from app.extensions import db
from app.migraciones import migrar_modalidad_libro
from app.models import AreaTematica, Autor, Ejemplar, Prestamo, Solicitante, TrabajoGrado
from app.seed import LIBROS
from app.services import crear_usuario
from app.services.reportes import REPORTES

CLAVE = "clave-de-prueba-1"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.app = create_app(
            "testing", {"SQLALCHEMY_DATABASE_URI": "sqlite:///" + self.tmp.name}
        )
        seguridad._intentos.clear()
        with self.app.app_context():
            db.create_all()
            crear_usuario("bibliotecaria", CLAVE, "administrador")
            crear_usuario("consulta", CLAVE, "consulta")

            trabajo = TrabajoGrado(
                titulo="Trabajo de prueba",
                gestion=2024,
                modalidad="tesis",
                fecha_recepcion=date.today().isoformat(),
                autoriza_publicacion=True,
                area=AreaTematica(nombre="Programación"),
            )
            trabajo.autores.append(Autor(nombre="Autora Prueba"))
            trabajo.ejemplares.append(Ejemplar(codigo="TG-0001-1", ubicacion="Estante 1"))
            db.session.add_all(
                [
                    trabajo,
                    Solicitante(nombre="Persona de prueba", ci="1234567", matricula="M-1"),
                ]
            )
            db.session.commit()
        self.c = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        os.unlink(self.tmp.name)

    def token(self):
        with self.c.session_transaction() as s:
            s.setdefault("csrf", "tok-prueba")
            return s["csrf"]

    def post(self, url, data=None, **k):
        d = dict(data or {}, csrf_token=self.token())
        return self.c.post(url, data=d, **k)

    def login(self, usuario="bibliotecaria", clave=CLAVE):
        return self.post("/login", {"username": usuario, "password": clave})

    def q(self, sql, *p):
        """Ejecuta SQL con marcadores '?' y devuelve filas accesibles por posición o nombre."""
        params = {}
        for numero, valor in enumerate(p, 1):
            sql = sql.replace("?", f":p{numero}", 1)
            params[f"p{numero}"] = valor
        with self.app.app_context():
            return db.session.execute(text(sql), params).all()


class AccesoTests(Base):
    def test_requiere_login(self):
        for url in ["/", "/trabajos/", "/solicitantes/", "/prestamos/", "/reportes/", "/usuarios"]:
            self.assertEqual(self.c.get(url).status_code, 302, url)

    def test_login_correcto_e_incorrecto(self):
        self.assertEqual(self.login(clave="mala-clave").status_code, 200)
        self.assertEqual(self.c.get("/").status_code, 302)
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.c.get("/").status_code, 200)

    def test_csrf_obligatorio(self):
        r = self.c.post("/login", data={"username": "bibliotecaria", "password": CLAVE})
        self.assertEqual(r.status_code, 400)

    def test_bloqueo_por_intentos(self):
        for _ in range(5):
            self.login(clave="mala")
        r = self.login()  # aunque ahora la clave sea correcta
        self.assertEqual(r.status_code, 429)

    def test_redireccion_abierta_bloqueada(self):
        for malo in ("https://malo.example/", "//malo.example/", "/\\malo.example/"):
            r = self.post("/login", {"username": "bibliotecaria", "password": CLAVE, "next": malo})
            self.assertEqual(r.headers["Location"], "/", malo)

    def test_contrasena_guardada_cifrada(self):
        h = self.q("SELECT contrasena FROM usuario WHERE nombre_usuario = 'bibliotecaria'")[0][0]
        self.assertNotIn(CLAVE, h)

    def test_consulta_no_puede_registrar(self):
        self.login("consulta")
        self.post("/trabajos/nuevo", {"titulo": "X"})
        self.assertEqual(len(self.q("SELECT 1 FROM trabajo_grado")), 1)
        self.assertEqual(self.c.get("/usuarios").status_code, 302)
        self.assertEqual(self.post("/prestamos/nuevo", {"id_ejemplar": 1, "documento": "1234567"}).status_code, 302)
        self.assertEqual(len(self.q("SELECT 1 FROM prestamo")), 0)


class UsuariosTests(Base):
    def test_crear_desactivar_usuario(self):
        self.login()
        self.post("/usuarios/nuevo", {"nombre_usuario": "nuevo1", "clave": "otra-clave-123", "rol": "consulta"})
        self.assertEqual(len(self.q("SELECT 1 FROM usuario WHERE nombre_usuario = 'nuevo1'")), 1)
        idu = self.q("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'nuevo1'")[0][0]
        self.post(f"/usuarios/{idu}/estado")
        self.assertEqual(self.q("SELECT activo FROM usuario WHERE id_usuario = ?", idu)[0][0], 0)
        c2 = self.app.test_client()
        with c2.session_transaction() as s:
            s["csrf"] = "t"
        r = c2.post("/login", data={"username": "nuevo1", "password": "otra-clave-123", "csrf_token": "t"})
        self.assertEqual(r.status_code, 200)  # desactivado: no ingresa

    def test_clave_corta_rechazada(self):
        self.login()
        self.post("/usuarios/nuevo", {"nombre_usuario": "corto", "clave": "123", "rol": "consulta"})
        self.assertEqual(len(self.q("SELECT 1 FROM usuario WHERE nombre_usuario = 'corto'")), 0)

    def test_no_se_desactiva_a_si_mismo(self):
        self.login()
        idu = self.q("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'bibliotecaria'")[0][0]
        self.post(f"/usuarios/{idu}/estado")
        self.assertEqual(self.q("SELECT activo FROM usuario WHERE id_usuario = ?", idu)[0][0], 1)


class TrabajoTests(Base):
    DATOS = {
        "titulo": "Nuevo trabajo",
        "gestion": "2025",
        "modalidad": "proyecto",
        "fecha_recepcion": "2026-11-01",
        "autores": "Autor A; Autor B",
        "tutor_nombre": "Tutor X",
        "num_ejemplares": "2",
        "ubicacion": "Estante 2",
        "area_nueva": "Redes",
    }

    def test_registro_con_ejemplares_sin_duplicados(self):
        self.login()
        r = self.post("/trabajos/nuevo", self.DATOS)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(self.q("SELECT 1 FROM ejemplar WHERE id_trabajo = 2")), 2)
        self.assertEqual(len(self.q("SELECT 1 FROM trabajo_autor WHERE id_trabajo = 2")), 2)
        self.assertEqual(
            self.q("SELECT a.nombre FROM trabajo_grado t JOIN area_tematica a USING(id_area) WHERE id_trabajo=2")[0][0],
            "Redes",
        )
        self.post("/trabajos/nuevo", dict(self.DATOS, titulo="NUEVO TRABAJO"))  # duplicado (mayúsculas)
        self.assertEqual(len(self.q("SELECT 1 FROM trabajo_grado")), 2)
        self.post("/trabajos/2/ejemplar", {"ubicacion": "Estante 3"})  # RF05
        self.assertEqual(len(self.q("SELECT 1 FROM ejemplar WHERE id_trabajo = 2")), 3)

    def test_validaciones(self):
        self.login()
        self.post("/trabajos/nuevo", dict(self.DATOS, titulo="", gestion="abc"))
        self.post("/trabajos/nuevo", dict(self.DATOS, gestion="2199"))  # fuera del rango 1980–2100
        self.assertEqual(len(self.q("SELECT 1 FROM trabajo_grado")), 1)

    def test_busqueda_sin_tildes_ni_mayusculas(self):
        self.login("consulta")
        self.assertIn(b"Trabajo de prueba", self.c.get("/trabajos/?q=PRUEBA").data)
        self.assertIn(b"Trabajo de prueba", self.c.get("/trabajos/?autor=autora").data)
        self.assertNotIn(b"Trabajo de prueba", self.c.get("/trabajos/?q=inexistente").data)
        self.assertIn(b"Trabajo de prueba", self.c.get("/trabajos/?area=1&anio=2024&estado=disponible").data)
        self.assertIn(b"Trabajo de prueba", self.c.get("/trabajos/?modalidad=tesis").data)
        self.assertNotIn(b"Trabajo de prueba", self.c.get("/trabajos/?modalidad=proyecto").data)

    def test_modificar_y_baja(self):
        self.login()
        self.post("/trabajos/1/editar", dict(self.DATOS, titulo="Título corregido", gestion="2024"))
        self.assertEqual(self.q("SELECT titulo FROM trabajo_grado WHERE id_trabajo=1")[0][0], "Título corregido")
        self.post("/trabajos/1/baja")
        self.assertEqual(self.q("SELECT activo FROM trabajo_grado WHERE id_trabajo=1")[0][0], 0)
        self.assertEqual(self.q("SELECT estado FROM ejemplar WHERE id_trabajo=1")[0][0], "baja")
        self.post("/trabajos/1/ejemplar", {"ubicacion": "Estante 9"})  # no se agregan a un trabajo de baja
        self.assertEqual(len(self.q("SELECT 1 FROM ejemplar WHERE id_trabajo=1")), 1)

    def test_no_baja_con_prestamo_vigente(self):
        self.login()
        self.post("/prestamos/nuevo", {"id_ejemplar": 1, "documento": "1234567", "tipo": "externo", "garantia": "ci"})
        self.post("/trabajos/1/baja")
        self.assertEqual(self.q("SELECT activo FROM trabajo_grado WHERE id_trabajo=1")[0][0], 1)


class PrestamoTests(Base):
    PRESTAR = {"id_ejemplar": 1, "documento": "1234567", "tipo": "externo", "garantia": "ci"}

    def test_flujo_prestamo_y_devolucion(self):
        self.login()
        r = self.post("/prestamos/nuevo", self.PRESTAR)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.q("SELECT estado FROM ejemplar WHERE id_ejemplar=1")[0][0], "en_prestamo")
        p = self.q("SELECT * FROM prestamo")[0]
        self.assertEqual(p._mapping["fecha_devolucion_prevista"], (date.today() + timedelta(days=7)).isoformat())
        self.assertEqual(self.c.get(f"/prestamos/{p._mapping['id_prestamo']}/comprobante").status_code, 200)
        self.post(f"/prestamos/{p._mapping['id_prestamo']}/devolver")
        self.assertEqual(self.q("SELECT estado FROM ejemplar WHERE id_ejemplar=1")[0][0], "disponible")
        self.assertEqual(self.q("SELECT estado FROM prestamo")[0][0], "devuelto")

    def test_no_presta_ejemplar_no_disponible(self):
        self.login()
        self.post("/prestamos/nuevo", self.PRESTAR)
        self.post("/prestamos/nuevo", dict(self.PRESTAR, tipo="interno"))
        self.assertEqual(len(self.q("SELECT 1 FROM prestamo")), 1)

    def test_solicitante_inexistente(self):
        self.login()
        self.post("/prestamos/nuevo", dict(self.PRESTAR, documento="9999999"))
        self.assertEqual(len(self.q("SELECT 1 FROM prestamo")), 0)
        self.assertEqual(self.q("SELECT estado FROM ejemplar WHERE id_ejemplar=1")[0][0], "disponible")

    def test_limite_de_prestamos_externos(self):
        with self.app.app_context():
            for n in range(2, 5):
                db.session.add(Ejemplar(id_trabajo=1, codigo=f"X-{n}", ubicacion="E"))
            db.session.commit()
        self.login()
        for n in (1, 2, 3):
            self.post("/prestamos/nuevo", dict(self.PRESTAR, id_ejemplar=n))
        self.assertEqual(len(self.q("SELECT 1 FROM prestamo")), 2)  # el tercero se rechaza (máximo 2)

    def test_prestamo_interno_misma_fecha(self):
        self.login()
        manana = (date.today() + timedelta(days=30)).isoformat()
        self.post("/prestamos/nuevo", dict(self.PRESTAR, tipo="interno", fecha_devolucion_prevista=manana))
        p = self.q("SELECT * FROM prestamo")[0]
        self.assertEqual(p._mapping["fecha_devolucion_prevista"], date.today().isoformat())
        self.assertEqual(self.q("SELECT estado FROM ejemplar WHERE id_ejemplar=1")[0][0], "en_consulta")

    def test_renovacion_una_vez(self):
        self.login()
        self.post("/prestamos/nuevo", self.PRESTAR)
        self.post("/prestamos/1/renovar")
        self.post("/prestamos/1/renovar")
        p = self.q("SELECT * FROM prestamo")[0]
        self.assertEqual(p._mapping["renovaciones"], 1)
        self.assertEqual(p._mapping["fecha_devolucion_prevista"], (date.today() + timedelta(days=14)).isoformat())

    def test_vencido_y_alerta(self):
        with self.app.app_context():
            db.session.add(
                Prestamo(
                    id_ejemplar=1,
                    id_solicitante=1,
                    id_usuario=1,
                    tipo="externo",
                    fecha_prestamo=(date.today() - timedelta(days=10)).isoformat(),
                    fecha_devolucion_prevista=(date.today() - timedelta(days=3)).isoformat(),
                )
            )
            db.session.commit()
        self.login()
        self.assertIn(b"Vencido", self.c.get("/prestamos/?ver=vencidos").data)
        self.assertIn(b"Persona de prueba", self.c.get("/reportes/alertas-retraso").data)

    def test_no_dos_vigentes_mismo_ejemplar_en_bd(self):
        import sqlite3

        self.login()
        self.post("/prestamos/nuevo", self.PRESTAR)
        con = sqlite3.connect(self.tmp.name)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO prestamo (id_ejemplar, id_solicitante, id_usuario, fecha_prestamo, fecha_devolucion_prevista) "
                "VALUES (1, 1, 1, '2026-01-01', '2026-01-02')"
            )
        con.close()


class ReportesYCatalogoTests(Base):
    def test_todos_los_reportes_cargan(self):
        self.login()
        self.post("/prestamos/nuevo", PrestamoTests.PRESTAR)
        self.assertEqual(self.c.get("/reportes/").status_code, 200)
        for clave in REPORTES:
            self.assertEqual(self.c.get(f"/reportes/{clave}").status_code, 200, clave)
            r = self.c.get(f"/reportes/{clave}?formato=csv")
            self.assertEqual(r.status_code, 200, clave)
            self.assertIn("text/csv", r.headers["Content-Type"])
        self.assertEqual(self.c.get("/reportes/no-existe").status_code, 404)

    def test_catalogo_publico_sin_datos_personales(self):
        with self.app.app_context():
            db.session.add(
                TrabajoGrado(
                    titulo="Trabajo reservado",
                    gestion=2023,
                    modalidad="tesis",
                    fecha_recepcion=date.today().isoformat(),
                    autoriza_publicacion=False,
                    area=db.session.get(AreaTematica, 1),
                )
            )
            db.session.commit()
        self.login()
        self.post("/prestamos/nuevo", PrestamoTests.PRESTAR)
        c2 = self.app.test_client()
        r = c2.get("/catalogo?q=trabajo")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Trabajo de prueba", r.data)
        self.assertNotIn(b"Trabajo reservado", r.data)  # sin autorización de publicación
        self.assertNotIn(b"Persona de prueba", r.data)
        self.assertNotIn(b"1234567", r.data)
        self.assertEqual(c2.get("/trabajos/").status_code, 302)  # lo demás sigue protegido

    def test_catalogo_se_puede_apagar(self):
        self.app.config["CATALOGO_PUBLICO"] = False
        self.assertEqual(self.app.test_client().get("/catalogo").status_code, 404)

    def test_cabeceras_de_seguridad(self):
        r = self.c.get("/login")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")


class DatosDemoTests(unittest.TestCase):
    def test_seed_y_pantallas(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        try:
            app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": "sqlite:///" + tmp.name})
            runner = app.test_cli_runner()
            self.assertIn("cargados", runner.invoke(args=["seed-demo"]).output)
            self.assertIn("Ya existen", runner.invoke(args=["seed-demo"]).output)
            c = app.test_client()
            with c.session_transaction() as s:
                s["csrf"] = "t"
            c.post(
                "/login",
                data={"username": "bibliotecaria", "password": "biblioteca2026", "csrf_token": "t"},
            )
            for url in (
                [
                    "/",
                    "/trabajos/",
                    "/trabajos/1",
                    "/trabajos/1/editar",
                    "/trabajos/nuevo",
                    "/solicitantes/",
                    "/solicitantes/nuevo",
                    "/solicitantes/1/editar",
                    "/prestamos/",
                    "/prestamos/?ver=todos",
                    "/prestamos/nuevo",
                    "/usuarios",
                    "/usuarios/nuevo",
                    "/clave",
                    "/catalogo",
                ]
                + [f"/reportes/{k}" for k in REPORTES]
            ):
                self.assertEqual(c.get(url).status_code, 200, url)
            out = runner.invoke(args=["backup", "--destino", tempfile.mkdtemp()]).output
            self.assertIn("Respaldo creado", out)
        finally:
            os.unlink(tmp.name)

    def test_seed_libros_y_catalogo(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        try:
            app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": "sqlite:///" + tmp.name})
            runner = app.test_cli_runner()
            self.assertEqual(runner.invoke(args=["init-db"]).exit_code, 0)

            salida = runner.invoke(args=["seed-libros"]).output
            self.assertIn("Libros de ejemplo cargados", salida)
            self.assertIn("ya estaban", runner.invoke(args=["seed-libros"]).output)

            with app.app_context():
                libros = db.session.scalar(
                    select(func.count())
                    .select_from(TrabajoGrado)
                    .where(TrabajoGrado.modalidad == "libro")
                )
                self.assertEqual(libros, len(LIBROS))
                ejemplares = db.session.scalar(
                    select(func.count())
                    .select_from(Ejemplar)
                    .join(TrabajoGrado)
                    .where(TrabajoGrado.modalidad == "libro")
                )
                self.assertEqual(ejemplares, sum(libro["cantidad"] for libro in LIBROS))

            r = app.test_client().get("/catalogo?q=clean+code")
            self.assertEqual(r.status_code, 200)
            self.assertIn(b"Clean Code", r.data)
            self.assertIn(b"Ingenier\xc3\xada de software", r.data)
        finally:
            os.unlink(tmp.name)


class MigracionTests(unittest.TestCase):
    def test_migra_esquema_antiguo_conservando_datos(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        try:
            con = sqlite3.connect(tmp.name)
            con.executescript(
                """
                CREATE TABLE trabajo_grado (
                    id_trabajo INTEGER NOT NULL PRIMARY KEY,
                    titulo VARCHAR(250) NOT NULL,
                    resumen TEXT NOT NULL,
                    gestion INTEGER NOT NULL,
                    modalidad VARCHAR(20) NOT NULL,
                    fecha_recepcion VARCHAR(10) NOT NULL,
                    cd_entregado BOOLEAN NOT NULL,
                    autoriza_publicacion BOOLEAN NOT NULL,
                    activo BOOLEAN NOT NULL,
                    id_area INTEGER,
                    id_tutor INTEGER,
                    CONSTRAINT ck_trabajo_modalidad
                        CHECK (modalidad IN ('tesis','proyecto','dirigido'))
                );
                CREATE UNIQUE INDEX ux_trabajo_titulo_gestion
                    ON trabajo_grado (lower(titulo), gestion);
                INSERT INTO trabajo_grado (
                    id_trabajo, titulo, resumen, gestion, modalidad,
                    fecha_recepcion, cd_entregado, autoriza_publicacion, activo
                ) VALUES (
                    1, 'Trabajo anterior', '', 2024, 'tesis',
                    '2024-01-01', 1, 1, 1
                );
                """
            )
            con.commit()
            con.close()

            self.assertTrue(migrar_modalidad_libro(tmp.name))
            self.assertFalse(migrar_modalidad_libro(tmp.name))  # idempotente

            con = sqlite3.connect(tmp.name)
            try:
                self.assertEqual(
                    con.execute("SELECT count(*) FROM trabajo_grado").fetchone()[0], 1
                )
                con.execute(
                    "INSERT INTO trabajo_grado ("
                    "id_trabajo, titulo, resumen, gestion, modalidad, "
                    "fecha_recepcion, cd_entregado, autoriza_publicacion, activo"
                    ") VALUES (2, 'Clean Code', '', 2008, 'libro', '2024-01-01', 0, 1, 1)"
                )
                con.commit()
                self.assertEqual(
                    con.execute(
                        "SELECT count(*) FROM trabajo_grado WHERE modalidad = 'libro'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    con.execute(
                        "SELECT count(*) FROM sqlite_master "
                        "WHERE type='index' AND name='ux_trabajo_titulo_gestion'"
                    ).fetchone()[0],
                    1,
                )
            finally:
                con.close()
        finally:
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
