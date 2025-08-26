import base64
from django.conf import settings
from django.http import JsonResponse
from rest_framework.response import Response
from urllib.parse import urlencode
from collections import OrderedDict
from rest_framework.parsers import MultiPartParser, FormParser
from uuid import uuid4
from authlib.integrations.requests_client import OAuth2Session
from rest_framework.decorators import api_view
import os
import json
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
# from django.utils.timezone import make_aware
from datetime import datetime
from rest_framework import status
import logging
import requests
from apps.account.helpers.s3_helpers import S3Uploader
import jwt
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .serializers import  CustomTokenObtainPairSerializer, MetaConfigurationSerializer
from .models import  Usercontent, ImageStatus, MetaConfiguration
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.account.responses import CustomResponse
# from urllib.parse import urlparse, unquote
import logging
import tempfile
import asyncio
# from apps.account.helpers.c2pa_utils import process_file
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.core.files.uploadedfile import InMemoryUploadedFile
import io
from rest_framework import generics,serializers

logger = logging.getLogger(__name__)

User = get_user_model()


s3_helper = S3Uploader()

class LoginView(APIView):
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        return CustomTokenObtainPairSerializer

    @swagger_auto_schema(request_body=CustomTokenObtainPairSerializer, tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        serializer = CustomTokenObtainPairSerializer(data=request.data)
        if serializer.is_valid():
            response_data = serializer.validated_data.get("data", {})
            return CustomResponse.success("Your data has been saved successfully", [response_data])
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# class CustomLogoutView(APIView):
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(
#         operation_description="Log out the authenticated user by blacklisting both access and refresh tokens.",
#         manual_parameters=[
#             openapi.Parameter(
#                 name="X-Refresh-Token",
#                 in_=openapi.IN_HEADER,
#                 description="Refresh token",
#                 type=openapi.TYPE_STRING,
#                 required=True,
#                 default="<refresh_token>"
#             )
#         ],
#         responses={
#             200: "Logged out successfully.",
#             400: "Access or refresh token missing or invalid.",
#             401: "Unauthorized.",
#         },
#         tags=["Authentication"]
#     )
#     def post(self, request):
#         try:
#             # Access token from Authorization header
#             auth_header = request.headers.get("Authorization")
#             if not auth_header or not auth_header.startswith("Bearer "):
#                 return CustomResponse.error(message="Access token missing in the Authorization header.")
            
#             access_token_str = auth_header.split("Bearer")[1].strip()
#             access_token = AccessToken(access_token_str)
#             BlacklistedToken.objects.create(token=str(access_token))

#             # Refresh token from X-Refresh-Token header
#             refresh_token_str = request.headers.get("X-Refresh-Token")
#             if not refresh_token_str:
#                 return CustomResponse.error(message="Refresh token missing in the header 'X-Refresh-Token'.")

#             refresh_token = RefreshToken(refresh_token_str)
#             refresh_token.blacklist()

#             return CustomResponse.success(message="Logged out successfully.")

#         except Exception as e:
#             logger.error(f"Logout error: {str(e)}", exc_info=True)
#             return CustomResponse.error(message="Invalid token or token expired.")
        
class ConfigurationView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Fetch the meta configuration for the authenticated user.",
        responses={
            200: "Meta configuration returned",
            404: "No configuration found"
        },
        tags=["v1/accounts"],
    )
    def get(self, request):
        try:
            meta_config = MetaConfiguration.objects.get(user=request.user)
            print(request.user,'llllllllllllllllllllllllllllllllllllllllllllllllllllllllll')
            logger.debug('meta_config __dict__: %s', meta_config.__dict__)   
            serializer = MetaConfigurationSerializer(meta_config)
            logger.debug('serializer.data: %s', serializer.data)  # Shows serialized JSON-ready data
            return CustomResponse.success("Meta configuration fetched", [{"meta_info": serializer.data["meta_info"]}])
        except MetaConfiguration.DoesNotExist:
            return CustomResponse.success("No configuration found", [{"meta_info": {}}])

    @swagger_auto_schema(
        request_body=MetaConfigurationSerializer,
        operation_description="Create or update the meta configuration for the authenticated user.",
        responses={
            200: "Configuration saved successfully",
            400: "Validation failed",
        },
        tags=["v1/accounts"],
    )
    def post(self, request):
        try:
            print(request.user,'1111111111111111111111111111111111111111111111')
            meta_config = MetaConfiguration.objects.get(user=request.user)
            print(meta_config,'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk')
            print(request.user,'qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq')
            print(request.data,"+++++++++++++++++++++",type(request.data))
            serializer = MetaConfigurationSerializer(meta_config, data=request.data)
        except MetaConfiguration.DoesNotExist:
            serializer = MetaConfigurationSerializer(data=request.data)
        # except Exception as e:
        #     print(e)

        if serializer.is_valid():
            instance = serializer.save(user=request.user)

            response_data = {
                "meta_info": serializer.data.get("meta_info"),
                "id": instance.id,
                "user_id": instance.user.id,
            }

            return CustomResponse.success("Your data has been saved successfully", [response_data])

        return CustomResponse.error("Validation failed", data={"meta_info": [serializer.errors]})

# class FileUploadAPIView(APIView):
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser]

#     @swagger_auto_schema(
#     manual_parameters=[
#         openapi.Parameter(
#             name="files",
#             in_=openapi.IN_FORM,
#             description="Upload one or more image/video files",
#             type=openapi.TYPE_ARRAY,
#             items=openapi.Items(type=openapi.TYPE_FILE),
#             required=True,
#             collection_format="multi",
#         ),
#     ],
#     request_body=FileUploadSerializer,
#     responses={200: "Success"},
#     tags=["v1/accounts"]
# )
#     def post(self, request, *args, **kwargs):
#         user = request.user
#         user_email = request.user.email

#         form_data = request.data
#         meta_info_str = form_data.get("meta_info")
#         files = request.FILES.getlist("files")

#         try:
#             meta_info = json.loads(meta_info_str)
#         except json.JSONDecodeError:
#             return CustomResponse.error("Invalid JSON in meta_info")

#         params = OrderedDict({
#             "creator_name": meta_info.get("creator_name"),
#             "creator_address": meta_info.get("creator_address"),
#             "creator_city": meta_info.get("creator_city"),
#             "creator_state": meta_info.get("creator_state"),
#             "creator_country": meta_info.get("creator_country"),
#             "creator_postal_code": meta_info.get("creator_postal_code"),
#             "creator_email": meta_info.get("creator_email"),
#             "creator_phone": meta_info.get("creator_phone"),
#             "creator_web_url": meta_info.get("creator_web_url"),
#             "creators_jobtitle": meta_info.get("creators_jobtitle"),
#             "credit_line": meta_info.get("credit_line"),
#             "date_created": meta_info.get("date_created"),
#             "copyright_notice": meta_info.get("copyright_notice"),
#             "rights_usage_terms": meta_info.get("rights_usage_terms"),
#             "description": meta_info.get("description"),
#             "description_writer": meta_info.get("description_writer"),
#             "headline": meta_info.get("headline"),
#             "instructions": meta_info.get("instructions"),
#             "keywords": meta_info.get("keywords"),
#             "title": meta_info.get("title"),
#             "ai_training": meta_info.get("ai_training"),
#             "ai_generative_training": meta_info.get("ai_generative_training"),
#             "data_mining": meta_info.get("data_mining"),
#             "ai_inference": meta_info.get("ai_inference"),
#             "ai_training_constraint_info": meta_info.get("ai_training_constraint_info"),
#             "ai_generative_training_constraint_info": meta_info.get("ai_generative_training_constraint_info"),
#             "data_mining_constraint_info": meta_info.get("data_mining_constraint_info"),
#             "ai_inference_constraint_info": meta_info.get("ai_inference_constraint_info"),
#             "user_email": user_email,
#         })

#         serializer = FileUploadSerializer(data={'meta_info': params}, context={'files':files})
#         if not serializer.is_valid():
#             return CustomResponse.error("Validation failed", data=serializer.errors)

#         uploaded_files = []

#         for file in files:
#             try:

#                 logger.info(f"Processing file: {file}")
#                 download_link, image_name = asyncio.run(process_file(file, **params))

#                 temp_file_path = os.path.join(tempfile.gettempdir(), image_name)

#                 local_file_path = os.path.abspath(download_link)

#                 with open(local_file_path, "rb") as src_file:
#                     with open(temp_file_path, "wb") as dest_file:
#                         dest_file.write(src_file.read())

#                 is_video = image_name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'))

#                 if is_video:
#                     s3_url = s3_helper.upload_video(temp_file_path, user_email, file)
#                     params["video_path"] = s3_url
#                     params.pop("image_path", None)
#                     existing_entry = Usercontent.objects.filter(user=user, video_url__icontains=file.name).first()
#                     if existing_entry:
#                         existing_entry.video_url = s3_url
#                         existing_entry.save()
#                     else:
#                         Usercontent.objects.create(user=user, video_url=s3_url)
#                 else:
#                     s3_url = s3_helper.upload_image(temp_file_path, user_email, file)
#                     params["image_path"] = s3_url
#                     params.pop("video_path", None)

#                     existing_entry = Usercontent.objects.filter(user=user, image_url__icontains=file.name).first()
#                     if existing_entry:
#                         existing_entry.image_url = s3_url
#                         existing_entry.save()
#                     else:
#                         Usercontent.objects.create(user=user, image_url=s3_url)

#                 # Create or update ImageStatus
#                 ImageStatus.objects.update_or_create(
#                     user=user,
#                     image_name=file.name,
#                     defaults={
#                         "image_status": "succeeded",
#                         "upload_date": timezone.now(),
#                         "media_url": s3_url,
#                         "meta_data": params,
#                     }
#                 )

#                 uploaded_files.append({
#                     "filename": file.name,
#                     "path": s3_url,
#                     "type": "video" if is_video else "image"
#                 })
#             except Exception as e:
#                 logger.exception(f"Error processing file {file.name}: {e}")
#                 continue


#             if os.path.exists(download_link):
#                 os.remove(download_link)
#             if os.path.exists(f"processed_files/{image_name}"):
#                 os.remove(f"processed_files/{image_name}")

#         return CustomResponse.success("Your files are being processed. You can check their status in the Media Status section.", data=[{
#             "files": uploaded_files,
#             "params": params,
#         }])
    
# class UserGalleryAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(
#         operation_description=(
#             "Retrieve the authenticated user's uploaded images/videos and generate S3 download URLs for them."
#         ),
#         responses={
#             200: "User contents fetched successfully.",
#             500: "Failed to fetch user contents."
#         },
#         tags=["v1/accounts"]
#     )

#     def get(self, request, *args, **kwargs):
#         try:
#             user = request.user
#             user_contents = Usercontent.objects.filter(user=user)
#             s3_uploader = S3Uploader()
#             content_data = []

#             for content in user_contents:
#                 file_url = content.image_url or content.video_url
#                 if not file_url:
#                     continue

#                 parsed_url = urlparse(file_url)
#                 s3_key = unquote(parsed_url.path.lstrip('/'))
#                 original_filename = os.path.basename(s3_key)

#                 download_url = s3_uploader.generate_download_url(s3_key, original_filename)

#                 content_data.append({
#                     "content_url": file_url,
#                     "download_url": download_url
#                 })
#             return CustomResponse.success(
#                 message="User contents fetched successfully.",
#                 data=[{
#                     "user": {
#                         "id": user.id,
#                         "email": user.email
#                     },
#                     "user_contents": content_data,
#                 }]
#             )

#         except Exception as e:
#             return CustomResponse.error(
#                 message="Failed to fetch user contents.",
#                 data=[{
#                     "user_contents": [],
#                 }],
#             )
        

# class DeleteImageAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(request_body=DeleteImageSerializer, tags=["v1/accounts"])
#     def post(self, request):
#         serializer = DeleteImageSerializer(data=request.data)
#         if serializer.is_valid():
#             user = request.user
#             deleted = []
#             not_found = []

#             file_urls = []

#             # Handle both cases
#             file_urls = serializer.validated_data["file_urls"]

#             for file_url in file_urls:
#                 content = Usercontent.objects.filter(
#                     user=user
#                 ).filter(
#                     Q(image_url=file_url) | Q(video_url=file_url)
#                 ).first()

#                 if content:
#                     content.delete()
#                     deleted.append(file_url)
#                 else:
#                     not_found.append(file_url)

#             return CustomResponse.success(
#             message="Deletion complete.",
#             data={
#                 "deleted": deleted,
#                 "not_found": not_found
#             }
#         )

#         return CustomResponse.error(
#             message="Failed to delete user contents.",
#             data=[{
#                 "deleted": [],
#                 "not_found": [],
#                 "errors": serializer.errors
#             }]
#         )
    
# class ImageStatusAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(
#         manual_parameters=[
#                     openapi.Parameter('from_date', openapi.IN_QUERY, description="Start date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
#                     openapi.Parameter('to_date', openapi.IN_QUERY, description="End date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
#                 ],
#         operation_description="Media records found",
#         tags=["v1/accounts"],
#     )
#     def get(self, request):
#             user = request.user
#             from_date_str = request.query_params.get("from_date")
#             to_date_str = request.query_params.get("to_date")

#             image_status_qs = ImageStatus.objects.filter(user=user)

#             if from_date_str:
#                 try:
#                     from_date = make_aware(datetime.strptime(from_date_str, "%Y-%m-%d"))
#                     image_status_qs = image_status_qs.filter(created_at__gte=from_date)
#                 except ValueError:
#                     return CustomResponse.error("Invalid from_date format. Use YYYY-MM-DD.")

#             if to_date_str:
#                 try:
#                     to_date = make_aware(datetime.strptime(to_date_str, "%Y-%m-%d"))
#                     to_date = to_date.replace(hour=23, minute=59, second=59)
#                     image_status_qs = image_status_qs.filter(created_at__lte=to_date)
#                 except ValueError:
#                     return CustomResponse.error("Invalid to_date format. Use YYYY-MM-DD.")

#             if not image_status_qs.exists():
#                 return CustomResponse.success("No media available on selected dates", data=[])

#             serializer = ImageStatusSerializer(image_status_qs, many=True)
#             return CustomResponse.success("Image status fetched successfully", data=serializer.data)
    
# class VersionCreateAPIView(generics.GenericAPIView):
#     permission_classes = [AllowAny]
#     serializer_class = VersionCreateSerializer

#     @swagger_auto_schema(
#         # request_body=VersionCreateSerializer,
#         operation_description="Check for app version updates",
#         responses={200: "Version created successfully.", 400: "Bad request."},
#         tags=["v1/accounts"],
#     )
#     def post(self, request, *args, **kwargs):
#         try:
#             serializer = self.get_serializer(data=request.data)
#             serializer.is_valid(raise_exception=True)
#             data = serializer.validated_data
        
#             AppVersion.objects.create(
#                 device_type=data["device_type"],
#                 version_name=data["current_version"],
#                 force_update=data["force_update"],
#                 remember_token="",
#                 created_at=timezone.now()
#             )
#             return CustomResponse.success(message="Version created successfully", data=[serializer.data])
        
#         except serializers.ValidationError as e:
#             errors = e.detail
#             if isinstance(errors, dict):
#                 first_key = next(iter(errors))
#                 message = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
#             elif isinstance(errors, list):
#                 message = errors[0]
#             else:
#                 message = str(errors)

#             return CustomResponse.error(
#                 message=message,
#                 status_code=status.HTTP_400_BAD_REQUEST 
#             )

#         except Exception as e:
#             logger.error(f"Unexpected error in VersionCreateAPIView: {e}")
#             return CustomResponse.error(
#                 message="Server error",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )

# class VersionController(generics.GenericAPIView):
#     serializer_class = VersionSerializer
 
#     @swagger_auto_schema(
#         operation_description="Check for app version updates",
#         responses={
#             200: "Version information retrieved successfully.",
#             400: "Bad request.",
#         },
#         tags=["v1/accounts"],
#     )
#     def post(self, request):
#         try:
#             serializer = self.get_serializer(data=request.data)
#             serializer.is_valid(raise_exception=True)
 
#             device_type = serializer.validated_data["device_type"]
#             current_version = serializer.validated_data["current_version"]
 
#             latest_versions = AppVersion.objects.filter(
#                 device_type=device_type
#             ).order_by("-created_at")  
 
#             if latest_versions.exists():
#                 latest_version = latest_versions.first()
#                 # Convert version strings to integer arrays for lexicographical comparison
#                 current_version_array = [int(i) for i in current_version.split(".")]
#                 db_version_array = [
#                     int(i) for i in latest_version.version_name.split(".")
#                 ]
 
#                 if db_version_array > current_version_array:
#                     data = {
#                         "device_type": device_type,
#                         "version_name": latest_version.version_name,
#                         "force_update": latest_version.force_update,
#                         "is_new_version_available": True,
#                     }
#                     return CustomResponse.success(
#                         data=data,
#                         message="Version information retrieved successfully",
#                     )
#                 else:
#                     data = {
#                         "device_type": device_type,
#                         "version_name": current_version,
#                         "force_update": False,
#                         "is_new_version_available": False,
#                     }
#                     return CustomResponse.success(
#                         data=data,
#                         message="Version information retrieved successfully",
#                     )
#             else:
#                 return CustomResponse.error(message="No data available")
#         except serializers.ValidationError as e:
#             errors = e.detail
#             if isinstance(errors, dict):
#                 first_key = next(iter(errors))
#                 message = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
#             elif isinstance(errors, list):
#                 message = errors[0]
#             else:
#                 message = str(errors)

#             return CustomResponse.error(
#                 message=message,
#                 status_code=status.HTTP_400_BAD_REQUEST 
#             )
#         except Exception as e:
#             return CustomResponse.error(
#                 message="Server error",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )
        

# class VersionList(generics.GenericAPIView):
    
#     serializer_class = VersionListSerializer
#     permission_classes = [AllowAny] 

#     @swagger_auto_schema(
#         operation_description="Retrieve a list of all AppVersion instances",
#         responses={200: "Version data retrieved successfully."},
#         tags=["v1/accounts"],
#     )
#     def get(self, request, *args, **kwargs):
#         queryset = AppVersion.objects.all()  
#         serializer = self.get_serializer(queryset, many=True)  
#         return CustomResponse.success(data=serializer.data, message="Version data retrieved successfully.")
    
# class ReloadImageView(APIView):
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(request_body=ImageReloadSerializer, tags=["v1/accounts"])
#     def post(self, request):
#         try:
#             image_id = request.data.get("image_id")
#             user = request.user  # Get the authenticated user
#             user_email = user.email

#             image_record = ImageStatus.objects.filter(id=image_id).first()
#             video_url = None
#             image_url = None

#             if not image_record:
#                 return Response({"error": "No image record found for the given ID"}, status=status.HTTP_404_NOT_FOUND)

#             img_url = image_record.media_url
#             img_meta = image_record.meta_data or {}
#             img_meta["record_id"] = image_record.id

#             response = requests.get(img_url, stream=True)
#             image_io = io.BytesIO(response.content)
#             image_io.seek(0)

#             filename = os.path.basename(img_url)
#             content_type = response.headers.get("Content-Type", "image/jpeg")

#             file_storage = InMemoryUploadedFile(
#                 file=image_io,
#                 field_name="file",
#                 name=filename,
#                 content_type=content_type,
#                 size=len(response.content),
#                 charset=None
#             )

#             download_link, image_name = asyncio.run(process_file(file_storage, **img_meta))

#             video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
#             if any(download_link.lower().endswith(ext) for ext in video_extensions):
#                 video_url = s3_helper.upload_video(local_video_path=download_link, user_email=user_email, original_filename=filename)
#             else:
#                 image_url = s3_helper.upload_image(local_image_path=download_link, user_email=user_email, original_filename=filename)

#             # Update image record
#             image_record.image_name = filename
#             image_record.image_status = "succeeded"
#             image_record.media_url = video_url if video_url else image_url
#             image_record.save()

#             # Add user content
#             Usercontent.objects.create(
#                 user=user,
#                 video_url=video_url if video_url else None,
#                 image_url=image_url if image_url else None
#             )

#             # Cleanup
#             if os.path.exists(download_link):
#                 os.remove(download_link)
#             processed_path = f"processed_files/{image_name}"
#             if os.path.exists(processed_path):
#                 os.remove(processed_path)

#             logger.info(f"Download link: {download_link}")
#             return Response({"success": "Your file has been reloaded"}, status=status.HTTP_200_OK)

#         except Exception as e:
#             logger.exception("Image reload failed")
#             return Response({"error": "Reload Unsuccessful! Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)