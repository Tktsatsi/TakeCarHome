from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import VehicleAuth
from .forms import VehicleAuthForm, RegistrationForm

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = RegistrationForm()
    
    return render(request, 'CityPowerVehicle/register.html', {'form': form})

@login_required
def dashboard(request):
    authorizations = VehicleAuth.objects.all()
    return render(request, 'CityPowerVehicle/dashboard.html',{'authorizations': authorizations})

@login_required
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
    
    return render(request, 'CityPowerVehicle/create_auth.html', {'form': form})

@login_required
def auth_detail(request, pk):
    authorization = get_object_or_404(VehicleAuth, pk=pk)

    return render(request, 'CityPowerVehicle/auth_detail.html', {
        'authorization': authorization
    })