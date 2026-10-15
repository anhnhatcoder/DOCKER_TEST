import grpc
from chirpstack_api import api

server = "localhost:8080"
api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjRmMWQxZjkzLWUxYmMtNDY1NC04MjQ0LTM5MzBlNjRhNzVkZiIsInR5cCI6ImtleSJ9.bxTSiQL6Tc5qENdT7wjNNTA23KHVF34h-toX53J0fLk"
application_id = "ae3454be-2350-4031-ad5d-8a9029642a19"

if __name__ == "__main__":
    channel = grpc.insecure_channel(server)
    client = api.DeviceServiceStub(channel)
    auth_token = [("authorization", f"Bearer {api_token}")]
    
    req = api.GetDeviceRequest()
    req.dev_eui = "24e124535d186881"

    try:
        resp = client.GetActivation(req, metadata=auth_token)
        print("=== THÔNG TIN THIẾT BỊ ===")
        print(f"{resp}")
    except grpc.RpcError as e:
        print(f"Lỗi gRPC: {e.details()}")