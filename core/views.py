import os
import subprocess
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import ExpressionWrapper, F, DurationField, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView

from .forms import InstrumentForm, RepairerForm, RepairForm, RelocationForm
from .models import Instrument, Repairer, Repair, Relocation, WriteOff
from .services.timecontrol import sync_users_from_timecontrol

User = get_user_model()


# === Инструменты ===

def search_instruments(request):
    query = request.GET.get('q', '').strip()
    if query:
        instruments = Instrument.objects.filter(
            Q(inventory_N__icontains=query) |
            Q(name__icontains=query) |
            Q(id__iexact=query)
        )[:10]
    else:
        instruments = Instrument.objects.none()

    # возвращаем JSON, иначе Select2 не получит данные
    data = [
        {
            'id': inst.id,
            'text': f"{inst.inventory_N} - {inst.name}"
        }
        for inst in instruments
    ]
    return JsonResponse({'results': data})


class InstrumentListView(ListView):
    model = Instrument
    template_name = 'core/instruments/instrument_list.html'
    context_object_name = 'instruments'
    paginate_by = 10

    def get_queryset(self):
        queryset = Instrument.objects.filter(is_deleted=False)
        if self.request.GET.get('show_written_off') != '1':
            queryset = queryset.exclude(status=Instrument.STATUS_WRITTEN_OFF)
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import Category
        context['categories'] = Category.objects.all()
        context['show_written_off'] = self.request.GET.get('show_written_off') == '1'
        return context


class InstrumentDetailView(DetailView):
    model = Instrument
    template_name = 'core/instruments/instrument_detail.html'
    context_object_name = 'instrument'


class InstrumentCreateView(LoginRequiredMixin, CreateView):
    model = Instrument
    form_class = InstrumentForm
    template_name = 'core/instruments/instruments_form.html'
    success_url = reverse_lazy('core:instrument_list')


class InstrumentUpdateView(LoginRequiredMixin, UpdateView):
    model = Instrument
    form_class = InstrumentForm
    template_name = 'core/instruments/instruments_form.html'
    success_url = reverse_lazy('core:instrument_list')


class InstrumentDeleteView(LoginRequiredMixin, DeleteView):
    model = Instrument
    template_name = 'core/instruments/instrument_confirm_delete.html'
    success_url = reverse_lazy('core:instrument_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Удалять инструменты может только суперпользователь.")
            return redirect('core:instrument_list')

        instrument = self.get_object()
        if instrument.status != Instrument.STATUS_WRITTEN_OFF:
            messages.error(request, "Можно удалять только списанные инструменты.")
            return redirect('core:instrument_list')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.is_deleted = True
        self.object.save()
        messages.success(self.request, f'Инструмент "{self.object.name}" удалён (перемещён в архив).')
        return redirect(success_url)


@login_required
def write_off_instrument(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)

    is_allowed = (
            request.user.is_superuser or
            request.user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()
    )
    if not is_allowed:
        messages.error(request, "У вас нет прав на списание.")
        return redirect('core:instrument_list')

    if instrument.status != Instrument.STATUS_BROKEN:
        messages.error(request, "Списывать можно только сломанные инструменты.")
        return redirect('core:instrument_list')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Укажите причину списания.")
            return redirect('core:instrument_detail', pk=instrument.pk)

        with transaction.atomic():
            WriteOff.objects.create(
                instrument=instrument,
                reason=reason,
                user=request.user,
            )
            instrument.status = Instrument.STATUS_WRITTEN_OFF
            instrument.save(update_fields=['status'])

        messages.success(request, f'Инструмент "{instrument.name}" списан.')
        return redirect('core:instrument_list')

    return redirect('core:instrument_detail', pk=instrument.pk)


# === Ремонтники ===

class RepairerListView(ListView):
    model = Repairer
    template_name = 'core/repairers/repairers_list.html'
    context_object_name = 'repairers'


class RepairerCreateView(LoginRequiredMixin, CreateView):
    model = Repairer
    form_class = RepairerForm
    template_name = 'core/repairers/repairers_form.html'
    success_url = reverse_lazy('core:repairer_list')


# === Ремонты ===

class RepairListView(ListView):
    model = Repair
    template_name = 'core/repairs/repairs_list.html'
    context_object_name = 'repairs'

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.annotate(
            duration_days=ExpressionWrapper(
                F('date_of_receipt_from_repair') - F('date_of_delivery_for_repair'),
                output_field=DurationField()
            )
        )

        sort = self.request.GET.get('sort', 'date_of_delivery_for_repair')
        order = self.request.GET.get('order', 'desc')

        if sort == 'duration':
            sort = 'duration_days'

        allowed_sort_fields = [
            'instrument__name',
            'repairer__name',
            'date_of_delivery_for_repair',
            'date_of_receipt_from_repair',
            'duration_days',
        ]
        if sort in allowed_sort_fields:
            if order == 'desc':
                sort = '-' + sort
            queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.request.GET.get('sort', 'date_of_delivery_for_repair')
        context['current_order'] = self.request.GET.get('order', 'desc')
        return context


class RepairCreateView(LoginRequiredMixin, CreateView):
    model = Repair
    form_class = RepairForm
    template_name = 'core/repairs/repairs_form.html'
    success_url = reverse_lazy('core:repair_list')

    def get_initial(self):
        initial = super().get_initial()
        instrument_id = self.request.GET.get('instrument')
        if instrument_id:
            initial['instrument'] = instrument_id
        return initial


@login_required
def issue_instrument(request):
    is_allowed = (
            request.user.is_superuser or
            request.user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()
    )
    if not is_allowed:
        messages.error(request, "У вас нет прав на выдачу инструментов.")
        return redirect('core:instrument_list')

    user_to_assign = None
    rfid_error = None

    if request.method == 'POST' and 'rfid_card' in request.POST:
        rfid = request.POST.get('rfid_card', '').strip()
        if rfid:
            try:
                user_to_assign = User.objects.get(rfid_card=rfid, is_active=True)
                messages.success(request, f'Пользователь найден: {user_to_assign}')
            except User.DoesNotExist:
                rfid_error = "Пользователь с такой картой не найден или неактивен."

    if request.method == 'POST' and 'instrument_id' in request.POST:
        instrument = get_object_or_404(Instrument, pk=request.POST.get('instrument_id'))
        user_id = request.POST.get('user_id')
        user_to_assign = get_object_or_404(User, pk=user_id)

        if instrument.status != Instrument.STATUS_IN_USE:
            messages.error(request, "Можно выдавать только инструменты со статусом «В работе».")
        elif instrument.assigned_to:
            messages.warning(request, f'Инструмент уже закреплён за {instrument.assigned_to}.')
        else:
            instrument.assigned_to = user_to_assign
            instrument.save()
            messages.success(request, f'Инструмент "{instrument.name}" выдан пользователю {user_to_assign}.')
            return redirect('core:issue_instrument')

    available_instruments = Instrument.objects.filter(
        is_deleted=False,
        status=Instrument.STATUS_IN_USE,
        assigned_to__isnull=True
    )

    return render(request, 'core/issue_instrument.html', {
        'user_to_assign': user_to_assign,
        'rfid_error': rfid_error,
        'available_instruments': available_instruments,
    })


# === Сдача инструмента ===

@login_required
def return_instrument(request):
    is_allowed = (
            request.user.is_superuser or
            request.user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()
    )
    if not is_allowed:
        messages.error(request, "У вас нет прав на прием инструментов.")
        return redirect('core:instrument_list')

    user_to_return = None
    rfid_error = None

    if request.method == 'POST' and 'rfid_card' in request.POST:
        rfid = request.POST.get('rfid_card', '').strip()
        if rfid:
            try:
                user_to_return = User.objects.get(rfid_card=rfid, is_active=True)
                messages.success(request, f'Пользователь найден: {user_to_return}')
            except User.DoesNotExist:
                rfid_error = "Пользователь с такой картой не найден или неактивен."

    if request.method == 'POST' and 'instrument_id' in request.POST:
        instrument = get_object_or_404(Instrument, pk=request.POST.get('instrument_id'))

        if instrument.assigned_to is None:
            messages.warning(request, f'Инструмент "{instrument.name}" и так не за кем не закреплен.')
        else:
            with transaction.atomic():
                instrument.assigned_to = None
                instrument.save(update_fields=['assigned_to'])
            messages.success(request, f'Инструмент "{instrument.name}" успешно возвращён на склад.')
            return redirect(
                f"{reverse_lazy('core:return_instrument')}?user_id={user_to_return.pk if user_to_return else ''}")

    user_instruments = []
    if user_to_return:
        user_instruments = Instrument.objects.filter(
            is_deleted=False,
            assigned_to=user_to_return
        )
    elif request.method == 'GET' and request.GET.get('user_id'):
        user_to_return = get_object_or_404(User, pk=request.GET.get('user_id'))
        user_instruments = Instrument.objects.filter(
            is_deleted=False,
            assigned_to=user_to_return
        )

    return render(request, 'core/return_instrument.html', {
        'user_to_return': user_to_return,
        'rfid_error': rfid_error,
        'user_instruments': user_instruments,
    })


# === Перемещения ===

class RelocationListView(ListView):
    model = Relocation
    template_name = 'core/relocations/relocations_list.html'
    context_object_name = 'relocations'


class RelocationCreateView(LoginRequiredMixin, CreateView):
    model = Relocation
    form_class = RelocationForm
    template_name = 'core/relocations/relocations_form.html'
    success_url = reverse_lazy('core:relocation_list')

    def get_initial(self):
        initial = super().get_initial()
        instrument_id = self.request.GET.get('instrument')
        if instrument_id:
            initial['instrument'] = instrument_id
        return initial


# === Пометка сломанным ===

@login_required
def mark_as_broken(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)

    is_allowed = (
            request.user.is_superuser or
            request.user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()
    )
    if not is_allowed:
        messages.error(request, "У вас нет прав на изменение статуса.")
        return redirect('core:instrument_list')

    if instrument.status not in (Instrument.STATUS_IN_USE, Instrument.STATUS_RELOCATED):
        messages.error(request, "Пометить сломанным можно только инструмент «В работе» или «Перемещён».")
        return redirect('core:instrument_detail', pk=instrument.pk)

    instrument.status = Instrument.STATUS_BROKEN
    instrument.save(update_fields=['status'])
    messages.success(request, f'Инструмент "{instrument.name}" отмечен как сломанный.')
    return redirect('core:instrument_list')


# === Возврат из ремонта ===

@login_required
def return_from_repair(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)

    is_allowed = (
            request.user.is_superuser or
            request.user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()
    )
    if not is_allowed:
        messages.error(request, "У вас нет прав на возврат из ремонта.")
        return redirect('core:instrument_list')

    if instrument.status != Instrument.STATUS_IN_REPAIR:
        messages.error(request, "Этот инструмент не находится в ремонте.")
        return redirect('core:instrument_list')

    if request.method == 'POST':
        raw_date = request.POST.get('date_of_receipt_from_repair', '').strip()
        raw_cost = request.POST.get('repair_cost', '').strip()

        try:
            date_of_receipt = date.fromisoformat(raw_date)
        except (ValueError, TypeError):
            messages.error(request, "Некорректная дата возврата.")
            return redirect('core:instrument_list')

        repair_cost = None
        if raw_cost:
            try:
                repair_cost = Decimal(raw_cost)
                if repair_cost < 0:
                    raise InvalidOperation
            except InvalidOperation:
                messages.error(request, "Некорректная стоимость ремонта.")
                return redirect('core:instrument_list')

        repair = Repair.objects.filter(
            instrument=instrument,
            date_of_receipt_from_repair__isnull=True
        ).order_by('-date_of_delivery_for_repair').first()

        if not repair:
            messages.warning(request, "Не найден активный ремонт для этого инструмента.")
            return redirect('core:instrument_list')

        if date_of_receipt < repair.date_of_delivery_for_repair:
            messages.error(request, "Дата возврата не может быть раньше даты сдачи в ремонт.")
            return redirect('core:instrument_list')

        with transaction.atomic():
            repair.date_of_receipt_from_repair = date_of_receipt
            if repair_cost is not None:
                repair.repair_cost = repair_cost
            repair.save(update_fields=['date_of_receipt_from_repair', 'repair_cost'])

            instrument.status = Instrument.STATUS_IN_USE
            instrument.save(update_fields=['status'])

        messages.success(request, f'Инструмент "{instrument.name}" возвращён из ремонта.')
        return redirect('core:instrument_list')
    return redirect('core:instrument_list')


# ========== ПРАВА ДОСТУПА ==========

def is_storekeeper_or_admin(user):
    return user.is_superuser or user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()


def is_superuser(user):
    return user.is_superuser


# ========== БЭКАП (PostgreSQL) ==========

@user_passes_test(is_storekeeper_or_admin)
def backup_view(request):
    """Создание бэкапа только базы данных PostgreSQL"""
    if request.method == 'POST':
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_filename = f"db_backup_{timestamp}.dump"

        backup_dir = Path(settings.BACKUP_ROOT)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / backup_filename

        pg_dump_path = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
        if not Path(pg_dump_path).exists():
            pg_dump_path = "pg_dump"

        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = settings.DATABASES['default']['PASSWORD']

            command = [
                pg_dump_path,
                "-h", settings.DATABASES['default']['HOST'],
                "-p", str(settings.DATABASES['default']['PORT']),
                "-U", settings.DATABASES['default']['USER'],
                "-F", "c",
                "-f", str(backup_path),
                settings.DATABASES['default']['NAME']
            ]

            subprocess.run(command, env=env, check=True)

            messages.success(request, f'Бэкап базы данных успешно создан: {backup_filename}')
            return FileResponse(open(backup_path, 'rb'), as_attachment=True, filename=backup_filename)

        except subprocess.CalledProcessError as e:
            messages.error(request, f'Ошибка при создании дампа БД: {str(e)}')
            return redirect('core:backup_view')
        except Exception as e:
            messages.error(request, f'Ошибка при создании бэкапа: {str(e)}')
            return redirect('core:backup_view')

    backups = []
    backup_dir = Path(settings.BACKUP_ROOT)
    if backup_dir.exists():
        for f in backup_dir.glob('*.dump'):
            backups.append(f.name)
    backups.sort(reverse=True)

    return render(request, 'core/backup.html', {'backups': backups})


@user_passes_test(is_storekeeper_or_admin)
def backup_download(request, filename: str):
    """Скачивание ранее созданного бэкапа"""
    if not filename.startswith("db_backup_") or not filename.endswith(".dump"):
        raise Http404

    root = Path(settings.BACKUP_ROOT).resolve()
    target = (root / filename).resolve()

    if root not in target.parents or not target.is_file():
        raise Http404

    return FileResponse(
        open(target, "rb"),
        as_attachment=True,
        filename=target.name,
        content_type="application/octet-stream",
    )


@user_passes_test(is_superuser)
def restore_view(request):
    """Восстановление из загруженного дампа базы (PostgreSQL) - только суперпользователь"""
    if request.method == 'POST' and request.FILES.get('backup_file'):
        uploaded_file = request.FILES['backup_file']

        if not uploaded_file.name.endswith('.dump'):
            messages.error(request, 'Файл должен быть в формате .dump')
            return redirect('core:backup_view')

        backup_dir = Path(settings.BACKUP_ROOT)
        backup_dir.mkdir(parents=True, exist_ok=True)
        temp_dump_path = backup_dir / 'temp_restore.dump'

        try:
            with open(temp_dump_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            pg_restore_path = r"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe"
            if not Path(pg_restore_path).exists():
                pg_restore_path = "pg_restore"

            env = os.environ.copy()
            env['PGPASSWORD'] = settings.DATABASES['default']['PASSWORD']

            command = [
                pg_restore_path,
                "-h", settings.DATABASES['default']['HOST'],
                "-p", str(settings.DATABASES['default']['PORT']),
                "-U", settings.DATABASES['default']['USER'],
                "-d", settings.DATABASES['default']['NAME'],
                "--clean",
                "--if-exists",
                str(temp_dump_path)
            ]

            subprocess.run(command, env=env, check=True)
            temp_dump_path.unlink()

            messages.success(request, 'База данных успешно восстановлена. Перезапустите сервер.')
            return redirect('core:instrument_list')

        except subprocess.CalledProcessError as e:
            messages.error(request, f'Ошибка при восстановлении БД: {str(e)}')
            if temp_dump_path.exists():
                temp_dump_path.unlink()
            return redirect('core:backup_view')
        except Exception as e:
            messages.error(request, f'Ошибка при восстановлении: {str(e)}')
            if temp_dump_path.exists():
                temp_dump_path.unlink()
            return redirect('core:backup_view')

    return redirect('core:backup_view')


# ========== СИНХРОНИЗАЦИЯ С TIMECONTROL ==========

@user_passes_test(is_storekeeper_or_admin)
def sync_timecontrol_view(request):
    if request.method == 'POST':
        # Вызываем функцию жесткой синхронизации
        stats = sync_users_from_timecontrol(force_overwrite=True)

        # 1. Выводим предупреждения о дубликатах карт (желтые плашки)
        if stats.get('conflicts'):
            for msg in stats['conflicts']:
                messages.warning(request, msg)

        # 2. Выводим ошибки, если они возникли (красные плашки)
        if stats.get('errors'):
            for err in stats['errors']:
                messages.error(request, err)


        # 3. Выводим финальную статистику
        messages.success(
            request,
            f"Синхронизация завершена. Создано: {stats.get('created', 0)}, "
            f"Обновлено: {stats.get('updated', 0)}, "
            f"Удалено: {stats.get('deleted', 0)}. "
            f"Всего обработано: {stats.get('total_processed', 0)}."
        )

        # ВЫВОДИМ СПИСОК УДАЛЕННЫХ (если они были)
        if stats.get('deleted_users'):
            deleted_str = ", ".join(stats['deleted_users'])
            messages.info(request, f"Удаленные сотрудники: {deleted_str}")
        return redirect('core:sync_timecontrol')

    # Для GET-запроса просто рендерим страницу
    return render(request, 'core/sync_timecontrol.html')