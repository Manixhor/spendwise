from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

from .models import UserProfile


class SpendWiseSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = (sociallogin.user.email or "").strip().lower()
        if not email or sociallogin.is_existing:
            return

        User = get_user_model()
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            sociallogin.connect(request, existing_user)

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        email = (user.email or "").strip().lower()
        if email and user.username != email:
            user.username = email
            user.save(update_fields=["username"])

        UserProfile.objects.get_or_create(
            user=user,
            defaults={"email_is_verified": True},
        )
        return user
