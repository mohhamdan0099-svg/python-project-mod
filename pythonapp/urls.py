from django.urls import path
from . import views

urlpatterns = [
    # public pages
    path('', views.index, name='index'),
    path('about', views.about_us, name='about_us'),
    path('services', views.browse_services, name='browse_services'),

    # accounts
    path('register', views.register, name='register'),
    path('register/provider', views.register_provider, name='register_provider'),
    path('login', views.login, name='login'),
    path('logout', views.logout, name='logout'),
    path('dashboard', views.dashboard, name='dashboard'),

    # client
    path('book/<int:service_id>', views.book_service, name='book_service'),
    path('book/confirm', views.confirm_booking, name='confirm_booking'),
    path('api/service/<int:service_id>/times', views.service_times_api, name='service_times_api'),
    path('appointments', views.appointments, name='appointments'),
    path('appointment/cancel/<int:appointment_id>', views.cancel_appointment, name='cancel_appointment'),

    # provider
    path('provider/profile', views.provider_profile, name='provider_profile'),
    path('provider/services', views.provider_services, name='provider_services'),
    path('provider/service/remove/<int:service_id>', views.remove_service, name='remove_service'),
    path('provider/schedule', views.provider_schedule, name='provider_schedule'),
    path('api/provider/events', views.provider_events_api, name='provider_events_api'),

    # admin
    path('portal/admin/dashboard', views.admin_dashboard, name='admin_dashboard'),
    path('portal/admin/providers', views.admin_providers, name='admin_providers'),
    path('portal/admin/provider/<int:provider_id>', views.admin_review_provider, name='admin_review_provider'),
    path('portal/admin/categories', views.admin_categories, name='admin_categories'),
]