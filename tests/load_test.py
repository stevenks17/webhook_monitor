import asyncio
import aiohttp
import random
import time

URL = "http://localhost:8000/webhook"
TOTAL_REQUESTS = 1000
CONCURRENT_REQUESTS = 100

async def send_webhook(session, order_id):
  payload = {"order_id": order_id, "status": random.choice(["created", "pending", "failed"])}
  try:
      async with session.post(URL, json=payload) as response:
         if response.status == 200:
            print(f"Sent: {order_id}")
         else: 
            print(f"Failed: {order_id} - Status: {response.status}")
  except  Exception as e:
      print(f"Exception sending order {order_id}: {e}")
  
async def run_load_test():
   connector = aiohttp.TCPConnector(limit= CONCURRENT_REQUESTS)
   async with aiohttp.ClientSession(connector=connector) as session:
      tasks = []
      for order_id in range(TOTAL_REQUESTS):
         tasks.append(send_webhook(session, order_id))
      await asyncio.gather(*tasks)

if __name__ == "__main__":
   start = time.time()
   asyncio.run(run_load_test())
   end = time.time()
   print(f"Sent {TOTAL_REQUESTS} requests in {end- start:.2f} seconds")