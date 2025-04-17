import hmac
import hashlib
import json
import requests
import uuid
import os 

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "TEST_SECRET")

url = "http://backend:8000/webhook"
customer_id = "acme" 
webhook_secret = WEBHOOK_SECRET

payload = {
    "order_id": 123,
    "status": "created",
    "customer_name": "Alice",
    "amount": 49.99
}

raw_body = json.dumps(payload).encode("utf-8")

signature = hmac.new(
    key=webhook_secret.encode(),
    msg=raw_body,
    digestmod=hashlib.sha256
).hexdigest()

delivery_id = f"test-{uuid.uuid4()}"

headers = {
    "Content-Type": "application/json",
    "X-Delivery-Id": delivery_id,  
    "X-Signature": signature
}

params = {"customer_id": customer_id}

response = requests.post(url, headers=headers, params=params, data=raw_body)

print("Status:", response.status_code)
try:
    print("Response:", response.json())
except Exception as e:
    print("Raw Response Text:", response.text)

