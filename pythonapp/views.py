from datetime import date, datetime, timedelta

import bcrypt
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .ai_helper import smart_search, write_description
from .data import CITIES, CATEGORY_GROUPS, GROUP_ICONS
from .models import (Appointment, Category, ProviderProfile, Service, User,
                     WorkSchedule, WEEKDAYS, DURATION_CHOICES, clean_phone)


# ------------------------------------------------------------------
# Small helpers used by many views
# ------------------------------------------------------------------

def get_user(request, role):
    """Return the logged-in user only if he has this role, otherwise None."""
    if request.session.get('user_role') != role:
        return None
    return User.objects.filter(id=request.session['user_id']).first()


def deny(request):
    """Where to send someone who is not allowed to see a page."""
    if 'user_id' in request.session:
        return redirect('/dashboard')
    messages.info(request, 'Please log in first.')
    return redirect('/login')


def start_session(request, user):
    request.session['user_id'] = user.id
    request.session['user_name'] = user.first_name
    request.session['user_role'] = user.role


def create_user(data, role):
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    return User.objects.create(
        first_name=data['first_name'], last_name=data['last_name'],
        email=data['email'], password=hashed, role=role,
    )


def parse_day(text):
    """Turn '2026-11-10' into a date. Returns None if it is invalid or out of range."""
    try:
        day = datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        return None
    if day < date.today() or day > date.today() + timedelta(days=60):
        return None
    return day


def show_errors(request, errors):
    for message in errors.values():
        messages.error(request, message)


# a simple guard for your AI credits: each login session may use the AI this many times
AI_LIMIT = 15


def ai_allowed(request):
    return request.session.get('ai_uses', 0) < AI_LIMIT


def ai_count(request):
    request.session['ai_uses'] = request.session.get('ai_uses', 0) + 1


# ------------------------------------------------------------------
# Public pages
# ------------------------------------------------------------------

def index(request):
    groups = [
        {'name': name, 'icon': GROUP_ICONS.get(name, 'bi-grid'), 'examples': ', '.join(items[:3])}
        for name, items in CATEGORY_GROUPS.items() if name != 'Other'
    ]
    return render(request, 'index.html', {'groups': groups})


def about_us(request):
    return render(request, 'about_us.html')


def browse_services(request):
    services = Service.objects.filter(
        is_active=True, provider__approval_status='Approved'
    ).order_by('-created_at')

    search = request.GET.get('search', '').strip()
    category = request.GET.get('category', '')
    city = request.GET.get('city', '')
    max_price = request.GET.get('max_price', '')

    if search:
        services = services.filter(Q(name__icontains=search) | Q(provider__profession__icontains=search))
    if category.isdigit():
        services = services.filter(category_id=category)
    if city:
        services = services.filter(provider__city=city)
    if max_price:
        try:
            services = services.filter(price__lte=float(max_price))
        except ValueError:
            pass

    # ---- AI smart search (logged-in clients only) ----
    ask = request.GET.get('ask', '').strip()[:200]
    ai_used = False
    if ask and request.session.get('user_role') == 'client':
        if not ai_allowed(request):
            messages.info(request, 'You reached the limit of AI searches for now. Please use the filters.')
        else:
            # select_related loads each category and provider in the same query (faster)
            candidates = list(services.select_related('category', 'provider')[:80])
            lines = '\n'.join(
                f'{s.id} | {s.name} | {s.category.name} | {s.provider.profession} | '
                f'{s.provider.city} | {s.price} | {s.duration}'
                for s in candidates
            )
            try:
                ids = smart_search(ask, lines) if candidates else []
            except Exception:
                messages.warning(request, 'AI search is not available right now. Showing the normal results.')
            else:                      # "else" runs only when the try had no error
                ai_count(request)
                by_id = {s.id: s for s in candidates}
                picked = []
                for i in ids:          # keep only ids that really exist, best first
                    if i in by_id and by_id[i] not in picked:
                        picked.append(by_id[i])
                services = picked
                ai_used = True

    return render(request, 'browse_services.html', {
        'services': services,
        'categories': Category.objects.order_by('group', 'name'),
        'cities': sorted(CITIES),
        'ask': ask,
        'ai_used': ai_used,
    })


# ------------------------------------------------------------------
# Accounts
# ------------------------------------------------------------------

def register(request):
    if 'user_id' in request.session:
        return redirect('/dashboard')
    if request.method != 'POST':
        return render(request, 'register.html')

    errors = User.objects.register_validator(request.POST)
    if errors:
        show_errors(request, errors)
        return render(request, 'register.html', {'old': request.POST})

    user = create_user(request.POST, 'client')
    start_session(request, user)
    messages.success(request, 'Your account is ready.')
    return redirect('/dashboard')


def register_provider(request):
    if 'user_id' in request.session:
        return redirect('/dashboard')
    context = {'cities': sorted(CITIES)}
    if request.method != 'POST':
        return render(request, 'register_provider.html', context)

    # two validators: the account fields and the business fields
    errors = User.objects.register_validator(request.POST)
    errors.update(ProviderProfile.objects.profile_validator(request.POST, request.FILES))
    if errors:
        show_errors(request, errors)
        context['old'] = request.POST
        return render(request, 'register_provider.html', context)

    user = create_user(request.POST, 'provider')
    ProviderProfile.objects.create(
        user=user,
        profession=request.POST['profession'].strip(),
        city=request.POST['city'],
        address=request.POST['address'].strip(),
        phone=clean_phone(request.POST['phone']),
        proof=request.FILES['proof'],
    )
    start_session(request, user)
    messages.success(request, 'Account created. The admin will now review your details and proof.')
    return redirect('/dashboard')


def login(request):
    if 'user_id' in request.session:
        return redirect('/dashboard')
    if request.method != 'POST':
        return render(request, 'login.html')

    errors = User.objects.login_validator(request.POST)
    if errors:
        show_errors(request, errors)
        return render(request, 'login.html', {'old': request.POST})

    user = User.objects.get(email=request.POST['email'])
    start_session(request, user)
    return redirect('/dashboard')


def logout(request):
    request.session.flush()
    return redirect('/')


def dashboard(request):
    if 'user_id' not in request.session:
        return deny(request)
    user = User.objects.get(id=request.session['user_id'])
    context = {'user': user}

    if user.role == 'admin':
        return redirect('/portal/admin/dashboard')

    if user.role == 'client':
        upcoming = Appointment.objects.upcoming().filter(client=user).order_by('date', 'start_time')
        context['next_appt'] = upcoming.first()
        context['upcoming_count'] = upcoming.count()
        context['total_count'] = Appointment.objects.filter(client=user).count()

    elif user.role == 'provider':
        profile = user.provider_profile
        context['profile'] = profile
        context['todays'] = Appointment.objects.filter(
            service__provider=profile, date=date.today(), status='Confirmed'
        ).order_by('start_time')
        context['upcoming_count'] = Appointment.objects.upcoming().filter(service__provider=profile).count()
        context['has_services'] = profile.services.filter(is_active=True).exists()
        context['has_schedule'] = profile.work_days.exists()

    return render(request, 'dashboard.html', context)


# ------------------------------------------------------------------
# Client: booking
# ------------------------------------------------------------------

def book_service(request, service_id):
    user = get_user(request, 'client')
    if not user:
        return deny(request)
    service = get_object_or_404(Service, id=service_id, is_active=True, provider__approval_status='Approved')

    # the calendar (JavaScript) numbers days Sunday = 0, Python numbers Monday = 0
    js_days = [(w.weekday + 1) % 7 for w in service.provider.work_days.all()]
    max_day = (date.today() + timedelta(days=60)).strftime('%Y-%m-%d')
    return render(request, 'book_service.html', {
        'service': service, 'provider': service.provider, 'js_days': js_days, 'max_day': max_day,
    })


def service_times_api(request, service_id):
    """Our own API: the free start times of one service on one day, as JSON."""
    if request.session.get('user_role') != 'client':
        return JsonResponse({'error': 'Clients only'}, status=403)
    service = get_object_or_404(Service, id=service_id, is_active=True, provider__approval_status='Approved')

    day = parse_day(request.GET.get('date', ''))
    if day is None:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    times = [t.strftime('%H:%M') for t in service.provider.free_times(service, day)]
    return JsonResponse({'date': str(day), 'times': times})


def confirm_booking(request):
    user = get_user(request, 'client')
    if not user:
        return deny(request)
    if request.method != 'POST':
        return redirect('/services')

    service_id = request.POST.get('service_id', '')
    if not service_id.isdigit():
        return redirect('/services')
    service = get_object_or_404(Service, id=service_id, is_active=True, provider__approval_status='Approved')

    day = parse_day(request.POST.get('date', ''))
    start_text = request.POST.get('start_time', '')
    if day is None or not start_text:
        messages.error(request, 'Please choose a date and a time.')
        return redirect(f'/book/{service.id}')

    # check again on the server: the time must still be free
    free = [t.strftime('%H:%M') for t in service.provider.free_times(service, day)]
    if start_text not in free:
        messages.error(request, 'Sorry, this time is no longer available. Please choose another one.')
        return redirect(f'/book/{service.id}')

    start = datetime.strptime(start_text, '%H:%M')
    end = start + timedelta(minutes=service.duration)
    Appointment.objects.create(
        client=user, service=service, date=day,
        start_time=start.time(), end_time=end.time(),
    )
    messages.success(request, 'Your appointment is confirmed.')
    return redirect('/appointments')


def appointments(request):
    user = get_user(request, 'client')
    if not user:
        return deny(request)
    upcoming = Appointment.objects.upcoming().filter(client=user).order_by('date', 'start_time')
    history = Appointment.objects.filter(client=user).exclude(pk__in=upcoming).order_by('-date', '-start_time')
    return render(request, 'appointments.html', {'upcoming': upcoming, 'history': history})


def cancel_appointment(request, appointment_id):
    user = get_user(request, 'client')
    if not user:
        return deny(request)
    appt = get_object_or_404(Appointment, id=appointment_id, client=user)
    if request.method == 'POST' and appt.is_upcoming():
        appt.status = 'Cancelled'       # we keep the record, the time becomes free again
        appt.save()
        messages.info(request, 'Appointment cancelled.')
    return redirect('/appointments')


# ------------------------------------------------------------------
# Provider
# ------------------------------------------------------------------

def provider_profile(request):
    user = get_user(request, 'provider')
    if not user:
        return deny(request)
    profile = user.provider_profile

    if request.method == 'POST':
        errors = ProviderProfile.objects.profile_validator(request.POST, request.FILES, proof_required=False)
        if errors:
            show_errors(request, errors)
            return redirect('/provider/profile')

        profession = request.POST['profession'].strip()
        address = request.POST['address'].strip()
        phone = clean_phone(request.POST['phone'])
        city = request.POST['city']

        changed = (profile.profession != profession or profile.city != city
                   or profile.address != address or profile.phone != phone
                   or 'proof' in request.FILES)

        profile.profession, profile.city = profession, city
        profile.address, profile.phone = address, phone
        if 'proof' in request.FILES:
            profile.proof = request.FILES['proof']
        if changed:
            profile.approval_status = 'Pending'      # the admin must confirm the new details
            profile.admin_note = ''
            messages.info(request, 'Saved. The admin will confirm your new details before clients see you again.')
        else:
            messages.success(request, 'Nothing was changed.')
        profile.save()
        return redirect('/provider/profile')

    return render(request, 'provider_profile.html', {'profile': profile, 'cities': sorted(CITIES)})


def provider_services(request):
    user = get_user(request, 'provider')
    if not user:
        return deny(request)
    profile = user.provider_profile

    if request.method == 'POST':
        errors = Service.objects.service_validator(request.POST)
        if errors:
            show_errors(request, errors)
        else:
            Service.objects.create(
                provider=profile,
                category_id=request.POST['category'],
                name=request.POST['name'].strip(),
                description=request.POST['description'].strip(),
                duration=int(request.POST['duration']),
                price=request.POST['price'],
            )
            messages.success(request, 'Service added.')
        return redirect('/provider/services')

    return render(request, 'provider_services.html', {
        'profile': profile,
        'services': profile.services.filter(is_active=True).order_by('-created_at'),
        'categories': Category.objects.order_by('group', 'name'),
        'durations': DURATION_CHOICES,
    })


def remove_service(request, service_id):
    user = get_user(request, 'provider')
    if not user:
        return deny(request)
    service = get_object_or_404(Service, id=service_id, provider=user.provider_profile)
    if request.method == 'POST':
        service.is_active = False        # hidden from clients, old bookings keep working
        service.save()
        messages.success(request, 'Service removed.')
    return redirect('/provider/services')


def ai_describe_service(request):
    """Our own API: the AI writes a service description for the provider."""
    if not get_user(request, 'provider'):
        return JsonResponse({'error': 'Providers only'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    name = request.POST.get('name', '').strip()
    if len(name) < 3:
        return JsonResponse({'error': 'Enter the service name first.'}, status=400)
    if not ai_allowed(request):
        return JsonResponse({'error': 'You reached the limit of AI suggestions for now.'}, status=429)

    try:
        text = write_description(name, request.POST.get('category', ''), request.POST.get('notes', '')[:300])
    except Exception:
        return JsonResponse({'error': 'The AI is not available right now. You can write the description yourself.'}, status=503)

    ai_count(request)
    return JsonResponse({'description': text})


def provider_schedule(request):
    user = get_user(request, 'provider')
    if not user:
        return deny(request)
    profile = user.provider_profile

    if request.method == 'POST':
        errors = WorkSchedule.objects.schedule_validator(request.POST)
        if errors:
            show_errors(request, errors)
        else:
            profile.work_days.all().delete()          # start fresh, then save the checked days
            for number, name in WEEKDAYS:
                if request.POST.get(f'work_{number}'):
                    WorkSchedule.objects.create(
                        provider=profile, weekday=number,
                        start_time=request.POST[f'start_{number}'],
                        end_time=request.POST[f'end_{number}'],
                    )
            messages.success(request, 'Working hours saved.')
        return redirect('/provider/schedule')

    rows = {w.weekday: w for w in profile.work_days.all()}
    days = [{'number': n, 'name': name, 'row': rows.get(n)} for n, name in WEEKDAYS]
    # working hours for the calendar background (JavaScript numbers days Sunday = 0)
    business = [
        {'daysOfWeek': [(w.weekday + 1) % 7],
         'startTime': w.start_time.strftime('%H:%M'),
         'endTime': w.end_time.strftime('%H:%M')}
        for w in profile.work_days.all()
    ]
    return render(request, 'provider_schedule.html', {'profile': profile, 'days': days, 'business': business})


def provider_events_api(request):
    """Our own API: the provider's booked appointments, for the calendar."""
    if request.session.get('user_role') != 'provider':
        return JsonResponse({'error': 'Providers only'}, status=403)
    profile = ProviderProfile.objects.filter(user_id=request.session['user_id']).first()

    events = []
    for a in Appointment.objects.filter(service__provider=profile, status='Confirmed'):
        events.append({
            'title': f'{a.service.name} - {a.client.first_name} {a.client.last_name}',
            'start': f'{a.date}T{a.start_time}',
            'end': f'{a.date}T{a.end_time}',
        })
    return JsonResponse(events, safe=False)


# ------------------------------------------------------------------
# Admin
# ------------------------------------------------------------------

def admin_dashboard(request):
    if not get_user(request, 'admin'):
        return deny(request)
    stats = {
        'clients': User.objects.filter(role='client').count(),
        'providers': ProviderProfile.objects.filter(approval_status='Approved').count(),
        'pending': ProviderProfile.objects.filter(approval_status='Pending').count(),
        'services': Service.objects.filter(is_active=True).count(),
        'upcoming': Appointment.objects.upcoming().count(),
        'cancelled': Appointment.objects.filter(status='Cancelled').count(),
    }
    return render(request, 'admin_dashboard.html', {
        'stats': stats,
        'pending_providers': ProviderProfile.objects.filter(approval_status='Pending').order_by('created_at'),
        'recent': Appointment.objects.order_by('-created_at')[:6],
    })


def admin_providers(request):
    if not get_user(request, 'admin'):
        return deny(request)
    status = request.GET.get('status', '')
    providers = ProviderProfile.objects.order_by('-created_at')
    if status in ('Pending', 'Approved', 'Rejected'):
        providers = providers.filter(approval_status=status)
    return render(request, 'admin_providers.html', {'providers': providers, 'status': status})


def admin_review_provider(request, provider_id):
    if not get_user(request, 'admin'):
        return deny(request)
    profile = get_object_or_404(ProviderProfile, id=provider_id)

    if request.method == 'POST':
        action = request.POST.get('action')          # save / approve / reject
        note = request.POST.get('admin_note', '').strip()

        errors = ProviderProfile.objects.profile_validator(request.POST, request.FILES, proof_required=False)
        if action == 'reject' and len(note) < 5:
            errors['note'] = 'Write the reason for rejecting (at least 5 characters).'
        if errors:
            show_errors(request, errors)
            return redirect(f'/portal/admin/provider/{profile.id}')

        # the admin can correct the details before deciding
        profile.profession = request.POST['profession'].strip()
        profile.city = request.POST['city']
        profile.address = request.POST['address'].strip()
        profile.phone = clean_phone(request.POST['phone'])

        if action == 'approve':
            profile.approval_status = 'Approved'
            profile.admin_note = ''
            messages.success(request, f'{profile.user.first_name} is approved and now visible to clients.')
        elif action == 'reject':
            profile.approval_status = 'Rejected'
            profile.admin_note = note
            messages.info(request, f'{profile.user.first_name} was rejected.')
        else:
            messages.success(request, 'Details saved.')
        profile.save()

        if action in ('approve', 'reject'):
            return redirect('/portal/admin/dashboard')
        return redirect(f'/portal/admin/provider/{profile.id}')

    return render(request, 'admin_review.html', {'profile': profile, 'cities': sorted(CITIES)})


def admin_categories(request):
    if not get_user(request, 'admin'):
        return deny(request)

    if request.method == 'POST':
        errors = Category.objects.category_validator(request.POST)
        if errors:
            show_errors(request, errors)
        else:
            Category.objects.create(name=request.POST['name'].strip(), group=request.POST['group'])
            messages.success(request, 'Category added.')
        return redirect('/portal/admin/categories')

    return render(request, 'admin_categories.html', {
        'categories': Category.objects.order_by('group', 'name'),
        'groups': list(CATEGORY_GROUPS),
    })
