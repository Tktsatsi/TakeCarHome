from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .models import VehicleAuth, Approval, APPROVAL_ROLES
from .forms import (
    VehicleAuthForm,
    RegistrationForm,
    ApprovalFormWithNextApprover,
    RequestApprovalPermissionForm,
)
from django.contrib.auth import logout
from django.contrib import messages
from django.core.mail import mail_admins, send_mail
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


def user_is_approval_manager(user):

    if user.is_superuser:
        return True
    approval_groups = {role.strip().lower() for role, _ in APPROVAL_ROLES}
    return any(
        group.name.strip().lower() in approval_groups
        for group in user.groups.all()
    )

def get_expected_approver_email(auth):
    role = auth.next_approval_role

    if role == "LINE MANAGER":
        return auth.line_manager_email

    elif role == "SENIOR MANAGER/GM":
        return auth.senior_manager_email

    elif role == "FLEET COMPLIANCE":
        return auth.fleet_compliance_email

    elif role == "FLEET MANAGER":
        return auth.fleet_manager_email

    return None

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
    has_permission = user_has_role(request.user, current_role)

    approver_email = get_expected_approver_email(authorization)

    is_expected_approver =(
        approver_email 
        and request.user.email.lower() == approver_email.lower()
    )

    # only the assigned approver may open the review page
    if not is_expected_approver:
        messages.error(
            request,
            "This request is assigned to another approver."
        )
        return redirect("auth_detail", pk=pk)
    
    existing = Approval.objects.filter(
        authorization=authorization,
        role=current_role,
        approved_by=request.user,
    ).exists()

    if existing:
        messages.info(request, "You have already reviewed this request.")
        return redirect("auth_detail", pk=pk)

    if request.method == 'POST':
        if not has_permission:
            return redirect("request_permission", pk=pk)
        
        form = ApprovalFormWithNextApprover(request.POST, role=current_role)
        if form.is_valid():
            decision = form.cleaned_data['decision']
            comments = form.cleaned_data['comments']

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
                try:
                    viewed = request.session.get('viewed_authorizations', [])
                    if authorization.id in viewed:
                        viewed.remove(authorization.id)
                        request.session['viewed_authorizations'] = viewed
                except Exception:
                    pass
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
                next_approver_name = form.cleaned_data.get('next_approver_name')
                next_approver_email = form.cleaned_data.get('next_approver_email')

                authorization.advance_approval()
                next_role = authorization.next_approval_role

                if next_role == 'SENIOR MANAGER/GM':
                    authorization.senior_manager_name = next_approver_name
                    authorization.senior_manager_email = next_approver_email
                elif next_role == 'FLEET COMPLIANCE':
                    authorization.fleet_compliance_name = next_approver_name
                    authorization.fleet_compliance_email = next_approver_email
                elif next_role == 'FLEET MANAGER':
                    authorization.fleet_manager_name = next_approver_name
                    authorization.fleet_manager_email = next_approver_email

                authorization.save()

                if next_role and next_approver_email:
                    try:
                        subject = (
                            f'Approval required: '
                            f'Vehicle auth {authorization.vehicle_registration}'
                        )
                        link = request.build_absolute_uri(
                            authorization.get_approval_url()
                        )
                        applicant_name = (
                            authorization.submitted_by.get_full_name()
                            or authorization.submitted_by.username
                        )
                        message = (
                            f'An approval is required from {next_role}.\n\n'
                            f'Applicant: {applicant_name}\n'
                            f'Vehicle: {authorization.vehicle_registration}\n'
                            f'Start: {authorization.start_date}\n'
                            f'End: {authorization.end_date}\n'
                            f'Motivation: {authorization.motivation}\n\n'
                            f'Review the application: {link}'
                        )
                        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
                        send_mail(subject, message, from_email, [next_approver_email])
                        print(f'\n✓ EMAIL SENT TO: {next_approver_email}\n')
                    except Exception as e:
                        print(f'\n✗ EMAIL FAILED: {type(e).__name__}: {e}\n')
            else:
                authorization.status = 'REJECTED'
                authorization.next_approval_role = ''
                authorization.save()

            try:
                
                if authorization.status != 'PENDING':
                    viewed = request.session.get('viewed_authorizations', [])
                    if authorization.id in viewed:
                        viewed.remove(authorization.id)
                        request.session['viewed_authorizations'] = viewed
            except Exception:
                pass

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
            'has_permission': has_permission,
        },
    )


@login_required
@never_cache
def request_approval_permission(request, pk):
    authorization = get_object_or_404(VehicleAuth, pk=pk)

    current_role = authorization.next_approval_role

    if request.method == "POST":
        form = RequestApprovalPermissionForm(request.POST)

        if form.is_valid():
            message = form.cleaned_data["message"]

            send_mail(
                subject=f"Approval Permission Request - {current_role}",
                message=(
                    f"User: {request.user.get_full_name() or request.user.username}\n"
                    f"Email: {request.user.email}\n"
                    f"Role Requested: {current_role}\n\n"
                    f"Reason:\n{message}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=["tktsatsi@gmail.com"],
            )
            messages.success(
                request,
                "Your approval permission request has been sent to the administrator."
            )

            return redirect("auth_detail", pk=pk)

    else:
        form = RequestApprovalPermissionForm()

    return render(
        request,
        "CityPowerVehicle/request_permission.html",
        {
            "form": form,
            "authorization": authorization,
            "current_role": current_role,
        },
    )


@login_required
@never_cache
def dashboard(request):
    # Requests this approver has opened from an email link
    viewed_ids = request.session.get("viewed_authorizations", [])
    
    if request.user.is_superuser:
        authorizations = VehicleAuth.objects.all()

    else:
        auth_by_id = {}

        # My own requests
        for auth in VehicleAuth.objects.filter(submitted_by=request.user):
            auth_by_id[auth.id] = auth

        # Requests assigned to me
        pending = VehicleAuth.objects.filter(status="PENDING")

        for auth in pending:
            approver_email = get_expected_approver_email(auth)

            if (
                approver_email
                and approver_email.strip().lower()
                == request.user.email.strip().lower()
            ):
                auth_by_id[auth.id] = auth

        # Requests I opened from an email
        for auth in VehicleAuth.objects.filter(id__in=viewed_ids):
            auth_by_id[auth.id] = auth

        authorizations = list(auth_by_id.values())

    authorizations_with_meta = []

    for auth in authorizations:

        approver_email = get_expected_approver_email(auth)

        is_expected_approver = (
            approver_email
            and approver_email.lower() == request.user.email.lower()
        )

        authorizations_with_meta.append({
            "authorization": auth,
            "can_approve": auth.can_be_approved_by(request.user),
            "is_expected_approver": is_expected_approver,
            "viewed": auth.id in viewed_ids,
        })

    pending_review_count = sum(
        1 for item in authorizations_with_meta
        if item["can_approve"]
    )

    return render(
        request,
        "CityPowerVehicle/dashboard.html",
        {
            "authorizations_with_meta": authorizations_with_meta,
            "pending_review_count": pending_review_count,
        },
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

    viewed = request.session.get('viewed_authorizations', [])

    if authorization.id not in viewed:
        viewed.insert(0, authorization.id)
        request.session['viewed_authorizations'] = viewed
    
    # Allow the requester to always view their own request
    if authorization.submitted_by != request.user and not request.user.is_superuser:

        viewed = request.session.get("viewed_authorizations", [])

        if authorization.id not in viewed:
            messages.error(
                request,
                "You can only access requests that have been shared with you."
            )
            return redirect("dashboard")

    approval_history = authorization.approvals.order_by('signed_on')
    
    next_role_label = None
    can_approve = False
    can_request_permission = False
    has_permission = False
    is_expected_approver = False

        # Request owner can always view
    if authorization.submitted_by == request.user:
        allowed = True

    # Admin can always view
    elif request.user.is_superuser:
        allowed = True

    else:
        expected_email = get_expected_approver_email(authorization)

        allowed = (
            expected_email
            and request.user.email.lower() == expected_email.lower()
        )

    if not allowed:
        messages.error(
            request,
            "You don't have permission to view this request."
        )
        return redirect("dashboard")
    
    if authorization.status == 'PENDING' and authorization.next_approval_role:
        next_role_label = dict(
            APPROVAL_ROLES,
        ).get(
            authorization.next_approval_role,
            authorization.next_approval_role,
        )

        current_role = authorization.next_approval_role
        expected_email = get_expected_approver_email(authorization)

        is_expected_approver = (
            expected_email
            and request.user.email.lower() == expected_email.lower()
        )

        has_permission = user_has_role(request.user, current_role)
        
        can_approve = (
            authorization.status == "PENDING"
            and is_expected_approver
            and has_permission
        )

        can_request_permission = (
            authorization.status == "PENDING"
            and is_expected_approver
            and not has_permission
        )

    # If this authorization was rejected, surface the latest rejection details
    rejection_notice = None
    if authorization.status == 'REJECTED':
        rejection = authorization.approvals.filter(approved=False, acknowledged=False).order_by('-signed_on').first()
        if rejection:
            rejection_notice = {
                'by': rejection.approved_by.get_full_name() if rejection.approved_by else 'An approver',
                'comments': rejection.comments,
                'when': rejection.signed_on,
            }

    return render(
        request,
        'CityPowerVehicle/auth_detail.html',
        {
            'authorization': authorization,
            'approval_history': approval_history,
            'can_edit': authorization.is_editable_by(request.user),
            'can_delete': authorization.is_deletable_by(request.user),
            'can_approve': can_approve,
            'next_role_label': next_role_label,
            'rejection_notice': rejection_notice,
            'can_request_permission': can_request_permission,
            'has_permission': has_permission,
            'is_expected_approver': is_expected_approver,
        },
    )
