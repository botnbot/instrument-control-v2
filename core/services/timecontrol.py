import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


def sync_users_from_timecontrol(force_overwrite=False):
    url = f"{settings.TIMECONTROL_URL}/persons"
    auth = (settings.TIMECONTROL_USER, settings.TIMECONTROL_PASSWORD)

    stats = {
        'created': 0,
        'updated': 0,
        'errors': [],
        'conflicts': [],
        'transferred': [],
        'total_processed': 0,
        'deleted': 0
    }

    try:
        response = requests.get(url, auth=auth, timeout=15)
        response.raise_for_status()
        persons = response.json().get('data', [])

        # --- ШАГ 1: Ищем дубликаты карт В САМОМ ТАЙМКОНТРОЛЕ ---
        card_owners = {}
        for person in persons:
            rfid = person.get('SHEDCARDKEY', '').strip()
            fullname = person.get('FULLNAME', '').strip()
            is_locked = person.get('ISLOCKED') == '1'

            # Берем в расчет только незаблокированных и с непустой картой
            if rfid and not is_locked:
                if rfid not in card_owners:
                    card_owners[rfid] = []
                card_owners[rfid].append(fullname)

        # Находим карты, которые принадлежат более чем одному человеку
        duplicate_cards = {card: names for card, names in card_owners.items() if len(names) > 1}

        for card, names in duplicate_cards.items():
            stats['conflicts'].append(
                f"ОШИБКА В ТАЙМКОНТРОЛЕ: Карта {card} назначена сразу нескольким сотрудникам: {', '.join(names)}. Карта не будет присвоена никому."
            )

        # Собираем UID всех сотрудников из TimeControl для последующей очистки старых записей
        timecontrol_uids = {str(p.get('UID')) for p in persons if p.get('UID')}

        # --- ШАГ 2: Жесткая синхронизация с базой InstrumentControl ---
        with transaction.atomic():
            # 1. Очищаем карты у ВСЕХ пользователей, чтобы избежать конфликтов уникальности
            User.objects.update(rfid_card=None)

            # 2. Удаляем пользователей, которых нет в TimeControl
            # (это уберет "фантомные" записи, которые занимают карты)
            deleted_count, _ = User.objects.exclude(username__in=timecontrol_uids).delete()
            stats['deleted'] = deleted_count

            # 3. Раздаем карты заново и обновляем/создаем пользователей
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
                    # Ищем пользователя по UID (username), если нет - создаем
                    user, created = User.objects.get_or_create(
                        username=str(uid),
                        defaults={'email': None}
                    )

                    # Разбираем ФИО на части
                    parts = fullname.split()
                    user.last_name = parts[0] if len(parts) > 0 else ''
                    user.first_name = parts[1] if len(parts) > 1 else ''
                    # Если в модели есть поле middle_name (отчество) - раскомментируйте:
                    # user.middle_name = parts[2] if len(parts) > 2 else ''

                    user.is_active = not is_locked
                    user.tabnum = tabnum.strip() if tabnum else ""
                    user.position = position
                    user.department = department

                    # Проверка на дубликат карты (найденный на Шаге 1)
                    if rfid_card and rfid_card in duplicate_cards:
                        user.rfid_card = None
                    else:
                        user.rfid_card = rfid_card if rfid_card else None

                    user.save()

                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1

                except Exception as e:
                    stats['errors'].append(f"Ошибка при обработке {fullname} (UID: {uid}): {str(e)}")
                    continue

    except requests.exceptions.RequestException as e:
        stats['errors'].append(f"Ошибка подключения к TimeControl: {str(e)}")
    except Exception as e:
        stats['errors'].append(f"Ошибка обработки данных: {str(e)}")

    print("Синхронизация завершена. Рабочий ПК.")
    return stats

