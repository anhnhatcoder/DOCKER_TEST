import grpc
from chirpstack_api import api

server = "localhost:8080"
api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjRmMWQxZjkzLWUxYmMtNDY1NC04MjQ0LTM5MzBlNjRhNzVkZiIsInR5cCI6ImtleSJ9.bxTSiQL6Tc5qENdT7wjNNTA23KHVF34h-toX53J0fLk"  # Thay API Key của bạn vào đây

# UUID của Application trên ChirpStack
application_id = "ae3454be-2350-4031-ad5d-8a9029642a19" 

if __name__ == "__main__":
    # 1. Kết nối kênh gRPC
    channel = grpc.insecure_channel(server)

    # 2. Tạo client kết nối tới ApplicationService (chứa các hàm về Integration)
    client = api.ApplicationServiceStub(channel)

    # 3. Tạo metadata xác thực
    auth_token = [("authorization", f"Bearer {api_token}")]

    # 4. Khởi tạo Yêu cầu (Request) dựa theo tài liệu GetHttpIntegrationRequest
    req = api.GetHttpIntegrationRequest()
    req.application_id = application_id  # Gán UUID của Application

    try:
        # 5. Gọi hàm lấy cấu hình Webhook
        resp = client.GetHttpIntegration(req, metadata=auth_token)

        # 6. In kết quả phản hồi (GetHttpIntegrationResponse)
        print("--- CẤU HÌNH HTTP INTEGRATION HIỆN TẠI ---")
        print(f"Payload Encoding: {resp.integration.encoding}")
        print(f"Endpoint URL: {resp.integration.event_endpoint_url}")
        print("Headers đính kèm:")
        for header_key, header_val in resp.integration.headers.items():
            print(f"  - {header_key}: {header_val}")

    except grpc.RpcError as e:
        print(f"Lỗi gRPC: {e.details()}")