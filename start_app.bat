@echo off
cd /d C:\Projects\instrument-control-v2
python -m waitress --host=0.0.0.0 --port=8000 config.wsgi:application
pause