import asyncio
import aiohttp
import json
import hmac
import hashlib
import uuid

URL = "http://backend:8000/webhook"
SECRET = "326487fb39a7bdfa85836046c9df5c42b8eafb192af16621df080f1b6f940b20"
CUSTOMER_ID = "acme"
TOTAL_REQUESTS = 150
CONCURRENT_REQUESTS = 50

def generate_headers(payload: dict):
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Delivery-Id": str(uuid.uuid4()),
        "X-Signature": sig
    }

async def send_webhook(session, i):
    payload = {
        "order_id": i,
        "status": "created",
        "customer_name": f"User-{i}",
        "amount": round(10 + i * 0.5, 2)
    }
    headers = generate_headers(payload)
    params = {"customer_id": CUSTOMER_ID}
    async with session.post(URL, json=payload, headers=headers, params=params) as resp:
        if resp.status == 200:
            print(f"✅ {i}")
        else:
            print(f"❌ {i} - {resp.status}")

async def main():
    connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [send_webhook(session, i) for i in range(TOTAL_REQUESTS)]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
