import grpc
from chirpstack_api import api
from google.protobuf.json_format import MessageToJson

server = "localhost:8080"
api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjRmMWQxZjkzLWUxYmMtNDY1NC04MjQ0LTM5MzBlNjRhNzVkZiIsInR5cCI6ImtleSJ9.bxTSiQL6Tc5qENdT7wjNNTA23KHVF34h-toX53J0fLk"  
dev_eui = "24e124535d186881"       

if __name__ == "__main__":
    channel = grpc.insecure_channel(server)
    client = api.DeviceServiceStub(channel)
    auth_token = [("authorization", f"Bearer {api_token}")]

    req = api.GetDeviceRequest()
    req.dev_eui = dev_eui

    try:
        
        resp = client.GetQueue(req, metadata=auth_token)

        
        raw_json = MessageToJson(resp, preserving_proto_field_name=True)

        print("=== RAW JSON RESPONSE FROM CHIRPSTACK ===")
        print(raw_json)

    except grpc.RpcError as e:
        print(f"Lỗi gRPC API: {e.details()}")