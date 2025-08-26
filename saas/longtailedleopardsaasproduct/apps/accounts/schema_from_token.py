# middleware/schema_from_token.py

import jwt
from django.db import connection
from django.conf import settings
from apps.accounts.models import Company, User  # adjust path if needed

class JWTBasedTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = self._get_token_from_header(request)

        if token:
            try:
                decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = decoded.get("user_id")
                user = User.objects.get(id=user_id)
                company = user.company

                if company and company.schema_name:
                    connection.set_schema(company.schema_name)
            except Exception as e:
                # log if needed
                pass  # fallback to public schema if error

        response = self.get_response(request)
        return response

    def _get_token_from_header(self, request):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth.split(" ")[1]
        return None
