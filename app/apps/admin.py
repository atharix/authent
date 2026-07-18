from django.contrib import admin

from .models import APIKey, Application


class APIKeyInline(admin.TabularInline):
    model = APIKey
    extra = 0
    readonly_fields = ("key", "last_used_at", "created_at")
    fields = ("name", "key", "is_active", "expires_at", "last_used_at", "created_at")
    show_change_link = True


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
        "enforce_app_access",
        "created_at",
        "api_key_count",
    )
    list_filter = ("is_active", "enforce_app_access")
    list_editable = ("enforce_app_access",)
    search_fields = ("name", "code", "description")
    prepopulated_fields = {"code": ("name",)}
    inlines = [APIKeyInline]

    @admin.display(description="API Keys")
    def api_key_count(self, obj):
        return obj.api_keys.filter(is_active=True).count()


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "application",
        "masked_key",
        "is_active",
        "expires_at",
        "last_used_at",
        "created_at",
    )
    list_filter = ("is_active", "application")
    search_fields = ("name", "application__name")
    readonly_fields = ("key", "last_used_at", "created_at")

    @admin.display(description="Key")
    def masked_key(self, obj):
        return f"{obj.key[:8]}...{obj.key[-4:]}"
