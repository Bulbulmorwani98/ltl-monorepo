from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils.translation import gettext_lazy as _
from django.db import connection
from rest_framework_simplejwt.settings import api_settings

from apps.accounts.models import User as PublicUser
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.exceptions import InvalidToken


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        result = super().authenticate(request)
        return result

    def get_user(self, validated_token):

        schema = connection.schema_name

        user_id = validated_token.get(api_settings.USER_ID_CLAIM)

        if not user_id:
            raise AuthenticationFailed("Token missing user_id claim")

        # Try tenant user first if not in public schema
        if schema != "public":
            try:
                from apps.organization.models import OrgUser
                user = OrgUser.objects.get(pk=user_id)
                return user
            except OrgUser.DoesNotExist:
                print("User not found in OrgUser")

        # Fallback to PublicUser
        try:
            from apps.accounts.models import User as PublicUser
            user = PublicUser.objects.get(pk=user_id)
            return user
        except PublicUser.DoesNotExist:
            raise AuthenticationFailed("User not found.")

        return None