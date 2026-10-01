"""WhatsApp webhook for the Cirugía Plástica channel (+57 304 488 6085).

Same WhApi payload shape as api/webhook.py, but routes every message
to BrainCX with canal='cirugia'.
"""
from http.server import BaseHTTPRequestHandler
import json, os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain_cx import BrainCX
from core.media import store_whapi_media


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        print(f"[WEBHOOK-CX] POST recibido", flush=True)
        try:
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            messages = payload.get('messages', [])
            if not messages:
                print(f"[WEBHOOK-CX] no_messages", flush=True)
                self._ok({'status': 'no_messages'}); return
            msg = messages[0]
            if msg.get('from_me'):
                print(f"[WEBHOOK-CX] echo (from_me)", flush=True)
                self._ok({'status': 'echo'}); return
            sender_id = msg.get('from', '').replace('@s.whatsapp.net', '')
            _tipo = msg.get('type', 'text')
            _media_url = None
            _media_caption = None
            _tok = os.environ.get('WHAPI_TOKEN_CX') or os.environ.get('WHAPI_TOKEN', '')
            if _tipo == 'text':
                text = msg.get('text', {}).get('body', '')
            elif _tipo == 'image':
                text = '[IMAGEN]'
                _img = msg.get('image', {}) or {}
                _media_caption = _img.get('caption') or None
                _media_url = store_whapi_media(_img, _tok, prefix='cx')
            elif _tipo == 'video':
                text = '[VIDEO]'
                _vid = msg.get('video', {}) or {}
                _media_caption = _vid.get('caption') or None
                _media_url = store_whapi_media(_vid, _tok, prefix='cx')
            elif _tipo in ('sticker', 'reaction'):
                text = '[STICKER]'
                _stk = msg.get('sticker', {}) or {}
                _media_url = store_whapi_media(_stk, _tok, prefix='cx')
            elif _tipo == 'document':
                text = '[DOCUMENTO]'
                _doc = msg.get('document', {}) or {}
                _media_caption = _doc.get('filename') or _doc.get('caption') or None
                _media_url = store_whapi_media(_doc, _tok, prefix='cx')
            elif _tipo in ('audio', 'voice', 'ptt'):
                text = '[AUDIO]'
                _aud = msg.get(_tipo, {}) or msg.get('audio', {}) or {}
                _media_url = store_whapi_media(_aud, _tok, prefix='cx')
            else:
                text = '[MEDIA]'
            name = msg.get('from_name', '')
            print(f"[WEBHOOK-CX] sender={sender_id} name={name!r} text={text[:60]!r} media={'yes' if _media_url else 'no'}", flush=True)
            if text and sender_id:
                _media_tipo_map = {'image':'image','video':'video','sticker':'image','document':'document','audio':'audio','voice':'audio','ptt':'audio'}
                BrainCX().process(sender_id, name, text, 'cirugia',
                                  media_url=_media_url,
                                  media_tipo=_media_tipo_map.get(_tipo, 'image') if _media_url else None,
                                  media_caption=_media_caption if _media_url else None)
            print(f"[WEBHOOK-CX] Procesado OK", flush=True)
            self._ok({'status': 'ok'})
        except Exception as e:
            print(f"[WEBHOOK-CX] Error: {e}", flush=True)
            self._ok({'error': str(e)})

    def do_GET(self):
        self._ok({'status': 'BOT440-CX running'})

    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
