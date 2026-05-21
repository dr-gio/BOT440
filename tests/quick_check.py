import requests
import time

BASE = "https://bot-440.vercel.app"
results = []

def check(condition, name):
    if condition:
        print(f"✅ {name}")
        results.append(True)
    else:
        print(f"❌ {name}")
        results.append(False)

print("\n⚡ QUICK CHECK BOT440\n")

r = requests.get(f"{BASE}/webhook", timeout=5)
check(r.status_code == 200, "GET /webhook → 200")

r = requests.get(f"{BASE}/webhook-cx", timeout=5)
check(r.status_code == 200, "GET /webhook-cx → 200")

r = requests.get(f"{BASE}/webhook-ig", timeout=5)
check(r.status_code == 200, "GET /webhook-ig → 200")

r = requests.get(f"{BASE}/webhook-ig-cx", timeout=5)
check(r.status_code == 200, "GET /webhook-ig-cx → 200")

r = requests.get(f"{BASE}/webhook-ig-cx-simple", timeout=5)
check(r.status_code == 200, "GET /webhook-ig-cx-simple → 200")

r = requests.get(f"{BASE}/webhook-ig-simple", timeout=5)
check(r.status_code == 200, "GET /webhook-ig-simple → 200")

payload = {"messages": [{"from_me": False,
    "from": "573999999999",
    "text": {"body": "test", "type": "text"},
    "chat_id": "573999999999@s.whatsapp.net",
    "id": "quickcheck_001",
    "timestamp": int(time.time()),
    "from_name": "Quick Check"}]}

r = requests.post(f"{BASE}/webhook",
    json=payload, timeout=15)
check(r.status_code == 200, "POST /webhook → 200")

r = requests.post(f"{BASE}/webhook-cx",
    json=payload, timeout=15)
check(r.status_code == 200, "POST /webhook-cx → 200")

passed = sum(results)
total = len(results)
print(f"\n⚡ QUICK: {passed}/{total}")
if passed == total:
    print("✅ OK — safe to deploy")
else:
    print("❌ FALLA — revisar antes de deployar")

exit(0 if passed == total else 1)
