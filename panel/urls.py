from .views_checkbox import checkbox_search_view
from .views_panel import rdb_gateway
from django.urls import path


urlpatterns = [
    path("search/text", rdb_gateway, name="search_text"),
    path("search/sql",  rdb_gateway, name="search_sql"),
    path("panels/search", checkbox_search_view, name="direct_panel"),
]
