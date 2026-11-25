from django.forms import forms

from .models import Instrument, Repairer, Repair, Relocation

class RepairForm(forms.ModelForm):
    class Meta:
        model = Repair
        fields = '__all__'
        widgets = {
            'instrument': forms.Select(attrs={'class': 'form-select'}),
            'failure_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_delivery_for_repair': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_receipt_from_repair': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'repairer': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['instrument'].required = False
        self.fields['instrument'].queryset = Instrument.objects.filter(is_deleted=False)
        self.fields['instrument'].empty_label = "-- Выберите инструмент --"