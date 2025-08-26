# middleware.py

class IdentifySchemaTypeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Tenant schema is set by django-tenants
        schema_name = getattr(request.tenant, 'schema_name', None)

        # If it's 'public', we treat it as superadmin
        request.is_superadmin = schema_name == 'public'

        return self.get_response(request)
