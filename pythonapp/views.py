
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RegistrationForm, ServiceForm, TimeSlotForm
from .models import Appointment, ProviderProfile, Service, TimeSlot


def approved_services():
    """Return active services offered by approved providers."""
    return Service.objects.filter(
        is_active=True,
        provider__provider_profile__approval_status="APPROVED",
    ).select_related("provider", "provider__provider_profile")


def home(request):
    featured_services = approved_services().order_by("-created_at")[:6]

    return render(
        request,
        "pythonapp/home.html",
        {"featured_services": featured_services},
    )


def about(request):
    return render(request, "pythonapp/about.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(
                request,
                "Your account was created successfully.",
            )

            if user.role == "PROVIDER":
                messages.info(
                    request,
                    "Your provider profile must be approved before "
                    "your services appear publicly.",
                )
                return redirect("provider_dashboard")

            return redirect("home")
    else:
        form = RegistrationForm()

    return render(
        request,
        "pythonapp/register.html",
        {"form": form},
    )


def services_list(request):
    services = approved_services().order_by("-created_at")
    search_query = request.GET.get("q", "").strip()

    if search_query:
        services = services.filter(
            title__icontains=search_query
        ) | services.filter(
            category__icontains=search_query
        ) | services.filter(
            provider__provider_profile__business_name__icontains=search_query
        )

    return render(
        request,
        "pythonapp/services.html",
        {
            "services": services.distinct(),
            "search_query": search_query,
        },
    )


def service_detail(request, service_id):
    service = get_object_or_404(
        approved_services(),
        pk=service_id,
    )

    booked_slot_ids = Appointment.objects.filter(
        status="BOOKED"
    ).values_list("time_slot_id", flat=True)

    available_slots = TimeSlot.objects.filter(
        provider=service.provider,
        is_active=True,
        start_at__gt=timezone.now(),
    ).exclude(
        pk__in=booked_slot_ids
    ).order_by("start_at")

    return render(
        request,
        "pythonapp/service_detail.html",
        {
            "service": service,
            "available_slots": available_slots,
        },
    )


def available_slots(request, service_id):
    service = get_object_or_404(
        approved_services(),
        pk=service_id,
    )

    booked_slot_ids = Appointment.objects.filter(
        status="BOOKED"
    ).values_list("time_slot_id", flat=True)

    slots = TimeSlot.objects.filter(
        provider=service.provider,
        is_active=True,
        start_at__gt=timezone.now(),
    ).exclude(
        pk__in=booked_slot_ids
    ).order_by("start_at")

    return JsonResponse({
        "slots": [
            {
                "id": slot.pk,
                "start_at": slot.start_at.isoformat(),
                "end_at": slot.end_at.isoformat(),
            }
            for slot in slots
        ]
    })


@login_required
@require_POST
def book_service(request, service_id):
    service = get_object_or_404(
        approved_services(),
        pk=service_id,
    )

    slot_id = request.POST.get("time_slot")

    if not slot_id:
        messages.error(request, "Please select an available time slot.")
        return redirect("service_detail", service_id=service.pk)

    try:
        with transaction.atomic():
            slot = TimeSlot.objects.select_for_update().get(
                pk=slot_id,
                provider=service.provider,
                is_active=True,
                start_at__gt=timezone.now(),
            )

            appointment = Appointment(
                client=request.user,
                service=service,
                time_slot=slot,
                status="BOOKED",
            )

            appointment.full_clean()
            appointment.save()

        messages.success(request, "Your appointment has been booked!")

        # Email is attempted after a successful booking.
        # An email failure must not undo the appointment.
        try:
            from .services.email_api import send_booking_email

            send_booking_email(appointment)
        except Exception:
            messages.warning(
                request,
                "Your booking was saved, but the confirmation email "
                "could not be sent.",
            )

        return redirect("my_appointments")

    except TimeSlot.DoesNotExist:
        messages.error(
            request,
            "That time slot is no longer available. Please select another.",
        )
    except (ValidationError, IntegrityError) as error:
        if isinstance(error, ValidationError):
            error_messages = error.messages
        else:
            error_messages = [
                "That time slot has already been booked. "
                "Please select another."
            ]

        for error_message in error_messages:
            messages.error(request, error_message)

    return redirect("service_detail", service_id=service.pk)


@login_required
def my_appointments(request):
    appointments = Appointment.objects.filter(
        client=request.user
    ).select_related(
        "service",
        "service__provider",
        "time_slot",
    ).order_by("-created_at")

    return render(
        request,
        "pythonapp/appointments.html",
        {"appointments": appointments},
    )


@login_required
@require_POST
def cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        client=request.user,
    )

    if appointment.status != "BOOKED":
        messages.error(
            request,
            "Only active appointments can be cancelled.",
        )
    else:
        appointment.status = "CANCELLED"
        appointment.save(update_fields=["status"])
        messages.success(request, "Your appointment was cancelled.")

    return redirect("my_appointments")


@login_required
def provider_dashboard(request):
    if request.user.role != "PROVIDER":
        messages.error(
            request,
            "Only provider accounts can access this dashboard.",
        )
        return redirect("home")

    try:
        profile = request.user.provider_profile
    except ProviderProfile.DoesNotExist:
        messages.error(
            request,
            "Your provider profile could not be found.",
        )
        return redirect("home")

    service_form = ServiceForm()
    slot_form = TimeSlotForm()

    if request.method == "POST":
        if "title" in request.POST:
            service_form = ServiceForm(request.POST)

            if service_form.is_valid():
                service = service_form.save(commit=False)
                service.provider = request.user
                service.save()

                messages.success(request, "Your service was created.")
                return redirect("provider_dashboard")

        elif "start_at" in request.POST and "end_at" in request.POST:
            slot_form = TimeSlotForm(request.POST)

            if slot_form.is_valid():
                slot = slot_form.save(commit=False)
                slot.provider = request.user

                try:
                    slot.full_clean()
                    slot.save()
                    messages.success(
                        request,
                        "Your time slot was created.",
                    )
                    return redirect("provider_dashboard")
                except ValidationError as error:
                    for error_message in error.messages:
                        slot_form.add_error(None, error_message)

    services = Service.objects.filter(
        provider=request.user
    ).order_by("-created_at")

    slots = TimeSlot.objects.filter(
        provider=request.user
    ).order_by("start_at")

    appointments = Appointment.objects.filter(
        service__provider=request.user
    ).select_related(
        "client",
        "service",
        "time_slot",
    ).order_by("-created_at")

    return render(
        request,
        "pythonapp/provider_dashboard.html",
        {
            "profile": profile,
            "service_form": service_form,
            "slot_form": slot_form,
            "services": services,
            "slots": slots,
            "appointments": appointments,
        },
    )


@login_required
@require_POST
def ai_recommendations(request):
    """Recommend matching approved services using the OpenAI API."""
    if not settings.OPENAI_API_KEY:
        return JsonResponse(
            {
                "error": (
                    "AI recommendations are not configured yet. "
                    "Add your OpenAI API key to the .env file."
                )
            },
            status=503,
        )

    try:
        body = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Please send valid JSON."},
            status=400,
        )

    description = body.get("description", "")

    if not isinstance(description, str):
        return JsonResponse(
            {"error": "The description must be text."},
            status=400,
        )

    description = description.strip()

    if not description:
        return JsonResponse(
            {"error": "Describe the service you need."},
            status=400,
        )

    if len(description) > 2000:
        return JsonResponse(
            {"error": "Keep your description under 2000 characters."},
            status=400,
        )

    catalogue = list(
        approved_services().values(
            "id",
            "title",
            "category",
            "description",
            "price",
        )[:100]
    )

    if not catalogue:
        return JsonResponse({
            "recommendations": [],
            "message": "There are no approved services available yet.",
        })

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = f"""
You help people find suitable local services in Palestine.

The user needs:
{description}

Available services, from the real database:
{json.dumps(catalogue, ensure_ascii=False, default=str)}

Recommend up to 3 relevant services from this catalogue.
Only recommend services that genuinely match the user's needs.
Return valid JSON in this exact format:
{{
  "recommendations": [
    {{"service_id": 1, "reason": "Short explanation"}}
  ]
}}
Use only service IDs from the supplied catalogue.
Do not invent services, IDs, prices, or providers.
"""

        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=prompt,
        )

        result = json.loads(response.output_text)
        recommendations = result.get("recommendations", [])

        if not isinstance(recommendations, list):
            raise ValueError("Invalid recommendation format.")

        valid_services = {item["id"] for item in catalogue}
        validated = []
        seen_ids = set()

        for item in recommendations:
            if not isinstance(item, dict):
                continue

            service_id = item.get("service_id")
            reason = item.get("reason", "")

            if (
                not isinstance(service_id, int)
                or service_id not in valid_services
                or service_id in seen_ids
            ):
                continue

            seen_ids.add(service_id)

            service = next(
                (s for s in catalogue if s["id"] == service_id),
                None,
            )

            if service:
                validated.append({
                    "service_id": service_id,
                    "title": service["title"],
                    "category": service["category"],
                    "price": str(service["price"]),
                    "reason": str(reason)[:500],
                    "url": f"/services/{service_id}/",
                })

            if len(validated) == 3:
                break

        return JsonResponse({"recommendations": validated})

    except Exception:
        return JsonResponse(
            {
                "error": (
                    "We couldn't generate recommendations right now. "
                    "Please try again later."
                )
            },
            status=502,
        )
