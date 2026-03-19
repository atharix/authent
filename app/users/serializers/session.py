"""Serializers for user session management."""

from datetime import datetime, timezone as dt_timezone

from rest_framework import serializers

from users.models.session import UserSession
from users.utils.session import get_client_ip, hash_token, parse_user_agent


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user session information."""

    is_current = serializers.SerializerMethodField()
    device_info = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    application_name = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id",
            "device_name",
            "device_type",
            "device_info",
            "location",
            "ip_address",
            "application_name",
            "created_at",
            "last_activity",
            "expires_at",
            "is_active",
            "is_current",
        ]
        read_only_fields = fields

    def get_is_current(self, obj):
        return obj.is_current_device

    def get_application_name(self, obj):
        if obj.api_key_id:
            return obj.api_key.application.name
        return None

    def get_device_info(self, obj):
        parts = []
        if obj.os_name:
            os_info = obj.os_name
            if obj.os_version:
                os_info += f" {obj.os_version}"
            parts.append(os_info)

        if obj.browser:
            browser_info = obj.browser
            if obj.browser_version:
                browser_info += f" {obj.browser_version}"
            parts.append(browser_info)

        return " • ".join(parts) if parts else obj.user_agent[:50]

    def get_location(self, obj):
        parts = []
        if obj.city:
            parts.append(obj.city)
        if obj.country:
            parts.append(obj.country)
        return ", ".join(parts) if parts else None


class CreateUserSessionSerializer(serializers.ModelSerializer):
    """Serializer for creating a new session.

    The client only provides device information. All JWT-derived and
    network fields are extracted server-side from the request.
    """

    class Meta:
        model = UserSession
        fields = [
            "device_name",
            "device_type",
            "os_name",
            "os_version",
            "browser",
            "browser_version",
            "country",
            "city",
        ]
        extra_kwargs = {f: {"required": False} for f in fields}

    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context is required.")

        # --- Server-derived fields from JWT token ---
        auth = request.auth
        if not auth:
            raise serializers.ValidationError("Valid JWT token required.")

        attrs["jti"] = auth["jti"]
        exp_timestamp = auth.get("exp")
        attrs["expires_at"] = datetime.fromtimestamp(exp_timestamp, tz=dt_timezone.utc)

        # Hash jti as session identifier (refresh token not available at this point)
        attrs["refresh_token_hash"] = hash_token(auth["jti"])

        # --- Server-derived fields from request ---
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        attrs["user_agent"] = user_agent
        attrs["ip_address"] = get_client_ip(request)

        # Auto-parse device info from user-agent if client didn't provide it
        if user_agent and not attrs.get("device_type"):
            parsed = parse_user_agent(user_agent)
            attrs.setdefault("device_type", parsed["device_type"])
            attrs.setdefault("os_name", parsed["os_name"])
            attrs.setdefault("os_version", parsed["os_version"])
            attrs.setdefault("browser", parsed["browser"])
            attrs.setdefault("browser_version", parsed["browser_version"])

        # --- Ownership ---
        attrs["user"] = request.user
        if hasattr(request, "api_key") and request.api_key is not None:
            attrs["api_key"] = request.api_key

        return attrs

    def create(self, validated_data):
        validated_data["is_active"] = True
        return UserSession.objects.create(**validated_data)
