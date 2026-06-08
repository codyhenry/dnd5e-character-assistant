from django.apps import AppConfig


class DndOptionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dnd_options'

    def ready(self):
        from . import signals  # noqa: F401
