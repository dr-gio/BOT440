import os, json, urllib.request, urllib.error

class WhapiClient:
    def __init__(self):
        self.base = os.environ.get('WHAPI_URL','https://gate.whapi.cloud')
        self.token = os.environ.get('WHAPI_TOKEN','')
        self.headers = {'Authorization':f'Bearer {self.token}','Content-Type':'application/json'}
        print(f"[WHAPI INIT] base={self.base!r} token_len={len(self.token)}", flush=True)

    def send_text(self, to, text):
        to = to.replace('+','').replace(' ','')
        payload = {'to': to, 'body': text}
        return self._post('/messages/text', payload)

    def send_image(self, to, url, caption=''):
        to = to.replace('+','').replace(' ','')
        return self._post('/messages/image', {'to':to,'media':url,'caption':caption})

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
