"""Instagram (Meta Graph) webhook endpoint for BOT440-CX — @drgiovannifuentes DMs.

GET  /webhook-ig-cx  → handles Meta's subscription verification (hub.challenge).
POST /webhook-ig-cx  → receives messaging events and processes them via BrainCX.

Expected env vars:
  IG_VERIFY_TOKEN       — same verify token used by /webhook-ig.
  IG_CX_PAGE_ACCESS_TOKEN or IG_PAGE_ACCESS_TOKEN — used to send replies.
  DRGIO_IG_ACCOUNT_ID   — optional; page_id for @drgiovannifuentes (17841400339315123).
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain_cx import BrainCX

_DRGIO_PAGE_IDS = {
    '26640901062231544',
    '26562617856680827',
    '17841400339315123',
}


def _extract_event(payload):
    """Return list of event dicts from a Meta IG payload OR a W20 pre-parsed event.

    W20's 'Code — Parsear evento IG' node emits:
      {tipo, sender_id, recipient_id, text, ig_account_id, ...}
    Raw Meta webhook format:
      {object:'instagram', entry:[{messaging:[...]}]}
    """
    out = []
    if not isinstance(payload, dict):
        return out

    # ── W20 pre-parsed format ──────────────────────────────────────────
    if 'sender_id' in payload and 'tipo' in payload:
        tipo = payload.get('tipo', '')
        if tipo != 'dm':
            return out  # ignore comments etc.
        sender = str(payload.get('sender_id', ''))
        page_id = str(payload.get('recipient_id', '') or payload.get('ig_account_id', ''))
        text = payload.get('text', '')
        if sender and text:
            out.append({'igsid': sender, 'page_id': page_id, 'text': text, 'from_name': ''})
        return out

    # ── Raw Meta webhook format ────────────────────────────────────────
    for entry in payload.get('entry', []) or []:
        page_id = entry.get('id', '')
        msgs = entry.get('messaging', []) or []
        for m in msgs:
            sender = (m.get('sender') or {}).get('id', '')
            recipient = (m.get('recipient') or {}).get('id', page_id)
            message = m.get('message') or {}
            if message.get('is_echo'):
                continue
            if 'read' in m or 'delivery' in m:
                continue
            text = message.get('text', '')
            if not text:
                if message.get('attachments'):
                    text = '[MEDIA]'
                else:
                    continue
            out.append({'igsid': sender, 'page_id': recipient, 'text': text, 'from_name': ''})
    return out


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[WEBHOOK-IG-CX] GET {self.path}", flush=True)
        try:
            q = parse_qs(urlparse(self.path).query)
            mode = (q.get('hub.mode') or [''])[0]
            verify_token = (q.get('hub.verify_token') or [''])[0]
            challenge = (q.get('hub.challenge') or [''])[0]
            expected = os.environ.get('IG_VERIFY_TOKEN', '')
            if mode == 'subscribe' and verify_token and verify_token == expected:
                print(f"[WEBHOOK-IG-CX] verification OK", flush=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(challenge.encode())
                return
            print(f"[WEBHOOK-IG-CX] verification FAIL", flush=True)
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error":"verification failed"}')
        except Exception as e:
            print(f"[WEBHOOK-IG-CX] GET error: {e}", flush=True)
            self._ok({'error': str(e)})

    def do_POST(self):
        print(f"[WEBHOOK-IG-CX] POST recibido", flush=True)
        try:
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            if payload.get('object') and payload.get('object') != 'instagram':
                print(f"[WEBHOOK-IG-CX] ignoring object={payload.get('object')!r}", flush=True)
                self._ok({'status': 'ignored'}); return
            events = _extract_event(payload)
            print(f"[WEBHOOK-IG-CX] events={len(events)}", flush=True)
            reply_text = ''
            for ev in events:
                if not ev['igsid'] or not ev['text']:
                    continue
                print(f"[WEBHOOK-IG-CX] igsid={ev['igsid']} page_id={ev['page_id']} text={ev['text'][:60]!r}", flush=True)
                # send=False → BrainCX devuelve el texto, W20 se encarga de enviarlo via IG
                reply_text = BrainCX().process(ev['igsid'], ev['from_name'], ev['text'], 'instagram_cx',
                                               cuenta_receptora='drgiovannifuentes', send=False)
            print(f"[WEBHOOK-IG-CX] Procesado OK reply_len={len(reply_text)}", flush=True)
            self._ok({'status': 'ok', 'reply': reply_text})
        except Exception as e:
            print(f"[WEBHOOK-IG-CX] Error: {e}", flush=True)
            self._ok({'error': str(e)})

    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
