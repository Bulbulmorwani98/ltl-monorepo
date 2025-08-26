from rest_framework import serializers
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.account.models import Users, MetaConfiguration
from django.utils import timezone
# from urllib.parse import quote
from rest_framework_simplejwt.tokens import RefreshToken
import jwt

class CustomTokenObtainPairSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=False)

    def generate_tokens(self, user):
        user.last_login = timezone.now()
        user.save()
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "email": user.email,
                "id": user.id,
            },
        }
    
    def create_user(self, email, auth_type=None, authid=None):
        user = Users.objects.create(
            email=email,
            auth_type=auth_type,
            authid=authid,
        )
        return user
    

    def validate(self, attrs):
        id_token = attrs.get("id_token")

        if id_token:
            decoded = jwt.decode(id_token, options={"verify_signature": False})
            email = decoded.get("email")
            if not email:
                raise serializers.ValidationError({"message": "Email not found in token."})
            
            sub_id = decoded.get("sub")  # Extract sub id
            
                # Extract providerType
            identities = decoded.get("identities", [])
            provider_type = None
            if identities and isinstance(identities, list):
                identity_info = identities[0]
                provider_type = identity_info.get("providerType")

            user = Users.objects.filter(email=email).first()
            if not user:
                user = self.create_user(email, provider_type, authid=sub_id)

            return {"data": self.generate_tokens(user)}
import json
class MetaConfigurationSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    user_id = serializers.SerializerMethodField()
    created_at = serializers.ReadOnlyField()
    meta_info = serializers.JSONField()

    class Meta:
        model = MetaConfiguration
        fields = ['id', 'user_id', 'created_at', 'meta_info']

    def get_user_id(self, obj):
        return obj.user.id if obj.user else None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        try:
            rep['meta_info'] = json.loads(instance.meta_info)
        except Exception:
            rep['meta_info'] = {}
        return rep
    
    def to_internal_value(self, data):
        data = data.copy()
        if isinstance(data.get('meta_info'), dict):
            data['meta_info'] = json.dumps(data['meta_info'])
        return super().to_internal_value(data)
    
    def validate_meta_info(self, value):
        required_fields = [
            "creator_name", "creator_address", "creator_city", "creator_state",
            "creator_country", "creator_postal_code", "country_code", "creator_country", "creator_email", "creator_phone",
            "creator_web_url", "creators_jobtitle", "credit_line", "date_created",
            "copyright_notice", "rights_usage_terms", "description", "description_writer",
            "headline", "instructions", "keywords", "title",
            "ai_training", "ai_generative_training", "data_mining", "ai_inference",
            "ai_training_constraint_info", "ai_generative_training_constraint_info",
            "data_mining_constraint_info", "ai_inference_constraint_info"
        ]

        missing = [field for field in required_fields if field not in value]
        if missing:
            raise serializers.ValidationError(f"Missing required fields: {', '.join(missing)}")
        
        alpha_fields = ["creator_name", "creator_city", "creator_state", "creator_country", "creators_jobtitle", "description_writer"]
        for field in alpha_fields:
            if not re.fullmatch(r"[A-Za-z\s]+", value[field] or ""):
                raise serializers.ValidationError(f"{field} must contain only alphabets and spaces.")

        digit_fields = {
            "creator_postal_code": r"^\d+$",
            "creator_phone": r"^\d+$"
        }
        # for field, pattern in digit_fields.items():
        #     # Validate postal code (digits only)
        #     if not re.fullmatch(r"^\d+$", value["creator_postal_code"] or ""):
        #         raise serializers.ValidationError("creator_postal_code must contain only digits.")

        #     # Validate phone number (10 digits only)
        #     phone = value["creator_phone"] or ""
        #     if not re.fullmatch(r"^\d{10}$", phone):
        #         raise serializers.ValidationError("creator_phone must be a valid 10-digit number.")

        # Validate email
        # try:
        #     validate_email(value["creator_email"])
        # except DjangoValidationError:
        #     raise serializers.ValidationError("Invalid email format.")

        # # Validate URL
        # url_pattern = r"^https?:\/\/[\w\-\.]+(\.[\w\-]+)+[/#?]?.*$"
        # if not re.fullmatch(url_pattern, value["creator_web_url"] or ""):
        #     raise serializers.ValidationError("Invalid web URL format.")
        
        # # Validate country code (must start with + and be followed by 1 to 4 digits)
        # country_code = value["country_code"] or ""
        # if not re.fullmatch(r"^\+\d{1,4}$", country_code):
        #     raise serializers.ValidationError("country_code must be a valid country code starting with '+' (e.g., '+1', '+91').")

        return value
    


# class FileUploadSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Metaconfiguration
#         fields = ['meta_info']

#     def validate_meta_info(self, value):
#         required_fields = [
#             "creator_name", "creator_address", "creator_city", "creator_state",
#             "creator_country", "creator_postal_code", "creator_email", "creator_phone",
#             "creator_web_url", "creators_jobtitle", "credit_line", "date_created",
#             "copyright_notice", "rights_usage_terms", "description", "description_writer",
#             "headline", "instructions", "keywords", "title",
#             "ai_training", "ai_generative_training", "data_mining", "ai_inference",
#             "ai_training_constraint_info", "ai_generative_training_constraint_info",
#             "data_mining_constraint_info", "ai_inference_constraint_info"
#         ]

#         missing_fields = [
#             field for field in required_fields 
#             if field not in value or value[field] in [None, '']
#         ]

#         if missing_fields:
#             raise serializers.ValidationError(
#                 f"Missing required fields: {', '.join(missing_fields)}"
#             )
        
#         alpha_fields = ["creator_name", "creator_city", "creator_state", "creator_country", "creators_jobtitle", "description_writer"]
#         for field in alpha_fields:
#             if not re.fullmatch(r"[A-Za-z\s]+", value[field]):
#                 raise serializers.ValidationError({field: f"{field} must contain only alphabets and spaces."})

#         if not re.fullmatch(r"^\d+$", value["creator_postal_code"]):
#             raise serializers.ValidationError({"creator_postal_code": "Postal code must contain only digits."})

#         if not re.fullmatch(r"^\d{10}$", value["creator_phone"]):
#             raise serializers.ValidationError({"creator_phone": "Phone number must be a valid 10-digit number."})

#         # Validate email
#         try:
#             validate_email(value["creator_email"])
#         except DjangoValidationError:
#             raise serializers.ValidationError({"creator_email": "Invalid email format."})

#         # Validate URL
#         url_pattern = r"^https?:\/\/[\w\-\.]+(\.[\w\-]+)+[/#?]?.*$"
#         if not re.fullmatch(url_pattern, value["creator_web_url"]):
#             raise serializers.ValidationError({"creator_web_url": "Invalid web URL format."})

#         return value    
    

#     def validate(self, data):
#         # File validation: only allow images and videos
#         files = self.context.get("files", [])

#         allowed_extensions = (
#             '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',  # Images
#             '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'              # Videos
#         )

#         invalid_files = [
#             file.name for file in files 
#             if not file.name.lower().endswith(allowed_extensions)
#         ]

#         if invalid_files:
#             raise serializers.ValidationError({
#                 "files": f"Unsupported file types: {', '.join(invalid_files)}. Only images and videos are allowed."
#             })

#         return data

# class DeleteImageSerializer(serializers.Serializer):
#     file_urls = serializers.ListField(
#         child=serializers.CharField(),
#         allow_empty=False
#     )

#     def to_internal_value(self, data):
#         file_urls = data.get("file_urls")

#         # If a single string is passed, wrap it in a list
#         if isinstance(file_urls, str):
#             data["file_urls"] = [file_urls]
#         elif not isinstance(file_urls, list):
#             raise serializers.ValidationError({
#                 "file_urls": "Must be a string or list of strings."
#             })

#         return super().to_internal_value(data)


# class LogoutSerializer(serializers.Serializer):
#     refresh = serializers.CharField()

# class ImageStatusSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ImageStatus
#         fields = ['id', 'image_name', 'image_status', 'upload_date', 'media_url']



# class VersionCreateSerializer(serializers.Serializer):
#     device_type = serializers.CharField(
#         max_length=10,
#         error_messages={"required": "Device Type Missing."}
#     )
#     current_version = serializers.CharField(
#         max_length=10,
#         error_messages={"required": "Current Version Type Missing."}
#     )
#     force_update = serializers.BooleanField(default=False)

#     def validate_device_type(self, value):
#         if value not in ["ios", "android"]:
#             raise serializers.ValidationError("Device Type Should be ios or android.")
#         return value
    

# class VersionSerializer(serializers.Serializer):
#     device_type = serializers.CharField(
#         max_length=50,
#         error_messages={"required": "Device Type Missing."}
#     )
#     current_version = serializers.CharField(
#         max_length=50,
#         error_messages={"required": "Current Version Type Missing."}
#     )

#     def validate(self, data):
#         return data
    

# class VersionListSerializer(serializers.Serializer):
#     id = serializers.CharField() 
#     device_type = serializers.CharField()
#     version_name = serializers.CharField()
#     force_update = serializers.BooleanField()
#     remember_token = serializers.CharField()
#     created_at = serializers.DateTimeField()
#     updated_at =serializers.DateTimeField()
 
# class ImageReloadSerializer(serializers.Serializer):
#     image_id = serializers.CharField()