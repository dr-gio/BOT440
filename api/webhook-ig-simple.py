import json
import os
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler
import anthropic

IG_TOKEN = os.environ.get('IG_PAGE_ACCESS_TOKEN','')
IG_ACCOUNT_ID = os.environ.get('IG_ACCOUNT_ID','17841457278507530')

WA_ESTETICA = '573135449024'
WA_CIRUGIA = '573137917168'

SYSTEM_440CLINIC = """
Eres el asistente de @440clinic
en Instagram — 440 Clinic,
centro de medicina estética
en Barranquilla, Colombia.

DETECTA LA INTENCIÓN Y RESPONDE:

INTERÉS EN ESTÉTICA:
(depilación, láser, hiperbárica,
body sculpt, facial, piel,
tratamiento, cita, precio,
cuánto cuesta, me interesa,
quiero hacerme, información)
→ Responde:
"¡Hola [nombre]! 💙
Para orientarte mejor sobre
[servicio específico]
escríbenos por WhatsApp:
📱 wa.me/573135449024?text=Hola!+Me+interesa+[servicio]
¡Te esperamos! 💙
La Belleza 440 ✨"

INTERÉS EN CIRUGÍA:
(lipoescultura, lipo, mamoplastia,
abdominoplastia, blefaroplastia,
lifting, cirugía plástica,
operación, Dr. Gio)
→ Responde:
"¡Hola [nombre]! 💙
Para cirugías con el Dr. Giovanni
Fuentes escríbenos por WhatsApp:
📱 wa.me/573137917168?text=Hola!+Me+interesa+[procedimiento]
¡Te esperamos! 💙
La Belleza 440 ✨"

ADMIRACIÓN/RESULTADO BONITO:
→ Respuesta cálida y natural
  máximo 3 líneas.
  Genera respuesta única según
  el comentario específico.

SALUDO/AMIGO/NEUTRAL:
→ Respuesta cálida corta.
  Sigue la conversación natural.

EMOJI SOLO:
→ "💙🙏" o "😊💙"

NEGATIVO/SPAM:
→ Devuelve texto vacío ""

REGLAS:
→ Máximo 4 líneas
→ Nunca digas que eres IA
→ Tono cálido y natural
→ Usa el nombre si lo conoces
→ Para comentarios con interés:
  respuesta pública corta +
  DM privado con link WhatsApp
→ Para admiración/saludo:
  solo respuesta pública
"""

# Palabras clave
ESTETICA_KEYWORDS = [
    'depilación','depilacion','láser','laser','hiperbárica','hiperbarica',
    'body sculpt','bodysculpt','facial','piel','tratamiento','cita',
    'precio','costo','cuánto cuesta','cuanto cuesta','me interesa',
    'quiero hacerme','información','informacion','medicina estética',
    'medicina estetica','tratamiento estético','tratamiento estetico',
]
CIRUGIA_KEYWORDS = [
    'lipoescultura','lipo','mamoplastia','abdominoplastia','blefaroplastia',
    'lifting','cirugía plástica','cirugia plastica','cirugía','cirugia',
    'operación','operacion','operarme','dr. gio','dr gio',
    'giovanni fuentes',
]

ESTETICA_SERVICIOS = [
    'depilación','depilacion','láser','laser','hiperbárica','hiperbarica',
    'body sculpt','bodysculpt','facial',
]
CIRUGIA_PROCS = [
    'lipoescultura','mamoplastia','abdominoplastia','blefaroplastia',
    'lifting','lipo',
]


def _first_match(text, words):
    t = (text or '').lower()
    for w in words:
        if w in t:
            return w
    return ''


def _detecta_cirugia(text):
    return bool(_first_match(text, CIRUGIA_KEYWORDS))


def _detecta_estetica(text):
    return bool(_first_match(text, ESTETICA_KEYWORDS))


def _saludo(nombre):
    return f'¡Hola {nombre}! 💙' if nombre else '¡Hola! 💙'


def _dm_estetica(text, nombre=''):
    serv = _first_match(text, ESTETICA_SERVICIOS) or 'tu tratamiento'
    q = urllib.parse.quote_plus(f'Hola! Me interesa {serv}')
    return (f'{_saludo(nombre)}\n'
            f'Para orientarte mejor sobre {serv} '
            f'escríbenos por WhatsApp:\n'
            f'📱 wa.me/{WA_ESTETICA}?text={q}\n'
            f'¡Te esperamos! 💙\n'
            f'La Belleza 440 ✨')


def _dm_cirugia(text, nombre=''):
    proc = _first_match(text, CIRUGIA_PROCS) or 'tu procedimiento'
    q = urllib.parse.quote_plus(f'Hola! Me interesa {proc}')
    return (f'{_saludo(nombre)}\n'
            f'Para cirugías con el Dr. Giovanni Fuentes '
            f'escríbenos por WhatsApp:\n'
            f'📱 wa.me/{WA_CIRUGIA}?text={q}\n'
            f'¡Te esperamos! 💙\n'
            f'La Belleza 440 ✨')


def _public_interes(text, nombre=''):
    """Respuesta pública corta para comentarios con interés — SIN link."""
    if _detecta_cirugia(text):
        tema = _first_match(text, CIRUGIA_PROCS) or 'tu procedimiento'
    else:
        tema = _first_match(text, ESTETICA_SERVICIOS) or 'tu tratamiento'
    return (f'{_saludo(nombre)}\n'
            f'Para orientarte mejor sobre {tema} '
            f'te escribimos por DM 😊')


def _graph_post(path, data):
    url = f'https://graph.instagram.com/v21.0/{path}'
    body = urllib.parse.urlencode({**data, 'access_token': IG_TOKEN}).encode()
    req = urllib.request.Request(url, data=body, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {'error': e.read().decode()[:300]}
        except Exception:
            return {'error': f'http {e.code}'}
    except Exception as e:
        return {'error': str(e)}


def _send_dm(recipient, text):
    """Envía DM. recipient = {'id': igsid} o {'comment_id': cid}."""
    url = f'https://graph.instagram.com/v21.0/{IG_ACCOUNT_ID}/messages'
    payload = json.dumps({'recipient': recipient,
                          'message': {'text': text}}).encode()
    req = urllib.request.Request(
        url, data=payload, method='POST',
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Bearer {IG_TOKEN}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {'error': e.read().decode()[:300]}
        except Exception:
            return {'error': f'http {e.code}'}
    except Exception as e:
        return {'error': str(e)}


def _claude_reply(text):
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY',''))
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=200,
        system=SYSTEM_440CLINIC,
        messages=[{'role': 'user', 'content': text}],
    )
    return response.content[0].text.strip()


def _dm_interes(text, nombre=''):
    """DM con link según el tipo de interés (cirugía tiene prioridad)."""
    if _detecta_cirugia(text):
        return _dm_cirugia(text, nombre)
    return _dm_estetica(text, nombre)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._respond(200, {'status': 'BOT440-IG-SIMPLE running'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))

            tipo = (body.get('tipo', '') or 'dm').lower()
            sender_id = body.get('sender_id', '')
            text = body.get('text', '') or body.get('message', '')
            comment_id = body.get('comment_id', '') or body.get('id', '')
            nombre = body.get('from_username', '') or body.get('name', '')

            if not text:
                self._respond(200, {'status': 'ok', 'reply': ''})
                return

            interes = _detecta_cirugia(text) or _detecta_estetica(text)

            # ── COMENTARIO DEL FEED ──────────────────────────────────
            if tipo in ('comment', 'comentario'):
                result = {'status': 'ok', 'tipo': 'comment', 'reply': ''}
                if interes:
                    # respuesta pública corta SIN link + DM privado con link
                    reply = _public_interes(text, nombre)
                    if comment_id:
                        result['public'] = _graph_post(
                            f'{comment_id}/replies', {'message': reply})
                        result['dm'] = _send_dm(
                            {'comment_id': comment_id},
                            _dm_interes(text, nombre))
                else:
                    # admiración / saludo → solo respuesta pública, sin DM
                    reply = _claude_reply(text)
                    if comment_id and reply:
                        result['public'] = _graph_post(
                            f'{comment_id}/replies', {'message': reply})
                self._respond(200, result)
                return

            # ── DM ───────────────────────────────────────────────────
            if not sender_id:
                self._respond(200, {'status': 'ok', 'reply': ''})
                return

            if interes:
                reply = _dm_interes(text, nombre)
            else:
                reply = _claude_reply(text)

            # el endpoint envía el DM directamente y devuelve el texto
            result = {'status': 'ok', 'tipo': 'dm', 'reply': reply}
            if reply:
                result['dm'] = _send_dm({'id': sender_id}, reply)
            self._respond(200, result)

        except Exception as e:
            self._respond(200, {'status': 'error', 'reply': '', 'error': str(e)})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass
