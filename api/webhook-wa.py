"""Webhook de WhatsApp Cloud API (oficial de Meta) para el número nuevo de atención (desde nov-2026).

GET  → verificación de Meta (hub.mode=subscribe, hub.verify_token = WA_META_VERIFY_TOKEN, responde hub.challenge).
POST → mensajes entrantes (entry[].changes[].value.messages[]) que se pasan a BrainCX igual que los de WHAPI.
Los avisos de estado (enviado, entregado, leído) se ignoran. La firma X-Hub-Signature-256 se revisa con WA_META_APP_SECRET.
"""
from http.server import BaseHTTPRequestHandler
import json, os, sys, hmac, hashlib, urllib.parse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain_cx import BrainCX
from core.media import store_whapi_media
from core.whatsapp_meta import media_url_meta

_IGNORAR = {'reaction', 'unsupported', 'system', 'request_welcome', 'order', 'button', 'interactive'}
_MEDIA_TIPO = {'image': 'image', 'video': 'video', 'sticker': 'image', 'document': 'document', 'audio': 'audio'}
_TEXTO_MEDIA = {'image': '[IMAGEN]', 'video': '[VIDEO]', 'sticker': '[STICKER]', 'document': '[DOCUMENTO]', 'audio': '[AUDIO]'}


def _guardar_media(obj):
    """Descarga el archivo de Meta (pide su URL temporal y la baja con el token) y lo deja en Storage."""
    if not obj or not obj.get('id'):
        return None
    tok = os.environ.get('WA_META_TOKEN', '')
    url = media_url_meta(obj['id'], tok)
    if not url:
        return None
    return store_whapi_media({'link': url, 'id': obj['id'], 'mime_type': obj.get('mime_type')}, tok, prefix='wa')


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        modo, token, reto = (q.get('hub.mode') or [''])[0], (q.get('hub.verify_token') or [''])[0], (q.get('hub.challenge') or [''])[0]
        esperado = os.environ.get('WA_META_VERIFY_TOKEN', '')
        if modo == 'subscribe' and esperado and token == esperado:
            self.send_response(200); self.send_header('Content-Type', 'text/plain'); self.end_headers()
            self.wfile.write(reto.encode()); return
        self.send_response(403); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        crudo = self.rfile.read(length)
        secreto = os.environ.get('WA_META_APP_SECRET', '')
        firma = self.headers.get('X-Hub-Signature-256', '')
        if secreto:
            esperada = 'sha256=' + hmac.new(secreto.encode(), crudo, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(esperada, firma):
                print('[WEBHOOK-WA] firma no válida', flush=True)
                self._ok({'error': 'firma'}); return
        try:
            payload = json.loads(crudo or b'{}')
            for entry in payload.get('entry', []):
                for change in entry.get('changes', []):
                    v = change.get('value', {}) or {}
                    nombres = {c.get('wa_id'): (c.get('profile') or {}).get('name', '') for c in v.get('contacts', []) or []}
                    for msg in v.get('messages', []) or []:
                        self._procesar(msg, nombres)
            self._ok({'status': 'ok'})
        except Exception as e:
            print(f"[WEBHOOK-WA] Error: {e}", flush=True)
            self._ok({'error': str(e)})

    def _procesar(self, msg, nombres):
        sender = msg.get('from', '')
        tipo = msg.get('type', 'text')
        media_url = caption = None
        if tipo == 'text':
            text = (msg.get('text') or {}).get('body', '')
        elif tipo in _TEXTO_MEDIA:
            obj = msg.get(tipo) or {}
            text = _TEXTO_MEDIA[tipo]
            caption = obj.get('caption') or obj.get('filename') or None
            media_url = _guardar_media(obj)
        elif tipo in _IGNORAR:
            print(f"[WEBHOOK-WA] tipo {tipo!r} ignorado", flush=True)
            return
        else:
            text = '[MEDIA]'
        # Llegó por un anuncio de clic a WhatsApp: Meta dice cuál (se guarda en el log para la atribución de pauta)
        ref = msg.get('referral') or {}
        if ref:
            print(f"[WEBHOOK-WA] anuncio source_id={ref.get('source_id')} headline={ref.get('headline')!r}", flush=True)
        name = nombres.get(sender, '')
        print(f"[WEBHOOK-WA] sender={sender} name={name!r} text={text[:60]!r} media={'yes' if media_url else 'no'}", flush=True)
        if text and sender:
            BrainCX().process(sender, name, text, 'cirugia', chat_id=f'{sender}@s.whatsapp.net',
                              media_url=media_url, media_tipo=_MEDIA_TIPO.get(tipo) if media_url else None,
                              media_caption=caption if media_url else None)

    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
