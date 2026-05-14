import os, json, urllib.request, urllib.error, urllib.parse
from core.whapi import WhapiClient

KNOWLEDGE = """
440 CLINIC BY DR. GIOVANNI FUENTES
Dirección: Carrera 47 #79-191, Barranquilla
Tel recepción: +57 318 180 0130
Horario: Lunes-Viernes 8am-5pm / Sábados 8am-12pm

SERVICIOS MEDICINA ESTÉTICA:

DEPILACIÓN LÁSER REMOVALL TRIO
- Triple longitud de onda (755/810/1064nm)
- Punta zafiro -9°C — SIN DOLOR
- Todo tipo de piel
- Video: https://youtu.be/_9JcZgSNc8M

PRECIOS x6 sesiones:
• Axilas: $540.000 (1ra sesión: $90.000)
• Bigote: $570.000 (1ra: $95.000)
• Bikini parcial: $900.000 (1ra: $150.000) — SOLO área genital
• Bikini completo: $1.200.000 (1ra: $200.000) — área genital + intraglútea
• Glúteos: $900.000 (1ra: $150.000)
• Abdomen: $900.000 (1ra: $150.000)
• Espalda: $1.152.000 (1ra: $192.000)
• Pecho: $1.200.000 (1ra: $200.000)
• Barba: $1.200.000 (1ra: $200.000)
• Media pierna: $1.080.000 (1ra: $180.000) — tobillo a rodilla
• Pierna completa: $1.560.000 (1ra: $260.000) — tobillo a ingle

CÁMARA HIPERBÁRICA
• Sesión individual: $150.000
• Paquete x5: $700.000
• Duración: 60 minutos
• Tiene pantalla, audio y video

VALORACIONES GRATUITAS 15 min
• Katherine: Martes y Jueves 1pm-5pm
• Roxana: Miércoles y Viernes 1pm-5pm

CIRUGÍAS — NO dar precios, redirigir a wa.me/573044886085
"""

SYSTEM = f"""Eres el asistente virtual de 440 Clinic (canal estética +57 313 544 9024).

{KNOWLEDGE}

PERSONALIDAD:
- Cálida, profesional, empática
- Respuestas cortas (máximo 4 líneas)
- Una pregunta por mensaje
- NUNCA digas que eres IA
- NUNCA inventes precios

FLUJO NATURAL:
1. Saludo → pregunta en qué puedes ayudar
2. Menciona depilación → comparte el video + pregunta nombre y ciudad
3. Menciona hiperbárica → da info + precios
4. Quiere agendar → pide nombre, ciudad, preferencia de día/hora
5. Da datos → confirma y notifica al equipo

CUANDO QUIERAS NOTIFICAR AL EQUIPO agrega al final:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número o 'por WhatsApp']
servicio: [servicio]
<<<END>>>

REGLAS:
- Si pregunta por cirugía → wa.me/573044886085
- Si es de otra ciudad → puede venir a Barranquilla
- Esteticistas: Katherine Pertuz y Roxana Chegwin
"""

# Default headers including User-Agent (gate.whapi.cloud and supabase use
# Cloudflare which blocks Python-urllib UA with HTTP 403 / error 1010)
_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440/1.0; +https://440clinic.com)'


class Brain:
    def __init__(self):
        self.whapi = WhapiClient()
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.sb_key = os.environ.get('SUPABASE_ANON_KEY', '')
        self.history_limit = 10
        print(f"[BRAIN INIT] sb_url={self.sb_url!r} sb_key_len={len(self.sb_key)} anth_key_len={len(self.api_key)}", flush=True)

    # ------------------------------------------------------------------
    # Supabase memory: conversaciones_440
    # ------------------------------------------------------------------
    def _sb_headers(self):
        return {
            'apikey': self.sb_key,
            'Authorization': f'Bearer {self.sb_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': _BROWSER_UA,
        }

    def _load_history(self, sender_id, canal):
        """Read last N messages for this contact and return Anthropic-format messages[]."""
        if not self.sb_url or not self.sb_key:
            print(f"[BRAIN] supabase not configured — using empty history", flush=True)
            return []
        params = (
            f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
            f'&canal=eq.{urllib.parse.quote(canal)}'
            f'&select=mensaje,direccion,remitente,created_at'
            f'&order=created_at.desc'
            f'&limit={self.history_limit}'
        )
        url = f'{self.sb_url}/rest/v1/conversaciones_440?{params}'
        try:
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=8) as r:
                rows = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:300]
            except: pass
            print(f"[BRAIN] sb_get HTTPError {e.code} body={body!r}", flush=True)
            return []
        except Exception as e:
            print(f"[BRAIN] sb_get error: {e}", flush=True)
            return []
        # rows are newest-first → reverse for chronological order
        rows = list(reversed(rows or []))
        messages = []
        for row in rows:
            content = (row.get('mensaje') or '').strip()
            if not content:
                continue
            direccion = (row.get('direccion') or '').lower()
            remitente = (row.get('remitente') or '').lower()
            # Heuristics: entrante / paciente → user; saliente / bot|asistente|sistema → assistant
            if direccion == 'saliente' or remitente in ('bot', 'asistente', 'sistema'):
                role = 'assistant'
            else:
                role = 'user'
            messages.append({'role': role, 'content': content})
        print(f"[BRAIN] loaded {len(messages)} history msgs from supabase", flush=True)
        # Anthropic requires the first message to be a user turn — drop leading assistant turns if any
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        # Collapse consecutive same-role turns (rare, defensive)
        collapsed = []
        for m in messages:
            if collapsed and collapsed[-1]['role'] == m['role']:
                collapsed[-1]['content'] = collapsed[-1]['content'] + '\n' + m['content']
            else:
                collapsed.append(dict(m))
        return collapsed

    def _save_message(self, sender_id, sender_name, canal, mensaje, direccion, remitente):
        """Insert a single message into conversaciones_440."""
        if not self.sb_url or not self.sb_key:
            return
        if not mensaje:
            return
        body = {
            'contacto_nombre': sender_name or None,
            'contacto_telefono': sender_id,
            'canal': canal,
            'mensaje': mensaje,
            'direccion': direccion,
            'remitente': remitente,
            'leido': direccion == 'saliente',
        }
        url = f'{self.sb_url}/rest/v1/conversaciones_440'
        headers = self._sb_headers()
        headers['Prefer'] = 'return=minimal'
        data = json.dumps(body).encode()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[BRAIN] sb_insert {direccion}/{remitente} OK status={r.status}", flush=True)
        except urllib.error.HTTPError as e:
            err = ''
            try: err = e.read().decode()[:300]
            except: pass
            print(f"[BRAIN] sb_insert HTTPError {e.code} body={err!r}", flush=True)
        except Exception as e:
            print(f"[BRAIN] sb_insert error: {e}", flush=True)

    # ------------------------------------------------------------------
    # Main flow
    # ------------------------------------------------------------------
    def process(self, sender_id, sender_name, text, canal='whatsapp'):
        print(f"[BRAIN] {sender_id}: {text[:50]}", flush=True)
        print(f"[BRAIN] api_key_len={len(self.api_key)} canal={canal}", flush=True)

        # 1. Load history from Supabase
        history = self._load_history(sender_id, canal)

        # 2. Append the new user message (with sender name prefix for context)
        user_content = f"[{sender_name or sender_id}]: {text}" if sender_name else text
        history.append({'role': 'user', 'content': user_content})

        # 3. Save user message to Supabase (fire before Claude call so it's
        #    captured even if the model call dies)
        self._save_message(sender_id, sender_name, canal, text,
                           direccion='entrante', remitente='paciente')

        # 4. Call Claude with history
        print(f"[BRAIN] calling Claude (history={len(history)} msgs)", flush=True)
        response = self._call_claude(history)
        print(f"[BRAIN] Claude responded len={len(response)} preview={response[:80]!r}", flush=True)
        text_resp, notify = self._parse(response)

        # 5. Send reply and persist
        if text_resp.strip():
            print(f"[BRAIN] sending reply to {sender_id} len={len(text_resp)}", flush=True)
            r = self.whapi.send_text(sender_id, text_resp.strip())
            print(f"[BRAIN] send_text result={r}", flush=True)
            self._save_message(sender_id, sender_name, canal, text_resp.strip(),
                               direccion='saliente', remitente='bot')
        else:
            print(f"[BRAIN] text_resp empty after parse — NOT sending", flush=True)

        if notify:
            print(f"[BRAIN] notify_admin trigger", flush=True)
            self._notify_admin(notify, sender_id)

    def _call_claude(self, messages):
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "system": SYSTEM,
            "messages": messages
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "user-agent": _BROWSER_UA,
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())["content"][0]["text"]
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[BRAIN] Claude HTTPError {e.code} body={body!r}", flush=True)
            return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"
        except Exception as e:
            print(f"[BRAIN] Claude error: {e}", flush=True)
            return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"

    def _parse(self, response):
        import re
        notify = None
        match = re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', response, re.DOTALL)
        if match:
            notify = match.group(1).strip()
            response = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', response, flags=re.DOTALL).strip()
        return response, notify

    def _notify_admin(self, data, sender_id):
        admin = os.environ.get('ADMIN_WHATSAPP', '573181800130')
        msg = f"🔔 LEAD ESTÉTICO\n━━━━━━━━━━━━━\n{data}\n📱 Canal: {sender_id}\n━━━━━━━━━━━━━"
        self.whapi.send_text(admin, msg)
