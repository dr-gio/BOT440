import os, json, urllib.request, urllib.error

_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440/1.0; +https://440clinic.com)'


class InstagramClient:
    """Outbound DM sender for @440clinic via Meta Graph Instagram API."""

    def __init__(self, token=None, account_id=None):
        self.base = os.environ.get('IG_GRAPH_BASE', 'https://graph.instagram.com/v18.0')
        self.token = token or os.environ.get('IG_PAGE_ACCESS_TOKEN', '')
        self.account_id = account_id or os.environ.get('IG_ACCOUNT_ID', '')
        print(f"[IG INIT] base={self.base!r} token_len={len(self.token)} account_id={self.account_id!r}", flush=True)

    def _post(self, payload):
        url = f'{self.base}/me/messages'
        print(f"[IG] POST {url} recipient={payload.get('recipient',{}).get('id','')}", flush=True)
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={
                    'Authorization': f'Bearer {self.token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': _BROWSER_UA,
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = json.loads(r.read())
                print(f"[IG] OK message_id={resp.get('message_id','')}", flush=True)
                return resp
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[IG] HTTPError {e.code} body={body!r}", flush=True)
            return {'error': f'HTTP {e.code}', 'body': body}
        except Exception as e:
            print(f"[IG] error: {e}", flush=True)
            return {'error': str(e)}

    def send_text(self, to, text):
        return self._post({
            'recipient': {'id': to},
            'message': {'text': text},
        })

    def send_image(self, to, url, caption=''):
        # IG message attachment doesn't support caption — caption sent as separate text if provided.
        first = self._post({
            'recipient': {'id': to},
            'message': {
                'attachment': {
                    'type': 'image',
                    'payload': {'url': url, 'is_reusable': True},
                },
            },
        })
        if caption:
            self._post({'recipient': {'id': to}, 'message': {'text': caption}})
        return first
