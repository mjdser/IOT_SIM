"""One tiny credential check; never prints keys or provider error bodies."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/ui_generator'))
import gemini_client

if '--models' in sys.argv:
    import os
    request = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models',
                                     headers={'x-goog-api-key': os.environ['GEMINI_API_KEY']})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        print('Available Flash models:', [m['name'] for m in data.get('models', [])
                                          if 'flash' in m['name'] and 'generateContent' in m.get('supportedGenerationMethods', [])])
    except urllib.error.HTTPError as exc:
        print('Model listing failed; HTTP status:', exc.code)
    raise SystemExit()

try:
    reply = gemini_client.generate('Reply with OK only.', [('user', 'Connection check.')],
                                   model='gemini-3.8-flash', timeout=30,
                                   fallback_model='', sleep=lambda _: None)
    print('Gemini authentication and model access succeeded:', reply.strip() == 'OK')
except gemini_client.GeminiError as exc:
    import re
    status = re.search(r'HTTP (\d+)', str(exc))
    print('Gemini access check failed; HTTP status:', status.group(1) if status else 'unavailable')
    print('Provider message:', exc.user_message)
    if status:
        import os
        detail = str(exc).replace(os.environ.get('GEMINI_API_KEY', ''), '[redacted]')
        print('Sanitized diagnosis:', detail[:700])

try:
    with urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=2) as response:
        status = json.load(response)
    print('Chat server:', status.get('provider'), status.get('model'), 'key configured:', status.get('key_configured'))
except (urllib.error.URLError, TimeoutError):
    print('Chat server is not running or reachable; start Start-IOT.cmd after setup.')
