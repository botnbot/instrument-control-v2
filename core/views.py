from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .models import Instrument, Repairer, Repair, Relocation
from .forms import InstrumentForm, RepairerForm, RepairForm, RelocationForm
from django.http import JsonResponse
from django.db.models import Q


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

    def get_queryset(self):
        queryset = super().get_queryset()
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import Category
        context['categories'] = Category.objects.all()
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