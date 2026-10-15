import paho.mqtt.client as mqtt
import time


BROKER = "127.0.0.1"
PORT = 1883
TOPIC = "test"

def on_connect(client, userdata, flag, reason_code, properties=None):
    if reason_code == 0:
        print("Successfully subscribed to topic:", TOPIC)
        client.subscribe(TOPIC)
    else:
        print("Failed to subscribe to topic:", TOPIC, "Reason code:", reason_code)
        
def on_message(client, userdata, msg):
    print(f"[nhan] Topic: {msg.topic} | Payload: {msg.payload.decode('utf-8')}")
    
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="python_iot_client")
client.on_connect = on_connect
client.on_message = on_message

# --- Phương thức 1: Basic Authentication (Built-in Database) ---
client.username_pw_set(username="user1", password="12345678")


# --- Phương thức 2: JWT Authentication ---
#JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InVzZXJuYW1lIiwiaWF0IjoxNzE4MDAwMDAwLCJleHAiOjE4OTM0NTYwMDB9.GXKFD4-DeEwXn_Nya2XlkZyc9u0wkiM8PkULxPMCeuM"
#client.username_pw_set(username="username", password=JWT_TOKEN)

# --- Phương thức 3: TLS phải mở cùng phương thức 1 và đổi cổng 1883 sang 8883
cacert = "C:\\Users\\anhnhat\\Desktop\\DOCKER_TEST\\cacert.pem"
cert = "C:\\Users\\anhnhat\\Desktop\\DOCKER_TEST\\cert.pem"
key = "C:\\Users\\anhnhat\\Desktop\\DOCKER_TEST\\key.pem"
client.tls_set(ca_certs=cacert, certfile=cert, keyfile=key)
client.tls_insecure_set(True)

# --- Phương thức 4: SCRAM Authentication (Yêu cầu MQTT 5.0) ---
# Lưu ý: Thư viện paho-mqtt hỗ trợ giao thức MQTT 5.0, nhưng không tích hợp sẵn bộ 
# băm mật khẩu (hasher) cho SCRAM-SHA-256. Để dùng SCRAM, bạn phải tự viết hàm băm 
# và xử lý gói tin AUTH qua hàm callback `on_auth`. Trong thực tế, các backend Python 
# thường dùng Phương thức 1 hoặc 2 kết hợp với TLS (cổng 8883) để tối ưu hiệu suất.
#
# Cấu hình nền tảng nếu muốn tự phát triển SCRAM:
# client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
# from paho.mqtt.properties import Properties
# from paho.mqtt.packettypes import PacketTypes
# conn_props = Properties(PacketTypes.CONNECT)
# conn_props.AuthMethod = "SCRAM-SHA-256"
# client.connect(BROKER, PORT, keepalive=60, clean_start=True, properties=conn_props)

client.connect(BROKER, 8883, keepalive=60)
#client.connect(BROKER, PORT, keepalive=60)

# Khởi chạy vòng lặp mạng ở chế độ chạy nền (background)
client.loop_start()

try:
    # Vòng lặp chính: Gửi tin nhắn mỗi 5 giây
    count = 1
    while True:
        payload = f"{{\"msg\": \"Tin nhắn thứ {count} từ Python\"}}"
        client.publish(TOPIC, payload, qos=1)
        print(f"[Gửi] {payload}")
        count += 1
        time.sleep(5)
        
except KeyboardInterrupt:
    print("\nĐang ngắt kết nối...")
    client.loop_stop()
    client.disconnect()