import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


def sync_users_from_timecontrol():
    url = f"{settings.TIMECONTROL_URL}/persons"
    auth = (settings.TIMECONTROL_USER, settings.TIMECONTROL_PASSWORD)

    stats = {'created': 0, 'updated': 0, 'errors': [], 'total_processed': 0}

    try:
        response = requests.get(url, auth=auth, timeout=10)
        response.raise_for_status()
        data = response.json()
        persons = data.get('data', [])

        with transaction.atomic():
            for person in persons:
                tabnum = person.get('TABNUM')
                fullname = person.get('FULLNAME')
                is_locked = person.get('ISLOCKED') == '1'
                rfid_card = person.get('SHEDCARDKEY')

                if not tabnum or not fullname:
                    continue

                stats['total_processed'] += 1

                # Ищем по табельному номеру (username)
                user, created = User.objects.get_or_create(username=tabnum)

                parts = fullname.split()
                last_name = parts[0] if len(parts) > 0 else ''
                first_name = parts[1] if len(parts) > 1 else ''

                user.first_name = first_name
                user.last_name = last_name
                user.is_active = not is_locked
                if rfid_card:
                    user.rfid_card = rfid_card
                user.save()

                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

    except requests.exceptions.RequestException as e:
        stats['errors'].append(f"Ошибка подключения: {str(e)}")
    except Exception as e:
        stats['errors'].append(f"Ошибка обработки: {str(e)}")

    return stats