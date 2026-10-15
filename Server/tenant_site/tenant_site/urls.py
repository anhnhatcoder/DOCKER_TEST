from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('Server_tenant.urls')),  # Trỏ trang chủ vào Dashboard
]
