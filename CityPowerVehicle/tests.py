from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import VehicleAuth


class PermissionRequestUiTests(TestCase):
    def test_permission_request_ui_is_hidden_on_auth_detail(self):
        user = User.objects.create_user(username='applicant', password='secret')
        authorization = VehicleAuth.objects.create(
            vehicle_decription='Test Vehicle',
            vehicle_registration='ABC123',
            odometer=1000,
            surname_initials='JD',
            sap_no=12345,
            department='Fleet',
            cost_centre=111,
            Designation='Driver',
            SDC='REUVEN',
            resident_address='123 Street',
            secure_locked_place='YES',
            behind_locked_gates='NO',
            motivation='Test',
            declaration=True,
            submitted_by=user,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('auth_detail', args=[authorization.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Request approval access')
        self.assertNotContains(response, 'Request Approval Permission')
        self.assertNotContains(response, 'requested approval')
