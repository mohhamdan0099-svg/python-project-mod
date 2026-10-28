from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "CLIENT", "Client"
        PROVIDER = "PROVIDER", "Service Provider"
        ADMIN = "ADMIN", "Administrator"

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CLIENT,
    )

    def __str__(self):
        return self.username


class ProviderProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_profile",
    )
    business_name = models.CharField(max_length=150)
    category = models.CharField(max_length=100)
    description = models.TextField()
    phone = models.CharField(max_length=30, blank=True)
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.business_name


class Service(models.Model):
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="services",
    )
    title = models.CharField(max_length=150)
    category = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="service_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0),
                name="service_duration_positive",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def provider_name(self):
        try:
            return self.provider.provider_profile.business_name
        except ProviderProfile.DoesNotExist:
            return self.provider.username


class TimeSlot(models.Model):
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="time_slots",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=models.F("start_at")),
                name="slot_end_after_start",
            ),
        ]

    def clean(self):
        if self.end_at <= self.start_at:
            raise ValidationError("End time must be after start time.")

        if self.start_at <= timezone.now():
            raise ValidationError("Choose a future time slot.")

        overlaps = TimeSlot.objects.filter(
            provider=self.provider,
            start_at__lt=self.end_at,
            end_at__gt=self.start_at,
        ).exclude(pk=self.pk)

        if overlaps.exists():
            raise ValidationError(
                "This time overlaps another slot for this provider."
            )

    def __str__(self):
        return f"{self.provider.username}: {self.start_at}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.BOOKED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["time_slot"],
                condition=Q(status="BOOKED"),
                name="one_active_booking_per_slot",
            ),
        ]

    def clean(self):
        if self.client_id and self.client.role != User.Role.CLIENT:
            raise ValidationError("Only clients can book appointments.")

        if self.service_id and self.time_slot_id:
            if self.service.provider_id != self.time_slot.provider_id:
                raise ValidationError(
                    "This slot belongs to a different provider."
                )

        if self.status == self.Status.BOOKED and self.time_slot_id:
            if self.time_slot.start_at <= timezone.now():
                raise ValidationError("This slot is in the past.")

            if not self.time_slot.is_active:
                raise ValidationError("This time slot is unavailable.")

            if not self.service.is_active:
                raise ValidationError("This service is unavailable.")

            try:
                profile = self.service.provider.provider_profile
            except ProviderProfile.DoesNotExist:
                raise ValidationError("The provider profile is missing.")

            if profile.approval_status != ProviderProfile.ApprovalStatus.APPROVED:
                raise ValidationError("The provider is not approved.")

    def __str__(self):
        return f"{self.service.title} - {self.client.username}"