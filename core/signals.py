from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Instrument, Repair, Relocation

@receiver(post_save, sender=Repair)
def update_instrument_status_on_repair(sender, instance, created, **kwargs):
    instrument = instance.instrument
    if not instrument:
        return

    if created and not instance.date_of_receipt_from_repair:
        if instrument.status != Instrument.STATUS_IN_REPAIR:
            instrument.status = Instrument.STATUS_IN_REPAIR
            instrument.save()

    if instance.date_of_receipt_from_repair:
        if instrument.status != Instrument.STATUS_IN_USE:
            instrument.status = Instrument.STATUS_IN_USE
            instrument.save()