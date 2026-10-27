
from django.contrib.auth import login, authenticate
from django import forms
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from .forms import UserRegisterForm


def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # Активируем сразу (или False, если нужна проверка админом)
            user.save()

            # Автоматически добавляем в группу "Кладовщики"
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
                return redirect('core:instrument_list')
            else:
                form.add_error('rfid_card', 'Карта не найдена или пользователь неактивен.')
    else:
        form = RFIDLoginForm()
    return render(request, 'user/card_login.html', {'form': form})