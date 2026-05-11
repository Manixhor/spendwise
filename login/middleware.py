from django.db import transaction, models
from .models import PageView


class PageViewMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith('/admin') and hasattr(request, 'user') and request.user.is_authenticated:
            with transaction.atomic():
                obj, _ = PageView.objects.get_or_create(
                    user=request.user,
                    path=path
                )
                obj.view_count += 1
                obj.save(update_fields=['view_count', 'last_viewed'])
        response = self.get_response(request)
        return response