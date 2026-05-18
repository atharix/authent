from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    name = "integrations"
    verbose_name = "Integrations"

    def ready(self) -> None:
        # Registra los signal handlers (signup → Atlas lead, business → Atlas account).
        from . import signals  # noqa: F401
