import json
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from .importers.services import import_transactions


@login_required(login_url="/login/")
@require_POST
def api_import_transactions(request: HttpRequest) -> JsonResponse:
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded.'}, status=400)
    file_obj = request.FILES['file']
    # basic size guard
    max_mb = 10
    if file_obj.size > max_mb * 1024 * 1024:
        return JsonResponse({'error': f'File too large. Max {max_mb} MB.'}, status=400)
    try:
        result = import_transactions(request.user, file_obj)
        return JsonResponse({'success': True, **result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
