
from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from apps.accounts.models import Company

@admin.register(Company)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
        list_display = ('name', 'paid_until')