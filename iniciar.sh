#!/bin/sh
[ -d venv ] || python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
if [ ! -f instance/biblioteca.sqlite3 ]; then
  flask --app wsgi init-db
  flask --app wsgi crear-usuario bibliotecaria
fi
python run.py
