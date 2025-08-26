from django.shortcuts import render
from rest_framework import generics, permissions, serializers, status, views
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from apps.organization import serializers as organization_serializer
from apps.organization import models as account_models
from drf_yasg import openapi
from datetime import datetime
from apps.organization.tasks import image_processing, video_processing 
from collections import OrderedDict
import base64
from apps.organization.helpers.s3_helpers import S3Uploader
import json
from django.db import connection
import os
from urllib.parse import urlparse, unquote
from apps.organization.responses import CustomResponse
import logging
from longtailedleopardsaasproduct.permissions import (
    IscreatororManager,
    IsOrganizationadmin
)
from utils.swagger_schema import TenantOnlySchema
from apps.accounts import models as account_model
from rest_framework.permissions import AllowAny

s3_helper = S3Uploader()

logger = logging.getLogger(__name__)

class ConfigurationDetailsView(generics.GenericAPIView):
    permission_classes = [IscreatororManager]
    serializer_class = organization_serializer.MetaInfoSerializer

    @swagger_auto_schema(
            auto_schema=TenantOnlySchema,
            tags=["Organization"]
    )

    def get(self, request):
        user = request.user
        existing_meta = account_models.MetaConfiguration.objects.filter(user_id=user.id).first()
        
        if existing_meta and existing_meta.meta_info:
            meta_info = existing_meta.meta_info

            # Add user_id to dict if it's a dict
            if isinstance(meta_info, dict):
                meta_info["user_id"] = user.id
                meta_info = json.dumps(meta_info)  # convert to JSON string

            return CustomResponse.success(
                message="Meta info fetched successfully.",
                data=[meta_info]
            )
        else:
            return CustomResponse.success(
                message="No meta info available.",
                data=[]
            )
        
    @swagger_auto_schema(
            auto_schema=TenantOnlySchema,
            tags=["Organization"]
    )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)

            validated_data = serializer.validated_data
            user = request.user

            meta_config, created = account_models.MetaConfiguration.objects.get_or_create(
                user_id=user.id,
                defaults={"meta_info": json.dumps(validated_data)}
            )
            if not created:
                meta_config.meta_info = json.dumps(validated_data)
                meta_config.save()

            meta_list = [dict(validated_data, user_id=user.id)]

            return CustomResponse.success(
                message="Your data has been saved successfully.",
                data=meta_list
            )
        except serializers.ValidationError as e:
            logger.error(f"Validation error: {e}")

            error_detail = e.detail
            if isinstance(error_detail, dict):
                errors = []
                for field, messages in error_detail.items():
                    if isinstance(messages, list):
                        errors.append(f"{field}: {' '.join(messages)}")
                    else:
                        errors.append(f"{field}: {messages}")
                message = "; ".join(errors)
            else:
                message = str(error_detail)

            return CustomResponse.error(
                message=message,
                status_code=status.HTTP_400_BAD_REQUEST
            )


# Create your views here.
class FileUploadAPIView(generics.GenericAPIView):
    permission_classes = [IscreatororManager]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = organization_serializer.FileUploadSerializer

    @swagger_auto_schema(
    auto_schema=TenantOnlySchema,
    manual_parameters=[
        openapi.Parameter(
            name="files",
            in_=openapi.IN_FORM,
            description="Upload one or more image/video files",
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(type=openapi.TYPE_FILE),
            required=True,
            collection_format="multi",
        ),
    ],
    responses={200: "Success"},
    tags=["Organization"]
)
    def post(self, request, *args, **kwargs):
        user = request.user
        user_email = request.user.email
        user_id = request.user.id

        meta_info_str = request.data.get("meta_info")
        files = request.FILES.getlist("files")

        try:
            meta_info = json.loads(meta_info_str)
        except json.JSONDecodeError:
            return CustomResponse.error(message = "Invalid JSON in meta_info")

        # Construct parameter dict
        params = OrderedDict({
            "creator_name": meta_info.get("creator_name"),
            "creator_address": meta_info.get("creator_address"),
            "creator_city": meta_info.get("creator_city"),
            "creator_state": meta_info.get("creator_state"),
            "creator_country": meta_info.get("creator_country"),
            "creator_postal_code": meta_info.get("creator_postal_code"),
            "creator_email": meta_info.get("creator_email"),
            "creator_phone": meta_info.get("creator_phone"),
            "creator_web_url": meta_info.get("creator_web_url"),
            "creators_jobtitle": meta_info.get("creators_jobtitle"),
            "credit_line": meta_info.get("credit_line"),
            "date_created": meta_info.get("date_created"),
            "copyright_notice": meta_info.get("copyright_notice"),
            "rights_usage_terms": meta_info.get("rights_usage_terms"),
            "description": meta_info.get("description"),
            "description_writer": meta_info.get("description_writer"),
            "headline": meta_info.get("headline"),
            "instructions": meta_info.get("instructions"),
            "keywords": meta_info.get("keywords"),
            "title": meta_info.get("title"),
            "ai_training": meta_info.get("ai_training"),
            "ai_generative_training": meta_info.get("ai_generative_training"),
            "data_mining": meta_info.get("data_mining"),
            "ai_inference": meta_info.get("ai_inference"),
            # "user_email": user_email,
        })

        serializer = self.get_serializer(data={'meta_info': params}, context={'files': files})
        if not serializer.is_valid():
            error_detail = serializer.errors

            def extract_first_error_message(errors):
                if isinstance(errors, dict):
                    first_value = next(iter(errors.values()))
                    return extract_first_error_message(first_value)
                elif isinstance(errors, list):
                    return extract_first_error_message(errors[0])
                else:
                    return str(errors)

            message = extract_first_error_message(error_detail)
            return CustomResponse.error(message=message, status_code=status.HTTP_400_BAD_REQUEST)

        uploaded_files = []

        for file in files:
            file_content = file.read()
            file_base64 = base64.b64encode(file_content).decode("utf-8")

            is_video = file.name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'))

            try:
                if is_video:
                    params["video_path"] = f"https://video-verify-metadata-processed-files.s3.us-west-2.amazonaws.com/{user_email}/{file.name}"
                    params.pop('image_path', None)
                    task = video_processing(self, user_id, user_email, file.name, file_base64, params)
                    file_type = "video"
                else:
                    params["image_path"] = f"https://video-verify-metadata-processed-files.s3.us-west-2.amazonaws.com/{user_email}/{file.name}"
                    params.pop('video_path', None)
                    task = image_processing(self, user_id, user_email, file.name, file_base64, params)
                    file_type = "image"

                # account_models.ImageStatus.objects.update_or_create(
                #     user_id=user.id,
                #     image_name=file.name,
                #     defaults={
                #         'image_status': 'in_progress',
                #         'upload_date': datetime.utcnow(),
                #         'thumbnail_url':None,
                #         'image_url': None,
                #         'meta_data': None,
                #     }
                # )

                uploaded_files.append({
                    "filename": file.name,
                    "task_id": 1,
                    "type": file_type,
                })
            except Exception as e:
                logger.exception(f"Failed to enqueue task for file {file.name}: {e}")
                continue

        return CustomResponse.success(
            message="Your files are being processed. You can check their status in the Media Status section.",
            data=[{
                "files": uploaded_files,
                "params": params,
            }]
        )
    
class AddOrganizationUserAPIView(generics.CreateAPIView):
    serializer_class = organization_serializer.AddOrganizationUserSerializer
    permission_classes = [IsOrganizationadmin]

    @swagger_auto_schema(
        auto_schema=TenantOnlySchema,
        operation_summary="Invite a new organization user",
        operation_description=(
            "Allows an organization admin to invite (create) a new user within their own tenant schema. "
            "The new user will be linked to the same company as the requesting admin."
            "When a organization admin adds a manager, assign the role as 3 for Creator and 4 for Manager in the organization user assignment."
        ),
        responses={
            201: "User invited successfully",
            400: "Validation Error or Permission Denied.",
        },
        tags=["Organization"],
    )
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(
                data=request.data, context={"request": request}
            )
            domain = account_model.Domain.objects.filter(tenant=request.user.company).first()
            if serializer.is_valid():
                org_user = serializer.save()
                return CustomResponse.success(
                    message="Organization user created successfully.",
                    data={
                        "user": org_user.email,
                        "schema": org_user.company.schema_name,
                        "domain": f"http://{domain.domain}:8000/swagger/" if domain else None,
                    },
                )
            # Handle standard serializer errors
            error_message = next(iter(serializer.errors.values()))[0]
            return CustomResponse.error(message=error_message)

        except serializers.ValidationError as e:  # Handle validation errors
            # Handle explicitly raised validation errors
            error_messages = []

            if isinstance(e.detail, list):
                error_messages.extend(e.detail)
            elif isinstance(e.detail, dict):
                for field, messages in e.detail.items():
                    if isinstance(messages, list):
                        error_messages.extend(messages)
                    else:
                        error_messages.append(str(messages))
            else:
                error_messages.append(str(e.detail))

            return CustomResponse.error(
                message=error_messages[0] if error_messages else "Validation error."
            )
        
class OrguserLoginAPIView(generics.CreateAPIView):
    serializer_class = organization_serializer.OrguserLoginSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        auto_schema=TenantOnlySchema,
        operation_description=(
            "Login endpoint for superadmin using email and password. Returns JWT token and user details on success."
        ),
        responses={
            200: "Login successful.",
            400: "Validation errors or incorrect login credentials.",
        },
        tags=["Organization"],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            if serializer.is_valid():
                user_data = serializer.validated_data
                return CustomResponse.success(
                    message="Logged in successfully.",
                    data=user_data,
                )

            error_message = next(
                iter(serializer.errors.values())
            )[
                0
            ]  # The iter method is used in this case to efficiently retrieve the first value from the serializer.errors dictionary
            return CustomResponse.error(message=error_message)
        except serializers.ValidationError as e:  # Handle validation errors
            error_messages = []
            for field, messages in e.detail.items():
                if isinstance(messages, list):
                    error_messages.extend(messages)
                else:
                    error_messages.append(messages)
            return CustomResponse.error(
                message=error_messages[0] if error_messages else "Validation error."
            )
class UserGalleryAPIView(generics.GenericAPIView):
    permission_classes = [IscreatororManager]

    @swagger_auto_schema(
        auto_schema=TenantOnlySchema,
        operation_description="Retrieve the authenticated user's uploaded images/videos and generate S3 download URLs for them.",
        responses={
            200: "User contents fetched successfully.",
            500: "Failed to fetch user contents."
        },
        tags=["Organization"]
    )
    def get(self, request, *args, **kwargs):
        try:
            user = request.user
            user_contents = account_models.Usercontent.objects.filter(user_id=user.id)
            s3_uploader = S3Uploader()
            content_data = []

            for content in user_contents:
                file_url = content.image_url or content.video_url
                if not file_url:
                    continue

                parsed_url = urlparse(file_url)
                s3_key = unquote(parsed_url.path.lstrip('/'))
                original_filename = os.path.basename(s3_key)
                media_type = "image" if content.image_url else "video"
                download_url = s3_uploader.generate_download_url(s3_key, original_filename)
                thumbnail_url = content.thumbnail_url

                content_data.append({
                    "media_id": content.id,
                    "content_url": file_url,
                    "download_url": download_url,
                    "type": media_type,
                    "thumb_nail": thumbnail_url
                })


            return CustomResponse.success(
                message="User contents fetched successfully.",
                data=[{
                    "user": {
                        "id": user.id,
                        "email": user.email
                    },
                    "user_contents": content_data,
                }]
            )

        except Exception as e:
            print(f"Error in UserGalleryAPIView: {e}")
            return CustomResponse.error(
                message="Failed to fetch user contents.",
                data=[{
                    "user_contents": [],
                }],
            )


class ImageHubAPIView(views.APIView):
    permission_classes = [IscreatororManager]

    @swagger_auto_schema(
        auto_schema=TenantOnlySchema,
        manual_parameters=[
            openapi.Parameter(
                'search', openapi.IN_QUERY,
                description="Search by email, file URL, or filename",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'sort', openapi.IN_QUERY,
                description="Sort order: 'name_asc' or 'name_desc'",
                type=openapi.TYPE_STRING,
                enum=['name_asc', 'name_desc'],
                default='name_asc'
            ),
        ],
        tags=["Organization"]
    )
    
    def get(self, request):
        try:
            user = request.user
            search_query = request.GET.get("search", "").strip().lower()
            sort_order = request.GET.get("sort", "name_asc")

            content_obj = account_models.Usercontent.objects.select_related("user").all()
            s3_uploader = S3Uploader()
            content_data = {}

            for content in content_obj:
                user_email = content.user.email
                file_url = content.image_url or content.video_url
                if not file_url:
                    continue

                parsed_url = urlparse(file_url)
                s3_key = unquote(parsed_url.path.lstrip('/'))
                filename = os.path.basename(s3_key)

                if search_query:
                    if (
                        search_query not in user_email.lower()
                    ):
                        continue

                download_url = s3_uploader.generate_download_url(s3_key, filename)

                media_type = "image" if content.image_url else "video"

                thumbnail_url = content.thumbnail_url

                if user_email not in content_data:
                    content_data[user_email] = {
                        "email": user_email,
                        "name": content.user.name,
                        "imageurl": []
                    }

                content_data[user_email]["imageurl"].append({
                    "media_id": content.id,
                    "original_url": file_url,
                    "filename": filename,
                    "download_url": download_url,
                    "media_type": media_type,
                    "thumbnail_url": thumbnail_url
                })

            # Sort by user email
            user_contents_list = sorted(
                content_data.values(),
                key=lambda x: x["email"].lower(),
                reverse=(sort_order == "name_desc")
            )

            return CustomResponse.success(
                message="User contents fetched successfully.",
                data={"user": {
                        "id": user.id,
                        "email": user.email
                    },
                    "user_contents": user_contents_list}
            )

        except Exception as e:
            print("Exception occurred:", str(e))
            return CustomResponse.error(
                message="Failed to fetch user contents.",
                data={"user_contents": []}
            )