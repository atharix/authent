from core.utilities.list import ImagePreviewListDisplayMixin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import TermsAndConditions, User, UserTermsAcceptance


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin, ImagePreviewListDisplayMixin):
    """Admin configuration for custom User model."""

    list_display = [
        "user_info_display",
        "profile_type_badge",
        "status_badge",
        "role_display",
    ]
    list_filter = [
        "is_active",
        "review_account_until",
        "is_staff",
        "is_superuser",
        "profile_type",
        "date_joined",
        "gender",
    ]
    search_fields = ["email", "first_name", "last_name", "phone_number"]
    readonly_fields_extra = ("review_account_set_by", "review_account_set_at")

    def save_model(self, request, obj, form, change):
        """Sella quién abrió la ventana de revisión y la recorta a 30 días."""
        from datetime import timedelta

        from django.utils import timezone

        if "review_account_until" in getattr(form, "changed_data", []):
            if obj.review_account_until:
                tope = timezone.now() + timedelta(days=30)
                if obj.review_account_until > tope:
                    obj.review_account_until = tope
                obj.review_account_set_by = request.user
                obj.review_account_set_at = timezone.now()
            else:
                obj.review_account_set_by = None
                obj.review_account_set_at = None
        super().save_model(request, obj, form, change)
    ordering = ["first_name", "last_name"]
    readonly_fields = ["date_joined", "last_login", "avatar_preview"]

    fieldsets = (
        (
            "Personal Information",
            {"fields": ("email", "password", "first_name", "last_name")},
        ),
        (
            "Tipo de Perfil",
            {
                "fields": ("profile_type",),
            },
        ),
        (
            "Optional Details",
            {
                "fields": (
                    "birth_date",
                    "phone_number",
                    "gender",
                    "avatar",
                    "avatar_preview",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Cuenta de revisión de tienda",
            {
                "fields": (
                    "review_account_until",
                    "review_account_reason",
                    "review_account_set_by",
                    "review_account_set_at",
                ),
                "description": (
                    "Solo para las cuentas de demostración de App Store y Google "
                    "Play, que no tienen acceso al buzón. Mientras la fecha esté "
                    "en el futuro, la cuenta entra sin código y sin passkey; los "
                    "términos y el resto de la app los ve igual que cualquiera. "
                    "Máximo 30 días: si pones más, se recorta solo."
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Dates",
            {
                "fields": ("last_login", "date_joined"),
                "classes": ("collapse",),
            },
        ),
    )

    add_fieldsets = (
        (
            "Create New User",
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @display(description=_("Perfil"))
    def profile_type_badge(self, obj):
        colors = {
            "developer": "#8b5cf6",
            "admin": "#3b82f6",
            "client": "#6b7280",
        }
        color = colors.get(obj.profile_type, "#9ca3af")
        label = obj.get_profile_type_display() or obj.profile_type or "-"
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            "border-radius: 12px; font-size: 11px; font-weight: 600; "
            'text-transform: uppercase; display: inline-block;">{}</span>',
            color,
            label,
        )

    @display(description=_("User"))
    def user_info_display(self, obj):
        avatar_url = obj.avatar.url if obj.avatar else "https://via.placeholder.com/40"
        full_name = obj.get_full_name() or obj.email
        return self.image_preview(avatar_url, full_name, obj.email)

    @display(description=_("Status"))
    def status_badge(self, obj):
        if obj.is_active:
            label = _("ACTIVE")
            color = "#10b981"
        else:
            label = _("INACTIVE")
            color = "#ef4444"
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            "border-radius: 12px; font-size: 11px; font-weight: 600; "
            'text-transform: uppercase; display: inline-block;">{}</span>',
            color,
            label,
        )

    @display(description=_("Role"))
    def role_display(self, obj):
        if obj.is_superuser:
            return format_html(
                '<span style="color: #8b5cf6; font-weight: 600;">{}</span>',
                _("SUPERUSER"),
            )
        elif obj.is_staff:
            return format_html(
                '<span style="color: #3b82f6; font-weight: 600;">{}</span>',
                _("STAFF"),
            )
        group = obj.groups.first()
        if group:
            return format_html(
                '<span style="color: #6b7280;">{}</span>',
                group.name.upper(),
            )
        return format_html('<span style="color: #9ca3af;">USER</span>')

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" width="50" height="50" style="{}" />',
                obj.avatar.url,
                "border-radius: 50%;",
            )
        return "No avatar"

    avatar_preview.short_description = "Avatar Preview"


@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(ModelAdmin):
    list_display = ["version", "is_active", "published_at", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["version"]
    ordering = ["-created_at"]


@admin.register(UserTermsAcceptance)
class UserTermsAcceptanceAdmin(ModelAdmin):
    list_display = ["user", "terms", "accepted_at", "ip_address"]
    list_filter = ["terms"]
    search_fields = ["user__email", "terms__version"]
    ordering = ["-accepted_at"]
    readonly_fields = ["accepted_at"]
