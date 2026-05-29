"""/cron-retomar — Re-enganche de leads tibios (toques escalonados).

Solo lectura sobre conversaciones_440, escribe solo en seguimientos_440.
NO toca los cerebros (brain.py / brain_cx.py).

Disparado por:
  - Vercel Cron (GET, cada 30 min) — schedule en vercel.json
  - curl manual (POST) — para dry-run / pruebas

Auth: header `Authorization: Bearer <CRON_SECRET>` — validado en GET y POST.

NOTA: las env vars se leen DENTRO de las funciones (no a nivel de módulo) para
que el import del módulo nunca reviente por una env var faltante. Esto permite
que en environments incompletos (Preview, dev) Vercel pueda al menos cargar el
handler y devolver un error controlado, en lugar de FUNCTION_INVOCATION_FAILED.
"""
from http.server import BaseHTTPRequestHandler
import os, re, json, time, datetime, urllib.request
from zoneinfo import ZoneInfo


# Postgres a veces devuelve microsegundos con 4-5 dígitos (no 0/3/6), y
# datetime.fromisoformat en Python <3.11 es estricto. Helper portable.
_FRAC_RE = re.compile(r'(\.\d{1,5})(?=[+\-Z]|$)')

def _iso(s):
    """Parsea ISO-8601 tolerando 'Z' y fracciones de microsegundo no estándar."""
    s = s.replace('Z', '+00:00')
    s = _FRAC_RE.sub(lambda m: m.group(1).ljust(7, '0'), s)  # '.5714' → '.571400'
    return datetime.datetime.fromisoformat(s)


CUENTAS = {
    ("drgio_wa",     "cirugia"):  {"token": "WHAPI_TOKEN_CX", "tipo": "cirugia"},
    # reactivado 2026-05-29: el 403 anterior lo causó el bug de cap (213 envíos
    # en una corrida); ya resuelto con cap por INTENTOS=2 + throttle 2s + filtro
    # warm 24h. Canal estética sano y enviando con normalidad.
    ("440clinic_wa", "whatsapp"): {"token": "WHAPI_TOKEN",    "tipo": "estetica"},
}

COPY = {
    ("cirugia", 1):  "¡Hola {n}! 💙 Vi que quedamos a mitad de la conversación sobre tu procedimiento. ¿Te quedó alguna duda que pueda resolverte? Estoy aquí para ayudarte 😊",
    ("cirugia", 2):  "{n}, no quiero que se te pase 💙 El Dr. Gio tiene agenda disponible esta semana para valoración. ¿Te gustaría que coordinemos un espacio? Cuéntame y seguimos.",
    ("estetica", 1): "¡Hola {n}! ✨ Quedé pendiente de tu mensaje en 440 Clinic. ¿Sigues interesad@ en conocer más? Con gusto te ayudo con lo que necesites 💙",
    ("estetica", 2): "{n}, te escribo de nuevo de 440 Clinic ✨ Tenemos espacios disponibles esta semana. ¿Quieres que te comparta los horarios? Aquí sigo para lo que necesites 💙",
}

# Fallback sin nombre — saludo neutro y bien formateado. Se usa cuando
# contacto_nombre viene vacío, sucio (emojis, números, basura) o muy corto
# (ej. "Ec", "L", iniciales). Mejor un saludo limpio que un "¡Hola Ec!".
COPY_NEUTRO = {
    ("cirugia", 1):  "¡Hola! 💙 Vi que quedamos a mitad de la conversación sobre tu procedimiento. ¿Te quedó alguna duda que pueda resolverte? Estoy aquí para ayudarte 😊",
    ("cirugia", 2):  "Hola 💙 No quiero que se te pase — el Dr. Gio tiene agenda disponible esta semana para valoración. ¿Te gustaría que coordinemos un espacio? Cuéntame y seguimos.",
    ("estetica", 1): "¡Hola! ✨ Quedé pendiente de tu mensaje en 440 Clinic. ¿Sigues interesad@ en conocer más? Con gusto te ayudo con lo que necesites 💙",
    ("estetica", 2): "Hola ✨ Te escribo de nuevo de 440 Clinic — tenemos espacios disponibles esta semana. ¿Quieres que te comparta los horarios? Aquí sigo para lo que necesites 💙",
}

# Lista corta de nombres "raros" que se ven feo en saludo — usar fallback.
_NOMBRE_INVALIDO = {"media", "imagen", "sticker", "audio", "video", "amigo", "amiga", "hola"}

def _saneo_nombre(raw):
    """Devuelve un primer nombre limpio, o '' si no es presentable.

    Reglas:
      - quita emojis, números, signos
      - toma el primer token
      - largo entre 3 y 20 chars
      - no está en lista de basura común ("Media", "Imagen", etc.)
      - title-case
    """
    if not raw:
        return ""
    limpio = re.sub(r"[^A-Za-zÁÉÍÓÚáéíóúÑñÜü\s'-]", "", str(raw)).strip()
    if not limpio:
        return ""
    primero = limpio.split()[0]
    if len(primero) < 3 or len(primero) > 20:
        return ""
    if primero.lower() in _NOMBRE_INVALIDO:
        return ""
    return primero.capitalize()

CAP_HORA = 2                  # máximo INTENTOS de envío por corrida (no éxitos)
HORA_INI, HORA_FIN = 9, 20
VENTANA_T1_HORAS = 4          # silencio mínimo para tocar T1
VENTANA_T2_HORAS = 24         # silencio mínimo desde T1 para tocar T2
VENTANA_MAX_SILENCIO_H = 24   # tope: si lleva más de esto, lead frío → skip
THROTTLE_SEG = 2              # pausa entre envíos (anti-rate-limit WhApi)
TZ = ZoneInfo("America/Bogota")


# ---------------- Supabase REST helpers ----------------

def _sb(path, method="GET", body=None):
    base = os.environ.get("SUPABASE_URL")
    key  = os.environ.get("SUPABASE_ANON_KEY")
    if not base or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY no configurados")
    url = f"{base}/rest/v1/{path}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
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
    whapi_url = os.environ.get("WHAPI_URL", "https://gate.whapi.cloud")
    req = urllib.request.Request(
        f"{whapi_url}/messages/text",
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
    # Las constantes HORA_INI/HORA_FIN pueden sobreescribirse vía env var
    # (útil para pruebas locales fuera de la franja real). En Production
    # no se setean → se usa el default 9-20 Bogotá.
    hora_ini = int(os.environ.get("HORA_INI", HORA_INI))
    hora_fin = int(os.environ.get("HORA_FIN", HORA_FIN))
    if not (hora_ini <= ahora.hour < hora_fin):
        print(f"[CRON] fuera de franja ({ahora.hour}h, vent={hora_ini}-{hora_fin}) — skip", flush=True)
        return {"status": "fuera_de_franja", "hora_local": ahora.hour}

    # CAP por INTENTOS (no éxitos). Si _send_whapi falla con 403/timeout,
    # el contador igual avanza → el break se dispara aunque el canal esté caído.
    # El cap es POR CUENTA: cada (cuenta, canal) tiene su propio presupuesto de
    # CAP_HORA intentos, independiente. Cirugía no consume el cap de estética ni
    # viceversa. `intentos_hora` queda como total global solo para log/return.
    intentos_hora = 0
    enviados_ok   = 0
    resumen = {"t1": 0, "t2": 0, "skip": 0, "intentos": 0, "ok": 0, "fail": 0}

    dry_run = os.environ.get("DRY_RUN", "") == "1"
    only_tel = os.environ.get("DRY_RUN_TEL", "").strip()
    if dry_run:  print("[CRON] 🧪 DRY_RUN=1 — no se enviará ni se insertará", flush=True)
    if only_tel: print(f"[CRON] 🧪 DRY_RUN_TEL={only_tel} — solo procesa ese número", flush=True)

    for (cuenta, canal), cfg in CUENTAS.items():
        # PostgREST decodifica '+' como espacio en el query string → '+00:00' rompe
        # el parsing del timestamp. Sustituir por 'Z' (UTC), aceptado por Postgres.
        desde = (ahora - datetime.timedelta(hours=72)).astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
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

        intentos_cuenta = 0
        for tel, d in leads.items():
            if intentos_cuenta >= CAP_HORA:
                print(f"[CRON] cap/hora alcanzado para {cuenta}/{canal} ({intentos_cuenta}/{CAP_HORA} intentos) — break", flush=True); break

            # Filtro test: solo procesar el número indicado
            if only_tel and tel != only_tel:
                continue

            if d["msgs"] < 2 or not d["entrantes"]:
                resumen["skip"] += 1; continue

            ult_entrante = max(_iso(x) for x in d["entrantes"])
            silencio_h = (ahora - ult_entrante.astimezone(TZ)).total_seconds() / 3600

            # Filtro warm: lead frío (>24h sin escribir) → skip
            if silencio_h > VENTANA_MAX_SILENCIO_H:
                resumen["skip"] += 1; continue

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
                ult_toque = max(_iso(p["enviado_at"]) for p in previos)
                if (ahora - ult_toque.astimezone(TZ)).total_seconds()/3600 >= VENTANA_T2_HORAS:
                    toque = 2
            if not toque:
                resumen["skip"] += 1; continue

            nombre = _saneo_nombre(d["nombre"])
            if nombre:
                text = COPY[(cfg["tipo"], toque)].format(n=nombre)
            else:
                text = COPY_NEUTRO[(cfg["tipo"], toque)]

            # ── INTENTO DE ENVÍO ──
            # Contar intento ANTES de llamar a WhApi: el CAP se respeta aunque
            # el envío falle (403/timeout). Crítico para no martillar WhApi.
            intentos_cuenta += 1
            intentos_hora += 1
            resumen["intentos"] += 1
            print(f"[CRON] intento {cuenta}/{canal} {intentos_cuenta}/{CAP_HORA} (global {intentos_hora}) → {tel} toque={toque} silencio_h={silencio_h:.1f}", flush=True)

            if dry_run:
                print(f"[CRON] 🧪 DRY_RUN — habría enviado a {tel}: {text[:80]!r}", flush=True)
                resumen[f"t{toque}"] += 1
                resumen["ok"] += 1
                # En dry-run no se inserta en seguimientos_440.
                time.sleep(THROTTLE_SEG)
                continue

            ok = _send_whapi(cfg["token"], tel, text)
            if ok:
                try:
                    _sb("seguimientos_440", "POST", {
                        "contacto_telefono": tel, "canal": canal,
                        "cuenta_receptora": cuenta, "toque": toque,
                        "enviado_at": ahora.astimezone(datetime.timezone.utc).isoformat(),
                    })
                except Exception as e:
                    print(f"[CRON] ❌ insert seguimientos falló {tel} toque={toque}: {e}", flush=True)
                enviados_ok += 1
                resumen[f"t{toque}"] += 1
                resumen["ok"] += 1
            else:
                resumen["fail"] += 1
            # Throttle entre envíos (anti-rate-limit WhApi). También en fallos.
            time.sleep(THROTTLE_SEG)

    print(f"[CRON] resumen={resumen} intentos={intentos_hora} enviados_ok={enviados_ok}", flush=True)
    return {"resumen": resumen, "intentos": intentos_hora, "enviados_ok": enviados_ok}


# ---------------- HTTP handler (patrón de webhook-cx.py) ----------------

class handler(BaseHTTPRequestHandler):
    def _check_auth(self):
        secret = os.environ.get("CRON_SECRET", "")
        if not secret:
            print("[CRON] ❌ CRON_SECRET no configurado", flush=True)
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "CRON_SECRET not configured"}).encode())
            return False
        auth = self.headers.get('Authorization', '') or self.headers.get('authorization', '')
        if auth != f"Bearer {secret}":
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
