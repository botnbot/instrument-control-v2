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
        'total_processed': 0
    }

    try:
        response = requests.get(url, auth=auth, timeout=15)
        response.raise_for_status()
        data = response.json()
        persons = data.get('data', [])

        with transaction.atomic():
            for person in persons:
                uid = person.get('UID')
                tabnum = person.get('TABNUM', '')
                fullname = person.get('FULLNAME', '')
                is_locked = person.get('ISLOCKED') == '1'
                rfid_card = person.get('SHEDCARDKEY', '')

                if not uid or not fullname:
                    continue

                stats['total_processed'] += 1

                user, created = User.objects.get_or_create(
                    username=str(uid),
                    defaults={'email': None}
                )

                parts = fullname.split()
                last_name = parts[0] if len(parts) > 0 else ''
                first_name = parts[1] if len(parts) > 1 else ''

                user.first_name = first_name
                user.last_name = last_name
                user.is_active = not is_locked
                user.tabnum = tabnum.strip() if tabnum else None

                # === БЛОК ОБРАБОТКИ КАРТЫ ===
                if rfid_card and rfid_card.strip():
                    clean_card = rfid_card.strip()
                    # Ищем, не занята ли карта другим пользователем
                    existing_owner = User.objects.filter(rfid_card=clean_card).exclude(pk=user.pk).first()

                    if existing_owner:
                        if force_overwrite:
                            # Перезаписываем (только если пользователь нажал "Да")
                            existing_owner.rfid_card = None
                            existing_owner.save(update_fields=['rfid_card'])
                            user.rfid_card = clean_card
                            stats['errors'].append(
                                f"Карта {clean_card} передана от '{existing_owner.first_name} {existing_owner.last_name}' "
                                f"к '{first_name} {last_name}'."
                            )
                        else:
                            # Если не нажал "Да", не трогаем карту
                            stats['conflicts'].append(
                                f"Карта {clean_card} уже есть у '{existing_owner.first_name} {existing_owner.last_name}'. "
                                f"Требуется передать её '{first_name} {last_name}'."
                            )
                    else:
                        user.rfid_card = clean_card
                else:
                    user.rfid_card = None

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