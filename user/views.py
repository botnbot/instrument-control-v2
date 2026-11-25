from django.contrib import messages
from django.contrib.auth import login, authenticate
from django import forms
from django.shortcuts import render, redirect
from django.conf import settings  # <-- Важно: импортируем настройки Django

from .forms import LoginForm, UserRegisterForm


def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.save()

            from django.contrib.auth.models import Group
            try:
                group = Group.objects.get(name='Кладовщики')
                user.groups.add(group)
            except Group.DoesNotExist:
                pass

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Добро пожаловать, {user.first_name}! Регистрация прошла успешно.')
            return redirect('core:instrument_list')
    else:
        form = UserRegisterForm()

    return render(request, 'user/register.html', {'form': form})


class RFIDLoginForm(forms.Form):
    rfid_card = forms.CharField(
        label="Приложите карту",
        widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Ожидание карты...', 'class': 'form-control'})
    )


def rfid_login_view(request):
    if request.method == 'POST':
        form = RFIDLoginForm(request.POST)
        if form.is_valid():
            rfid = form.cleaned_data['rfid_card']
            user = authenticate(request, rfid_card=rfid)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.first_name or user.username}!')
                return redirect('core:instrument_list')
            else:
                form.add_error('rfid_card', 'Карта не найдена или пользователь неактивен.')
    else:
        form = RFIDLoginForm()

    # Передаем debug в шаблон, чтобы спрятать поле ввода, если DEBUG=False
    return render(request, 'user/card_login.html', {
        'form': form,
        'debug': settings.DEBUG
    })


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.first_name or user.username}!')
                return redirect('core:instrument_list')
            else:
                messages.error(request, 'Неверный логин или пароль.')
    else:
        form = LoginForm()

    return render(request, 'user/login.html', {
        'form': form,
        'debug': settings.DEBUG
    })