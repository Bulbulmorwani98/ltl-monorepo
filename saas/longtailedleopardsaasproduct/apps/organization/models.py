from django.db import models
from django.utils import timezone
from apps.accounts.models import Company 
from apps.accounts.constants import Org_Role
# This should be your tenant-specific User model or a separate OrgUser model.
class OrgUser(models.Model):
    authid = models.CharField(max_length=100, null=True, blank=True)
    auth_type = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(max_length=100, unique=True)
    profile_picture = models.TextField(null=True, blank=True)
    open_id = models.CharField(max_length=100, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=128)
    last_loggedin = models.DateTimeField(null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="org_userss")
    is_active = models.BooleanField(default=True)
    org_role= models.PositiveSmallIntegerField(choices=Org_Role.CHOICES , blank=True, null=True)


    class Meta:
        verbose_name = "Organization User"
        verbose_name_plural = "Organization Users"

    def __str__(self):
        return f"{self.email} - {self.company.schema_name}"



class Usercontent(models.Model):
    user = models.ForeignKey(OrgUser, on_delete=models.CASCADE, db_column='user_id')
    image_url = models.CharField(max_length=500, null=True, blank=True)
    video_url = models.CharField(max_length=500, null=True, blank=True)
    thumbnail_url = models.CharField(max_length=500, null=True, blank=True, default=None)
    meta_data = models.JSONField(null=True, blank=True)

    class Meta:
        managed = True  # change to False only if table already exists
        db_table = 'usercontent'


class MetaConfiguration(models.Model):
    user = models.ForeignKey(OrgUser, on_delete=models.CASCADE, db_column='user_id')
    meta_info = models.JSONField()

    class Meta:
        managed = True
        db_table = 'meta_configuration'


class ImageStatus(models.Model):
    image_name = models.CharField(max_length=100, null=True, blank=True)
    image_status = models.CharField(max_length=50, null=True, blank=True)
    upload_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    image_url = models.CharField(max_length=500, null=True, blank=True)
    meta_data = models.JSONField(null=True, blank=True)
    thumbnail_url = models.CharField(max_length=500, null=True, blank=True, default=None)
    user = models.ForeignKey(OrgUser, on_delete=models.CASCADE, db_column='user_id')

    class Meta:
        managed = True
        db_table = 'image_status'


class TaskLog(models.Model):
    task_id = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20)
    result = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'image_task_logs'

    def __str__(self):
        return f"Task {self.task_id} - {self.status}"
