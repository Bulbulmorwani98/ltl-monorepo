from django.urls import re_path,path

from apps.organization import views

app_name = "organization"

urlpatterns = [
    re_path(r"^add-user/", views.AddOrganizationUserAPIView.as_view(), name="add-user"),
    re_path(
        r"^org-user-login/$", views.OrguserLoginAPIView.as_view(), name="org-user-login"
    ),
    re_path(r"^upload/", views.FileUploadAPIView.as_view(), name="file-upload"),
    re_path(r"^configuration_details/:", views.ConfigurationDetailsView.as_view(), name='configuration_details'),
    re_path(r"^user_gallery/", views.UserGalleryAPIView.as_view(), name='user-gallery'),
    path(r"image-hub/", views.ImageHubAPIView.as_view(), name="image-hub"),
]