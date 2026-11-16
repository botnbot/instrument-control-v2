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
        'conflicts': [],  # Сюда будем писать дубликаты из ТаймКонтроля
        'transferred': [],
        'total_processed': 0
    }

    try:
        response = requests.get(url, auth=auth, timeout=15)
        response.raise_for_status()
        persons = response.json().get('data', [])

        # --- ШАГ 1: Ищем дубликаты карт В САМОМ ТАЙМКОНТРОЛЕ ---
        # Создаем словарь: карта -> список ФИО, кому она принадлежит
        card_owners = {}
        for person in persons:
            rfid = person.get('SHEDCARDKEY', '').strip()
            fullname = person.get('FULLNAME', '').strip()
            is_locked = person.get('ISLOCKED') == '1'

            # Учитываем только карты активных сотрудников
            if rfid and not is_locked:
                if rfid not in card_owners:
                    card_owners[rfid] = []
                card_owners[rfid].append(fullname)

        # Находим карты, которые принадлежат более чем одному человеку
        duplicate_cards = {card: names for card, names in card_owners.items() if len(names) > 1}

        # Если дубликаты есть, пишем их в конфликты, чтобы пользователь увидел
        for card, names in duplicate_cards.items():
            stats['conflicts'].append(
                f"ОШИБКА В ТАЙМКОНТРОЛЕ: Карта {card} назначена сразу нескольким сотрудникам: {', '.join(names)}. Карта не будет присвоена никому."
            )

        # --- ШАГ 2: Жесткая очистка и присвоение ---
        with transaction.atomic():
            # 1. Очищаем ВСЕ карты в базе Django
            User.objects.update(rfid_card=None)

            # 2. Раздаем карты заново
            for person in persons:
                uid = person.get('UID')
                tabnum = person.get('TABNUM', '')
                fullname = person.get('FULLNAME', '')
                is_locked = person.get('ISLOCKED') == '1'
                rfid_card = person.get('SHEDCARDKEY', '').strip()

                if not uid or not fullname:
                    continue

                stats['total_processed'] += 1

                user, created = User.objects.get_or_create(username=str(uid), defaults={'email': None})

                parts = fullname.split()
                user.last_name = parts[0] if len(parts) > 0 else ''
                user.first_name = parts[1] if len(parts) > 1 else ''
                user.is_active = not is_locked
                user.tabnum = tabnum.strip() if tabnum else ""

                # === ГЛАВНАЯ ПРОВЕРКА ===
                # Если карта есть в списке дубликатов, НЕ ПРИСВАИВАЕМ её этому сотруднику
                if rfid_card and rfid_card in duplicate_cards:
                    user.rfid_card = None
                else:
                    user.rfid_card = rfid_card if rfid_card else None

                user.save()

                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

    except requests.exceptions.RequestException as e:
        stats['errors'].append(f"Ошибка подключения к TimeControl: {str(e)}")
    except Exception as e:
        stats['errors'].append(f"Ошибка обработки данных: {str(e)}")

    return stats