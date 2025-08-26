# apps/accounts/urls.py

from django.urls import path, re_path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    re_path(
        r"^superuser-login/$",
        views.SuperuserLoginAPIView.as_view(),
        name="superuser-login",
    ),
    re_path(
        r"^create-business-account/$",
        views.CreateBusinessAccountAPIView.as_view(),
        name="create-business-account",
    ),
    re_path(
        r"^superuser-forget-password/$",
        views.ForgotPasswordView.as_view(),
        name="superuser-login",
    ),
    re_path(
        r"^reset-password/(?P<token>[0-9a-f\-]{36})/$",
        views.ResetPasswordView.as_view(),
        name="resetpassword",
    ),
    re_path(
        r"^organization-lister/",
        views.OrganizationListAPIView.as_view(),
        name="list-organization",
    ),
    re_path(
        r"^organization-detail/(?P<id>[0-9a-f-]{36})/$",
        views.OrganizationDetailAPIView.as_view(),
    ),
    re_path(
        r"^organization-delete/(?P<uid>[0-9a-f-]{36})/$",
        views.OrganizationDeleteAPIView.as_view(),
        name="organization-delete",
    ),
    re_path(
        r"^organization-deactivate/(?P<uid>[0-9a-f-]{36})/$",
        views.OrganizationDeactivateAPIView.as_view(),
        name="organization-deactivate",
    ),
    re_path(
        r"^dashboards_counts",
        views.DashboardCountsAPIView.as_view(),
        name="organization-dashboard",
    ),
    re_path(
        r"^logout",
        views.logOutAPIView.as_view(),
        name="logout",
    ),
    re_path(
        r"^exportcsv/?$",
        views.ExportCSVAPIView.as_view(),
        name="exportcsv",
    ),
    re_path(
        r"^organization-usage-report",
        views.OrganizationReportsAPIView.as_view(),
        name="organization-reports",
    ),
    re_path(
        r"^organization-usage-metrics",
        views.OrganizationStatsAPIView.as_view(),
        name="organization-metrics",
    )
    
]    
