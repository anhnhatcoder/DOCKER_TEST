import grpc
from chirpstack_api import api
from google.protobuf.json_format import MessageToJson

server = "localhost:8080"
api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjRmMWQxZjkzLWUxYmMtNDY1NC04MjQ0LTM5MzBlNjRhNzVkZiIsInR5cCI6ImtleSJ9.bxTSiQL6Tc5qENdT7wjNNTA23KHVF34h-toX53J0fLk"
# ID của Application bạn muốn lấy danh sách thiết bị
application_id = "ae3454be-2350-4031-ad5d-8a9029642a19" 

if __name__ == "__main__":
    channel = grpc.insecure_channel(server)
    client = api.DeviceServiceStub(channel)
    auth_token = [("authorization", f"Bearer {api_token}")]

    # Khởi tạo Request ListDevices
    req = api.ListDevicesRequest()
    req.application_id = application_id
    req.limit = 10  # Lấy tối đa 10 thiết bị (tùy chỉnh số lượng)
    

    
    try:
        # Gọi hàm List
        resp = client.List(req, metadata=auth_token)
        raw_json = MessageToJson(resp, preserving_proto_field_name=True)

        print("=== DANH SÁCH THIẾT BỊ TRONG APPLICATION ===")
        print(raw_json)

    except grpc.RpcError as e:
        print(f"Lỗi gRPC API: {e.details()}")