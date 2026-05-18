from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_auth, name='create_auth'),
    path('authorization/<int:pk>/', views.auth_detail, name='auth_detail'),
    path('authorization/<int:pk>/edit/', views.edit_auth, name='edit_auth'),
    path(
        'authorization/<int:pk>/delete/',
        views.delete_auth,
        name='delete_auth',
    ),
    path(
        'authorization/<int:pk>/approve/',
        views.approve_auth,
        name='approve_auth',
    ),
]
