from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Webhook Receiver đang hoạt động và chờ dữ liệu từ ChirpStack!", 200 

@app.route('/webhook', methods=['POST'])
def chirpstack_webhook():
    Authorization_header = request.headers.get('Authorization')
    print(Authorization_header)
    
    if Authorization_header != "nhatdeptrai": 
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    # ChirpStack v4 tự động gắn thêm tham số event vào URL (vd: ?event=up)
    event_type = request.args.get('event', 'unknown')
    
    if event_type == 'up':
        data = request.json
        
        # Trích xuất metadata và dữ liệu giải mã
        dev_eui = data.get('deviceInfo', {}).get('devEui')
        f_port = data.get('fPort')
        decoded_object = data.get('object', {}) # Dữ liệu đã qua Codec
        
        # Xử lý riêng cho sự kiện của WS101
        if 'button_event' in decoded_object:
            status = decoded_object['button_event'].get('status')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] CẢNH BÁO: Nút nhấn {dev_eui} vừa kích hoạt trạng thái: {status.upper()}")
            
        elif 'battery' in decoded_object:
            battery = decoded_object.get('battery')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] HEARTBEAT: Thiết bị {dev_eui} - Pin: {battery}%")

        # Lưu toàn bộ luồng dữ liệu vào file log
        with open('sensor_log.jsonl', 'a') as f:
            log_entry = {
                "timestamp": data.get('time'),
                "devEui": dev_eui,
                "port": f_port,
                "data": decoded_object
            }
            f.write(json.dumps(log_entry) + '\n')
            
    return jsonify({"status": "success", "message": "Payload received"}), 200

if __name__ == '__main__':
    # Lắng nghe trên tất cả các interface mạng tại cổng 5000
    app.run(host='0.0.0.0', port=5000)