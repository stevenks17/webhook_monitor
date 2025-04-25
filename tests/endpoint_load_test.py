import requests, time, sys
import asyncio
import aiohttp
import json
import hmac
import hashlib
import uuid
import statistics
import random
import secrets

URL = "http://backend:8000/webhook"
SECRET = "326487fb39a7bdfa85836046c9df5c42b8eafb192af16621df080f1b6f940b20"
CUSTOMER_IDS = [f"acme_{i}" for i in range(4)]
TOTAL_REQUESTS = 150
CONCURRENT_REQUESTS = 4

durations = []
status_counts = {"success": 0, "other": 0}
failures = []


def make_payload(i):
    return {
        "order_id": i,
        "status": "created",
        "customer_name": f"User-{i}",
        "amount": round(10 + i * 0.5, 2),
        "nonce": secrets.token_urlsafe(16),
    }


def generate_headers(raw_body: bytes):
    sig = hmac.new(SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Delivery-Id": str(uuid.uuid4()),
        "X-Signature": sig,
    }


async def send_webhook(session, i):
    payload = make_payload(i)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    headers = generate_headers(raw)
    customer = random.choice(CUSTOMER_IDS)
    params = {"customer_id": customer}

    start = time.monotonic()
    try:
        resp = await session.post(URL, data=raw, headers=headers, params=params)
        if 200 <= resp.status < 300:
            status_counts["success"] += 1
        else:
            status_counts["other"] += 1
            body = await resp.text()
            failures.append({"index": i, "status": resp.status, "body": body})
    except aiohttp.ClientError as e:
        status_counts["other"] += 1
        failures.append({"index": i, "error": str(e)})
    except asyncio.TimeoutError:
        status_counts["other"] += 1
        failures.append({"index": i, "error": "Timeout"})
    except Exception as e:
        status_counts["other"] += 1
        failures.append({"index": i, "error": str(e)})
    finally:
        durations.append(time.monotonic() - start)


async def main():
    connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        interval = 1 / 4
        for i in range(1, TOTAL_REQUESTS + 1):
            tasks.append(asyncio.create_task(send_webhook(session, i)))
            await asyncio.sleep(interval)
        await asyncio.gather(*tasks)

        if failures:
            print("\n––– FAILURE DETAILS –––")
            for f in failures:
                print(f)
            print("––––––––––––––––––––––\n")

    durations.sort()
    print(f"\nResults: {status_counts['success']} OK, {status_counts['other']} failed")
    print(f"Min    : {durations[0]:.3f}s")
    print(f"p50    : {statistics.median(durations):.3f}s")
    print(f"p95    : {durations[int(0.95*len(durations))]:.3f}s")
    print(f"p99    : {durations[int(0.99*len(durations))]:.3f}s")
    print(f"Max    : {durations[-1]:.3f}s")
    print(f"Avg    : {statistics.mean(durations):.3f}s")
