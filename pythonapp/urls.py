from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register', views.register, name='register'),
    path('login', views.login, name='login'),
    path('logout', views.logout, name='logout'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('services', views.browse_services, name='browse_services'),
    path('book/<int:provider_id>', views.book_appointment, name='book_appointment'),
    path('book/slot/<int:slot_id>',views.confirm_booking,name='confirm_booking',),
    path('provider/schedule', views.manage_schedule, name='manage_schedule'),
    path('portal/admin/dashboard', views.admin_dashboard, name='admin_dashboard'),
    path('portal/admin/approve/<int:provider_id>', views.approve_provider, name='approve_provider'),
    path('portal/admin/reject/<int:provider_id>', views.reject_provider, name='reject_provider'),
    path('about', views.about_us, name='about_us'),
    path('provider/service/remove/<int:service_id>', views.remove_service, name='remove_service'),
    
]