import bcrypt
import re
from datetime import datetime
from django.db import models
from django.db.models import Q


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

        EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')
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
        # Check if email is empty or invalid format
        EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')
        if not postData['email']:
            errors['login_email'] = 'Email address is required.'
        elif not EMAIL_REGEX.match(postData['email']):
            errors['login_email'] = 'Invalid email address format.'

        # Check if password is provided
        if not postData['password']:
            errors['login_password'] = 'Password is required.'
        elif len(postData['password']) < 8:
            errors['login_password'] = 'Password must be at least 8 characters long.'

        # If basic fields are filled, check credentials against database
        if not errors:
            user_list = User.objects.filter(email=postData['email'])
            if len(user_list) == 0:
                errors['login_credentials'] = 'Email not found. Please register first.'
            else:
                user = user_list[0]
                # Verify password hash
                if not bcrypt.checkpw(postData['password'].encode(), user.password.encode()):
                    errors['login_credentials'] = 'Invalid password.'

        return errors


class TimeSlotManager(models.Manager):

    def upcoming(self):
        """Only slots that are still in the future (later today or any later day)."""
        now = datetime.now()
        return self.filter(
            Q(date__gt=now.date()) | Q(date=now.date(), start_time__gt=now.time())
        )

    def slot_validator(self, postData):
        errors = {}
        try:
            slot_date = datetime.strptime(postData['date'], '%Y-%m-%d').date()
            start = datetime.strptime(postData['start_time'], '%H:%M').time()
            end = datetime.strptime(postData['end_time'], '%H:%M').time()
        except (ValueError, KeyError):
            errors['format'] = 'Please choose a valid date, start time and end time.'
            return errors

        now = datetime.now()
        if slot_date < now.date():
            errors['date'] = 'The date cannot be in the past.'
        elif slot_date == now.date() and start <= now.time():
            errors['start_time'] = 'The start time has already passed today.'

        if end <= start:
            errors['end_time'] = 'End time must be after start time.'
        return errors


class User(models.Model):
    first_name = models.CharField(max_length=45)
    last_name = models.CharField(max_length=45)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, default='client')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()


class ProviderProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='provider_profile'
    )
    service_title = models.CharField(max_length=100)
    bio = models.TextField(default='')
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    approval_status = models.CharField(max_length=20, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TimeSlot(models.Model):
    provider = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name='time_slots'
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TimeSlotManager()

    def is_past(self):
        now = datetime.now()
        return self.date < now.date() or (
            self.date == now.date() and self.start_time <= now.time()
        )


class Appointment(models.Model):
    client = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='client_appointments'
    )
    time_slot = models.OneToOneField(
        TimeSlot, on_delete=models.CASCADE, related_name='appointment'
    )
    status = models.CharField(max_length=45, default='Confirmed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Service(models.Model):
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='Other')
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)