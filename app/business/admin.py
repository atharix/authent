from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Business, Collaborator, Industry


@admin.register(Business)
class BusinessAdmin(ModelAdmin):
    list_display = [
        "name",
        "tax_id",
        "country",
        "currency",
        "vat_regime",
        "industry",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "country", "industry", "currency"]
    search_fields = ["name", "legal_name", "fiscal_name", "tax_id", "registration_number"]
    ordering = ["name"]


@admin.register(Industry)
class IndustryAdmin(ModelAdmin):
    list_display = ["name", "code", "is_active", "sort_order", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    ordering = ["sort_order", "name"]


@admin.register(Collaborator)
class CollaboratorAdmin(ModelAdmin):
    list_display = ["user", "business", "role", "title", "is_active", "joined_at"]
    list_filter = ["is_active", "business", "role"]
    search_fields = ["user__email", "business__name", "title"]
    ordering = ["-joined_at"]
    autocomplete_fields = ["user", "business", "role"]
