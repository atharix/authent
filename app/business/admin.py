from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Business, Collaborator


@admin.register(Business)
class BusinessAdmin(ModelAdmin):
    list_display = ["name", "tax_id", "country", "industry", "is_active", "created_at"]
    list_filter = ["is_active", "country", "industry"]
    search_fields = ["name", "legal_name", "tax_id"]
    ordering = ["name"]


@admin.register(Collaborator)
class CollaboratorAdmin(ModelAdmin):
    list_display = ["user", "business", "role", "title", "is_active", "joined_at"]
    list_filter = ["is_active", "business", "role"]
    search_fields = ["user__email", "business__name", "title"]
    ordering = ["-joined_at"]
    autocomplete_fields = ["user", "business", "role"]
