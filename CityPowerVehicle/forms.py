from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import VehicleAuth


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'password1',
            'password2',
        ]


class ApprovalForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
        ],
        widget=forms.RadioSelect,
        initial='approve',
    )
    comments = forms.CharField(
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': 4}
        ),
        required=False,
        label='Comments',
    )


class VehicleAuthForm(forms.ModelForm):
    class Meta:
        model = VehicleAuth

        exclude = ['submitted_by', 'status']

        widgets = {
            'vehicle_decription': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'vehicle_registration': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'odometer': forms.NumberInput(
                attrs={'class': 'form-control'},
            ),
            'surname_initials': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'sap_no': forms.NumberInput(
                attrs={'class': 'form-control'},
            ),
            'department': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'cost_centre': forms.NumberInput(
                attrs={'class': 'form-control'},
            ),
            'Designation': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'SDC': forms.Select(
                attrs={'class': 'form-control'},
            ),
            'resident_address': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3},
            ),
            'secure_locked_place': forms.Select(
                attrs={'class': 'form-control'},
            ),
            'behind_locked_gates': forms.Select(
                attrs={'class': 'form-control'},
            ),
            'start_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
            ),
            'end_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
            ),
            'motivation': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4},
            ),
            'declaration': forms.CheckboxInput(
                attrs={'class': 'form-check-input'},
            ),
        }

    def clean(self):

        cleaned_data = super().clean()

        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end and end < start:
            raise forms.ValidationError(
                'End date cannot be before start date.'
            )

        return cleaned_data
