import requests
import json
import time

BASE = "https://bot-440.vercel.app"

def send_msg(endpoint, sender, text, name="Test"):
    payload = {"messages": [{"from_me": False,
        "from": sender, "text": {"body": text},
        "chat_id": f"{sender}@s.whatsapp.net",
        "id": f"test_{int(time.time())}",
        "timestamp": int(time.time()),
        "from_name": name}]}
    r = requests.post(f"{BASE}{endpoint}",
        json=payload, timeout=30)
    return r.json()

def check(condition, test_name, detail=""):
    if condition:
        print(f"✅ {test_name}")
        return True
    else:
        print(f"❌ {test_name}: {detail}")
        return False

# Supabase para verificar DB
import os
SUPA_URL = os.environ.get("SUPABASE_URL")
SUPA_KEY = os.environ.get("SUPABASE_ANON_KEY")

def get_last_bot_msg(sender, canal='whatsapp'):
    import urllib.request
    url = f"{SUPA_URL}/rest/v1/conversaciones_440?contacto_telefono=eq.{sender}&canal=eq.{canal}&direccion=eq.saliente&order=created_at.desc&limit=1"
    req = urllib.request.Request(url,
        headers={"apikey": SUPA_KEY,
                 "Authorization": f"Bearer {SUPA_KEY}"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
        return data[0]["mensaje"] if data else ""

def clean(sender):
    import urllib.request
    for table in ["conversaciones_440", "pacientes_440"]:
        field = "contacto_telefono" if table == "conversaciones_440" else "telefono"
        url = f"{SUPA_URL}/rest/v1/{table}?{field}=eq.{sender}"
        req = urllib.request.Request(url,
            headers={"apikey": SUPA_KEY,
                     "Authorization": f"Bearer {SUPA_KEY}",
                     "Content-Type": "application/json"},
            method="DELETE")
        urllib.request.urlopen(req)
    time.sleep(1)

results = []

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("BOT440 — REGRESSION TESTS")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

# ── TEST 1: BOTOX ──
sender = "573999900001"
clean(sender)
send_msg("/webhook", sender, "Hola")
time.sleep(8)
send_msg("/webhook", sender, "Quiero botox")
time.sleep(10)
msg = get_last_bot_msg(sender)
results.append(check(
    "500" in msg or "500.000" in msg,
    "TEST 1 — Botox: da precio",
    f"Respuesta: {msg[:100]}"))
results.append(check(
    "asesora" in msg.lower() or "contactar" in msg.lower(),
    "TEST 1 — Botox: menciona asesora",
    f"Respuesta: {msg[:100]}"))
results.append(check(
    "horario" not in msg.lower() and "disponible" not in msg.lower(),
    "TEST 1 — Botox: NO muestra horarios",
    f"Respuesta: {msg[:100]}"))
clean(sender)

# ── TEST 2: LABIOS ──
sender = "573999900002"
clean(sender)
send_msg("/webhook", sender, "Hola")
time.sleep(8)
send_msg("/webhook", sender, "Quiero labios")
time.sleep(10)
msg = get_last_bot_msg(sender)
results.append(check(
    "1.200" in msg or "1200" in msg,
    "TEST 2 — Labios: da precio $1.200.000",
    f"Respuesta: {msg[:100]}"))
results.append(check(
    "horario" not in msg.lower() and "disponible" not in msg.lower(),
    "TEST 2 — Labios: NO muestra horarios",
    f"Respuesta: {msg[:100]}"))
clean(sender)

# ── TEST 3: RINOMODELACIÓN ──
sender = "573999900003"
clean(sender)
send_msg("/webhook", sender, "Hola")
time.sleep(8)
send_msg("/webhook", sender, "Quiero rinomodelación")
time.sleep(10)
msg = get_last_bot_msg(sender)
results.append(check(
    "1.500" in msg or "1500" in msg,
    "TEST 3 — Rinomodelación: da precio $1.500.000",
    f"Respuesta: {msg[:100]}"))
results.append(check(
    "horario" not in msg.lower() and "disponible" not in msg.lower(),
    "TEST 3 — Rinomodelación: NO muestra horarios",
    f"Respuesta: {msg[:100]}"))
clean(sender)

# ── TEST 4: DEPILACIÓN ──
sender = "573999900004"
clean(sender)
send_msg("/webhook", sender, "Hola")
time.sleep(8)
send_msg("/webhook", sender, "Quiero depilación de axilas")
time.sleep(10)
send_msg("/webhook", sender, "María")
time.sleep(8)
send_msg("/webhook", sender, "Barranquilla")
time.sleep(10)
msg = get_last_bot_msg(sender)
results.append(check(
    "620" in msg or "horario" in msg.lower() or "disponible" in msg.lower() or "lunes" in msg.lower() or "martes" in msg.lower(),
    "TEST 4 — Depilación: muestra precio o slots",
    f"Respuesta: {msg[:100]}"))
clean(sender)

# ── TEST 5: CIRUGÍAS — BANT ──
sender = "573999900005"
clean(sender)
send_msg("/webhook-cx", sender, "Hola")
time.sleep(8)
send_msg("/webhook-cx", sender, "quiero lipoescultura")
time.sleep(10)
msg = get_last_bot_msg(sender, 'cirugia')
results.append(check(
    "nombre" in msg.lower() or "cuál es tu nombre" in msg.lower() or "mucho gusto" in msg.lower() or "giovanni" in msg.lower(),
    "TEST 5 — Cirugías: inicia flujo correctamente",
    f"Respuesta: {msg[:100]}"))
clean(sender)

# ── TEST 6: VALORACIÓN DR. GIO (sin slots) ──
sender = "573999900006"
clean(sender)
msgs_cx = [
    "Hola", "quiero lipoescultura",
    "Pedro", "Barranquilla",
    "No", "Sí", "No", "No", "En 1 mes"
]
for m in msgs_cx:
    send_msg("/webhook-cx", sender, m)
    time.sleep(10)
send_msg("/webhook-cx", sender, "Valoración presencial")
time.sleep(12)
msg = get_last_bot_msg(sender, 'cirugia')
results.append(check(
    "asesora" in msg.lower() and "horario" not in msg.lower(),
    "TEST 6 — Valoración Dr. Gio: sin slots + asesora coordina",
    f"Respuesta: {msg[:100]}"))
clean(sender)

# ── TEST 7: PREDIAGNÓSTICO PIDE CORREO ──
sender = "573999900007"
clean(sender)
send_msg("/webhook-cx", sender, "Hola")
time.sleep(8)
send_msg("/webhook-cx", sender, "Quiero prediagnóstico gratuito")
time.sleep(10)
send_msg("/webhook-cx", sender, "María")
time.sleep(10)
msg = get_last_bot_msg(sender, 'cirugia')
_low = msg.lower()
results.append(check(
    ("correo" in _low or "email" in _low) and
    ("lunes" not in _low and "martes" not in _low and
     "miércoles" not in _low and "miercoles" not in _low and
     "jueves" not in _low and "viernes" not in _low and
     "sábado" not in _low and "sabado" not in _low),
    "TEST 7 — Prediagnóstico: pide correo, no muestra días",
    f"Respuesta: {msg[:120]}"))
clean(sender)

# ── TEST 8: VALORACIÓN SIN SLOTS ──
sender = "573999900008"
clean(sender)
msgs_v = [
    "Hola", "quiero lipoescultura",
    "Andrea", "Barranquilla",
    "No", "Sí", "No", "No", "En 1 mes",
]
for m in msgs_v:
    send_msg("/webhook-cx", sender, m)
    time.sleep(10)
send_msg("/webhook-cx", sender, "Valoración presencial")
time.sleep(12)
msg = get_last_bot_msg(sender, 'cirugia')
_low = msg.lower()
results.append(check(
    ("asesora" in _low or "contactará" in _low or "contactara" in _low) and
    "horario" not in _low and "disponible" not in _low and
    "mañana" not in _low and "manana" not in _low and
    "tarde" not in _low,
    "TEST 8 — Valoración: asesora, sin slots, sin mañana/tarde",
    f"Respuesta: {msg[:120]}"))
clean(sender)

# ── RESUMEN ──
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━")
passed = sum(results)
total = len(results)
print(f"RESULTADO: {passed}/{total} tests pasaron")
if passed == total:
    print("✅ TODO OK — safe to deploy")
else:
    print("❌ HAY FALLAS — NO deployear")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

exit(0 if passed == total else 1)
