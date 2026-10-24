import os, json, urllib.request, urllib.error

class WhapiClient:
    def __init__(self, token=None, base=None):
        # token/base optional overrides — used by the cirugía channel which
        # may have its own WhApi channel (WHAPI_TOKEN_CX). Falls back to the
        # default estética channel env vars.
        self.base = base or os.environ.get('WHAPI_URL', 'https://gate.whapi.cloud')
        self.token = token or os.environ.get('WHAPI_TOKEN', '')
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (compatible; BOT440/1.0; +https://440clinic.com)'
        }
        print(f"[WHAPI INIT] base={self.base!r} token_len={len(self.token)}", flush=True)

    def send_text(self, to, text):
        to = to.replace('+','').replace(' ','')
        payload = {'to': to, 'body': text}
        return self._post('/messages/text', payload)

    def send_image(self, to, url, caption=''):
        to = to.replace('+','').replace(' ','')
        return self._post('/messages/image', {'to':to,'media':url,'caption':caption})

    def numero_de_lid(self, lid):
        """Número real de un contacto que WhatsApp identifica con "LID" (número oculto, ej. 147484932362413@lid).
        Solo funciona si WhatsApp ya lo compartió con este número; si no, devuelve ''."""
        import re, urllib.parse
        lid = str(lid or '')
        if not lid:
            return ''
        if '@' not in lid:
            lid += '@lid'
        try:
            req = urllib.request.Request(f"{self.base}/contacts/ids/{urllib.parse.quote(lid, safe='')}", headers=self.headers, method='GET')
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read() or b'{}')
        except Exception as e:
            print(f"[WHAPI] LID {lid} sin número: {e}", flush=True)
            return ''
        propio = re.sub(r'\D', '', lid.split('@')[0])
        for v in (data.get('phone'), data.get('id'), (data.get('contact') or {}).get('id') if isinstance(data.get('contact'), dict) else None):
            v = str(v or '')
            if v.endswith('@lid'):
                continue
            d = re.sub(r'\D', '', v.split('@')[0])
            if 10 <= len(d) <= 15 and d != propio:
                return d
        return ''

    def _post(self, endpoint, payload):
        url = f'{self.base}{endpoint}'
        print(f"[WHAPI] POST {url} to={payload.get('to')} body_len={len(str(payload.get('body','')))}", flush=True)
        try:
            req = urllib.request.Request(
                url,
                json.dumps(payload).encode(),
                self.headers, method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = json.loads(r.read())
                print(f"[WHAPI] OK sent={resp.get('sent')} id={(resp.get('message') or {}).get('id','')}", flush=True)
                return resp
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:300]
            except: pass
            print(f"[WHAPI] HTTPError {e.code} body={body!r}", flush=True)
            return {'error': f'HTTP {e.code}', 'body': body}
        except Exception as e:
            print(f'[WHAPI] Error: {e}', flush=True)
            return {'error': str(e)}
