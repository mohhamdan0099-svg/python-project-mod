from datetime import datetime

import bcrypt
from django.contrib import messages
from django.http import JsonResponse
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
    return redirect('/portal/admin/dashboard')

  return render(request, 'dashboard.html', context)


def browse_services(request):
    if 'user_id' not in request.session:
        return redirect('/')
    if request.session.get('user_role') != 'client':
          return redirect('/dashboard')
    services = Service.objects.filter(provider__approval_status='Approved')

    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    max_price = request.GET.get('max_price', '')

    if search:
        services = services.filter(name__icontains=search)
    if category:
        services = services.filter(category=category)
    if max_price:
        services = services.filter(price__lte=max_price)

    return render(request, 'browse_services.html', {'services': services})


def appointments(request):
  if 'user_id' not in request.session:
    return redirect('/')
  if request.session.get('user_role') != 'client':
    return redirect('/dashboard')

  appts = Appointment.objects.filter(
      client_id=request.session['user_id']
  ).order_by('time_slot__date', 'time_slot__start_time')
  return render(request, 'appointments.html', {'appointments': appts})


def book_appointment(request, provider_id):
    if 'user_id' not in request.session:
        return redirect('/')
    if request.session.get('user_role') != 'client':
        return redirect('/dashboard')
    provider = get_object_or_404(ProviderProfile, id=provider_id)

    # only free slots that are NOT in the past
    future_slots = TimeSlot.objects.upcoming().filter(provider=provider, is_booked=False)

    # dates (as text) that have at least one open slot -> used by the calendar
    available_dates = sorted({s.date.strftime('%Y-%m-%d') for s in future_slots})

    return render(request, 'book_appointment.html', {
        'provider': provider,
        'services': provider.services.all(),
        'available_dates': available_dates,
    })


def available_slots_api(request, provider_id):
    """Our own API: returns the open times of one day as JSON."""
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Login required'}, status=401)
    if request.session.get('user_role') != 'client':
        return JsonResponse({'error': 'Clients only'}, status=403)

    date = request.GET.get('date', '')
    try:
        datetime.strptime(date, '%Y-%m-%d')   # make sure the date format is valid
    except ValueError:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    slots = TimeSlot.objects.upcoming().filter(
        provider_id=provider_id, is_booked=False, date=date
    ).order_by('start_time')

    data = [
        {
            'id': s.id,
            'start': s.start_time.strftime('%H:%M'),
            'end': s.end_time.strftime('%H:%M'),
        }
        for s in slots
    ]
    return JsonResponse({'date': date, 'slots': data})


def confirm_booking(request):
    if 'user_id' not in request.session:
        return redirect('/')
    if request.session.get('user_role') != 'client':
        return redirect('/dashboard')
    if request.method != 'POST':
        return redirect('/services')

    slot_id = request.POST.get('slot_id')
    if not slot_id:
        messages.error(request, 'Please choose a date and a time first.')
        return redirect('/services')

    slot = get_object_or_404(TimeSlot, id=slot_id)

    if slot.is_booked:
        messages.error(request, 'Sorry, this slot was just booked by someone else.')
        return redirect(f'/book/{slot.provider.id}')
    if slot.is_past():
        messages.error(request, 'You cannot book a time in the past.')
        return redirect(f'/book/{slot.provider.id}')

    slot.is_booked = True
    slot.save()
    client = User.objects.get(id=request.session['user_id'])
    Appointment.objects.create(client=client, time_slot=slot, status='Confirmed')
    messages.success(request, 'Appointment successfully booked!')
    return redirect('/appointments')


def get_approved_provider(request):
    """Return the logged-in provider's profile only if approved, otherwise None."""
    if request.session.get('user_role') != 'provider':
        return None
    profile = ProviderProfile.objects.filter(user_id=request.session['user_id']).first()
    if profile and profile.approval_status == 'Approved':
        return profile
    return None


def manage_schedule(request):
    # This page handles TIME SLOTS only
    profile = get_approved_provider(request)
    if not profile:
        messages.error(request, 'Only approved providers can manage time slots.')
        return redirect('/dashboard' if 'user_id' in request.session else '/')

    if request.method == 'POST':
        errors = TimeSlot.objects.slot_validator(request.POST)
        if errors:
            for msg in errors.values():
                messages.error(request, msg)
        else:
            TimeSlot.objects.create(
                provider=profile,
                date=request.POST['date'],
                start_time=request.POST['start_time'],
                end_time=request.POST['end_time']
            )
            messages.success(request, 'Time slot added successfully!')
        return redirect('/provider/schedule')

    slots = TimeSlot.objects.upcoming().filter(provider=profile).order_by('date', 'start_time')
    return render(request, 'manage_schedule.html', {'profile': profile, 'slots': slots})


def remove_slot(request, slot_id):
    profile = get_approved_provider(request)
    if not profile:
        return redirect('/')
    slot = get_object_or_404(TimeSlot, id=slot_id, provider=profile)
    if slot.is_booked:
        messages.error(request, 'You cannot remove a slot that is already booked.')
    else:
        slot.delete()
        messages.success(request, 'Time slot removed.')
    return redirect('/provider/schedule')


def provider_services(request):
    # This page handles SERVICES and the bio only
    profile = get_approved_provider(request)
    if not profile:
        messages.error(request, 'Only approved providers can manage services.')
        return redirect('/dashboard' if 'user_id' in request.session else '/')

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile.bio = request.POST['bio']
            profile.save()
            messages.success(request, 'Profile updated successfully!')
        elif 'add_service' in request.POST:
            name = request.POST['service_name'].strip()
            try:
                price_ok = float(request.POST['price']) > 0
            except ValueError:
                price_ok = False

            if not name:
                messages.error(request, 'Service name is required.')
            elif not price_ok:
                messages.error(request, 'Price must be a number greater than 0.')
            else:
                Service.objects.create(
                    provider=profile,
                    name=name,
                    category=request.POST['category'],
                    description=request.POST['description'],
                    price=request.POST['price']
                )
                messages.success(request, 'Service added successfully!')
        return redirect('/provider/services')

    return render(request, 'provider_services.html', {
        'profile': profile, 'services': Service.objects.filter(provider=profile)
    })


def cancel_appointment(request, appointment_id):
    if 'user_id' not in request.session:
        return redirect('/')
    if request.session.get('user_role') != 'client':
        return redirect('/dashboard')
    appt = get_object_or_404(Appointment, id=appointment_id, client_id=request.session['user_id'])
    slot = appt.time_slot
    slot.is_booked = False   # free the slot again
    slot.save()
    appt.delete()
    messages.info(request, 'Appointment cancelled.')
    return redirect('/appointments')


def remove_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    # Ensure only the owner can delete it
    if service.provider.user.id == request.session.get('user_id'):
        service.delete()
        messages.success(request, "Service removed successfully.")
    return redirect('/provider/services')


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
  if request.session.get('user_role') != 'admin':
    return redirect('/')
  profile = get_object_or_404(ProviderProfile, id=provider_id)
  profile.approval_status = 'Approved'
  profile.save()
  messages.success(
      request, f'Approved {profile.user.first_name} as a service provider.'
  )
  return redirect('/portal/admin/dashboard')


def reject_provider(request, provider_id):
  if request.session.get('user_role') != 'admin':
    return redirect('/')
  profile = get_object_or_404(ProviderProfile, id=provider_id)
  profile.approval_status = 'Rejected'
  profile.save()
  messages.info(request, f'Rejected {profile.user.first_name}.')
  return redirect('/portal/admin/dashboard')


def about_us(request):
  return render(request, 'about_us.html')