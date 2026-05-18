from django import forms
from .models import VehicleAuth

class VehicleAuthForm(forms.ModelForm):
    class Meta:
        model = VehicleAuth

        exclude = ['submitted_by', 'status']

        widgets = {
            'authorization_start': forms.DateInput(attrs={'type': 'date'}),
            'authorization_end': forms.DateInput(attrs={'type': 'date'}),
            'motivation': forms.Textarea(attrs={'rows': 4}),
            'residential_address': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):

        cleaned_data = super().clean()

        start = cleaned_data.get('authorization_start')
        end = cleaned_data.get('authorization_end')

        if start and end and end < start:
            raise forms.ValidationError(
                'End date cannot be before start date.'
            )

        return cleaned_data