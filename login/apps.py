from django.apps import AppConfig


class LoginConfig(AppConfig):
    name = 'login'

    def ready(self):
        from . import signals  # noqa: F401
