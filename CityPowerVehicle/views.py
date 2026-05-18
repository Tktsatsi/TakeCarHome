from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .models import VehicleAuth, Approval, APPROVAL_ROLES
from .forms import VehicleAuthForm, RegistrationForm, ApprovalForm
from django.contrib.auth import logout
from django.shortcuts import redirect


def user_has_role(user, role):
    if user.is_superuser:
        return True
    return user.groups.filter(name=role).exists()


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
    authorization = get_object_or_404(VehicleAuth, pk=pk)
    if authorization.status != 'PENDING':
        return redirect('auth_detail', pk=pk)

    if not user_has_role(request.user, authorization.next_approval_role):
        return redirect('auth_detail', pk=pk)

    if request.method == 'POST':
        form = ApprovalForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data['decision']
            comments = form.cleaned_data['comments']
            approved = decision == 'approve'
            Approval.objects.create(
                authorization=authorization,
                role=authorization.next_approval_role,
                approved_by=request.user,
                approved=approved,
                comments=comments,
                signed_on=timezone.now(),
            )
            if approved:
                authorization.advance_approval()
            else:
                authorization.status = 'REJECTED'
                authorization.next_approval_role = ''
            authorization.save()
            return redirect('auth_detail', pk=pk)
    else:
        form = ApprovalForm()

    return render(request, 'CityPowerVehicle/approve_auth.html', {
        'form': form,
        'authorization': authorization,
    })


@login_required
@never_cache
def dashboard(request):
    authorizations = VehicleAuth.objects.all()
    return render(
        request,
        'CityPowerVehicle/dashboard.html',
        {'authorizations': authorizations},
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
