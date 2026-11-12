@echo off
echo Starting Django (Waitress)...
cd /d C:\instrument-control-v2
start "Django Waitress" cmd /c "py -3.12 -m poetry run waitress-serve --host=0.0.0.0 --port=8000 config.wsgi:application"