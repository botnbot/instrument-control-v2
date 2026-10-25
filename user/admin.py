from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'rfid_card', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'rfid_card')

    fieldsets = UserAdmin.fieldsets + (
        ('RFID-карта', {'fields': ('rfid_card',)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('RFID-карта', {'fields': ('rfid_card',)}),
    )