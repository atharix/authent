from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import WebAuthnChallenge, WebAuthnCredential


@admin.register(WebAuthnCredential)
class WebAuthnCredentialAdmin(ModelAdmin):
    list_display = (
        "friendly_name",
        "user",
        "backup_state",
        "created_at",
        "last_used_at",
    )
    search_fields = ("user__email", "friendly_name")
    readonly_fields = ("credential_id", "public_key", "aaguid", "sign_count")


@admin.register(WebAuthnChallenge)
class WebAuthnChallengeAdmin(ModelAdmin):
    list_display = ("state", "ceremony", "user", "created_at", "expires_at", "consumed_at")
    readonly_fields = ("state", "challenge")
