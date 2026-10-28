from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .models import Instrument, Repairer, Repair, Relocation
from .forms import InstrumentForm, RepairerForm, RepairForm, RelocationForm
from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required


def search_instruments(request):
    query = request.GET.get('q', '')
    if query:
        # Ищем по инвентарному номеру или названию
        instruments = Instrument.objects.filter(
            Q(inventory_N__icontains=query) | Q(name__icontains=query)
        )[:10]  # Ограничиваем вывод 10 результатами
    else:
        instruments = Instrument.objects.none()

    data = [
        {
            'id': inst.id,
            'text': f"{inst.inventory_N} - {inst.name}"  # Что видит пользователь
        }
        for inst in instruments
    ]
    return JsonResponse({'results': data})

# === Инструменты ===

class InstrumentListView(ListView):
    model = Instrument
    template_name = 'core/instruments/instrument_list.html'
    context_object_name = 'instruments'
    paginate_by = 10

    def get_queryset(self):
        # 1. Всегда скрываем мягко удалённые инструменты
        queryset = Instrument.objects.filter(is_deleted=False)

        # 2. По умолчанию скрываем списанные (если не стоит галочка)
        if self.request.GET.get('show_written_off') != '1':
            queryset = queryset.exclude(status=Instrument.STATUS_WRITTEN_OFF)

        # 3. Фильтр по категории
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
        # Мягкое удаление: не удаляем, а помечаем как удалённый
        success_url = self.get_success_url()
        self.object.is_deleted = True
        self.object.save()
        messages.success(self.request, f'Инструмент "{self.object.name}" удалён (перемещён в архив).')
        return redirect(success_url)

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
from django.db.models import F, ExpressionWrapper, DurationField
from django.db.models.functions import Coalesce
from django.utils import timezone


class RepairListView(ListView):
    model = Repair
    template_name = 'core/repairs/repairs_list.html'
    context_object_name = 'repairs'

    def get_queryset(self):
        queryset = super().get_queryset()

        # Аннотация: продолжительность в днях (для завершённых ремонтов)
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

@login_required
def write_off_instrument(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)

    # Проверка прав
    is_allowed = (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()
    )
    if not is_allowed:
        messages.error(request, "У вас нет прав на списание.")
        return redirect('core:instrument_list')

    # Проверка статуса: списывать можно только сломанные
    if instrument.status != Instrument.STATUS_BROKEN:
        messages.error(request, "Списывать можно только сломанные инструменты.")
        return redirect('core:instrument_list')

    instrument.status = Instrument.STATUS_WRITTEN_OFF
    instrument.save()
    messages.success(request, f'Инструмент "{instrument.name}" списан.')
    return redirect('core:instrument_list')

@login_required
def mark_as_broken(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)

    # Проверка прав: суперпользователь, Администрация или Кладовщики
    is_allowed = (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Администрация', 'Кладовщики']).exists()
    )
    if not is_allowed:
        messages.error(request, "У вас нет прав на изменение статуса.")
        return redirect('core:instrument_list')

    # Смена статуса на "Сломан"
    instrument.status = Instrument.STATUS_BROKEN
    instrument.save()
    messages.success(request, f'Инструмент "{instrument.name}" отмечен как сломанный.')

    return redirect('core:instrument_list')

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
        date_of_receipt = request.POST.get('date_of_receipt_from_repair')
        repair_cost = request.POST.get('repair_cost')

        if not date_of_receipt:
            messages.error(request, "Укажите дату возврата из ремонта.")
            return redirect('core:instrument_list')

        # Находим последний ремонт этого инструмента, у которого нет даты возврата
        repair = Repair.objects.filter(
            instrument=instrument,
            date_of_receipt_from_repair__isnull=True
        ).order_by('-date_of_delivery_for_repair').first()

        if repair:
            repair.date_of_receipt_from_repair = date_of_receipt
            if repair_cost:
                repair.repair_cost = repair_cost
            repair.save()
            messages.success(request, f'Инструмент "{instrument.name}" возвращён из ремонта.')
        else:
            messages.warning(request, "Не найден активный ремонт для этого инструмента.")

        instrument.status = Instrument.STATUS_IN_USE
        instrument.save()
        return redirect('core:instrument_list')
    return redirect('core:instrument_list')