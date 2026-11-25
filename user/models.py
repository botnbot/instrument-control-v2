from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class User(AbstractUser):

    username = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Имя пользователя"
)


    rfid_card = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Номер карты"
)

#     email = models.EmailField(
#         max_length=50,
#         unique=True,
#         blank=True,
#         null=True,
#         verbose_name="E-mail"
# )

    tabnum = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Табельный номер",
)

    is_active = models.BooleanField(
        default=True,

)

    password = models.CharField(
        blank=True,
        null=True,
        verbose_name='Пароль',
)

    # department  = models.CharField(
    #     blank=True,
    #     null=True
    # )

    position = models.CharField(
        blank=True,
        null=True
)

    REQUIRED_FIELDS = ['first_name', 'last_name']


    def __str__(self):
        return f'{self.first_name} {self.last_name}'

objects = UserManager()