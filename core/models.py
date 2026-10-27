from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название категории')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Instrument(models.Model):
    STATUS_IN_USE = "IN_USE"
    STATUS_IN_REPAIR = "IN_REPAIR"
    STATUS_RELOCATED = "RELOCATED"
    STATUS_BROKEN = "BROKEN"
    STATUS_WRITTEN_OFF = "WRITTEN_OFF"

    STATUS_CHOICES = [
        (STATUS_IN_USE, "в работе"),
        (STATUS_IN_REPAIR, "в ремонте"),
        (STATUS_RELOCATED, "перемещен"),
        (STATUS_BROKEN, "сломан"),
        (STATUS_WRITTEN_OFF, "списан"),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instruments',
        verbose_name='Категория',
    )
    name = models.CharField(max_length=100, verbose_name='Наименование')
    inventory_N = models.CharField(max_length=20, unique=True, verbose_name='Инвентарный номер')
    entry_date = models.DateField(verbose_name="Дата ввода")
    price = models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Цена")
    is_new = models.BooleanField(default=True, verbose_name="Новый")
    image1 = models.ImageField(upload_to="instruments/foto", verbose_name="Фото 1")
    image2 = models.ImageField(upload_to="instruments/foto", verbose_name="Фото 2", blank=True, null=True)
    image3 = models.ImageField(upload_to="instruments/foto", verbose_name="Фото 3", blank=True, null=True)
    comment = models.TextField(max_length=200, blank=True, null=True, verbose_name="Комментарий")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_IN_USE, verbose_name="Статус")
    is_deleted = models.BooleanField(default=False, verbose_name="Удалён")

    def __str__(self):
        return f"{self.name} ({self.inventory_N})"

    @property
    def status_badge(self):
        return {
            self.STATUS_IN_USE: ("В работе", "success"),
            self.STATUS_IN_REPAIR: ("В ремонте", "warning text-dark"),
            self.STATUS_RELOCATED: ("Перемещен", "info text-dark"),
            self.STATUS_BROKEN: ("Сломан", "danger"),
            self.STATUS_WRITTEN_OFF: ("Списан", "danger text-dark"),
        }.get(self.status, ("Неизвестно", "secondary"))

    @property
    def total_repair_duration(self):
        """Суммарная продолжительность всех ремонтов (в днях)"""
        # Берем все ремонты этого инструмента, у которых заполнена дата возврата
        repairs = self.repairs.filter(date_of_receipt_from_repair__isnull=False)
        return sum(r.duration for r in repairs if r.duration is not None)

    class Meta:
        verbose_name = 'Инструмент'
        verbose_name_plural = 'Инструменты'
        ordering = ['-entry_date']


class Repairer(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    address = models.CharField(max_length=300, verbose_name="Адрес", blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name="Телефон", blank=True, null=True)
    contact_person = models.CharField(max_length=100, verbose_name="Контактное лицо", blank=True, null=True)
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    comment = models.CharField(max_length=300, verbose_name="Комментарий", blank=True, null=True)

    class Meta:
        verbose_name = 'Ремонтник'
        verbose_name_plural = 'Ремонтники'

    def __str__(self):
        return self.name


class Repair(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='repairs',
                                   verbose_name='Инструмент')
    repairer = models.ForeignKey(Repairer, on_delete=models.PROTECT, related_name='repairs', verbose_name='Исполнитель')
    failure_date = models.DateField(verbose_name='Дата поломки')
    date_of_delivery_for_repair = models.DateField(verbose_name="Дата сдачи в ремонт")
    date_of_receipt_from_repair = models.DateField(blank=True, null=True, verbose_name="Дата получения из ремонта")
    repair_cost = models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Стоимость ремонта", blank=True,
                                      null=True)
    comment = models.TextField(verbose_name="Комментарий", blank=True, null=True)

    @property
    def duration(self):
        if self.date_of_receipt_from_repair:
            return (self.date_of_receipt_from_repair - self.date_of_delivery_for_repair).days
        return None

    class Meta:
        verbose_name = 'Ремонт'
        verbose_name_plural = 'Ремонты'
        ordering = ['-date_of_delivery_for_repair']

    def __str__(self):
        return f"Ремонт {self.instrument.name}"


class Relocation(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='relocations',
                                   verbose_name="Инструмент")
    comment = models.CharField(max_length=255, verbose_name="Комментарий", blank=True)
    location = models.CharField(max_length=255, verbose_name="Куда перемещен")
    date = models.DateField(auto_now_add=True, verbose_name="Дата перемещения")

    def clean(self):
        if self.instrument and self.instrument.status == Instrument.STATUS_RELOCATED and not self.comment:
            raise ValidationError("Нужно указать комментарий для перемещенного инструмента")

    class Meta:
        verbose_name = 'Перемещение'
        verbose_name_plural = 'Перемещения'

    def __str__(self):
        return f"{self.instrument.name} -> {self.location}"


class WriteOff(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='write_offs',
                                   verbose_name="Инструмент")

    reason = models.CharField(max_length=250, verbose_name='Причина списания')
    date = models.DateField(auto_now_add=True, verbose_name='Дата списания')
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, verbose_name="Кто списал")

    class Meta:
        verbose_name = 'Списание'
        verbose_name_plural = 'Списания'

    def __str__(self):
        return f"Списание {self.instrument.name} {self.date}"
