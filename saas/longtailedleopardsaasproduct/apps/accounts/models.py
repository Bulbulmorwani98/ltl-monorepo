from django.db import models
import uuid
from django_tenants.models import TenantMixin, DomainMixin
from django.contrib.auth.models import AbstractUser
from apps.accounts.constants import RoleType,GenderType,SocialAccountType
import datetime

class TimeStampModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(TenantMixin):
    name = models.CharField(max_length=100)
    paid_until =  models.DateField()
    on_trial = models.BooleanField()
    created_on = models.DateField(auto_now_add=True)
    email = models.EmailField(unique=True)
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

class Domain(DomainMixin):
    pass

class User(AbstractUser):
    username = None
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=17, blank=True)
    role = models.PositiveSmallIntegerField(choices=RoleType.CHOICES, blank=True, null=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, blank=True, null=True
    )
    social_account = models.PositiveSmallIntegerField(
        choices=SocialAccountType.CHOICES, default=SocialAccountType.NORMAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    invite_token = models.CharField(max_length=100, blank=True)
    invite_status = models.BooleanField(default=False)
    invite_link_expire = models.DateTimeField(blank=True, null=True)

    profile_pic = models.CharField(max_length=500, blank=True,null=True)
    country = models.CharField(max_length=150, blank=True,null=True)
    gender = models.PositiveSmallIntegerField(choices=GenderType.CHOICES,blank=True, null=True)
    type_business = models.CharField(max_length=500, blank=True,null=True)
    status = models.BooleanField(default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []


class ForgotPasswordToken(TimeStampModel):
    user = models.ForeignKey(
        "User", related_name="reset_tokens", on_delete=models.CASCADE
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # token = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        get_latest_by = ("created_at",)

    def __str__(self):
        return f"{self.user} - {self.token}"

    @classmethod
    def has_latest_token(cls, user):
        last_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
        return cls.objects.filter(
            is_active=True, user=user, created_at__lte=last_time
        ).exists()

class BlacklistedToken(TimeStampModel):
    token_id = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True
    )  # Unique identifier for the token
    token = models.TextField()

    class Meta:
        verbose_name = "Blacklisted Token"
        verbose_name_plural = "Blacklisted Tokens"

    def __str__(self):
        return str(self.token_id)
    

