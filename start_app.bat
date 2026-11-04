@echo off
cd C:\Projects\instrument-control-v2
"C:\Users\skoro\AppData\Local\pypoetry\Cache\virtualenvs\instrument-control-v2-RDWJ1kmw-py3.12\Scripts\python.exe" -m waitress --host=0.0.0.0 --port=8000 config.wsgi:application
pause