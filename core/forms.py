from django import forms
from .models import Instrument, Repairer, Repair, Relocation


class InstrumentForm(forms.ModelForm):

    class Meta:
        model = Instrument
        fields = [
            'category',
            'name',
            'inventory_N',
            'is_new',
            'entry_date',
            'price',
            'image1',
            'image2',
            'image3',
            'comment',
            'assigned_to',
            'status',
            'is_deleted',
        ]
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'entry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = "-- Выберите категорию --"
        # self.fields['assigned_to'].queryset = self.fields['assigned_to'].queryset.filter(is_active=True)


class RepairerForm(forms.ModelForm):
    class Meta:
        model = Repairer
        fields = '__all__'


class RepairForm(forms.ModelForm):
    class Meta:
        model = Repair
        fields = '__all__'
        widgets = {
            'instrument': forms.HiddenInput(),
            'failure_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_delivery_for_repair': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_receipt_from_repair': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'repairer': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['instrument'].required = False


class RelocationForm(forms.ModelForm):
    class Meta:
        model = Relocation
        fields = ['instrument', 'location', 'comment']
        widgets = {
             'instrument': forms.HiddenInput(),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['instrument'].required = True
