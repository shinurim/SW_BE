from django.urls import path, include

urlpatterns = [
    path("api/v1/", include("panel.urls")),   
    path("api/v1/insight/", include("insight.urls")),
    path("api/v1/", include("apis.urls")), 
]
