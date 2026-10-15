from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),
    path('api/state/', views.api_dashboard_state, name='api_dashboard_state'),
    path('api/stats/', views.api_stats_data, name='api_stats_data'),
    path('api/devices/register/', views.api_register_device, name='api_register_device'),
    path('api/devices/delete/', views.api_delete_devices, name='api_delete_devices'),
    path('api/users/create/', views.api_create_user, name='api_create_user'),
    path('api/users/delete/', views.api_delete_user, name='api_delete_user'),
    path('api/users/<int:user_id>/delete/', views.api_delete_user, name='api_delete_user_by_id'),
    path('api/webhook/uplink/', views.webhook_iot_uplink, name='webhook_iot_uplink'),
    path('api/stream/events/', views.sse_stream, name='sse_stream'),
    path('api/alerts/<int:alert_id>/process/', views.api_process_alert, name='api_process_alert'),
    path('api/alerts/dispatch/', views.api_dispatch_emergency, name='api_dispatch_emergency'),
    path('api/devices/<int:device_id>/turn_off_alert/', views.api_turn_off_device_alert, name='api_turn_off_device_alert'),
    path('api/devices/<int:device_id>/route/', views.api_route_history, name='api_route_history'),
    path('export/alerts/csv/', views.export_alerts_csv, name='export_alerts_csv'),
]