@echo off
cd C:\instrument-control-v2
py -3.12 -m poetry run waitress-serve --host=127.0.0.1 --port=8000 config.wsgi:application
pause