from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
import re
from apps.organization import models as organization_models
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password
from apps.accounts import models as account_model
from longtailedleopardsaasproduct import settings
from django.core.mail import send_mail
from django.db import connection
from apps.accounts.models import User
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password



class MetaInfoSerializer(serializers.Serializer):
    required_fields = [
        "creator_name", "creator_email", "date_created",
        "copyright_notice", "description", "title",
    ]

    def validate(self, data):
        input_data = self.initial_data

        # Check required fields
        missing = []
        for field in self.required_fields:
            value = input_data.get(field)
            if value is None or str(value).strip() == "":
                missing.append(field)

        if missing:
            def prettify(field):
                return field.replace("_", " ").capitalize()

            field_messages = [f"{prettify(field)} is required" for field in missing]
            message = ", ".join(field_messages) + "."
            raise serializers.ValidationError({"message": message})
        
        for key, value in input_data.items():
                if isinstance(value, str):
                    input_data[key] = value.strip()


        # Field-specific validations
        alpha_fields = ["creator_name", "creator_state", "creator_country", "creators_jobtitle",]

        for field in alpha_fields:
            value = input_data.get(field, "")
            if not all(word.isalpha() for word in value.split()):
                raise serializers.ValidationError({field: "Only alphabetic characters are allowed."})

        # Basic validation for email and URL format
        email = input_data.get("creator_email")
        if email and "@" not in email:
            raise serializers.ValidationError({"creator_email": "Enter a valid email address."})

        url = input_data.get("creator_web_url")
        url_regex = r'^(https?:\/\/)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if url and not re.match(url_regex, url):
            raise serializers.ValidationError({"creator_web_url": "Enter a valid URL (e.g., https://www.example.com)."})
        

        # Step 6: Phone number validation (optional but must be digits and reasonable length)
        phone = input_data.get("creator_phone")
        if phone:
            if not phone.isdigit():
                raise serializers.ValidationError({"creator_phone": "Only digits are allowed."})
            if len(phone) > 10:
                raise serializers.ValidationError({"creator_phone": "Enter a valid phone number."})

        # Step 7: Postal code validation (optional, digits only)
        postal_code = input_data.get("creator_postal_code")
        if postal_code and not postal_code.isdigit():
            raise serializers.ValidationError({"creator_postal_code": "Only digits are allowed."})

        return input_data

class FileUploadSerializer(serializers.Serializer):
    meta_info = serializers.DictField()

    def validate_meta_info(self, value):
        required_fields = [
            "creator_name", "creator_email", "date_created",
            "copyright_notice", "description", "title"
        ]

        # Check for missing or empty required fields
        missing_fields = [
            field for field in required_fields
            if field not in value or not str(value[field]).strip()
        ]

        if missing_fields:
            raise serializers.ValidationError(
                {field: f"{field} is required." for field in missing_fields}
            )

        # Validate required fields
        if not re.fullmatch(r"[A-Za-z\s]+", value["creator_name"].strip()):
            raise serializers.ValidationError({"creator_name": "Must contain only alphabets and spaces."})

        try:
            validate_email(value["creator_email"])
        except DjangoValidationError:
            raise serializers.ValidationError({"creator_email": "Invalid email format."})

        # Optional fields to validate only if present
        alpha_fields = [
            "creator_state", "creator_country",
            "creators_jobtitle", "description_writer"
        ]
        for field in alpha_fields:
            field_value = value.get(field)
            if field_value:
                if not isinstance(field_value, str):
                    raise serializers.ValidationError({field: f"{field} must be a string."})
                if not re.fullmatch(r"[A-Za-z\s]+", field_value.strip()):
                    raise serializers.ValidationError({field: f"{field} must contain only alphabets and spaces."})

        # Postal code validation (optional)
        postal_code = value.get("creator_postal_code")
        if postal_code:
            if not re.fullmatch(r"^\d+$", str(postal_code).strip()):
                raise serializers.ValidationError({"creator_postal_code": "Postal code must contain only digits."})

        # Phone number validation (optional)
        phone = value.get("creator_phone")
        if phone:
            if not re.fullmatch(r"^\d{10}$", str(phone).strip()):
                raise serializers.ValidationError({"creator_phone": "Phone number must be a valid 10-digit number."})

        # Web URL validation (optional)
        url = value.get("creator_web_url")
        if url:
            url_regex = r'^(https?:\/\/)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.fullmatch(url_regex, url.strip()):
                raise serializers.ValidationError({"creator_web_url": "Invalid web URL format."})

        return value
    

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
    
class OrguserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True, error_messages={"required": "Email is required."}
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={"required": "Password is required."},
    )

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        tenant = connection.tenant

        # 1. Try authenticating from User table
        user = User.objects.filter(email=email).first()
        if user and user.check_password(password):
            if not user.status:
                raise serializers.ValidationError("Your account is deactivated.")
            if user.role not in (1, 2, 3):
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
                    "role": user.role,
                    "schema_name": user.company.schema_name,
                    "domain": f"http://{user.company.schema_name}:8000/swagger/"
                    if user.company.schema_name
                    else None,
                    "type_business": user.type_business,
                },
            }

        org_user = organization_models.OrgUser.objects.filter(email=email).first()
        if org_user and check_password(password, org_user.password):
            org_user.last_loggedin = timezone.now()
            org_user.save()
            refresh = RefreshToken.for_user(org_user)
            access_token = refresh.access_token
            access_token["role"] = org_user.org_role
            return {
                "refresh": str(refresh),
                "access": str(access_token),
                "user": {
                    "email": org_user.email,
                    "org_user": org_user.org_role,
                    "schema_name": org_user.company.schema_name,
                    "domain": f"http://{org_user.company.schema_name}:8000/swagger/"
                    if org_user.company.schema_name
                    else None,
                },
            }

        # If neither User nor OrgUser found
        raise serializers.ValidationError(
            "Invalid email or password. Please try again."
        )