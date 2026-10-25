from django.urls import path
from .views import rfid_login_view

urlpatterns = [
    path('login/', rfid_login_view, name='rfid_login'),
]