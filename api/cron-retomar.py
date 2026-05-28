"""/cron-retomar — Re-enganche de leads tibios (toques escalonados).

Solo lectura sobre conversaciones_440, escribe solo en seguimientos_440.
NO toca los cerebros (brain.py / brain_cx.py).

Disparado por:
  - Vercel Cron (GET, cada 30 min) — schedule en vercel.json
  - curl manual (POST) — para dry-run / pruebas

Auth: header `Authorization: Bearer <CRON_SECRET>` — validado en GET y POST.
"""
from http.server import BaseHTTPRequestHandler
import os, json, datetime, urllib.request
from zoneinfo import ZoneInfo


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
WHAPI_URL    = os.environ.get("WHAPI_URL", "https://gate.whapi.cloud")
CRON_SECRET  = os.environ["CRON_SECRET"]

CUENTAS = {
    ("drgio_wa",     "cirugia"):  {"token": "WHAPI_TOKEN_CX", "tipo": "cirugia"},
    ("440clinic_wa", "whatsapp"): {"token": "WHAPI_TOKEN",    "tipo": "estetica"},
}

COPY = {
    ("cirugia", 1):  "¡Hola {n}! 💙 Vi que quedamos a mitad de la conversación sobre tu procedimiento. ¿Te quedó alguna duda que pueda resolverte? Estoy aquí para ayudarte 😊",
    ("cirugia", 2):  "{n}, no quiero que se te pase 💙 El Dr. Gio tiene agenda disponible esta semana para valoración. ¿Te gustaría que coordinemos un espacio? Cuéntame y seguimos.",
    ("estetica", 1): "¡Hola {n}! ✨ Quedé pendiente de tu mensaje en 440 Clinic. ¿Sigues interesad@ en conocer más? Con gusto te ayudo con lo que necesites 💙",
    ("estetica", 2): "{n}, te escribo de nuevo de 440 Clinic ✨ Tenemos espacios disponibles esta semana. ¿Quieres que te comparta los horarios? Aquí sigo para lo que necesites 💙",
}

CAP_HORA = 2
HORA_INI, HORA_FIN = 9, 20
VENTANA_T1_HORAS = 4
VENTANA_T2_HORAS = 24
TZ = ZoneInfo("America/Bogota")


# ---------------- Supabase REST helpers ----------------

def _sb(path, method="GET", body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if method == "POST":
        headers["Prefer"] = "return=minimal"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt else []


def _send_whapi(token_env, to, text):
    token = os.environ.get(token_env, "")
    if not token:
        print(f"[CRON] ❌ token vacío: {token_env}", flush=True)
        return False
    req = urllib.request.Request(
        f"{WHAPI_URL}/messages/text",
        data=json.dumps({"to": to, "body": text}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"[CRON] ✅ enviado a {to}", flush=True)
            return True
    except Exception as e:
        print(f"[CRON] ❌ envío falló {to}: {e}", flush=True)
        return False


def _ya_notificado(tel, cuenta):
    q = (f"conversaciones_440?contacto_telefono=eq.{tel}"
         f"&cuenta_receptora=eq.{cuenta}&direccion=eq.saliente"
         f"&mensaje=ilike.*NOTIFY*&select=id&limit=1")
    return len(_sb(q)) > 0


def _bot_pausado(tel):
    q = f"leads_comerciales?telefono=eq.{tel}&bot_pausado=eq.true&select=telefono&limit=1"
    return len(_sb(q)) > 0


def _toques_previos(tel, canal):
    q = f"seguimientos_440?contacto_telefono=eq.{tel}&canal=eq.{canal}&select=toque,enviado_at"
    return _sb(q)


# ---------------- Cron core ----------------

def _run_cron():
    ahora = datetime.datetime.now(TZ)
    if not (HORA_INI <= ahora.hour < HORA_FIN):
        print(f"[CRON] fuera de franja ({ahora.hour}h) — skip", flush=True)
        return {"status": "fuera_de_franja", "hora_local": ahora.hour}

    enviados_hora = 0
    resumen = {"t1": 0, "t2": 0, "skip": 0}

    for (cuenta, canal), cfg in CUENTAS.items():
        desde = (ahora - datetime.timedelta(hours=72)).astimezone(datetime.timezone.utc).isoformat()
        rows = _sb(
            f"conversaciones_440?cuenta_receptora=eq.{cuenta}&canal=eq.{canal}"
            f"&created_at=gte.{desde}&select=contacto_telefono,contacto_nombre,"
            f"direccion,created_at&order=created_at.desc"
        )

        leads = {}
        for r in rows:
            tel = r.get("contacto_telefono")
            if not tel:
                continue
            leads.setdefault(tel, {"nombre": r.get("contacto_nombre"),
                                   "entrantes": [], "msgs": 0})
            leads[tel]["msgs"] += 1
            if r.get("direccion") == "entrante":
                leads[tel]["entrantes"].append(r["created_at"])

        for tel, d in leads.items():
            if enviados_hora >= CAP_HORA:
                print("[CRON] cap/hora alcanzado", flush=True); break

            if d["msgs"] < 2 or not d["entrantes"]:
                resumen["skip"] += 1; continue

            ult_entrante = max(datetime.datetime.fromisoformat(x) for x in d["entrantes"])
            silencio_h = (ahora - ult_entrante.astimezone(TZ)).total_seconds() / 3600

            if _ya_notificado(tel, cuenta) or _bot_pausado(tel):
                resumen["skip"] += 1; continue

            previos = _toques_previos(tel, canal)
            n_toques = len(previos)
            if n_toques >= 2:
                resumen["skip"] += 1; continue

            toque = None
            if n_toques == 0 and silencio_h >= VENTANA_T1_HORAS:
                toque = 1
            elif n_toques == 1:
                ult_toque = max(datetime.datetime.fromisoformat(p["enviado_at"]) for p in previos)
                if (ahora - ult_toque.astimezone(TZ)).total_seconds()/3600 >= VENTANA_T2_HORAS:
                    toque = 2
            if not toque:
                resumen["skip"] += 1; continue

            nombre = (d["nombre"] or "").split(" ")[0] if d["nombre"] else ""
            if nombre:
                text = COPY[(cfg["tipo"], toque)].format(n=nombre)
            else:
                text = COPY[(cfg["tipo"], toque)].format(n="").lstrip(", ").replace("¡Hola ! ", "¡Hola! ").replace("  ", " ")

            if _send_whapi(cfg["token"], tel, text):
                try:
                    _sb("seguimientos_440", "POST", {
                        "contacto_telefono": tel, "canal": canal,
                        "cuenta_receptora": cuenta, "toque": toque,
                        "enviado_at": ahora.astimezone(datetime.timezone.utc).isoformat(),
                    })
                except Exception as e:
                    print(f"[CRON] ❌ insert seguimientos falló {tel} toque={toque}: {e}", flush=True)
                enviados_hora += 1
                resumen[f"t{toque}"] += 1

    print(f"[CRON] resumen={resumen} enviados={enviados_hora}", flush=True)
    return {"resumen": resumen, "enviados": enviados_hora}


# ---------------- HTTP handler (patrón de webhook-cx.py) ----------------

class handler(BaseHTTPRequestHandler):
    def _check_auth(self):
        auth = self.headers.get('Authorization', '') or self.headers.get('authorization', '')
        if auth != f"Bearer {CRON_SECRET}":
            print("[CRON] 401 unauthorized", flush=True)
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return False
        return True

    def _dispatch(self):
        if not self._check_auth():
            return
        try:
            result = _run_cron()
            self._ok(result)
        except Exception as e:
            print(f"[CRON] ❌ Error: {e}", flush=True)
            self._ok({"error": str(e)})

    def do_POST(self):
        print("[CRON] POST recibido", flush=True)
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
            if length > 0:
                self.rfile.read(length)
        except Exception:
            pass
        self._dispatch()

    def do_GET(self):
        print("[CRON] GET recibido (Vercel cron)", flush=True)
        self._dispatch()

    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
