import os

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate
from django.dispatch import receiver


def _env_enabled(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


@receiver(post_migrate)
def ensure_deploy_superuser(sender, **kwargs):
    if sender.label != "login":
        return

    if not _env_enabled("CREATE_SUPERUSER_ON_START"):
        return

    username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")

    if not username or not password:
        print("Auto superuser skipped: missing DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD.")
        return

    User = get_user_model()

    defaults = {
        "email": email,
        "is_staff": True,
        "is_superuser": True,
        "is_active": True,
    }
    user, created = User.objects.get_or_create(username=username, defaults=defaults)

    changed = created
    for field, expected in defaults.items():
        if getattr(user, field) != expected:
            setattr(user, field, expected)
            changed = True

    if email and user.email != email:
        user.email = email
        changed = True

    user.set_password(password)
    changed = True

    if changed:
        user.save()

    print(
        f"Auto superuser {'created' if created else 'updated'} for username='{username}'."
    )
