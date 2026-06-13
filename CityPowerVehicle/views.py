from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
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
        return redirect('request_permission', pk=pk)

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
                # remove from viewed session list when finalized
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

            # clear from viewed list if the request is no longer pending
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
        },
    )


@login_required
@never_cache
def request_approval_permission(request, pk):
    authorization = get_object_or_404(VehicleAuth, pk=pk)
    if authorization.status != 'PENDING':
        return redirect('auth_detail', pk=pk)

    current_role = authorization.next_approval_role
    if user_has_role(request.user, current_role):
        return redirect('approve_auth', pk=pk)

    # Prevent duplicate permission requests if already requested and not yet responded
    if authorization.permission_requested and not authorization.permission_request_response:
        messages.info(
            request,
            'You have already requested approval for this authorization. An administrator has been notified.',
        )
        return redirect('auth_detail', pk=pk)

    if request.method == 'POST':
        form = RequestApprovalPermissionForm(request.POST)
        if form.is_valid():
            message_text = form.cleaned_data['message']
            admin_emails = [
                email for _, email in getattr(settings, 'ADMINS', [])
                if email
            ]
            if not admin_emails:
                admin_emails = list(
                    User.objects.filter(is_superuser=True)
                    .exclude(email='')
                    .values_list('email', flat=True)
                )
            if not admin_emails:
                default_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
                if default_email:
                    admin_emails = [default_email]

            subject = (
                f"Approval access request for {authorization.vehicle_registration}"
            )
            link = request.build_absolute_uri(
                authorization.get_approval_url()
            )
            applicant = (
                request.user.get_full_name() or request.user.username
            )
            message = (
                f"User: {applicant}\n"
                f"Requested role: {current_role or 'Approval'}\n"
                f"Authorization: {authorization.vehicle_registration}\n"
                f"Request message:\n{message_text}\n\n"
                f"Review link: {link}"
            )

            if admin_emails:
                try:
                    if getattr(settings, 'ADMINS', None):
                        mail_admins(subject, message)
                    else:
                        send_mail(
                            subject,
                            message,
                            getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                            admin_emails,
                        )
                    print(f"\n✓ PERMISSION EMAIL SENT TO: {admin_emails}\n")
                    # persist request on the authorization so it can't be re-requested until an admin responds
                    try:
                        authorization.permission_requested = True
                        authorization.permission_requested_by = request.user
                        authorization.permission_requested_at = timezone.now()
                        authorization.permission_request_response = ''
                        authorization.permission_request_responded_at = None
                        authorization.save()
                    except Exception:
                        pass
                except Exception as e:
                    print(f"\n✗ PERMISSION EMAIL FAILED: {type(e).__name__}: {e}\n")
            else:
                print(
                    "\n✗ NO ADMIN EMAIL CONFIGURED FOR PERMISSION REQUEST."
                )

            messages.success(
                request,
                'Your request has been sent to an administrator.',
            )
            return redirect('auth_detail', pk=pk)
    else:
        form = RequestApprovalPermissionForm()

    return render(
        request,
        'CityPowerVehicle/request_permission.html',
        {
            'form': form,
            'authorization': authorization,
            'current_role': current_role,
        },
    )


@login_required
@never_cache
def dashboard(request):
    # Superusers see all applications.
    if request.user.is_superuser:
        authorizations = VehicleAuth.objects.all()
    else:
        own_authorizations = list(
            VehicleAuth.objects.filter(submitted_by=request.user)
        )
        pending_authorizations = VehicleAuth.objects.filter(status='PENDING')
        approval_requests = [
            auth for auth in pending_authorizations
            if auth.can_be_approved_by(request.user)
        ]

        # Avoid duplicates if the user is both applicant and approver.
        auth_by_id = {auth.id: auth for auth in own_authorizations}
        for auth in approval_requests:
            if auth.id not in auth_by_id:
                auth_by_id[auth.id] = auth

        authorizations = list(auth_by_id.values())

        # Include any pending authorizations the user has recently viewed
        viewed_ids = request.session.get('viewed_authorizations', [])
        if viewed_ids:
            viewed_qs = VehicleAuth.objects.filter(id__in=viewed_ids, status='PENDING')
            for auth in viewed_qs:
                if auth.id not in auth_by_id:
                    authorizations.append(auth)

    # Build a list of dicts so template can decide whether to link to approval view
    viewed_ids = request.session.get('viewed_authorizations', [])
    authorizations_with_meta = [
        {
            'authorization': a,
            'can_approve': a.can_be_approved_by(request.user),
            'viewed': a.id in viewed_ids,
        }
        for a in authorizations
    ]

    viewed_count = sum(1 for item in authorizations_with_meta if item.get('viewed'))

    return render(
        request,
        'CityPowerVehicle/dashboard.html',
        {
            'authorizations_with_meta': authorizations_with_meta,
            'viewed_count': viewed_count,
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
    approval_history = authorization.approvals.order_by('signed_on')
    next_role_label = None
    if authorization.status == 'PENDING' and authorization.next_approval_role:
        next_role_label = dict(
            APPROVAL_ROLES,
        ).get(
            authorization.next_approval_role,
            authorization.next_approval_role,
        )

    can_approve = (
        authorization.status == 'PENDING'
        and user_has_role(
            request.user,
            authorization.next_approval_role,
        )
    )

    can_request_permission = (
        authorization.status == 'PENDING'
        and not can_approve
    )

    # Determine if the current user has already requested permission (persisted)
    permission_requested = bool(authorization.permission_requested)
    permission_request_response = authorization.permission_request_response or None

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

    # Record that this user viewed the authorization so it can appear on their dashboard
    try:
        viewed = request.session.get('viewed_authorizations', [])
        if not isinstance(viewed, list):
            viewed = []
        if authorization.id not in viewed:
            viewed.insert(0, authorization.id)
            # keep the list bounded
            if len(viewed) > 50:
                viewed = viewed[:50]
            request.session['viewed_authorizations'] = viewed
    except Exception:
        # session backend problems shouldn't block the view
        pass

    return render(
        request,
        'CityPowerVehicle/auth_detail.html',
        {
            'authorization': authorization,
            'approval_history': approval_history,
            'can_edit': authorization.is_editable_by(request.user),
            'can_delete': authorization.is_deletable_by(request.user),
            'can_approve': can_approve,
            'can_request_permission': can_request_permission,
            'next_role_label': next_role_label,
            'permission_requested': permission_requested,
            'permission_request_response': permission_request_response,
            'rejection_notice': rejection_notice,
        },
    )
