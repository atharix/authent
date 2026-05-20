# Asegura que la app de Celery se cargue al iniciar Django, de modo que
# @shared_task quede vinculado a esta app y autodiscover_tasks() funcione.
from .celery import app as celery_app

__all__ = ("celery_app",)
