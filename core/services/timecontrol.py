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
        'conflicts': [],
        'transferred': [],
        'total_processed': 0,
        'deleted': 0,
        'deleted_users': []  # Сюда будем складывать "лишних" пользователей
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

            if rfid and not is_locked:
                if rfid not in card_owners:
                    card_owners[rfid] = []
                card_owners[rfid].append(fullname)

        duplicate_cards = {card: names for card, names in card_owners.items() if len(names) > 1}

        for card, names in duplicate_cards.items():
            stats['conflicts'].append(
                f"ОШИБКА В ТАЙМКОНТРОЛЕ: Карта {card} назначена сразу нескольким сотрудникам: {', '.join(names)}."
                f" Карта не будет присвоена никому."
            )

        timecontrol_uids = {str(p.get('UID')) for p in persons if p.get('UID')}

        # --- ШАГ 2: Синхронизация ---
        with transaction.atomic():
            # 1. Очищаем все карты
            User.objects.update(rfid_card=None)

            # 2. Находим пользователей, которых нет в TimeControl (но НЕ УДАЛЯЕМ)
            users_to_keep = User.objects.exclude(username__in=timecontrol_uids).exclude(is_superuser=True)

            # Запоминаем их ФИО
            kept_users_list = [
                f"{u.first_name} {u.last_name}".strip() or u.username
                for u in users_to_keep
            ]

            stats['deleted'] = 0  # Мы никого не удаляем
            stats['deleted_users'] = kept_users_list  # Передаем список для предупреждения

        # 3. Раздаем карты заново
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
                    user, created = User.objects.get_or_create(username=str(uid), defaults={'email': None})

                    parts = fullname.split()
                    user.last_name = parts[0] if len(parts) > 0 else ''
                    user.first_name = parts[1] if len(parts) > 1 else ''
                    user.is_active = not is_locked
                    user.tabnum = tabnum.strip() if tabnum else ""
                    user.position = position
                    user.department = department

                    # Проверка на дубликаты
                    if rfid_card and rfid_card in duplicate_cards:
                        user.rfid_card = None
                    else:
                        user.rfid_card = rfid_card if rfid_card else None

                    user.save()

                    # === АВТОМАТИЧЕСКОЕ ДОБАВЛЕНИЕ В ГРУППУ ===
                    if position and "кладовщик" in position.lower():
                        group, _ = Group.objects.get_or_create(name='Кладовщики')
                        user.groups.add(group)
                    else:
                        group = Group.objects.filter(name='Кладовщики').first()
                        if group and group in user.groups.all():
                            user.groups.remove(group)

                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

            except IntegrityError:
                stats['errors'].append(
                    f"Пользователь {fullname} (UID: {uid}): карта {rfid_card} уже занята другим сотрудником. Пропущен."
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