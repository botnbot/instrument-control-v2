from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class User(AbstractUser):
    username = models.CharField(max_length=20, unique=True, verbose_name="Имя пользователя")
    email = models.EmailField(unique=True, verbose_name='Email')
    rfid_card = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Номер RFID-карты"
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    REQUIRED_FIELDS = ['first_name', 'last_name', 'email']

    objects = UserManager()

    def __str__(self):
        return f'{self.first_name} {self.last_name}'