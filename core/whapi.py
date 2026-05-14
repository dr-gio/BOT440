import os, json, urllib.request

class WhapiClient:
    def __init__(self):
        self.base = os.environ.get('WHAPI_URL','https://gate.whapi.cloud')
        self.token = os.environ.get('WHAPI_TOKEN','')
        self.headers = {'Authorization':f'Bearer {self.token}','Content-Type':'application/json'}
    
    def send_text(self, to, text):
        to = to.replace('+','').replace(' ','')
        payload = {'to': to, 'body': text}
        return self._post('/messages/text', payload)
    
    def send_image(self, to, url, caption=''):
        to = to.replace('+','').replace(' ','')
        return self._post('/messages/image', {'to':to,'media':url,'caption':caption})
    
    def _post(self, endpoint, payload):
        try:
            req = urllib.request.Request(
                f'{self.base}{endpoint}',
                json.dumps(payload).encode(),
                self.headers, method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f'[WHAPI] Error: {e}')
            return {'error': str(e)}
