"""Endpoint de diagnóstico TEMPORAL — test de envío Instagram.

GET /test-ig-send?igsid=XXXXX   → intenta enviar mensaje de prueba al IGSID dado
                                   y devuelve el resultado crudo de Meta Graph API.

⚠️  ELIMINAR después del diagnóstico.
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.instagram import InstagramClient


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        igsid = (q.get('igsid') or [''])[0].strip()

        ig_cx_token = os.environ.get('IG_CX_PAGE_ACCESS_TOKEN', '').strip()
        ig_cx_account = os.environ.get('IG_CX_ACCOUNT_ID', '17841400339315123').strip()
        fallback_token = os.environ.get('IG_PAGE_ACCESS_TOKEN', '').strip()

        result = {
            'igsid': igsid,
            'token_source': 'IG_CX_PAGE_ACCESS_TOKEN' if ig_cx_token else 'IG_PAGE_ACCESS_TOKEN (fallback)',
            'token_len': len(ig_cx_token or fallback_token),
            'token_prefix': (ig_cx_token or fallback_token)[:20] + '...' if (ig_cx_token or fallback_token) else 'EMPTY',
            'ig_cx_account': ig_cx_account,
        }

        if not igsid:
            result['error'] = 'Falta igsid en query param'
        else:
            client = InstagramClient(
                token=ig_cx_token or fallback_token,
                account_id=ig_cx_account,
            )
            send_result = client.send_text(igsid, 'Test diagnóstico BOT440 — ignora este mensaje 🔧')
            result['send_result'] = send_result

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result, indent=2).encode())

    def log_message(self, *a): pass
