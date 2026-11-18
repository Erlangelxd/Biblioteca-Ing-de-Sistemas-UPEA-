"""Punto de entrada para servidores (PythonAnywhere, gunicorn, waitress...).
En PythonAnywhere: en el archivo WSGI de la pestaña Web, importar:  from wsgi import application"""
from app import create_app

application = create_app()
