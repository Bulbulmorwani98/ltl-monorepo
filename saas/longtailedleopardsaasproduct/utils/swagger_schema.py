from drf_yasg.inspectors import SwaggerAutoSchema


class SuperadminOnlySchema(SwaggerAutoSchema):
    def get_operation(self, operation_keys=None):
        # Hide from tenant swagger if the user is not a superadmin
        if not getattr(self.view.request, "is_superadmin", False):
            return None
        return super().get_operation(operation_keys)


class TenantOnlySchema(SwaggerAutoSchema):
    def get_operation(self, operation_keys=None):
        # Hide from superadmin swagger if the user is a superadmin
        if getattr(self.view.request, "is_superadmin", False):
            return None
        return super().get_operation(operation_keys)
