from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Инструменты
    path('', views.InstrumentListView.as_view(), name='instrument_list'),
    path('instruments/create/', views.InstrumentCreateView.as_view(), name='instrument_create'),
    path('instruments/<int:pk>/', views.InstrumentDetailView.as_view(), name='instrument_detail'),
    path('instruments/<int:pk>/update/', views.InstrumentUpdateView.as_view(), name='instrument_update'),
    path('instruments/<int:pk>/delete/', views.InstrumentDeleteView.as_view(), name='instrument_delete'),
    path('instruments/<int:pk>/write-off/', views.write_off_instrument, name='instrument_write_off'),
    path('instruments/<int:pk>/mark-broken/', views.mark_as_broken, name='instrument_mark_broken'),

    # Ремонтники
    path('repairers/', views.RepairerListView.as_view(), name='repairer_list'),
    path('repairers/create/', views.RepairerCreateView.as_view(), name='repairer_create'),

    # Ремонты
    path('repairs/', views.RepairListView.as_view(), name='repair_list'),
    path('repairs/create/', views.RepairCreateView.as_view(), name='repair_create'),
    path('instruments/<int:pk>/return-from-repair/', views.return_from_repair, name='instrument_return_from_repair'),

    # Перемещения
    path('relocations/', views.RelocationListView.as_view(), name='relocation_list'),
    path('relocations/create/', views.RelocationCreateView.as_view(), name='relocation_create'),

    path('api/search-instruments/', views.search_instruments, name='search_instruments'),
]