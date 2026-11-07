"""OpenAI-compatible chat client for Kit's one-pass turn.

The client is the voice. It is not the rules engine, and it is not the
paid ``kit_agent play`` command. Any base URL the player configures is
called here: a local llama-server, or a no-cost hosted endpoint.
"""
import json
import re
import urllib.error
import urllib.request


class ModelError(Exception):
    pass


SYSTEM = (
    'You are the voice model inside Kit\'s table host. The packet is authoritative. '
    'Return one JSON object and nothing else, with the keys "decision" and "performance". '
    'No markdown fence. Performance text is what the player hears. It must not contain '
    'difficulty classes, hidden motives, unrevealed facts, or the private decision fields.'
)


def parse_model_json(text):
    raw = (text or '').strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find('{'), raw.rfind('}')
        if start < 0 or end <= start:
            raise ModelError('model did not return a JSON object')
        try:
            value = json.loads(raw[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ModelError('model returned invalid JSON') from exc
    if not isinstance(value, dict):
        raise ModelError('model JSON was not an object')
    return value


class ModelClient:
    def __init__(self, base_url='', model='', api_key='', timeout=180):
        self.base_url = (base_url or '').strip().rstrip('/')
        self.model = (model or '').strip()
        self.api_key = (api_key or '').strip()
        self.timeout = timeout

    @property
    def configured(self):
        return bool(self.base_url and self.model)

    def warn(self):
        host = self.base_url.lower()
        if 'api.openai.com' in host:
            return ('That base URL is OpenAI\'s paid API. This table does not require it, '
                    'and the ChatGPT app is not this API.')
        return ''

    def complete(self, packet, correction=None):
        if not self.configured:
            raise ModelError('no voice model is configured')
        if not (self.base_url.startswith('http://') or self.base_url.startswith('https://')):
            raise ModelError('the model base URL must start with http:// or https://')
        user = 'PACKET\n' + json.dumps(packet, ensure_ascii=False)
        if correction:
            user += '\n\nThe engine rejected the previous object. Fix every problem and return the whole object again.\n' + correction
        body = {
            'model': self.model,
            'temperature': 0.2,
            'max_tokens': 1800,
            'messages': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': user},
            ],
        }
        return self._post(body, with_json_mode=True)

    def _post(self, body, with_json_mode):
        payload = dict(body)
        if with_json_mode:
            payload['response_format'] = {'type': 'json_object'}
        data = json.dumps(payload).encode('utf-8')
        url = self.base_url + '/chat/completions'
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = 'Bearer ' + self.api_key
        request = urllib.request.Request(url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')[:500]
            if with_json_mode and exc.code == 400 and 'response_format' in detail:
                return self._post(body, with_json_mode=False)
            raise ModelError(f'model HTTP {exc.code}') from exc
        except urllib.error.URLError as exc:
            raise ModelError('the voice model could not be reached') from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ModelError('model endpoint returned non-JSON') from exc
        try:
            content = parsed['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError('model endpoint returned no message') from exc
        return parse_model_json(content)
