from django.urls import path
from .views import rfid_login_view, register_view, login_view

urlpatterns = [
    path('login/', rfid_login_view, name='rfid_login'),
    path('login-password/', login_view, name='login_password'),
    path('register/', register_view, name='register'),
]
