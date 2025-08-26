from django.urls import re_path

from apps.account import views

app_name = "account"

urlpatterns = [
    re_path('login/', views.LoginView.as_view(), name='login'),
    re_path('configuration_details/', views.ConfigurationView.as_view(), name='configuration_details'),
#     re_path("logout/", views.CustomLogoutView.as_view(), name="logout"),
#     re_path("upload/", views.FileUploadAPIView.as_view(), name="file-upload"),
#     re_path('user_gallery/', views.UserGalleryAPIView.as_view(), name='user-gallery'),
#     re_path('delete_image/', views.DeleteImageAPIView.as_view(), name='delete_image'),
#     re_path("image_status/", views.ImageStatusAPIView.as_view(), name="image_status"),
#     # re_path('version_create/', views.VersionCreateAPIView.as_view(), name='VersionCreate'),
#     # re_path('version-list/', views.VersionList.as_view(), name='VersionList'),
#     # re_path('version/',views.VersionController.as_view(),name='get_app_version'),
#     re_path('reload/', views.ReloadImageView.as_view(), name='img_reload'),
]