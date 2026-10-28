
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="pythonapp/login.html"
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("services/", views.services_list, name="services"),
    path(
        "services/<int:service_id>/",
        views.service_detail,
        name="service_detail",
    ),
    path(
        "services/<int:service_id>/book/",
        views.book_service,
        name="book_service",
    ),
    path(
        "api/services/<int:service_id>/availability/",
        views.available_slots,
        name="available_slots",
    ),
    path(
        "api/ai-recommendations/",
        views.ai_recommendations,
        name="ai_recommendations",
    ),
    path("appointments/", views.my_appointments, name="my_appointments"),
    path(
        "appointments/<int:appointment_id>/cancel/",
        views.cancel_appointment,
        name="cancel_appointment",
    ),
    path(
        "provider/dashboard/",
        views.provider_dashboard,
        name="provider_dashboard",
    ),
]
