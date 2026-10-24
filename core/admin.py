from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Category, Instrument, Repairer, Repair, Relocation


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ('inventory_N', 'name', 'category', 'status', 'price')
    list_display_links = ('inventory_N', 'name')
    list_filter = ('category', 'status')
    search_fields = ('name', 'inventory_N')


@admin.register(Repairer)
class RepairerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone')
    search_fields = ('name',)


@admin.register(Repair)
class RepairAdmin(admin.ModelAdmin):
    list_display = ('instrument', 'repairer', 'failure_date', 'duration')


@admin.register(Relocation)
class RelocationAdmin(admin.ModelAdmin):
    list_display = ('instrument', 'location', 'date')