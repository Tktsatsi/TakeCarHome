from django.contrib import admin
from .models import VehicleAuth, Approval

@admin.register(VehicleAuth)
class VehicleAuthAdmin(admin.ModelAdmin):
    list_display = (
        'surname_initials',
        'vehicle_registration',
        'created_at',
        'status',
    )

@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = (
        'authorization',
        'role',
        'approved',
        'signed_on',
    )