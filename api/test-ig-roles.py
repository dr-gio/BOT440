"""Endpoint diagnóstico TEMPORAL — verifica y envía invitación de Tester.

GET /test-ig-roles?action=check          → lista roles de la app
GET /test-ig-roles?action=invite&uid=ID  → envía invitación de Tester al Facebook ID dado

⚠️  ELIMINAR después del diagnóstico.
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os, sys, urllib.request, urllib.error

APP_IDS = ['975100148387109', '1641188737000657']


def _graph(path, token, method='GET', data=None):
    url = f'https://graph.facebook.com/v21.0/{path}'
    if method == 'GET':
        url += ('&' if '?' in url else '?') + f'access_token={token}'
    body = None
    if data:
        body = urllib.parse.urlencode({**data, 'access_token': token}).encode()
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('User-Agent', 'BOT440-diag/1.0')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_err = ''
        try: body_err = e.read().decode()[:600]
        except: pass
        return {'http_error': e.code, 'body': body_err}
    except Exception as e:
        return {'exception': str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        action = (q.get('action') or ['check'])[0]
        uid = (q.get('uid') or [''])[0].strip()

        token_cx = os.environ.get('IG_CX_PAGE_ACCESS_TOKEN', '').strip()
        token_main = os.environ.get('IG_PAGE_ACCESS_TOKEN', '').strip()
        token = token_cx or token_main

        result = {
            'token_source': 'IG_CX_PAGE_ACCESS_TOKEN' if token_cx else 'IG_PAGE_ACCESS_TOKEN',
            'token_prefix': token[:20] + '...' if token else 'EMPTY',
        }

        if action == 'check':
            for app_id in APP_IDS:
                roles = _graph(f'{app_id}/roles?access_token={token}', token)
                result[f'roles_{app_id}'] = roles

        elif action == 'invite' and uid:
            for app_id in APP_IDS:
                import urllib.parse
                url = f'https://graph.facebook.com/v21.0/{app_id}/roles'
                body = urllib.parse.urlencode({
                    'user': uid,
                    'role': 'testers',
                    'access_token': token,
                }).encode()
                req = urllib.request.Request(url, data=body, method='POST')
                req.add_header('User-Agent', 'BOT440-diag/1.0')
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        result[f'invite_{app_id}'] = json.loads(r.read())
                except urllib.error.HTTPError as e:
                    err = ''
                    try: err = e.read().decode()[:600]
                    except: pass
                    result[f'invite_{app_id}'] = {'http_error': e.code, 'body': err}
                except Exception as e:
                    result[f'invite_{app_id}'] = {'exception': str(e)}
        else:
            result['error'] = 'action debe ser check o invite&uid=FacebookID'

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result, indent=2).encode())

    def log_message(self, *a): pass
