from django.db import connection
from django.contrib.auth.backends import ModelBackend
from apps.accounts.models import User as PublicUser
from apps.organization.models import OrgUser

class TenantAwareBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        schema = connection.schema_name
        user = None

        # First try tenant schema (OrgUser)
        if schema != "public":
            try:
                user = OrgUser.objects.get(email=username)
                if user.check_password(password):
                    return user
            except OrgUser.DoesNotExist:
                pass  # fallback to PublicUser

        # Fallback to PublicUser
        try:
            user = PublicUser.objects.get(email=username)
            if user.check_password(password):
                return user
        except PublicUser.DoesNotExist:
            return None

        return None