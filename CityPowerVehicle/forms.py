from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import VehicleAuth


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text='A valid email address is required.',
    )
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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'This email address is already registered.'
            )
        return email


class ApprovalForm(forms.Form):
    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Fleet manager only acknowledges
        if role == 'FLEET MANAGER':
            choices = [('acknowledge', 'Acknowledge')]
        else:
            choices = [
                ('approve', 'Approve'),
                ('reject', 'Reject'),
            ]
        self.fields['decision'] = forms.ChoiceField(
            choices=choices,
            widget=forms.RadioSelect,
            initial=choices[0][0],
        )
    comments = forms.CharField(
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': 4}
        ),
        required=False,
        label='Comments',
    )


class RequestApprovalPermissionForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': 4}
        ),
        required=True,
        label='Reason for requesting approval rights',
    )


class VehicleAuthForm(forms.ModelForm):
    class Meta:
        model = VehicleAuth

        exclude = [
            'submitted_by',
            'status',
            'next_approval_role',
            'senior_manager_name',
            'senior_manager_email',
            'fleet_compliance_name',
            'fleet_compliance_email',
            'fleet_manager_name',
            'fleet_manager_email',

            'permission_requested',
            'permission_requested_by',
            'permission_requested_at',
            'permission_request_response',
            'permission_request_responded_at',
        ]

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
            'line_manager_name': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'line_manager_email': forms.EmailInput(
                attrs={'class': 'form-control'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['line_manager_name'].required = True
        self.fields['line_manager_email'].required = True
        self.fields['declaration'].required = True

    def clean(self):

        cleaned_data = super().clean()

        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end and end < start:
            raise forms.ValidationError(
                'End date cannot be before start date.'
            )

        if not cleaned_data.get('declaration'):
            self.add_error(
                'declaration',
                'You must accept the declaration to submit this form.',
            )

        return cleaned_data


class ApprovalFormWithNextApprover(forms.Form):
    """Form for approvers to review, decide, and enter next approver details."""

    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        # Fleet manager only acknowledges
        if role == 'FLEET MANAGER':
            choices = [('acknowledge', 'Acknowledge')]
        else:
            choices = [
                ('approve', 'Approve'),
                ('reject', 'Reject'),
            ]
        self.fields['decision'] = forms.ChoiceField(
            choices=choices,
            widget=forms.RadioSelect,
            initial=choices[0][0],
        )
        # Add next approver fields if not fleet manager
        if role != 'FLEET MANAGER':
            self.fields['next_approver_name'] = forms.CharField(
                max_length=255,
                required=False,
                label='Next Approver Name',
                widget=forms.TextInput(attrs={'class': 'form-control'}),
            )
            self.fields['next_approver_email'] = forms.EmailField(
                required=False,
                label='Next Approver Email',
                widget=forms.EmailInput(attrs={'class': 'form-control'}),
            )

        self.fields['comments'] = forms.CharField(
            widget=forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4}
            ),
            required=False,
            label='Comments',
        )

    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')

        if self.role != 'FLEET MANAGER' and decision == 'approve':
            if not cleaned_data.get('next_approver_name'):
                self.add_error(
                    'next_approver_name',
                    'This field is required when approving.',
                )
            if not cleaned_data.get('next_approver_email'):
                self.add_error(
                    'next_approver_email',
                    'This field is required when approving.',
                )

        return cleaned_data
