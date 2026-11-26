import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.contrib.auth.models import Group

User = get_user_model()


def sync_users_from_timecontrol(force_overwrite=False):
    url = f"{settings.TIMECONTROL_URL}/persons"
    auth = (settings.TIMECONTROL_USER, settings.TIMECONTROL_PASSWORD)

    stats = {
        'created': 0,
        'updated': 0,
        'errors': [],
        'total_processed': 0,
    }

    try:
        response = requests.get(url, auth=auth, timeout=15)
        response.raise_for_status()
        persons = response.json().get('data', [])

        # --- ОСНОВНОЙ ЦИКЛ: Создаем или обновляем пользователей ---
        for person in persons:
            uid = person.get('UID')
            tabnum = person.get('TABNUM', '')
            fullname = person.get('FULLNAME', '')
            is_locked = person.get('ISLOCKED') == '1'
            rfid_card = person.get('SHEDCARDKEY', '').strip()
            position = person.get('DOLJNAME', '').strip()
            department = person.get('DEPNAME', '').strip()

            if not uid or not fullname:
                continue

            stats['total_processed'] += 1

            try:
                with transaction.atomic():
                    # Ищем по UID или создаем нового
                    user, created = User.objects.get_or_create(
                        username=str(uid),
                        defaults={'email': None}
                    )

                    parts = fullname.split()
                    user.last_name = parts[0] if len(parts) > 0 else ''
                    user.first_name = parts[1] if len(parts) > 1 else ''
                    user.is_active = not is_locked
                    user.tabnum = tabnum.strip() if tabnum else ""
                    user.position = position
                    user.department = department
                    user.rfid_card = rfid_card if rfid_card else None

                    user.save()

                    # === АВТОМАТИЧЕСКОЕ ДОБАВЛЕНИЕ В ГРУППУ ===
                    if position and "кладовщик" in position.lower():
                        group, _ = Group.objects.get_or_create(name='Кладовщики')
                        user.groups.add(group)

                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

            except IntegrityError:
                stats['errors'].append(
                    f"Пользователь {fullname} (UID: {uid}): карта {rfid_card} уже занята."
                )
                continue
            except Exception as e:
                stats['errors'].append(f"Ошибка при обработке {fullname} (UID: {uid}): {str(e)}")
                continue

    except requests.exceptions.RequestException as e:
        stats['errors'].append(f"Ошибка подключения к TimeControl: {str(e)}")
    except Exception as e:
        stats['errors'].append(f"Ошибка обработки данных: {str(e)}")

    return stats