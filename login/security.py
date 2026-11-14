"""OTP abuse limits and safe avatar handling."""
import hashlib
import io
import uuid
from datetime import timedelta
from functools import wraps

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from PIL import Image, UnidentifiedImageError


def otp_limited(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == 'POST':
            from .models import AuthAttemptWindow
            verifying = view.__name__.endswith('_verify') and request.POST.get('action', 'verify') != 'resend'
            purpose = 'verify' if verifying else 'send'
            user_id = (request.session.get('password_reset_user_id')
                       or request.session.get('pending_signup_user_id')
                       or request.session.get('pending_invitation_user_id'))
            identity = request.POST.get('email', request.session.get('password_reset_email', '')).strip().lower()
            if user_id:
                from django.contrib.auth.models import User
                identity = User.objects.filter(pk=user_id).values_list('email', flat=True).first() or identity
            now = timezone.now()
            bucket = int(now.timestamp()) // 900
            keys = [('ip:' + request.META.get('REMOTE_ADDR', 'unknown'), 50 if verifying else 10)]
            if identity:
                keys.append(('account:' + identity, 5 if verifying else 3))
            allowed = True
            for identity_key, limit in keys:
                key = hashlib.sha256(f'{purpose}:{identity_key}:{bucket}'.encode()).hexdigest()
                row, _ = AuthAttemptWindow.objects.get_or_create(key=key, defaults={'expires_at': now + timedelta(minutes=30)})
                if not AuthAttemptWindow.objects.filter(pk=row.pk, attempts__lt=limit).update(attempts=F('attempts') + 1):
                    allowed = False
            AuthAttemptWindow.objects.filter(expires_at__lt=now).delete()
            if not allowed:
                response = HttpResponse('Too many attempts. Please try again later.', status=429)
                response['Retry-After'] = str(900 - int(now.timestamp()) % 900)
                return response
        return view(request, *args, **kwargs)
    return wrapped


def login_attempt_state(request, identity):
    """Return the current failed-login window without counting successful sign-ins."""
    from .models import AuthAttemptWindow
    now = timezone.now()
    AuthAttemptWindow.objects.filter(expires_at__lt=now).delete()
    bucket = int(now.timestamp()) // 900
    identities = (
        ('account:' + identity, 10),
        ('ip:' + request.META.get('REMOTE_ADDR', 'unknown'), 100),
    )
    rows = []
    for identity_key, limit in identities:
        key = hashlib.sha256(f'login:{identity_key}:{bucket}'.encode()).hexdigest()
        row, _ = AuthAttemptWindow.objects.get_or_create(
            key=key, defaults={'expires_at': now + timedelta(minutes=30)},
        )
        rows.append((row, limit))
    return rows, 900 - int(now.timestamp()) % 900


def record_failed_login(rows):
    from .models import AuthAttemptWindow
    for row, _ in rows:
        AuthAttemptWindow.objects.filter(pk=row.pk).update(attempts=F('attempts') + 1)


def clear_login_attempts(rows):
    from .models import AuthAttemptWindow
    AuthAttemptWindow.objects.filter(pk__in=[row.pk for row, _ in rows]).delete()


def validate_avatar(upload):
    if upload.size > 2 * 1024 * 1024:
        raise ValidationError('Choose an image smaller than 2 MB.')
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValidationError('Choose a JPEG, PNG or WebP image.')
            if image.width * image.height > 16_000_000:
                raise ValidationError('Choose an image with at most 16 million pixels.')
            image.verify()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValidationError('Choose a valid image.') from exc
    finally:
        upload.seek(0)


def clean_avatar(upload):
    validate_avatar(upload)
    with Image.open(upload) as image:
        image = image.convert('RGB')
        image.thumbnail((1024, 1024))
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=85)
    return ContentFile(output.getvalue(), name=f'{uuid.uuid4().hex}.jpg')
