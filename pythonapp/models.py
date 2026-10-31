
import re
from datetime import datetime, timedelta
from urllib.parse import quote
import bcrypt
from django.db import models
from django.db.models import Q

from .data import CITIES, CATEGORY_GROUPS

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')
# Palestinian mobile (059 / 056) or landline (02 / 04 / 09), with or without +970
PHONE_REGEX = re.compile(r'^(\+970|00970|0)?(5[69]\d{7}|[249]\d{7})$')
ALLOWED_PROOF = ('.pdf', '.jpg', '.jpeg', '.png')

# the number is Python's weekday (Monday = 0). The list starts on Sunday for display.
WEEKDAYS = [(6, 'Sunday'), (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
            (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday')]

DURATION_CHOICES = [(15, '15 minutes'), (30, '30 minutes'), (45, '45 minutes'),
                    (60, '1 hour'), (90, '1.5 hours'), (120, '2 hours'), (180, '3 hours')]


def clean_phone(text):
    return text.replace(' ', '').replace('-', '')


# ------------------------------------------------------------------
# Managers: they hold the validation rules (same idea as before)
# ------------------------------------------------------------------

class UserManager(models.Manager):

    def register_validator(self, postData):
        errors = {}
        if len(postData['first_name']) < 2:
            errors['first_name'] = 'First name must be at least 2 characters.'
        elif not postData['first_name'].isalpha():
            errors['first_name'] = 'First name must contain letters only.'

        if len(postData['last_name']) < 2:
            errors['last_name'] = 'Last name must be at least 2 characters.'
        elif not postData['last_name'].isalpha():
            errors['last_name'] = 'Last name must contain letters only.'

        if not EMAIL_REGEX.match(postData['email']):
            errors['email'] = 'Invalid email address format.'
        if User.objects.filter(email=postData['email']).exists():
            errors['email_exists'] = 'Email is already registered.'

        if len(postData['password']) < 8:
            errors['password'] = 'Password must be at least 8 characters.'
        if postData['password'] != postData['confirm_password']:
            errors['password_confirm'] = 'Passwords must match.'
        return errors

    def login_validator(self, postData):
        errors = {}
        if not postData['email']:
            errors['login_email'] = 'Email address is required.'
        elif not EMAIL_REGEX.match(postData['email']):
            errors['login_email'] = 'Invalid email address format.'

        if not postData['password']:
            errors['login_password'] = 'Password is required.'
        elif len(postData['password']) < 8:
            errors['login_password'] = 'Password must be at least 8 characters long.'

        if not errors:
            user_list = User.objects.filter(email=postData['email'])
            if len(user_list) == 0:
                errors['login_credentials'] = 'Email not found. Please register first.'
            else:
                user = user_list[0]
                if not bcrypt.checkpw(postData['password'].encode(), user.password.encode()):
                    errors['login_credentials'] = 'Invalid password.'
        return errors


class ProviderManager(models.Manager):

    def profile_validator(self, postData, files, proof_required=True):
        errors = {}
        if len(postData.get('profession', '').strip()) < 3:
            errors['profession'] = 'Profession must be at least 3 characters (example: Dentist).'
        if postData.get('city') not in CITIES:
            errors['city'] = 'Please choose a city from the list.'

        address = postData.get('address', '').strip()
        if len(address) < 5 or len(address) > 150:
            errors['address'] = 'Address must be between 5 and 150 characters.'

        if not PHONE_REGEX.match(clean_phone(postData.get('phone', ''))):
            errors['phone'] = 'Enter a valid Palestinian phone number, for example 0599123456.'

        proof = files.get('proof')
        if proof:
            if not proof.name.lower().endswith(ALLOWED_PROOF):
                errors['proof'] = 'The proof must be a PDF, JPG or PNG file.'
            elif proof.size > 5 * 1024 * 1024:
                errors['proof'] = 'The proof file must be smaller than 5 MB.'
        elif proof_required:
            errors['proof'] = 'Please upload a proof of your work (license, certificate or work photo).'
        return errors


class ServiceManager(models.Manager):

    def service_validator(self, postData):
        errors = {}
        name = postData.get('name', '').strip()
        if len(name) < 3 or len(name) > 100:
            errors['name'] = 'Service name must be between 3 and 100 characters.'

        category_id = postData.get('category', '')
        if not category_id.isdigit() or not Category.objects.filter(id=category_id).exists():
            errors['category'] = 'Please choose a category.'

        allowed = [minutes for minutes, label in DURATION_CHOICES]
        if not postData.get('duration', '').isdigit() or int(postData['duration']) not in allowed:
            errors['duration'] = 'Please choose a duration from the list.'

        try:
            price = float(postData.get('price', ''))
            if price <= 0 or price > 10000:
                errors['price'] = 'Price must be more than 0 and not more than 10000.'
        except ValueError:
            errors['price'] = 'Price must be a number.'

        if len(postData.get('description', '').strip()) < 10:
            errors['description'] = 'Description must be at least 10 characters.'
        return errors


class ScheduleManager(models.Manager):

    def schedule_validator(self, postData):
        errors = {}
        working = 0
        for number, name in WEEKDAYS:
            if not postData.get(f'work_{number}'):
                continue          # this day is not checked, skip it
            working += 1
            try:
                start = datetime.strptime(postData.get(f'start_{number}', ''), '%H:%M').time()
                end = datetime.strptime(postData.get(f'end_{number}', ''), '%H:%M').time()
            except ValueError:
                errors[f'time_{number}'] = f'{name}: please enter valid times.'
                continue
            if end <= start:
                errors[f'time_{number}'] = f'{name}: closing time must be after opening time.'
        if working == 0:
            errors['days'] = 'Choose at least one working day.'
        return errors


class CategoryManager(models.Manager):

    def category_validator(self, postData):
        errors = {}
        name = postData.get('name', '').strip()
        if len(name) < 2 or len(name) > 60:
            errors['name'] = 'Category name must be between 2 and 60 characters.'
        elif self.filter(name__iexact=name).exists():
            errors['name_exists'] = 'This category already exists.'
        if postData.get('group') not in CATEGORY_GROUPS:
            errors['group'] = 'Please choose a group.'
        return errors


class AppointmentManager(models.Manager):

    def upcoming(self):
        """Confirmed appointments that are still in the future."""
        now = datetime.now()
        return self.filter(status='Confirmed').filter(
            Q(date__gt=now.date()) | Q(date=now.date(), start_time__gt=now.time())
        )


# ------------------------------------------------------------------
# Models (the tables)
# ------------------------------------------------------------------

class User(models.Model):
    first_name = models.CharField(max_length=45)
    last_name = models.CharField(max_length=45)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, default='client')   # client / provider / admin
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    group = models.CharField(max_length=60, default='Other')

    objects = CategoryManager()


class ProviderProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='provider_profile')
    profession = models.CharField(max_length=100)
    city = models.CharField(max_length=50)
    address = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    proof = models.FileField(upload_to='proofs/')
    approval_status = models.CharField(max_length=20, default='Pending')   # Pending / Approved / Rejected
    admin_note = models.CharField(max_length=255, blank=True, default='')  # reason when rejected
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProviderManager()

    def proof_is_image(self):
        return self.proof.name.lower().endswith(('.jpg', '.jpeg', '.png'))

    def free_times(self, service, day):
        """The start times a client can book for this service on this day."""
        work = self.work_days.filter(weekday=day.weekday()).first()
        if work is None:
            return []                      # the provider does not work on this weekday

        booked = list(Appointment.objects.filter(
            service__provider=self, date=day, status='Confirmed'
        ))
        now = datetime.now()
        length = timedelta(minutes=service.duration)
        step = timedelta(minutes=30)       # a new possible start every 30 minutes

        start = datetime.combine(day, work.start_time)
        closing = datetime.combine(day, work.end_time)
        times = []
        while start + length <= closing:   # the service must finish before closing
            end = start + length
            free = start > now             # not in the past
            for b in booked:               # overlap rule with every booked appointment
                b_start = datetime.combine(day, b.start_time)
                b_end = datetime.combine(day, b.end_time)
                if start < b_end and end > b_start:
                    free = False
            if free:
                times.append(start.time())
            start = start + step
        return times


class WorkSchedule(models.Model):
    """One row = one working day of one provider (example: Sunday 09:00-17:00)."""
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='work_days')
    weekday = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()

    objects = ScheduleManager()


class Service(models.Model):
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='services')
    # PROTECT = a category that has services cannot be deleted by mistake
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='services')
    name = models.CharField(max_length=100)
    description = models.TextField()
    duration = models.IntegerField(default=30)          # in minutes
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)       # "removed" services are only hidden
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceManager()


class Appointment(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_appointments')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=45, default='Confirmed')   # Confirmed / Cancelled
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppointmentManager()

    def is_upcoming(self):
        return self.status == 'Confirmed' and datetime.combine(self.date, self.start_time) > datetime.now()

    def google_calendar_link(self):
        """A link that opens Google Calendar with this appointment already filled in."""
        start = datetime.combine(self.date, self.start_time).strftime('%Y%m%dT%H%M%S')
        end = datetime.combine(self.date, self.end_time).strftime('%Y%m%dT%H%M%S')
        provider = self.service.provider
        title = quote(f'{self.service.name} with {provider.user.first_name}')
        place = quote(f'{provider.address}, {provider.city}')
        return ('https://calendar.google.com/calendar/render?action=TEMPLATE'
                f'&text={title}&dates={start}/{end}&location={place}')
