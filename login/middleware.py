import re
from django.db import models
from django.utils import timezone
from .models import PageView

_ASSET_PATH_RE = re.compile(r"\.(?:js|css|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|otf|eot|map|txt|json)(?:/|$)", re.IGNORECASE)


def _is_page_view(path: str) -> bool:
    """True only for real page renders — not API calls, assets, or admin."""
    if path.startswith(("/admin", "/api/", "/static/", "/media/")):
        return False
    if _ASSET_PATH_RE.search(path):
        return False
    return True


class PageViewMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method == "GET"
            and _is_page_view(request.path)
            and hasattr(request, "user")
            and request.user.is_authenticated
        ):
            obj, _ = PageView.objects.get_or_create(
                user=request.user,
                path=request.path,
                defaults={"view_count": 0},
            )
            PageView.objects.filter(pk=obj.pk).update(
                view_count=models.F("view_count") + 1,
                last_viewed=timezone.now(),
            )
        response = self.get_response(request)
        return response
