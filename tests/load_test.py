import requests, time, sys
import asyncio
import aiohttp
import json
import hmac
import hashlib
import uuid
import statistics
import random

URL = "http://backend:8000/webhook"
SECRET = "326487fb39a7bdfa85836046c9df5c42b8eafb192af16621df080f1b6f940b20"
CUSTOMER_IDS = [f"acme_{i}" for i in range(4)]
TOTAL_REQUESTS = 150
CONCURRENT_REQUESTS = 10

durations = []
status_counts = {"success": 0, "other": 0}
failures = []


def make_payload(i):
    return {
        "order_id": i,
        "status": "created",
        "customer_name": f"User-{i}",
        "amount": round(10 + i * 0.5, 2),
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
        for _ in range(5):
            try:
                r = await session.get("http://backend:8000/")
                if r.status == 200:
                    break
            except:
                await asyncio.sleep(1)
        await asyncio.gather(
            *[send_webhook(session, i) for i in range(1, TOTAL_REQUESTS + 1)]
        )

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


if __name__ == "__main__":
    asyncio.run(main())

    deadline = time.time() + 10
    while time.time() < deadline:
        total_seen = sum(
            len(
                requests.get(
                    "http://backend:8000/webhooks", params={"customer_id": c}
                ).json()["webhooks"]
            )
            for c in CUSTOMER_IDS
        )
        if total_seen == TOTAL_REQUESTS:
            break
        time.sleep(0.5)
    else:
        print("❌ workers didn’t finish in time")
        sys.exit(1)

    # check each customer shard
    total_seen = 0
    total_processed = 0
    for cust in CUSTOMER_IDS:
        r = requests.get("http://backend:8000/webhooks", params={"customer_id": cust})
        r.raise_for_status()
        events = r.json()["webhooks"]
        total_seen += len(events)
        total_processed += sum(1 for e in events if e["status"] == "processed")

    print(f"➡️  delivery_ids rows seen:      {total_seen}/{TOTAL_REQUESTS}")
    print(f"➡️  processed events marked:    {total_processed}/{TOTAL_REQUESTS}")

    if total_seen != TOTAL_REQUESTS or total_processed != TOTAL_REQUESTS:
        print("❌ Some events never made it through the worker:")
        for cust in CUSTOMER_IDS:
            evs = requests.get(
                "http://backend:8000/webhooks", params={"customer_id": cust}
            ).json()["webhooks"]
            bad = [e for e in evs if e["status"] != "processed"]
            if bad:
                print(f"  • {cust} failed: {bad}")
        sys.exit(1)
    else:
        print("🎉 All events were queued and processed successfully!")
