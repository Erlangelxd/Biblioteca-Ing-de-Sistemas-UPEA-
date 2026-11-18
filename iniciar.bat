@echo off
if not exist venv python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
if not exist instance\biblioteca.sqlite3 (
  flask --app wsgi init-db
  flask --app wsgi crear-usuario bibliotecaria
)
python run.py
