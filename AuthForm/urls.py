from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from CityPowerVehicle import views as cpv_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', include('CityPowerVehicle.urls')),
    path('CityPowerVehicle/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', cpv_views.logout_view, name='logout'),
]
