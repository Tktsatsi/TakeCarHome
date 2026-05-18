from django.db import models
from django.contrib.auth.models import User

class VehicleAuth(models.Model):
    SERVICE_DELIVERY_CENTRE = [
        ('REUVEN', 'reuven'),
        ('ROODEPORT', 'roodeport'),
        ('MIDRAND', 'midrand'),
        ('INNER CITY', 'inner city'),
        ('SIEMERT', 'siemert'),
        ('LENASIA', 'lenasia')
    ]

    VEHICLE_SECURITY =[
        ('YES', 'yes'),
        ('NO', 'no'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    #Vehicle pariculars
    vehicle_decription = models.CharField(max_length=255)
    vehicle_registration= models.CharField(max_length=10)
    odometer = models.PositiveIntegerField()

    #Driver particulars
    surname_initials = models.CharField(max_length=255)
    sap_no = models.IntegerField()
    department = models.CharField(max_length=255)
    cost_centre = models.IntegerField()
    Designation = models.CharField(max_length=255)
    SDC = models.CharField(max_length=10,choices=SERVICE_DELIVERY_CENTRE)
    resident_address = models.TextField()
    secure_locked_place = models.CharField(max_length=3,choices=VEHICLE_SECURITY)
    behind_locked_gates = models.CharField(max_length=3,choices=VEHICLE_SECURITY)
    #start_date = models.DateField()
    #end_date = models.DateField()
    motivation = models.TextField()
    declaration = models.BooleanField(default=False)
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='PENDING')

    def __str__(self):
        return self.vehicle_registration
    

class Approval(models.Model):
    ROLES = [
        ('SENIOR MANAGER/GM', 'senior manager/gm'),
        ('LINE MANAGER', 'line manager'),
        ('FLEET COMLPLIANCE', 'fleet compliance'),
        ('FLEET MANAGER', 'fleet manager'),
    ]

    authorization = models.ForeignKey(VehicleAuth, on_delete=models.CASCADE,related_name='approvals')
    role = models.CharField(max_length=50, choices=ROLES)
    approved_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    approved = models.BooleanField(default=False)
    comments = models.TextField(blank=True)
    signed_on = models.DateTimeField(null=True,blank=True)

