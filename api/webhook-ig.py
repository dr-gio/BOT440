"""Instagram (Meta Graph) webhook endpoint for BOT440.

GET  /webhook-ig  → handles Meta's subscription verification (hub.challenge).
POST /webhook-ig  → receives messaging events and processes them via Brain.

Expected env vars:
  IG_VERIFY_TOKEN       — string used to verify the subscription in Meta.
  IG_PAGE_ACCESS_TOKEN  — used by core/instagram.py to send replies.
  IG_ACCOUNT_ID         — optional; if set, only events targeting this page
                          ID are processed (echo guard).
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain import Brain

# Map IG page IDs → slug (matches the value W20 writes and CORE440 reads).
# Keep in sync with CORE440's IG_CUENTAS map.
_IG_PAGE_TO_SLUG = {
    '17841457278507530': '440clinic',
    '27130606726557229': '440clinic',
    '35111588048488167': '440clinic',
    '26640901062231544': 'drgiovannifuentes',
    '26562617856680827': 'drgiovannifuentes',
    '17841400339315123': 'drgiovannifuentes',
}


def _extract_event(payload):
    """Return list of (igsid, page_id, text, from_name) tuples extracted from a Meta IG payload."""
    out = []
    if not isinstance(payload, dict):
        return out
    for entry in payload.get('entry', []) or []:
        page_id = entry.get('id', '')
        # Both 'messaging' (Instagram Messenger Platform) and 'changes' (legacy)
        msgs = entry.get('messaging', []) or []
        for m in msgs:
            sender = (m.get('sender') or {}).get('id', '')
            recipient = (m.get('recipient') or {}).get('id', page_id)
            message = m.get('message') or {}
            # Skip echo (the page itself sending) and read/delivery receipts
            if message.get('is_echo'):
                continue
            if 'read' in m or 'delivery' in m:
                continue
            text = message.get('text', '')
            if not text:
                # ignore attachments-only for now (mark as media for the Brain)
                if message.get('attachments'):
                    text = '[MEDIA]'
                else:
                    continue
            out.append({
                'igsid': sender,
                'page_id': recipient,
                'text': text,
                'from_name': '',  # Meta doesn't include profile name in webhook
            })
    return out


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[WEBHOOK-IG] GET {self.path}", flush=True)
        try:
            q = parse_qs(urlparse(self.path).query)
            mode = (q.get('hub.mode') or [''])[0]
            verify_token = (q.get('hub.verify_token') or [''])[0]
            challenge = (q.get('hub.challenge') or [''])[0]
            expected = os.environ.get('IG_VERIFY_TOKEN', '')
            if mode == 'subscribe' and verify_token and verify_token == expected:
                print(f"[WEBHOOK-IG] verification OK", flush=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(challenge.encode())
                return
            print(f"[WEBHOOK-IG] verification FAIL mode={mode!r} token_match={verify_token == expected}", flush=True)
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error":"verification failed"}')
        except Exception as e:
            print(f"[WEBHOOK-IG] GET error: {e}", flush=True)
            self._ok({'error': str(e)})

    def do_POST(self):
        print(f"[WEBHOOK-IG] POST recibido", flush=True)
        try:
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            if payload.get('object') and payload.get('object') != 'instagram':
                print(f"[WEBHOOK-IG] ignoring object={payload.get('object')!r}", flush=True)
                self._ok({'status': 'ignored'}); return
            expected_account = os.environ.get('IG_ACCOUNT_ID', '')
            events = _extract_event(payload)
            print(f"[WEBHOOK-IG] events={len(events)}", flush=True)
            for ev in events:
                if expected_account and ev['page_id'] and ev['page_id'] != expected_account:
                    print(f"[WEBHOOK-IG] skip — page_id={ev['page_id']} != expected {expected_account}", flush=True)
                    continue
                # Slug for cuenta_receptora — matches what W20 writes and what
                # the CORE440 frontend filters by. Fall back to expected_account
                # if the map doesn't know this page_id, then to '440clinic'
                # since this BOT serves only @440clinic.
                cuenta = (
                    _IG_PAGE_TO_SLUG.get(ev['page_id'])
                    or _IG_PAGE_TO_SLUG.get(expected_account)
                    or '440clinic'
                )
                print(f"[WEBHOOK-IG] igsid={ev['igsid']} cuenta={cuenta!r} text={ev['text'][:60]!r}", flush=True)
                if ev['text'] and ev['igsid']:
                    Brain().process(ev['igsid'], ev['from_name'], ev['text'], 'instagram',
                                    cuenta_receptora=cuenta)
            print(f"[WEBHOOK-IG] Procesado OK", flush=True)
            self._ok({'status': 'ok'})
        except Exception as e:
            print(f"[WEBHOOK-IG] Error: {e}", flush=True)
            self._ok({'error': str(e)})

    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
