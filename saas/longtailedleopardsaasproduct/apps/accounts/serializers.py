import binascii
import os
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, Permission
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import models as account_model
from apps.accounts.constants import RoleType, SocialAccountType
from apps.accounts.custom_exception import PlainValidationError
from apps.accounts.models import User
from apps.organization import models as organization_models
from django.db import connection
from django.contrib.auth.hashers import check_password
from apps.organization.backends import TenantAwareBackend
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from longtailedleopardsaasproduct import settings


class BusinessAccountSerializer(serializers.ModelSerializer):
    """
    This class represents a serializer for business accounts.
    It handles the validation and creation of business accounts,
    including setting the role to ADMIN and encrypting the password.
    """

    # company_name = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password")

    def validate(self, attrs):
        attrs["password"] = make_password(attrs.get("password"))
        attrs["role"] = RoleType.ADMIN
        return attrs

    def is_valid(self, raise_exception=False):
        email = self.initial_data["email"]
        user = User.objects.filter(email=email)
        if user.exists() and (len(user[0].password) == 0 or user[0].password is None):
            social_account = None
            if user[0].social_account == SocialAccountType.GOOGLE:
                social_account = "Google"
            elif user[0].social_account == SocialAccountType.FACEBOOK:
                social_account = "Facebook"
            if social_account:
                raise PlainValidationError(
                    detail={
                        "error": False,
                        "data": [],
                        "message": f"user is already register via {social_account}",
                    }
                )
        elif user.exists() and user[0].password:
            raise PlainValidationError(
                detail={
                    "error": False,
                    "data": [],
                    "message": f"Account already exists.",
                }
            )
        return super(BusinessAccountSerializer, self).is_valid(
            raise_exception=raise_exception
        )


class AddOrganizationUserSerializer(serializers.ModelSerializer):
    org_role = serializers.IntegerField(required=False)

    class Meta:
        model = organization_models.OrgUser
        fields = ("name", "email", "org_role")
        # No need for extra_kwargs now

    def validate(self, attrs):
        # Generate a random password
        random_password = get_random_string(length=10)
        attrs["raw_password"] = random_password
        attrs["password"] = make_password(random_password)
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        company = request.user.company
        total_users_in_company = organization_models.OrgUser.objects.filter(
            company=company
        ).count()
        if total_users_in_company >= 10:
            raise serializers.ValidationError(
                "An organization cannot add more than 10 users"
            )
        password = validated_data.pop("raw_password")
        user = organization_models.OrgUser.objects.create(
            company=company, **validated_data
        )
        domain = account_model.Domain.objects.filter(tenant=request.user.company).first()
        # Send welcome email
        subject = "Welcome to Longtail Product"
        message = (
            f"Hi {user.name},\n\n"
            f"Welcome to Longtail! Your account has been created successfully.\n\n"
            f"Here are your login details:\n"
            f"Email: {user.email}\n"
            f"Password: {password}\n"
            f"Website: http://{domain.domain}:8000/swagger/\n\n"
            f"Please log in and change your password immediately for security reasons.\n\n"
            f"Thank you,\n"
            f"Team Longtail"
        )
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [user.email]
        try:
            send_mail(subject, message, email_from, recipient_list)

        except Exception as e:
            print(f"Failed to send email: {e}")

        return user


class SuperuserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True, error_messages={"required": "email field is required."}
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={"required": "password field is required."},
    )

    def validate(self, data):
        email = data.get("email")

        password = data.get("password")

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError(
                "Invalid email or password. Please try again."
            )
        if not user.is_superuser:
            raise serializers.ValidationError("Invalid email or password.")

        user.last_login = timezone.now()
        user.save()

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        access_token["role"] = user.role

        return {
            "refresh": str(refresh),
            "access": str(access_token),
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        }


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"success": False, "message": "User with this email does not exist."}
            )
        return email


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")
        if len(data["new_password"]) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long."
            )
        # Add your password complexity rules here (e.g. must contain number/symbol)
        return data


class OrganizationList(serializers.Serializer):
    uid = serializers.CharField(read_only=True)
    schema_name = serializers.CharField()
    email = serializers.EmailField()
    domain = serializers.CharField()
    created_at = serializers.DateTimeField()
    status = serializers.BooleanField()


class OrganizationEditSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(required=False)

    class Meta:
        model = account_model.Company
        fields = ["schema_name", "email", "domain"]


class AdminUserSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    active_vs_total_users = serializers.SerializerMethodField()
    last_active = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()
    feature_list = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = account_model.User
        fields = [
            "organization_name",
            "active_vs_total_users",
            "last_active",
            "usage",
            "feature_list",
            "status",
        ]

    def get_organization_name(self, obj):
        return obj.company.schema_name if obj.company else ""

    def get_active_vs_total_users(self, obj):
        try:
            if obj.company:
                with schema_context(obj.company.schema_name):
                    total_users = organization_models.OrgUser.objects.count()
                    active_users = organization_models.OrgUser.objects.filter(
                        is_active=True
                    ).count()
                    return f"{active_users} / {total_users}"
        except Exception as e:
            return "0 / 0"
        return ""

    def get_last_active(self, obj):
        return obj.last_login.strftime("%Y-%m-%d") if obj.last_login else ""

    def get_usage(self, obj):
        return ""  # Placeholder for now

    def get_feature_list(self, obj):
        return ""  # Placeholder for now

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"
