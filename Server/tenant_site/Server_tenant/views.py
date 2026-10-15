import csv
import json
import math
import queue
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, StreamingHttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import User, Device, AlertLog, LocationHistory, Area
from .sse import register_subscriber, unregister_subscriber, broadcast_event


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def ensure_default_accounts():
    # Chỉ tạo tài khoản mặc định khi hệ thống chưa có bất kỳ user nào
    if not User.objects.exists():
        u_admin = User.objects.create_user(
            username='admin',
            password='123',
            first_name='Nguyễn Bảo Nguyên',
            email='admin@hctech.com.vn',
            role=User.Role.TENANT_ADMIN,
            phone_number='0905111222'
        )
        u_admin.is_staff = True
        u_admin.is_superuser = True
        u_admin.save()

        User.objects.create_user(
            username='viewer',
            password='123',
            first_name='Vận Hành Viên',
            email='viewer@hctech.com.vn',
            role=User.Role.VIEWER,
            phone_number='0905333444'
        )


def login_view(request):
    ensure_default_accounts()
    error_msg = None
    if request.method == 'POST':
        uname = request.POST.get('username', '').strip()
        pwd = request.POST.get('password', '').strip()
        user = authenticate(request, username=uname, password=pwd)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            error_msg = "Tài khoản hoặc mật khẩu không chính xác!"
    return render(request, 'login.html', {'error_msg': error_msg})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='/login/')
def dashboard_view(request):
    ensure_default_accounts()
    devices = list(Device.objects.filter(is_active=True).order_by('-id'))
    users_list = list(User.objects.all().order_by('id'))
    alerts = list(AlertLog.objects.select_related('device', 'acknowledged_by', 'resolved_by')[:50])

    for d in devices:
        d.gps_code = 'GPS' if d.has_gps else 'STATIC'
        d.loc_display = f"{d.latitude}, {d.longitude}" if d.has_gps else (d.address or '-')
        if d.device_type == 'CAMERA':
            d.type_label, d.type_bg = 'Camera', 'bg-emerald-600'
        elif d.device_type == 'GATEWAY':
            d.type_label, d.type_bg = 'Gateway', 'bg-purple-600'
        else:
            d.type_label, d.type_bg = 'Nút nhấn', 'bg-cyan-600'

        if d.category_type == 'CHAY':
            d.cat_label, d.cat_cls = 'Báo Cháy', 'border-red-500 text-red-500'
        elif d.category_type == 'AN_NINH':
            d.cat_label, d.cat_cls = 'An Ninh', 'border-amber-500 text-amber-500'
        else:
            d.cat_label, d.cat_cls = 'Cấp Cứu/Y tế', 'border-emerald-500 text-emerald-500'

    for log in alerts:
        log.loc_display = f"Tọa độ biển: {log.latitude}, {log.longitude}" if log.device.has_gps else (log.address or '-')
        log.notes_display = log.notes if log.notes else '-'
        log.report_display = log.resolution_report if log.resolution_report else '-'
        log.is_open = (log.status != 'RESOLVED')

    for u in users_list:
        u.display_name = u.first_name if u.first_name else u.username
        u.phone_display = u.phone_number if u.phone_number else '-'
        u.can_delete = (u.id != request.user.id)

    all_devs = Device.objects.filter(is_active=True)
    cam_qs = all_devs.filter(device_type='CAMERA')
    btn_qs = all_devs.filter(device_type='NUT_NHAN')
    gw_qs = all_devs.filter(device_type='GATEWAY')

    chay_count = AlertLog.objects.filter(alert_type='CHAY').count()
    yte_count = AlertLog.objects.filter(alert_type__in=['CAP_CUU_Y_TE', 'CUU_HO_BIEN']).count()
    anninh_count = AlertLog.objects.filter(alert_type='AN_NINH').count()

    alert_new = AlertLog.objects.filter(status='NEW').count()
    alert_proc = AlertLog.objects.filter(status='PROCESSING').count()
    alert_res = AlertLog.objects.filter(status='RESOLVED').count()
    alert_false = AlertLog.objects.filter(status='FALSE_ALARM').count()
    total_alerts = max(alert_new + alert_proc + alert_res + alert_false, 1)

    online_count = all_devs.filter(connection_status='ONLINE').count()
    sos_count = all_devs.filter(connection_status__in=['SOS', 'PROCESSING']).count()
    offline_count = all_devs.filter(connection_status='OFFLINE').count()
    maint_count = all_devs.filter(connection_status='MAINTENANCE').count()

    is_admin = request.user.role in ['SYSTEM_ADMIN', 'TENANT_ADMIN'] or request.user.is_superuser
    current_user_display = request.user.first_name if request.user.first_name else request.user.username

    context = {
        'devices': devices,
        'users_list': users_list,
        'alerts': alerts,
        'is_admin': is_admin,
        'role_badge_cls': 'bg-cyan-500/20 text-cyan-500' if is_admin else 'bg-amber-500/20 text-amber-500',
        'current_user_display': current_user_display,
        'current_username': request.user.username,
        'user_role_label': 'Tenant Admin' if is_admin else 'Viewer',
        'total_devices': all_devs.count(),
        'online_count': online_count,
        'sos_count': sos_count,
        'offline_count': offline_count,
        'maint_count': maint_count,
        'cam_total': cam_qs.count(),
        'cam_online': cam_qs.filter(connection_status='ONLINE').count(),
        'cam_offline': cam_qs.exclude(connection_status='ONLINE').count(),
        'btn_total': btn_qs.count(),
        'btn_online': btn_qs.filter(connection_status='ONLINE').count(),
        'btn_offline': btn_qs.exclude(connection_status='ONLINE').count(),
        'gw_total': gw_qs.count(),
        'gw_online': gw_qs.filter(connection_status='ONLINE').count(),
        'gw_offline': gw_qs.exclude(connection_status='ONLINE').count(),
        'chay_count': chay_count,
        'yte_count': yte_count,
        'anninh_count': anninh_count,
        'alert_new': alert_new,
        'alert_proc': alert_proc,
        'alert_res': alert_res,
        'alert_false': alert_false,
        'pct_new': int((alert_new / total_alerts) * 100),
        'pct_proc': int((alert_proc / total_alerts) * 100),
        'pct_res': int((alert_res / total_alerts) * 100),
        'pct_false': int((alert_false / total_alerts) * 100),
    }
    return render(request, 'dashboard.html', context)


def api_dashboard_state(request):
    gps_filter = request.GET.get('has_gps')
    status_filter = request.GET.get('status')

    devices_qs = Device.objects.filter(is_active=True)
    if gps_filter in ['true', 'false']:
        devices_qs = devices_qs.filter(has_gps=(gps_filter == 'true'))
    if status_filter:
        devices_qs = devices_qs.filter(connection_status=status_filter)

    devices_data = [{
        'id': d.id,
        'dev_eui': d.dev_eui,
        'device_name': d.device_name,
        'device_type': d.get_device_type_display(),
        'has_gps': d.has_gps,
        'customer_name': d.customer_name,
        'emergency_phone': d.emergency_phone,
        'address': d.address or 'Đang cập nhật GPS trên biển',
        'latitude': float(d.latitude) if d.latitude else 16.054407,
        'longitude': float(d.longitude) if d.longitude else 108.202167,
        'connection_status': d.connection_status,
        'battery_level': d.battery_level,
        'last_seen': d.last_seen.strftime('%d/%m/%Y %H:%M:%S') if d.last_seen else 'Chưa kết nối'
    } for d in devices_qs]

    emergency_alert = AlertLog.objects.filter(status='NEW').select_related('device').first()
    emergency_data = None
    if emergency_alert:
        emergency_data = {
            'alert_id': emergency_alert.id,
            'device_id': emergency_alert.device.id,
            'dev_eui': emergency_alert.device.dev_eui,
            'device_name': emergency_alert.device.device_name,
            'customer_name': emergency_alert.device.customer_name,
            'emergency_phone': emergency_alert.device.emergency_phone,
            'has_gps': emergency_alert.device.has_gps,
            'latitude': float(emergency_alert.latitude or emergency_alert.device.latitude or 16.054407),
            'longitude': float(emergency_alert.longitude or emergency_alert.device.longitude or 108.202167),
            'address': emergency_alert.address or emergency_alert.device.address,
            'created_at': emergency_alert.created_at.strftime('%H:%M:%S - %d/%m/%Y'),
            'alert_type': emergency_alert.get_alert_type_display(),
            'notes': emergency_alert.notes or '',
        }

    return JsonResponse({'devices': devices_data, 'emergency': emergency_data})


def api_stats_data(request):
    range_filter = request.GET.get('range', '12m')
    alert_type_filter = request.GET.get('alert_type', '')

    now = timezone.now()
    if range_filter == 'today':
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_filter == '7d':
        start_time = now - timedelta(days=7)
    elif range_filter == '30d':
        start_time = now - timedelta(days=30)
    elif range_filter == '3m':
        start_time = now - timedelta(days=90)
    else:
        start_time = now - timedelta(days=365)

    alerts_qs = AlertLog.objects.filter(created_at__gte=start_time)

    chay_count = alerts_qs.filter(alert_type='CHAY').count()
    yte_count = alerts_qs.filter(alert_type__in=['CAP_CUU_Y_TE', 'CUU_HO_BIEN']).count()
    anninh_count = alerts_qs.filter(alert_type='AN_NINH').count()

    status_qs = alerts_qs
    if alert_type_filter:
        if alert_type_filter == 'CAP_CUU_Y_TE':
            status_qs = status_qs.filter(alert_type__in=['CAP_CUU_Y_TE', 'CUU_HO_BIEN'])
        else:
            status_qs = status_qs.filter(alert_type=alert_type_filter)

    alert_new = status_qs.filter(status='NEW').count()
    alert_proc = status_qs.filter(status='PROCESSING').count()
    alert_res = status_qs.filter(status='RESOLVED').count()
    alert_false = status_qs.filter(status='FALSE_ALARM').count()
    total = max(alert_new + alert_proc + alert_res + alert_false, 1)

    return JsonResponse({
        'chay_count': chay_count,
        'yte_count': yte_count,
        'anninh_count': anninh_count,
        'alert_new': alert_new,
        'alert_proc': alert_proc,
        'alert_res': alert_res,
        'alert_false': alert_false,
        'pct_new': int((alert_new / total) * 100),
        'pct_proc': int((alert_proc / total) * 100),
        'pct_res': int((alert_res / total) * 100),
        'pct_false': int((alert_false / total) * 100),
    })


@csrf_exempt
def api_register_device(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    if request.user.is_authenticated and request.user.role == 'VIEWER' and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Tài khoản Viewer không có quyền thêm thiết bị!'}, status=403)

    try:
        data = json.loads(request.body)
        dev_eui = data.get('dev_eui', '').strip().upper()
        device_name = data.get('device_name', '').strip()
        device_type = data.get('device_type', 'NUT_NHAN')
        category_type = data.get('category_type', 'CAP_CUU_Y_TE')
        customer_name = data.get('customer_name', '').strip() or 'Demo LoRaWAN'
        emergency_phone = data.get('emergency_phone', '').strip() or '0905123456'
        has_gps = bool(data.get('has_gps', False))
        address = data.get('address', '').strip()

        if not dev_eui or not device_name:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập đầy đủ Tên thiết bị và Mã định danh ID/DevEUI!'}, status=400)

        if Device.objects.filter(dev_eui=dev_eui).exists():
            return JsonResponse({'status': 'error', 'message': f'Mã DevEUI "{dev_eui}" đã tồn tại!'}, status=400)

        try:
            lat = float(data.get('latitude')) if data.get('latitude') not in [None, '', 'NaN'] else 16.054407
            lng = float(data.get('longitude')) if data.get('longitude') not in [None, '', 'NaN'] else 108.202167
        except (ValueError, TypeError):
            lat, lng = 16.054407, 108.202167

        device = Device.objects.create(
            dev_eui=dev_eui,
            device_name=device_name,
            device_type=device_type,
            category_type=category_type,
            customer_name=customer_name,
            emergency_phone=emergency_phone,
            has_gps=has_gps,
            address=address if not has_gps else f'{lat}, {lng}',
            latitude=lat,
            longitude=lng,
            connection_status=Device.ConnectionStatus.ONLINE,
            last_seen=timezone.now()
        )

        if has_gps:
            LocationHistory.objects.create(device=device, latitude=lat, longitude=lng, speed=0.0, battery_level=100)

        return JsonResponse({'status': 'success', 'message': f'Đã đăng ký thiết bị: {device_name}', 'device_id': device.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def api_delete_devices(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    if request.user.is_authenticated and request.user.role == 'VIEWER' and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Viewer không có quyền xóa thiết bị!'}, status=403)

    data = json.loads(request.body)
    ids = data.get('ids', [])
    Device.objects.filter(id__in=ids).delete()
    return JsonResponse({'status': 'success', 'message': f'Đã xóa {len(ids)} thiết bị.'})


@csrf_exempt
def api_create_user(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    if request.user.is_authenticated and request.user.role == 'VIEWER' and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Viewer không có quyền tạo tài khoản!'}, status=403)

    data = json.loads(request.body)
    uname = data.get('username', '').strip()
    pwd = data.get('password', '').strip()
    if not uname or not pwd:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập đầy đủ Username và Mật khẩu!'}, status=400)
    if User.objects.filter(username=uname).exists():
        return JsonResponse({'status': 'error', 'message': f'Tài khoản "{uname}" đã tồn tại!'}, status=400)

    role = data.get('role', 'VIEWER')
    u = User.objects.create_user(
        username=uname,
        password=pwd,
        first_name=data.get('full_name', '').strip() or uname,
        role=role,
        phone_number=data.get('phone_number', '').strip()
    )
    if role == 'TENANT_ADMIN':
        u.is_staff = True
        u.save()
    return JsonResponse({'status': 'success', 'message': f'Đã tạo tài khoản {uname} thành công!'})


@csrf_exempt
def api_delete_user(request, user_id=None):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    if request.user.is_authenticated and getattr(request.user, 'role', '') == 'VIEWER' and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Viewer không có quyền xóa tài khoản!'}, status=403)

    try:
        if user_id is None:
            data = json.loads(request.body or '{}')
            user_id = data.get('user_id')

        target_user = User.objects.filter(id=user_id).first()
        if not target_user:
            return JsonResponse({'status': 'error', 'message': 'Không tìm thấy tài khoản cần xóa!'}, status=404)

        if target_user.id == request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Không thể tự xóa tài khoản đang đăng nhập!'}, status=400)

        deleted_name = target_user.username
        target_user.delete()
        return JsonResponse({'status': 'success', 'message': f'Đã xóa tài khoản "{deleted_name}" vĩnh viễn!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Lỗi khi xóa: {str(e)}'}, status=500)


@csrf_exempt
def webhook_iot_uplink(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    # Hỗ trợ cả cấu trúc từ ChirpStack v4 (deviceInfo, object) và JSON phẳng
    device_info = payload.get('deviceInfo', {})
    dev_eui = (device_info.get('devEui') or payload.get('dev_eui', '')).strip().upper()

    decoded = payload.get('object', {})
    button_event = decoded.get('button_event', {})
    button_status = button_event.get('status') if isinstance(button_event, dict) else None

    # Xác định bấm nút SOS (WS101 hoặc cờ is_sos)
    is_sos = bool(button_status) or payload.get('is_sos', False)

    lat = decoded.get('latitude', payload.get('latitude', 16.0825))
    lng = decoded.get('longitude', payload.get('longitude', 108.2615))
    battery = decoded.get('battery', payload.get('battery_level', 100))
    speed = decoded.get('speed', payload.get('speed', 0.0))

    if not dev_eui:
        return JsonResponse({'error': 'Missing dev_eui'}, status=400)

    device, _ = Device.objects.get_or_create(
        dev_eui=dev_eui,
        defaults={
            'device_name': device_info.get('deviceName', payload.get('device_name', f'Thiết bị {dev_eui[-4:]}')),
            'customer_name': payload.get('customer_name', 'Ngư dân Trần Văn Biển'),
            'emergency_phone': payload.get('emergency_phone', '0914888999'),
            'category_type': 'CAP_CUU_Y_TE',
            'has_gps': True if (lat and lng) else False,
            'latitude': lat,
            'longitude': lng,
        }
    )

    if lat and lng:
        device.latitude = lat
        device.longitude = lng
    device.battery_level = battery
    device.last_seen = timezone.now()

    created_alert = None
    if is_sos:
        uplink_notes = payload.get('notes', '').strip()
        custom_type = payload.get('alert_type')
        if custom_type and custom_type in AlertLog.AlertType.values:
            final_alert_type = custom_type
        else:
            final_alert_type = AlertLog.AlertType.CUU_HO_BIEN if device.has_gps else AlertLog.AlertType.CAP_CUU_Y_TE

        device.connection_status = Device.ConnectionStatus.SOS
        created_alert = AlertLog.objects.create(
            device=device,
            alert_type=final_alert_type,
            status=AlertLog.AlertStatus.NEW,
            latitude=device.latitude,
            longitude=device.longitude,
            address=device.address,
            notes=uplink_notes if uplink_notes else None,
            area=device.area
        )
    elif device.connection_status == Device.ConnectionStatus.OFFLINE:
        device.connection_status = Device.ConnectionStatus.ONLINE

    device.save()

    if device.has_gps and device.latitude and device.longitude:
        LocationHistory.objects.create(
            device=device, latitude=device.latitude, longitude=device.longitude,
            speed=speed, battery_level=battery, is_sos_point=is_sos
        )

    # ⚡ PHÁT TÍN HIỆU THỜI GIAN THỰC QUA SSE TỚI GIAO DIỆN (0ms DELAY)
    broadcast_event("IOT_UPLINK", {
        "device_id": device.id,
        "dev_eui": dev_eui,
        "device_name": device.device_name,
        "connection_status": device.connection_status,
        "is_sos": is_sos,
        "battery_level": battery,
        "latitude": float(device.latitude) if device.latitude else None,
        "longitude": float(device.longitude) if device.longitude else None,
        "alert_id": created_alert.id if created_alert else None,
        "alert_type": created_alert.get_alert_type_display() if created_alert else None,
        "notes": created_alert.notes if created_alert else ""
    })

    return JsonResponse({'status': 'ok', 'sos_triggered': is_sos})


@csrf_exempt
def api_dispatch_emergency(request):
    """
    Phát thông báo khẩn cấp thủ công từ giao diện điều hành.
    Cho phép chọn thiết bị tiếp nhận và tùy chọn ghi chú cảnh báo.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không được hỗ trợ'}, status=405)

    try:
        data = json.loads(request.body or '{}')
        device_id = data.get('device_id')
        alert_type = data.get('alert_type', 'CUU_HO_BIEN')
        notes = (data.get('notes') or '').strip()

        device = None
        if device_id:
            device = Device.objects.filter(id=device_id, is_active=True).first()

        if not device:
            dev_eui = (data.get('dev_eui') or '').strip().upper()
            if dev_eui:
                device = Device.objects.filter(dev_eui=dev_eui, is_active=True).first()

        if not device:
            return JsonResponse({'status': 'error', 'message': 'Không tìm thấy thiết bị để phát cảnh báo!'}, status=404)

        # Cập nhật trạng thái thiết bị sang SOS
        device.connection_status = Device.ConnectionStatus.SOS
        device.last_seen = timezone.now()
        device.save()

        # Tạo bản ghi AlertLog mới
        created_alert = AlertLog.objects.create(
            device=device,
            alert_type=alert_type if alert_type in AlertLog.AlertType.values else (
                AlertLog.AlertType.CUU_HO_BIEN if device.has_gps else AlertLog.AlertType.CAP_CUU_Y_TE
            ),
            status=AlertLog.AlertStatus.NEW,
            latitude=device.latitude,
            longitude=device.longitude,
            address=device.address,
            notes=notes if notes else None,
            area=device.area
        )

        # Ghi nhận điểm SOS vào lịch sử hành trình nếu có tọa độ GPS
        if device.has_gps and device.latitude and device.longitude:
            LocationHistory.objects.create(
                device=device,
                latitude=device.latitude,
                longitude=device.longitude,
                speed=0.0,
                battery_level=device.battery_level,
                is_sos_point=True
            )

        # ⚡ Phát tín hiệu thời gian thực SSE tới tất cả Dashboard đang mở
        broadcast_event("IOT_UPLINK", {
            "device_id": device.id,
            "dev_eui": device.dev_eui,
            "device_name": device.device_name,
            "connection_status": device.connection_status,
            "is_sos": True,
            "battery_level": device.battery_level,
            "latitude": float(device.latitude) if device.latitude else None,
            "longitude": float(device.longitude) if device.longitude else None,
            "alert_id": created_alert.id,
            "alert_type": created_alert.get_alert_type_display(),
            "notes": notes
        })

        return JsonResponse({
            'status': 'success',
            'message': f'Đã phát thông báo khẩn cấp cho {device.device_name}',
            'alert_id': created_alert.id,
            'device_id': device.id,
            'device_name': device.device_name,
            'latitude': float(device.latitude) if device.latitude else None,
            'longitude': float(device.longitude) if device.longitude else None
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Lỗi hệ thống: {str(e)}'}, status=500)


def sse_stream(request):
    """
    Endpoint Server-Sent Events (SSE) để truyền dữ liệu thời gian thực tới trình duyệt.
    """
    q = register_subscriber()

    def event_stream():
        try:
            # Gửi gói tin chào mừng khi client kết nối
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    msg = q.get(timeout=15)
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    # Gửi heartbeat keep-alive tránh browser ngắt kết nối
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            unregister_subscriber(q)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
def api_process_alert(request, alert_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    alert = get_object_or_404(AlertLog, id=alert_id)
    device = alert.device
    data = json.loads(request.body)
    action = data.get('action')

    if action == 'acknowledge':
        alert.status = AlertLog.AlertStatus.PROCESSING
        alert.acknowledged_at = timezone.now()
        if request.user.is_authenticated:
            alert.acknowledged_by = request.user
        device.connection_status = Device.ConnectionStatus.PROCESSING
        device.save()
        alert.save()
    elif action == 'update_notes':
        alert.notes = data.get('notes', '')
        alert.save()
    elif action == 'resolve':
        alert.status = AlertLog.AlertStatus.RESOLVED
        alert.resolved_at = timezone.now()
        alert.resolution_report = data.get('resolution_report') or 'Đã tiếp nhận & hoàn tất điều phối cứu hộ'
        if data.get('notes'):
            alert.notes = data.get('notes')
        if request.user.is_authenticated:
            alert.resolved_by = request.user
        device.connection_status = Device.ConnectionStatus.ONLINE
        device.save()
        alert.save()

        broadcast_event("IOT_UPLINK", {
            "dev_eui": device.dev_eui,
            "device_name": device.device_name,
            "connection_status": device.connection_status,
            "is_sos": False,
            "battery_level": device.battery_level,
            "latitude": float(device.latitude) if device.latitude else None,
            "longitude": float(device.longitude) if device.longitude else None,
            "alert_id": alert.id,
            "resolved": True
        })

    return JsonResponse({'status': 'success', 'alert_status': alert.status})


@csrf_exempt
def api_turn_off_device_alert(request, device_id):
    """
    Tắt cảnh báo khẩn cấp trực tiếp từ popup của thiết bị trên bản đồ.
    Đưa trạng thái thiết bị về ONLINE và đóng các AlertLog đang mở của thiết bị này.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không được hỗ trợ'}, status=405)

    device = get_object_or_404(Device, id=device_id)

    # Cập nhật thiết bị về ONLINE
    device.connection_status = Device.ConnectionStatus.ONLINE
    device.save()

    # Đóng các bản ghi AlertLog chưa hoàn tất của thiết bị
    now = timezone.now()
    active_alerts = AlertLog.objects.filter(device=device, status__in=['NEW', 'PROCESSING'])
    closed_count = 0
    for a in active_alerts:
        a.status = AlertLog.AlertStatus.RESOLVED
        a.resolved_at = now
        if not a.resolution_report:
            a.resolution_report = "Đã tắt cảnh báo trực tiếp từ bản đồ điều phối"
        if request.user.is_authenticated:
            a.resolved_by = request.user
        a.save()
        closed_count += 1

    # Phát tín hiệu SSE để toàn bộ giao diện cập nhật ngay lập tức (0ms delay)
    broadcast_event("IOT_UPLINK", {
        "dev_eui": device.dev_eui,
        "device_name": device.device_name,
        "connection_status": device.connection_status,
        "is_sos": False,
        "battery_level": device.battery_level,
        "latitude": float(device.latitude) if device.latitude else None,
        "longitude": float(device.longitude) if device.longitude else None,
        "resolved": True
    })

    return JsonResponse({
        'status': 'success',
        'message': f'Đã tắt cảnh báo cho {device.device_name}',
        'closed_alerts': closed_count
    })


def api_route_history(request, device_id):
    range_filter = request.GET.get('range', '24h')
    now = timezone.now()
    if range_filter == 'today':
        start_time = now.replace(hour=0, minute=0, second=0)
    elif range_filter == '7d':
        start_time = now - timedelta(days=7)
    elif range_filter == '30d':
        start_time = now - timedelta(days=30)
    else:
        start_time = now - timedelta(hours=24)

    points = list(LocationHistory.objects.filter(device_id=device_id, recorded_at__gte=start_time).order_by('recorded_at'))
    total_distance_km = 0.0
    history_data = []

    for i, pt in enumerate(points):
        if i > 0:
            prev = points[i - 1]
            total_distance_km += haversine_distance(prev.latitude, prev.longitude, pt.latitude, pt.longitude)
        history_data.append({
            'lat': float(pt.latitude),
            'lng': float(pt.longitude),
            'speed': pt.speed,
            'battery': pt.battery_level,
            'is_sos': pt.is_sos_point,
            'is_drifting': pt.is_drifting,
            'time': pt.recorded_at.strftime('%H:%M:%S %d/%m/%Y')
        })

    return JsonResponse({
        'points': history_data,
        'total_distance_km': round(total_distance_km, 2),
        'point_count': len(history_data)
    })


def export_alerts_csv(request):
    if request.user.is_authenticated and request.user.role == 'VIEWER' and not request.user.is_superuser:
        return HttpResponseForbidden("Chỉ Tenant Admin mới có quyền tải dữ liệu báo cáo.")

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="Bao_Cao_Su_Kien_Cuu_Ho.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Mã sự kiện', 'DevEUI', 'Tên thiết bị', 'Loại cứu hộ', 'Trạng thái',
        'Thời điểm SOS', 'Thời điểm tiếp nhận', 'Thời điểm hoàn tất',
        'Tọa độ / Địa chỉ', 'Ghi chú điều phối', 'Báo cáo kết quả'
    ])
    for log in AlertLog.objects.select_related('device').all():
        writer.writerow([
            f"SOS-{log.id}", log.device.dev_eui, log.device.device_name,
            "Cứu hộ Biển (GPS)" if log.device.has_gps else "Cứu hộ Đất liền",
            log.get_status_display(),
            log.created_at.strftime('%d/%m/%Y %H:%M:%S'),
            log.acknowledged_at.strftime('%d/%m/%Y %H:%M:%S') if log.acknowledged_at else '-',
            log.resolved_at.strftime('%d/%m/%Y %H:%M:%S') if log.resolved_at else '-',
            f"{log.latitude}, {log.longitude}" if log.device.has_gps else log.address,
            log.notes or '', log.resolution_report or ''
        ])
    return response