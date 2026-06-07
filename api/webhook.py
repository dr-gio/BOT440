from http.server import BaseHTTPRequestHandler
import json, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain import Brain
from core.media import store_whapi_media

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        print(f"[WEBHOOK] POST recibido", flush=True)
        try:
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            messages = payload.get('messages', [])
            if not messages:
                print(f"[WEBHOOK] no_messages", flush=True)
                self._ok({'status': 'no_messages'}); return
            msg = messages[0]
            if msg.get('from_me'):
                print(f"[WEBHOOK] echo (from_me)", flush=True)
                self._ok({'status': 'echo'}); return
            sender_id = msg.get('from','').replace('@s.whatsapp.net','')
            _tipo = msg.get('type', 'text')
            _media_url = None
            _media_caption = None
            if _tipo == 'text':
                text = msg.get('text', {}).get('body', '')
            elif _tipo == 'image':
                text = '[IMAGEN]'
                _img = msg.get('image', {}) or {}
                _media_caption = _img.get('caption') or None
                _tok = os.environ.get('WHAPI_TOKEN') or os.environ.get('WHAPI_TOKEN_CX', '')
                _media_url = store_whapi_media(_img, _tok, prefix='est')
            else:
                text = '[MEDIA]'
            name = msg.get('from_name','')
            print(f"[WEBHOOK] sender={sender_id} name={name!r} text={text[:60]!r} media={'yes' if _media_url else 'no'}", flush=True)
            if text and sender_id:
                Brain().process(sender_id, name, text, 'whatsapp',
                                media_url=_media_url,
                                media_tipo='image' if _media_url else None,
                                media_caption=_media_caption if _media_url else None)
            print(f"[WEBHOOK] Procesado OK", flush=True)
            self._ok({'status': 'ok'})
        except Exception as e:
            print(f"[WEBHOOK] Error: {e}", flush=True)
            self._ok({'error': str(e)})
    def do_GET(self):
        self._ok({'status': 'BOT440 running'})
    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def log_message(self, *a): pass
