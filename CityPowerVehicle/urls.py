from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_auth, name='create_auth'),
    path('authorization/<int:pk>/', views.auth_detail, name='auth_detail' ),
]