from datetime import datetime, timedelta

import pandas as pd
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import connection, transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, generics, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.db import connection


from apps.accounts import models as account_model
from apps.accounts import pagination as account_pagination
from apps.accounts import serializers as account_serializer
from apps.accounts.forms import ResetPasswordForm
from apps.accounts.helper import CustomResponse
from apps.organization import models as organization_models
from longtailedleopardsaasproduct import settings
from longtailedleopardsaasproduct.permissions import (
    IsOrganizationadmin,
    IsSuperAdminHost,
    IsSuperuser,
)

# Create your views here.
from utils.swagger_schema import SuperadminOnlySchema, TenantOnlySchema
from django.utils.timezone import now


class SuperuserLoginAPIView(generics.CreateAPIView):
    serializer_class = account_serializer.SuperuserLoginSerializer
    permission_classes = [IsSuperAdminHost]

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description=(
            "Login endpoint for superadmin using email and password. Returns JWT token and user details on success."
        ),
        responses={
            200: "Login successful.",
            400: "Validation errors or incorrect login credentials.",
        },
        tags=["Superuser"],
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


class CreateBusinessAccountAPIView(generics.CreateAPIView):
    """
    This is a view for creating a business account. It handles the process of creating
    a name and a user associated with the company, and setting default data in the
    database. It also generates a unique schema name for the company and auth token for the user.
    """

    serializer_class = account_serializer.BusinessAccountSerializer
    permission_classes = (IsSuperuser,)

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_summary="Create a new tenant (organization)",
        operation_description="Only superuser can create a new organization. A schema and domain will be generated, and an admin user created.",
        responses={
            201: "Organization created successfully.",
            400: "Validation errors.",
        },
        tags=["Superuser"],
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        email = request.data.get("email")
        company_name = request.data.get("company_name", "").lower()
        password = request.data.get("password")
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return CustomResponse.error(message=str(e))

        # check schema name unique or not if not then again new schema name generate
        while account_model.Company.objects.filter(schema_name=company_name).exists():
            return CustomResponse.error(message="Company name already exit")

        company = account_model.Company(
            schema_name=company_name,
            name=company_name,
            paid_until="2099-12-31",
            on_trial=True,
            email=email,
        )
        company.save()
        account_model.Domain.objects.create(
            domain=f"{company_name}.localhost",  # Or use your local dev or production domain
            tenant=company,
            is_primary=True,
        )
        user = serializer.save(company=company, is_staff=True)
        domain = account_model.Domain.objects.filter(tenant=user.company).first()

        subject = "Welcome to Longtail Product"
        message = (
            f"Hi {user.first_name},\n\n"
            f"Thank you for choosing Longtail.\n\n"
            f"Here are your login credentials:\n"
            f"Username: {user.email}\n"
            f"Password: {password}\n"
            f"Website: http://{domain.domain}:8000/swagger/\n\n"
            f"Thank you,\n"
            f"Team Longtail"
        )
        # email_from = "inx.email001@gmail.com"
        # recipient_list = [user.email]
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [user.email]
        send_mail(subject, message, email_from, recipient_list)

        # set default data to database
        return CustomResponse.success(
            message="Account successfully created!",
            data=[
                {
                    "user": user.email,
                    "uid": user.company.uid,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "type_business": user.type_business,
                    "password": password,
                    "schema_name": user.company.schema_name,
                    "domain": f"http://{domain.domain}:8000/swagger/"
                    if domain
                    else None,
                }
            ],
        )

class ForgotPasswordView(generics.GenericAPIView):
    # permission_classes = (IsSuperuser,)
    serializer_class = account_serializer.ForgotPasswordSerializer

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="partial_update description override",
        responses={404: "slug not found", 200: "not found"},
        tags=["Superuser"],
    )
    def post(self, request, *args, **kwargs):
        try:
            # Validate the request data
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            email = serializer.validated_data["email"]

            try:
                user = account_model.User.objects.get(email=email)
                if not user.is_superuser:
                    return CustomResponse.error(
                        "Only superusers are allowed to reset ."
                    )
            except account_model.User.DoesNotExist:
                return Response(
                    {"detail": "Superuser with this email does not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Construct the password reset link

            # Generate token and save
            reset_entry = account_model.ForgotPasswordToken.objects.create(user=user)
            reset_link = f"{settings.USER_BASE_URL}reset-password/{reset_entry.token}/"

            # Send the reset password email
            subject = "Password Reset Request"
            message = f"Hi {user.first_name},\n\nPlease click the link below to reset your password:\n{reset_link}\n\nIf you did not request this, please ignore this email."
            email_from = settings.EMAIL_HOST_USER
            recipient_list = [user.email]
            send_mail(subject, message, email_from, recipient_list)

            return CustomResponse.success(
                message="Password reset link sent to your email.",
            )

        except serializers.ValidationError:
            return CustomResponse.error(
                message="Invalid email format",
            )

        except Exception as e:
            return CustomResponse.error(
                message=str(e),
            )


class ResetPasswordView(View):
    def get(self, request, token=None):
        form = ResetPasswordForm()
        return render(request, "reset_password.html", {"form": form, "token": token})

    def post(self, request, token=None):
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["password"]
            try:
                token_entry = account_model.ForgotPasswordToken.objects.get(token=token)

                user = token_entry.user  # <- This is key
                user.set_password(password)
                user.save()
                return HttpResponse("Password has been reset successfully.")
            except account_model.User.DoesNotExist:
                messages.error(request, "Invalid token or user does not exist.")

        return render(request, "reset_password.html", {"form": form, "token": token})


class OrganizationListAPIView(generics.ListAPIView):
    serializer_class = account_serializer.OrganizationList
    permission_classes = (IsSuperuser,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["schema_name", "email", "created_on"]
    pagination_class = account_pagination.CustomPageNumberPagination

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="List of organizations",
        manual_parameters=[
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filter by user status (true/false)",
                type=openapi.TYPE_BOOLEAN,
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Search by organization name or email",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                description="Page number",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                description="Number of items per page",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={
            200: "Retrieve the list of organizations.",
            400: "Empty Organization",
        },
        tags=["Superuser"],
    )
    def get(self, request, *args, **kwargs):
        status_filter = request.query_params.get("status")
        search_query = request.query_params.get("search", "").lower()

        organization = []
        companies = account_model.Company.objects.all()

        for company in companies:
            domain = account_model.Domain.objects.filter(tenant=company).first()
            user = account_model.User.objects.filter(
                company=company, is_superuser=False
            ).first()

            user_status = user.status if user else False
            if (
                status_filter is not None
                and str(user_status).lower() != status_filter.lower()
            ):
                continue

            if search_query:
                if not (
                    search_query in company.schema_name.lower()
                    or search_query in company.email.lower()
                    or search_query in str(company.created_on).lower()
                ):
                    continue

            organization.append(
                {
                    "id": company.uid,
                    "organization_name": company.schema_name,
                    "organization_email": company.email,
                    "created_at": company.created_on,
                    "sub_domain": domain.domain if domain else None,
                    "status": user.status if user else False,
                }
            )

        page = self.paginate_queryset(organization)
        if page is not None:
            if not page:
                return self.get_paginated_response([])

            return self.get_paginated_response(page)

        return CustomResponse.success(
            message="List of organizations", data=organization
        )


from django.db import connection
from django_tenants.utils import schema_context


class OrganizationDetailAPIView(generics.RetrieveAPIView):
    serializer_class = account_serializer.OrganizationList
    permission_classes = [IsSuperuser]

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Get organization details by ID.",
        manual_parameters=[
            openapi.Parameter(
                "id",
                openapi.IN_PATH,
                description="ID of the organization (Company UUID)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={
            200: "Organization details retrieved successfully.",
            404: "Organization not found.",
        },
        tags=["Superuser"],
    )
    def get(self, request, *args, **kwargs):
        company_id = kwargs.get("id")

        try:
            company = account_model.Company.objects.get(uid=company_id)
        except account_model.Company.DoesNotExist:
            return CustomResponse.error(
                message="Organization not found.", status_code=status.HTTP_404_NOT_FOUND
            )

        domain = account_model.Domain.objects.filter(tenant=company).first()
        user = account_model.User.objects.filter(
            company=company, is_superuser=False
        ).first()
        with schema_context(company.schema_name):
            total_org_users = organization_models.OrgUser.objects.count()

        response_data = {
            "organization_name": company.schema_name,
            "organization_email": company.email,
            "created_at": company.created_on,
            "sub_domain": domain.domain if domain else None,
            "status": user.status if user else False,
            "total_organization_user": total_org_users,
        }

        return CustomResponse.success(
            message="Organization detail retrieved successfully.", data=response_data
        )


from django_tenants.utils import schema_context, schema_exists


class OrganizationDeleteAPIView(generics.DestroyAPIView):
    permission_classes = [IsSuperuser]

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Delete an organization, related users, and tenant schema by UID.",
        manual_parameters=[
            openapi.Parameter(
                "uid",
                openapi.IN_PATH,
                description="UUID of the company to delete",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ],
        responses={
            200: "Organization deleted successfully.",
            404: "Organization not found.",
        },
        tags=["Superuser"],
    )
    def delete(self, request, *args, **kwargs):
        company_uid = kwargs.get("uid")

        try:
            # Get the company by UID
            company = account_model.Company.objects.get(uid=company_uid)
        except account_model.Company.DoesNotExist:
            return CustomResponse.error(
                message="Organization not found.", status_code=status.HTTP_404_NOT_FOUND
            )

        schema_name = company.schema_name

        try:
            # Step 1: Delete data from tenant schema if schema exists
            if schema_exists(schema_name):
                try:
                    with schema_context(schema_name):
                        if (
                            organization_models.OrgUser._meta.db_table
                            in connection.introspection.table_names()
                        ):
                            organization_models.OrgUser.objects.all().delete()
                except Exception as e:
                    print(
                        f"Warning: Could not delete OrgUser data from {schema_name}: {e}"
                    )

                # Step 2: Drop tenant schema completely
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;')

            # Step 3: Delete users, domain, and company from public schema
            account_model.User.objects.filter(company=company).delete()
            account_model.Domain.objects.filter(tenant=company).delete()
            # company.delete()
            return CustomResponse.success(
                message="Organization, users, and schema deleted successfully."
            )

        except Exception as e:
            return CustomResponse.error(
                message=f"Error deleting organization: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


from django.shortcuts import get_object_or_404


class OrganizationDeactivateAPIView(APIView):
    permission_classes = [IsSuperuser]

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Deactivate an organization by UID",
        manual_parameters=[
            openapi.Parameter(
                "uid",
                openapi.IN_PATH,
                description="UUID of the organization",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ],
        responses={
            200: "Organization deactivated successfully.",
            404: "Organization not found.",
        },
        tags=["Superuser"],
    )
    def patch(self, request, *args, **kwargs):
        company_uid = kwargs.get("uid")
        # Optional: Deactivate all users of this organization
        account_model.User.objects.filter(company=company_uid).update(status=False)
        return CustomResponse.success(message="Organization deactivated successfully.")


class DashboardCountsAPIView(generics.RetrieveAPIView):
    permission_classes = [IsSuperAdminHost]  # or your custom IsSuperuser

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Superadmin dashboard showing total organization and user counts.",
        responses={
            200: "Successfully retrieved organization and user counts.",
            400: "Error retrieving counts.",
        },
        tags=["Superuser"],
    )
    def get(self, request, *args, **kwargs):
        try:
            total_organizations = account_model.Company.objects.count()
            total_organization_users = 0
            total_image_uploads = 0

            # Loop through each organization's schema and count users
            for company in account_model.Company.objects.all():
                schema_name = company.schema_name
                try:
                    with schema_context(schema_name):
                        count = organization_models.OrgUser.objects.count()
                        counters = organization_models.Usercontent.objects.count()
                        total_organization_users += count
                        total_image_uploads += counters

                except Exception as e:
                    print(f"Skipping schema {schema_name} due to error: {e}")
                    continue

            return CustomResponse.success(
                message="Counts retrieved successfully",
                data={
                    "total_organizations": total_organizations,
                    "total_organization_users": total_organization_users,
                    "total_image_uploads": total_image_uploads,
                },
            )

        except Exception as e:
            return CustomResponse.error(message=f"Error retrieving counts: {str(e)}")


class logOutAPIView(APIView):
    permission_classes = [IsSuperAdminHost]

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Log out the user by blacklisting their refresh token.",
        responses={
            200: "User logged out successfully.",
            400: "Refresh token missing or invalid token.",
        },
        tags=["Superuser"],
    )
    def post(self, request, *args, **kwargs):
        try:
            # Get the Bearer token from the Authorization header
            auth_header = request.headers.get("Authorization")

            if not auth_header or not auth_header.startswith("Bearer"):
                return CustomResponse.error(
                    message="Access token missing in the Authorization header."
                )

            # Extract the access token
            access_token = auth_header.split("Bearer ")[1]

            # Blacklist the access token
            token = AccessToken(access_token)
            account_model.BlacklistedToken.objects.create(token=str(token))

            return CustomResponse.success(message="Logged out successfully.")

        except Exception:
            return CustomResponse.error(message="Invalid token or token expired.")


class ExportCSVAPIView(generics.GenericAPIView):
    serializer_class = account_serializer.AdminUserSerializer
    permission_classes = [IsSuperAdminHost]

    def get_queryset(self):
        return account_model.User.objects.filter(is_superuser=False)

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Export user data with organization details to Excel.",
        responses={200: "Excel file generated successfully."},
        tags=["Superuser"],
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        df = pd.DataFrame(serializer.data)

        # Optional column renaming for cleaner export
        df.rename(
            columns={
                "organization_name": "Organization Name",
                "active_vs_total_users": "Active Users / Total Users",
                "last_active": "Last Login",
                "usage": "Usage",
                "feature_list": "Feature List",
                "status": "Status",
            },
            inplace=True,
        )

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            'attachment; filename="organization_users.xlsx"'
        )

        df.to_excel(response, index=False)
        return response


class OrganizationReportsAPIView(generics.ListAPIView):
    serializer_class = account_serializer.AdminUserSerializer
    permission_classes = [IsSuperAdminHost]
    pagination_class = account_pagination.CustomPageNumberPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["company__name"]

    def get_queryset(self):
        queryset = account_model.User.objects.filter(is_superuser=False)

        status_param = self.request.query_params.get("status")
        if status_param is not None:
            if status_param.lower() == "true":
                queryset = queryset.filter(is_active=True)
            elif status_param.lower() == "false":
                queryset = queryset.filter(is_active=False)

        # Filter by time range
        range_param = self.request.query_params.get("range")
        if range_param == "30days":
            date_threshold = datetime.now() - timedelta(days=30)
            queryset = queryset.filter(last_login__gte=date_threshold)
        elif range_param == "6months":
            date_threshold = datetime.now() - timedelta(days=180)
            queryset = queryset.filter(last_login__gte=date_threshold)
        elif range_param == "1year":
            date_threshold = datetime.now() - timedelta(days=365)
            queryset = queryset.filter(last_login__gte=date_threshold)

        return queryset

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Get organization report list with filters and pagination.",
        manual_parameters=[
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filter by user status (true/false)",
                type=openapi.TYPE_BOOLEAN,
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Search by organization name",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "range",
                openapi.IN_QUERY,
                description="Filter by login range: 30days, 6months, 1year",
                type=openapi.TYPE_STRING,
                enum=["30days", "6months", "1year"],
            ),
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                description="Page number",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                description="Number of items per page",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={200: "List of organization users with filters", 400: "Bad Request"},
        tags=["Superuser"],
    )
    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return CustomResponse.success(
            message="Retrieved the list of organization reports", data=serializer.data
        )


class OrganizationStatsAPIView(APIView):
    permission_classes = [IsSuperAdminHost]

    @swagger_auto_schema(
        auto_schema=SuperadminOnlySchema,
        operation_description="Get Organization-usage-metrics.",
        responses={200: "List of organization-usage-metrics", 400: "Bad Request"},
        tags=["Superuser"],
    )
    def get(self, request):
        total_organizations = account_model.Company.objects.count()
        total_active_users = 0
        most_active_org = None
        most_logins = 0
        at_risk_orgs = []

        for company in account_model.Company.objects.all():
            schema = company.schema_name
            try:
                with schema_context(schema):
                    active_users = organization_models.OrgUser.objects.filter(
                        is_active=True
                    )
                    total_active_users += active_users.count()

                    recent_logins = organization_models.OrgUser.objects.filter(
                        last_loggedin__isnull=False
                    ).count()
                    if recent_logins > most_logins:
                        most_logins = recent_logins
                        most_active_org = company.name

                    # Check if no user has logged in in the last 30 days
                    threshold_date = now() - timedelta(days=30)
                    if not organization_models.OrgUser.objects.filter(
                        last_loggedin__gte=threshold_date
                    ).exists():
                        at_risk_orgs.append(company.name)

            except Exception as e:
                print(f"Skipping schema {schema} due to error: {e}")
                continue

        return CustomResponse.success(
            message="Organization statistics retrieved successfully",
            data={
                "total_organizations": total_organizations,
                "total_active_users": total_active_users,
                "most_active_organization": most_active_org,
                "at_risk_organizations": at_risk_orgs,
            },
        )
