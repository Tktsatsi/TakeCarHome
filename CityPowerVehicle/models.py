from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

SERVICE_DELIVERY_CENTRE = [
    ('REUVEN', 'reuven'),
    ('ROODEPORT', 'roodeport'),
    ('MIDRAND', 'midrand'),
    ('INNER CITY', 'inner city'),
    ('SIEMERT', 'siemert'),
    ('LENASIA', 'lenasia')
]

VEHICLE_SECURITY = [
    ('YES', 'yes'),
    ('NO', 'no'),
]

STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
]

APPROVAL_ROLES = [
    ('LINE MANAGER', 'Line Manager'),
    ('SENIOR MANAGER/GM', 'Senior Manager/GM'),
    ('FLEET COMLPLIANCE', 'Fleet Compliance'),
    ('FLEET MANAGER', 'Fleet Manager'),
]

APPROVAL_ORDER = {
    'LINE MANAGER': 0,
    'SENIOR MANAGER/GM': 1,
    'FLEET COMLPLIANCE': 2,
    'FLEET MANAGER': 3,
}


class VehicleAuth(models.Model):
    # Vehicle particulars
    vehicle_decription = models.CharField(max_length=255)
    vehicle_registration = models.CharField(max_length=10)
    odometer = models.PositiveIntegerField()

    # Driver particulars
    surname_initials = models.CharField(max_length=255)
    sap_no = models.IntegerField()
    department = models.CharField(max_length=255)
    cost_centre = models.IntegerField()
    Designation = models.CharField(max_length=255)
    SDC = models.CharField(
        max_length=10,
        choices=SERVICE_DELIVERY_CENTRE,
    )
    resident_address = models.TextField()
    secure_locked_place = models.CharField(
        max_length=3,
        choices=VEHICLE_SECURITY,
    )
    behind_locked_gates = models.CharField(
        max_length=3,
        choices=VEHICLE_SECURITY,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    motivation = models.TextField()
    declaration = models.BooleanField(default=False)
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
    )
    next_approval_role = models.CharField(
        max_length=50,
        choices=APPROVAL_ROLES,
        default='LINE MANAGER',
    )
    # Manager contact details provided by applicant
    line_manager_name = models.CharField(max_length=255, blank=True)
    line_manager_email = models.EmailField(blank=True)
    senior_manager_name = models.CharField(max_length=255, blank=True)
    senior_manager_email = models.EmailField(blank=True)
    fleet_compliance_name = models.CharField(max_length=255, blank=True)
    fleet_compliance_email = models.EmailField(blank=True)
    fleet_manager_name = models.CharField(max_length=255, blank=True)
    fleet_manager_email = models.EmailField(blank=True)

    def __str__(self):
        return self.vehicle_registration

    def get_absolute_url(self):
        return reverse('auth_detail', args=[self.pk])

    def get_approval_url(self):
        return reverse('approve_auth', args=[self.pk])

    def is_editable_by(self, user):
        return self.status == 'PENDING' and self.submitted_by == user

    def is_deletable_by(self, user):
        return self.status == 'PENDING' and self.submitted_by == user

    def get_current_approval_index(self):
        return APPROVAL_ORDER.get(self.next_approval_role, -1)

    def advance_approval(self):
        current_index = self.get_current_approval_index()
        if current_index + 1 < len(APPROVAL_ORDER):
            self.next_approval_role = list(
                APPROVAL_ORDER.keys())[current_index + 1]
        else:
            self.status = 'APPROVED'
            self.next_approval_role = ''

    def can_be_approved_by(self, user):
        if self.status != 'PENDING':
            return False
        if user.is_superuser:
            return True
        if not self.next_approval_role:
            return False
        expected = self.next_approval_role.strip().lower()
        return any(
            group.name.strip().lower() == expected
            for group in user.groups.all()
        )

    def get_manager_email(self, role_key):
        mapping = {
            'LINE MANAGER': self.line_manager_email,
            'SENIOR MANAGER/GM': self.senior_manager_email,
            'FLEET COMLPLIANCE': self.fleet_compliance_email,
            'FLEET MANAGER': self.fleet_manager_email,
        }
        return mapping.get(role_key)


class Approval(models.Model):
    authorization = models.ForeignKey(
        VehicleAuth,
        on_delete=models.CASCADE,
        related_name='approvals',
    )
    role = models.CharField(max_length=50, choices=APPROVAL_ROLES)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approved = models.BooleanField(default=False)
    acknowledged = models.BooleanField(default=False)
    comments = models.TextField(blank=True)
    signed_on = models.DateTimeField(null=True, blank=True)

    def get_display_status(self):
        if self.acknowledged:
            return 'Acknowledged'
        return 'Approved' if self.approved else 'Rejected'
