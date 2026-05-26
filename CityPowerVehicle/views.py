from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .models import VehicleAuth, Approval, APPROVAL_ROLES
from django.urls import reverse
from .forms import VehicleAuthForm, RegistrationForm, ApprovalFormWithNextApprover
from django.contrib.auth import logout
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings


def user_has_role(user, role):
    if user.is_superuser:
        return True
    if not role:
        return False
    expected = role.strip().lower()
    return any(
        group.name.strip().lower() == expected
        for group in user.groups.all()
    )


def logout_view(request):
    """Log out the user and redirect to the login page.

    Accepts GET so the logout link can perform a simple redirect.
    """
    logout(request)
    return redirect('login')


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Registration successful! Please log in with your credentials.',
            )
            return redirect('login')
    else:
        form = RegistrationForm()

    return render(
        request,
        'CityPowerVehicle/register.html',
        {'form': form},
    )


@login_required
@never_cache
def edit_auth(request, pk):
    authorization = get_object_or_404(VehicleAuth, pk=pk)
    if not authorization.is_editable_by(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        form = VehicleAuthForm(request.POST, instance=authorization)
        if form.is_valid():
            form.save()
            return redirect('auth_detail', pk=pk)
    else:
        form = VehicleAuthForm(instance=authorization)

    return render(request, 'CityPowerVehicle/create_auth.html', {
        'form': form,
        'is_edit': True,
        'authorization': authorization,
    })


@login_required
@never_cache
def delete_auth(request, pk):
    authorization = get_object_or_404(VehicleAuth, pk=pk)
    if not authorization.is_deletable_by(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        authorization.delete()
        return redirect('dashboard')

    return render(request, 'CityPowerVehicle/delete_auth.html', {
        'authorization': authorization,
    })


@login_required
@never_cache
def approve_auth(request, pk):
    """Handle approval workflow where approvers can enter next approver details."""
    authorization = get_object_or_404(VehicleAuth, pk=pk)
    if authorization.status != 'PENDING':
        return redirect('auth_detail', pk=pk)

    current_role = authorization.next_approval_role
    if not user_has_role(request.user, current_role):
        return redirect('auth_detail', pk=pk)

    if request.method == 'POST':
        form = ApprovalFormWithNextApprover(
            request.POST,
            role=current_role,
        )
        if form.is_valid():
            decision = form.cleaned_data['decision']
            comments = form.cleaned_data['comments']

            # Handle fleet manager acknowledgement separately
            if decision == 'acknowledge' and current_role == 'FLEET MANAGER':
                Approval.objects.create(
                    authorization=authorization,
                    role=current_role,
                    approved_by=request.user,
                    approved=False,
                    acknowledged=True,
                    comments=comments,
                    signed_on=timezone.now(),
                )
                authorization.status = 'APPROVED'
                authorization.next_approval_role = ''
                authorization.save()
                return redirect('auth_detail', pk=pk)

            approved = decision == 'approve'
            Approval.objects.create(
                authorization=authorization,
                role=current_role,
                approved_by=request.user,
                approved=approved,
                comments=comments,
                signed_on=timezone.now(),
            )

            if approved:
                # Get next approver details from form
                next_approver_name = form.cleaned_data.get('next_approver_name')
                next_approver_email = form.cleaned_data.get('next_approver_email')

                # Advance to next role
                authorization.advance_approval()
                next_role = authorization.next_approval_role

                # Store the provided approver details on the VehicleAuth record
                if next_role == 'SENIOR MANAGER/GM':
                    authorization.senior_manager_name = next_approver_name
                    authorization.senior_manager_email = next_approver_email
                elif next_role == 'FLEET COMLPLIANCE':
                    authorization.fleet_compliance_name = next_approver_name
                    authorization.fleet_compliance_email = next_approver_email
                elif next_role == 'FLEET MANAGER':
                    authorization.fleet_manager_name = next_approver_name
                    authorization.fleet_manager_email = next_approver_email

                authorization.save()

                # Send email to next approver
                if next_role and next_approver_email:
                    try:
                        subject = (
                            f"Approval required: "
                            f"Vehicle auth {authorization.vehicle_registration}"
                        )
                        link = request.build_absolute_uri(
                            authorization.get_approval_url()
                        )
                        applicant_name = (
                            authorization.submitted_by.get_full_name()
                            or authorization.submitted_by.username
                        )
                        message = (
                            f"An approval is required from {next_role}.\n\n"
                            f"Applicant: {applicant_name}\n"
                            f"Vehicle: {authorization.vehicle_registration}\n"
                            f"Start: {authorization.start_date}\n"
                            f"End: {authorization.end_date}\n"
                            f"Motivation: {authorization.motivation}\n\n"
                            f"Review the application: {link}"
                        )
                        from_email = getattr(
                            settings,
                            'DEFAULT_FROM_EMAIL',
                            None,
                        )
                        send_mail(
                            subject,
                            message,
                            from_email,
                            [next_approver_email],
                        )
                        print(f"\n✓ EMAIL SENT TO: {next_approver_email}\n")
                    except Exception as e:
                        print(f"\n✗ EMAIL FAILED: {type(e).__name__}: {e}\n")
            else:
                authorization.status = 'REJECTED'
                authorization.next_approval_role = ''
                authorization.save()

            return redirect('auth_detail', pk=pk)
    else:
        form = ApprovalFormWithNextApprover(role=current_role)

    return render(
        request,
        'CityPowerVehicle/approve_auth.html',
        {
            'form': form,
            'authorization': authorization,
            'current_role': current_role,
        },
    )


@login_required
@never_cache
def dashboard(request):
    # Applicants should only see their own application history.
    # Superusers keep the old behaviour and see all applications.
    if request.user.is_superuser:
        authorizations = VehicleAuth.objects.all()
    else:
        authorizations = VehicleAuth.objects.filter(submitted_by=request.user)

    # Build a list of dicts so template can decide whether to link to approval view
    authorizations_with_meta = [
        {
            'authorization': a,
            'can_approve': a.can_be_approved_by(request.user),
        }
        for a in authorizations
    ]

    return render(
        request,
        'CityPowerVehicle/dashboard.html',
        {'authorizations_with_meta': authorizations_with_meta},
    )


@login_required
@never_cache
def create_auth(request):
    if request.method == 'POST':
        form = VehicleAuthForm(request.POST)

        if form.is_valid():
            authorization = form.save(commit=False)
            authorization.submitted_by = request.user
            authorization.save()

            # Send email to line manager
            line_manager_email = authorization.line_manager_email
            if line_manager_email:
                try:
                    subject = (
                        f"Vehicle authorization approval required: "
                        f"{authorization.vehicle_registration}"
                    )
                    link = request.build_absolute_uri(
                        authorization.get_approval_url()
                    )
                    message = (
                        f"A vehicle authorization request requires your approval.\n\n"
                        f"Applicant: "
                        f"{request.user.get_full_name() or request.user.username}\n"
                        f"Vehicle: {authorization.vehicle_registration}\n"
                        f"Start: {authorization.start_date}\n"
                        f"End: {authorization.end_date}\n"
                        f"Motivation: {authorization.motivation}\n\n"
                        f"Review and approve: {link}"
                    )
                    from_email = getattr(
                        settings,
                        'DEFAULT_FROM_EMAIL',
                        None,
                    )
                    send_mail(
                        subject,
                        message,
                        from_email,
                        [line_manager_email],
                    )
                    print(f"\n✓ EMAIL SENT TO: {line_manager_email}\n")
                except Exception as e:
                    print(f"\n✗ EMAIL FAILED: {type(e).__name__}: {e}\n")

            return redirect('dashboard')
    else:
        form = VehicleAuthForm()

    return render(
        request,
        'CityPowerVehicle/create_auth.html',
        {'form': form},
    )


@login_required
@never_cache
def auth_detail(request, pk):
    authorization = get_object_or_404(VehicleAuth, pk=pk)
    approval_history = authorization.approvals.order_by('signed_on')
    next_role_label = None
    if authorization.status == 'PENDING' and authorization.next_approval_role:
        next_role_label = dict(
            APPROVAL_ROLES,
        ).get(
            authorization.next_approval_role,
            authorization.next_approval_role,
        )

    return render(
        request,
        'CityPowerVehicle/auth_detail.html',
        {
            'authorization': authorization,
            'approval_history': approval_history,
            'can_edit': authorization.is_editable_by(request.user),
            'can_delete': authorization.is_deletable_by(request.user),
            'can_approve': (
                authorization.status == 'PENDING'
                and user_has_role(
                    request.user,
                    authorization.next_approval_role,
                )
            ),
            'next_role_label': next_role_label,
        },
    )
