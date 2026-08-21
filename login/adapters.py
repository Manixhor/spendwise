from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import UserProfile


class SpendWiseSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = (data.get("email") or "").strip().lower()
        if email:
            user.email = email
            user.username = email
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        if user.email and user.username != user.email:
            user.username = user.email
            user.save(update_fields=["username"])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.email_is_verified:
            profile.email_is_verified = True
            profile.email_verification_code = ""
            profile.save(update_fields=["email_is_verified", "email_verification_code"])
        return user
