import bcrypt
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from .models import Appointment, ProviderProfile, TimeSlot, User, Service


def index(request):
  if 'user_id' in request.session:
    return redirect('/dashboard')
  return render(request, 'index.html')


def register(request):
  if request.method == 'POST':
    errors = User.objects.register_validator(request.POST)
    if len(errors) > 0:
      for key, value in errors.items():
        messages.error(request, value)
      return redirect('/')

    hashed_password = bcrypt.hashpw(
        request.POST['password'].encode(), bcrypt.gensalt()
    ).decode()

    role = request.POST.get('role', 'client')
    new_user = User.objects.create(
        first_name=request.POST['first_name'],
        last_name=request.POST['last_name'],
        email=request.POST['email'],
        password=hashed_password,
        role=role,
    )

    if role == 'provider':
      ProviderProfile.objects.create(
        user=new_user,
        service_title='Pending Service Setup',
        bio='Please update your professional bio and price.',
        price=50.00,
        approval_status='Pending',
    )

    request.session['user_id'] = new_user.id
    request.session['user_name'] = new_user.first_name
    request.session['user_role'] = new_user.role

    messages.success(request, 'Successfully registered!')
    return redirect('/dashboard')
  return redirect('/')


def login(request):
  if request.method == 'POST':
    errors = User.objects.login_validator(request.POST)
    if len(errors) > 0:
      for key, value in errors.items():
        messages.error(request, value)
      return redirect('/')

    user = User.objects.get(email=request.POST['email'])
    request.session['user_id'] = user.id
    request.session['user_name'] = user.first_name
    request.session['user_role'] = user.role
    return redirect('/dashboard')
  return redirect('/')


def logout(request):
  request.session.flush()
  return redirect('/')


def dashboard(request):
  if 'user_id' not in request.session:
    return redirect('/')

  user = User.objects.get(id=request.session['user_id'])
  context = {'user': user}

  if user.role == 'client':
    context['appointments'] = Appointment.objects.filter(client=user)
  elif user.role == 'provider':
    try:
      context['profile'] = user.provider_profile
    except ProviderProfile.DoesNotExist:
      context['profile'] = None
  elif user.role == 'admin':
    context['pending_providers'] = ProviderProfile.objects.filter(
        approval_status='Pending'
    )

  return render(request, 'dashboard.html', context)


def browse_services(request):
  if 'user_id' not in request.session:
    return redirect('/')
  search_query = request.GET.get('search', '')
  if search_query:
    providers = ProviderProfile.objects.filter(
        approval_status='Approved', service_title__icontains=search_query
    ) | ProviderProfile.objects.filter(
        approval_status='Approved', user__first_name__icontains=search_query
    )
  else:
    providers = ProviderProfile.objects.filter(approval_status='Approved')
  return render(request, 'browse_services.html', {'providers': providers})


def book_appointment(request, provider_id):
  if 'user_id' not in request.session:
    return redirect('/')
  provider = get_object_or_404(ProviderProfile, id=provider_id)
  available_slots = TimeSlot.objects.filter(
      provider=provider, is_booked=False
  ).order_by('date', 'start_time')
  return render(
      request,
      'book_appointment.html',
      {'provider': provider, 'available_slots': available_slots},
  )


def confirm_booking(request, slot_id):
  if 'user_id' not in request.session:
    return redirect('/')
  slot = get_object_or_404(TimeSlot, id=slot_id)
  if not slot.is_booked:
    slot.is_booked = True
    slot.save()
    client = User.objects.get(id=request.session['user_id'])
    Appointment.objects.create(client=client, time_slot=slot, status='Confirmed')
    messages.success(request, 'Appointment successfully booked!')
  return redirect('/services')


def manage_schedule(request):
    if 'user_id' not in request.session:
        return redirect('/')
    user = User.objects.get(id=request.session['user_id'])
    if user.role != 'provider':
        return redirect('/dashboard')
    
    # Safely get or create the provider profile if it's missing
    profile, created = ProviderProfile.objects.get_or_create(
        user=user,
        defaults={
            'service_title': 'Pending Service Setup',
            'bio': 'Please update your professional bio and price.',
            'price': 50.00,
            'approval_status': 'Pending'
        }
    )

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile.bio = request.POST['bio']
            profile.save()
            messages.success(request, "Profile updated successfully!")
        elif 'add_slot' in request.POST:
            TimeSlot.objects.create(
                provider=profile,
                date=request.POST['date'],
                start_time=request.POST['start_time'],
                end_time=request.POST['end_time']
            )
            messages.success(request, "Time slot added successfully!")
        return redirect('/provider/schedule')

    slots = TimeSlot.objects.filter(provider=profile).order_by('date')
    return render(request, 'manage_schedule.html', {'profile': profile, 'slots': slots})

# Add a quick delete/remove service view:
def remove_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    # Ensure only the owner can delete it
    if service.provider.user.id == request.session.get('user_id'):
        service.delete()
        messages.success(request, "Service removed successfully.")
    return redirect('/provider/schedule')

def admin_dashboard(request):
  if 'user_id' not in request.session:
    return redirect('/')
  user = User.objects.get(id=request.session['user_id'])
  if user.role != 'admin':
    return redirect('/dashboard')

  pending_providers = ProviderProfile.objects.filter(approval_status='Pending')
  return render(
      request, 'admin_dashboard.html', {'pending_providers': pending_providers}
  )


def approve_provider(request, provider_id):
  profile = get_object_or_404(ProviderProfile, id=provider_id)
  profile.approval_status = 'Approved'
  profile.save()
  messages.success(
      request, f'Approved {profile.user.first_name} as a service provider.'
  )
  return redirect('/dashboard')


def reject_provider(request, provider_id):
  profile = get_object_or_404(ProviderProfile, id=provider_id)
  profile.approval_status = 'Rejected'
  profile.save()
  messages.info(request, f'Rejected {profile.user.first_name}.')
  return redirect('/dashboard')


def about_us(request):
  return render(request, 'about_us.html')