import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command

with open('dump.json', 'w', encoding='utf-8') as f:
    call_command(
        'dumpdata',
        'core', 'user',
        '--natural-foreign',
        '--natural-primary',
        '--indent', '2',
        stdout=f
    )

print("Дамп успешно создан в dump.json (UTF-8)")