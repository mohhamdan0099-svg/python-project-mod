
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import ProviderProfile, Service, TimeSlot, User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    role = forms.ChoiceField(
        choices=[
            (User.Role.CLIENT, "Client"),
            (User.Role.PROVIDER, "Service Provider"),
        ],
        initial=User.Role.CLIENT,
    )

    business_name = forms.CharField(
        max_length=150,
        required=False,
    )
    category = forms.CharField(
        max_length=100,
        required=False,
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "role",
            "password1",
            "password2",
        ]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")

        return email

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("role") == User.Role.PROVIDER:
            required_fields = [
                "business_name",
                "category",
                "description",
            ]

            for field in required_fields:
                if not cleaned_data.get(field, "").strip():
                    self.add_error(
                        field,
                        "This field is required for service providers.",
                    )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = self.cleaned_data["role"]

        if commit:
            user.save()

            if user.role == User.Role.PROVIDER:
                ProviderProfile.objects.create(
                    user=user,
                    business_name=self.cleaned_data["business_name"],
                    category=self.cleaned_data["category"],
                    description=self.cleaned_data["description"],
                    phone=self.cleaned_data.get("phone", ""),
                )

        return user


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "title",
            "category",
            "description",
            "price",
            "duration_minutes",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "duration_minutes": forms.NumberInput(attrs={"min": "1"}),
        }

    def clean_price(self):
        price = self.cleaned_data["price"]

        if price < 0:
            raise ValidationError("Price cannot be negative.")

        return price

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]

        if duration < 1:
            raise ValidationError("Duration must be at least one minute.")

        return duration


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = [
            "start_at",
            "end_at",
            "is_active",
        ]
        widgets = {
            "start_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "end_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_time_format = "%Y-%m-%dT%H:%M"
        self.fields["start_at"].input_formats = [date_time_format]
        self.fields["end_at"].input_formats = [date_time_format]

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if start_at and end_at and end_at <= start_at:
            self.add_error("end_at", "End time must be after start time.")

        return cleaned_data
