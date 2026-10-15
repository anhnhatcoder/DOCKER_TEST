from time import sleep

import requests
import json

api_urls = "https://jsonplaceholder.typicode.com/todos/1"
response = requests.get(api_urls)
response_json = response.json()
response_status = response.status_code
print(response.json())
print(response_status)