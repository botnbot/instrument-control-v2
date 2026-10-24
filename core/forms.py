from django import forms
from .models import Instrument, Repairer, Repair, Relocation


class InstrumentForm(forms.ModelForm):
    class Meta:
        model = Instrument
        fields = '__all__'
        widgets = {
            'entry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }


class RepairerForm(forms.ModelForm):
    class Meta:
        model = Repairer
        fields = '__all__'


class RepairForm(forms.ModelForm):
    class Meta:
        model = Repair
        fields = '__all__'
        widgets = {
            'failure_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_delivery_for_repair': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_receipt_from_repair': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class RelocationForm(forms.ModelForm):
    class Meta:
        model = Relocation
        fields = '__all__'