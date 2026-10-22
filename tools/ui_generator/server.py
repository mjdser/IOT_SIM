"""Local web UI: describe the interface you want, then keep asking for changes.

    python tools/ui_generator/server.py            # then open http://127.0.0.1:8765

The user only sees plain-language messages. Code, rule violations and compiler
output stay in this terminal (the developer log).

A session remembers the conversation, so follow-ups ("make the button bigger")
change the current interface instead of starting over. Sessions live on the
server, so refreshing the page keeps the conversation.

Listens on 127.0.0.1 only. Requests from other websites are rejected, because
this server can call Gemini with your key and flash the board.
"""

import json
import os
import re
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gemini_client
import pipeline

HOST, PORT = "127.0.0.1", 8765
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
MAX_REQUEST_CHARS = 2000
MAX_HISTORY_TURNS = 4  # earlier (request, code) pairs sent back to Gemini
MAX_CHAT_MESSAGES = 200
FLASH = os.environ.get("FLASH", "0") != "0"  # default: compile + test PC LVGL, never flash
TESTS = os.environ.get("TESTS", "1") != "0"  # set TESTS=0 to flash without running the tests
UPLOAD_PORT = os.environ.get("UPLOAD_PORT")

WELCOME = "Hi! Tell me what interface you want on the screen, and I'll build it. You can ask for changes afterwards."

busy = threading.Lock()
sessions = {}  # sid -> {"history": [(role, text)], "chat": [{"who", "text"}]}
sessions_lock = threading.Lock()
SID_RE = re.compile(r"^[0-9a-f]{16}$")
CHAT_CACHE = pipeline.ROOT / 'simulator/build/chat-sessions.json'
cache_enabled = False  # Enabled for the running server, not imported unit tests.

def save_sessions():
    if not cache_enabled: return
    with sessions_lock:
        CHAT_CACHE.parent.mkdir(parents=True, exist_ok=True)
        temp = CHAT_CACHE.with_suffix('.tmp')
        temp.write_text(json.dumps(sessions, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, CHAT_CACHE)

def restore_sessions():
    try:
        saved = json.loads(CHAT_CACHE.read_text(encoding='utf-8'))
        for sid, session in saved.items():
            if not SID_RE.fullmatch(sid) or not isinstance(session.get('chat'), list): continue
            if session.get('running'):
                session['chat'].append({'who':'bot', 'text':'The previous run was interrupted. Saved attempts and the last accepted interface are preserved.', 'err':True})
            session['running'] = False
            sessions[sid] = session
    except (OSError, ValueError, TypeError, AttributeError): pass

PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Screen designer</title>
<style>
  body { font: 15px system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 1rem;
         display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
  header { display: flex; justify-content: space-between; align-items: center; }
  h1 { font-size: 1.2rem; margin: .2rem 0; }
  #chat { flex: 1; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px; padding: .75rem; margin: .5rem 0; }
  .msg { margin: .4rem 0; padding: .55rem .8rem; border-radius: 10px; max-width: 85%; white-space: pre-wrap; }
  .user { background: #dbeafe; margin-left: auto; }
  .bot { background: #f1f1f1; }
  .bot.err { background: #fde2e2; }
  form { display: flex; gap: .5rem; }
  textarea { flex: 1; font: inherit; padding: .5rem; height: 3.2rem; resize: none; }
  button { font: inherit; padding: .4rem 1rem; }
</style>
<header><h1>Screen designer</h1><button id="reset" type="button">Start over</button></header>
<p id="target" style="font-size:12px;color:#52606b">PC simulator · board flashing off</p>
<div id="chat"></div>
<button id="retry" type="button" hidden>Continue repairing the failed version</button>
<form id="form">
  <textarea id="req" placeholder="Describe the screen, or ask for a change..." maxlength="2000"></textarea>
  <button id="send">Send</button>
</form>
<script>
const $ = id => document.getElementById(id);
let sid = null;
try { sid = localStorage.getItem("sid"); } catch (e) {}

function add(who, text, err) {
  const d = document.createElement("div");
  d.className = "msg " + (who === "user" ? "user" : "bot") + (err ? " err" : "");
  d.textContent = text;
  $("chat").appendChild(d);
  $("chat").scrollTop = $("chat").scrollHeight;
  return d;
}
async function api(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                body: JSON.stringify(body) });
  return r.json();
}
async function load(reset) {
  const j = await api(reset ? "/api/reset" : "/api/session", { sid });
  sid = j.sid;
  try { localStorage.setItem("sid", sid); } catch (e) {}
  $("chat").textContent = "";
  j.chat.forEach(m => add(m.who, m.text, m.err));
  $('retry').hidden=!j.can_repair;
}
$("reset").onclick = () => load(true);
$('retry').onclick = () => { $('req').value='Continue repairing the last failed interface. Preserve the original requirements.'; $('form').requestSubmit(); };
$("req").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("form").requestSubmit(); }
});
$("form").onsubmit = async e => {
  e.preventDefault();
  const text = $("req").value.trim();
  if (!text) return;
  $("req").value = "";
  add("user", text);
  $("send").disabled = true;
  $('retry').hidden=true;
  const wait = add("bot", "Working on it... building and testing on the screen takes a few minutes.");
  const progressTimer = setInterval(async () => {
    try {
      const p = await api('/api/progress', {sid});
      if (p.running && p.progress) wait.textContent = p.progress;
    } catch (e) {}
  }, 500);
  try {
    const j = await api("/api/generate", { sid, request: text });
    wait.textContent = j.message;
    if (!j.ok) wait.classList.add("err");
    $('retry').hidden=j.ok||!j.can_repair;
    if (j.sid && j.sid !== sid) {
      sid = j.sid;
      try { localStorage.setItem("sid", sid); } catch (e) {}
    }
  } catch (err) {
    wait.textContent = "Something went wrong talking to the tool. Please try again.";
    wait.classList.add("err");
  }
  $("send").disabled = false;
  clearInterval(progressTimer);
};
load(false);
fetch('/api/status').then(r=>r.json()).then(s=>{
  $('target').textContent=s.target+' · '+s.provider+(s.model?' / '+s.model:'')+' · '+(s.key_configured?'API key configured':'API key missing: edit .env')+' · '+(s.flash?'board flashing enabled':'board flashing off')+(s.vision_judge?' · image review on':'');
});
</script>
"""


def friendly_failure(exc):
    """User-facing text for an exception. The technical detail is only logged."""
    if isinstance(exc, gemini_client.GeminiError):
        return exc.user_message
    if isinstance(exc,RuntimeError) and 'Another generation is already' in str(exc):
        return 'A local generation is already running. Please wait for it to finish; your interface is preserved.'
    return "The build tools aren't available on this computer."


def get_session(sid):
    with sessions_lock:
        if not sid or not SID_RE.match(sid) or sid not in sessions:
            sid = secrets.token_hex(8)
            sessions[sid] = {"history": [], "chat": [{"who": "bot", "text": WELCOME}]}
        return sid, sessions[sid]


def add_chat(session, who, text, err=False):
    session["chat"].append({"who": who, "text": text, "err": err})
    del session["chat"][:-MAX_CHAT_MESSAGES]


def developer_log(line):
    sys.stderr.write("[generator] " + line + "\n")


def result_message(result):
    """Plain-language summary of a pipeline.Result for the user."""
    message = _result_message(result)
    if result.not_possible:
        message += "\n\nWhat this screen can't do:\n" + "\n".join(
            f"- {x['item']}: {x['why']}" for x in result.not_possible)
    return message


def _result_message(result):
    more = " Tell me if you want anything changed."
    if result.target == 'hardware_capture':
        if result.ok and result.tests == 'passed':
            return (f"Done! The real ESP32 passed {result.checks_total} checks. "
                    + (f"The image judge reviewed {result.photos} device screenshots. " if result.visual else "Image judging was disabled. ")
                    + "The PC displays pixels rendered by the board; no camera or CPU simulation is used.")
        return "The firmware was uploaded but hardware checks did not complete: " + result.problem
    if result.target == 'host' and result.ok:
        colours = (' Checked in dark first, then switched to the requested light colours.'
                   if result.theme == 'light' and result.palette_mode=='both' else ' Showing the tested white/light colours.' if result.theme=='light' else ' Showing the tested dark colours.')
        return (f"Done! Your interface passed {result.checks_total} PC checks and is ready on the simulated glass."
                + (f' The image judge also reviewed {result.photos} framebuffer captures.' if result.visual else '')
                + colours + "\nReady for real board: pio run -e lvgl_ui_test -t upload"
                + "\nThis uses the same generated_ui.cpp; the ESP32 binary is compiled separately." + more)
    if result.ok and result.theme_wanted == "light":
        if result.theme == "light" and result.tests == "passed":
            more = (" I checked it in dark colours, which the camera sees best, then switched it to "
                    "the light colours you asked for." + more)
        elif result.theme != "light" and result.tests == "passed":
            more = (" It's showing dark colours for now: the light version didn't pass its final "
                    "check, so I kept the version that did." + more)
        elif result.theme != "light" and result.tests == "not_run":
            more = " It stays in dark colours until the checks can run." + more
    if result.ok and result.tests == "passed":
        photos = f", including {result.photos} photos of the screen" if result.photos else ""
        return f"Done! Your interface is on the screen and passed all {result.checks_total} checks{photos}." + more
    if result.ok and result.tests == "not_run":
        if "Camera" in result.problem or "camera" in result.problem:
            why = ("the camera couldn't see the screen properly. If the camera preview or another "
                   "app (Zoom, Teams) is open, close it and ask again")
        else:
            why = "the board didn't answer. Check the USB cable and ask again"
        return ("I sent your interface to the board, but couldn't check it: " + why + "." + more)
    if result.ok and result.flashed:
        return "Done! Your interface is on the screen." + more
    if result.ok:
        return "Done! Your interface is built (not sent to the board)." + more
    if result.reply:
        return "The interface is ready, but I couldn't send it to the board. Check the USB cable and try again."
    if result.tests == "failed":
        details = []
        for f in (result.failures or [])[:3]:
            details.append(f"{f.get('test', 'Test')}: expected {f.get('expected', '')}; got {f.get('actual', '')}.")
        return (f"The candidate passed {result.checks_passed}/{result.checks_total} checks. Your previous interface is preserved."
                + ('\nFailed checks:\n' + '\n'.join(details) if details else '')
                + f"\nRepair limit reached ({pipeline.MAX_ATTEMPTS} attempts). Continue repairing to resume from the failed code and diagnostics."
                + "\nThe attempt and test evidence are saved locally.")
    return ("The candidate failed validation or compilation. Your previous interface is preserved."
            + ('\n' + result.problem[:1600] if result.problem else '')
            + "\nThe attempt is saved locally.")


def handle_generate(sid, request):
    """Runs one turn. Returns the plain-language reply for the user."""
    gemini_client.load_dotenv()  # Allow a missing key to be added locally after server startup.
    sid, session = get_session(sid)
    sync_accepted_source(session)
    add_chat(session, "user", request)
    _, user_text = pipeline.build_messages(request, session["history"])
    session['running'] = True
    session['progress'] = 'Generating the candidate interface…'
    save_sessions()
    def progress_log(line):
        developer_log(line)
        # Show stages and test actions, keeping raw host output in the terminal.
        if line.startswith(('Attempt ', 'Rule check ', 'Rejected by rule check', 'Compile failed',
                            'Compiled successfully', 'Flashing', 'Flashed', 'Running the tests', 'Tests:', 'Running the same', 'Initial render', 'Test:',
                            'Test ', 'Host tests:', 'Dark checks', 'Giving up', 'Ready for real board', 'Repair needed', 'Repair budget', 'Light palette failed','Image judge:')):
            session['progress'] = line.split('\n')[0]

    try:
        result = pipeline.run(
            request + ('\nPresentation preference: use a white/light background by default. Test the selected palette only unless SIM_TEST_PALETTES=both was configured. Keep compile-time palette differences limited to colours.' if not FLASH and os.environ.get('UI_PRESENTATION_THEME') == 'light' and not re.search(r'\b(?:keep|use|prefer|want|make)\b.{0,20}\b(?:dark|black)\b',request,re.I) else ''), flash=FLASH, port=UPLOAD_PORT, log=progress_log,
            history=list(session.get('repair_history') or session['history']) if re.search(r'continue repairing|retry|redo',request,re.I) else list(session['history']), test=TESTS,
            presentation_theme=('light' if not FLASH and os.environ.get('UI_PRESENTATION_THEME')=='light' and not re.search(r'\b(?:keep|use|prefer|want|make)\b.{0,20}\b(?:dark|black)\b',request,re.I) else None)
        )
    except (gemini_client.GeminiError, RuntimeError) as e:
        developer_log(f"error: {e}")
        message, ok = friendly_failure(e), False
    else:
        ok = result.ok
        if ok and result.source_sha256:session['source_sha256']=result.source_sha256
        session['repair_history'] = result.repair_history if not ok else None
        if result.reply:  # accepted, so it is now the current interface even if flashing failed
            session["history"] += [("user", user_text), ("model", result.reply)]
            del session["history"][: -2 * MAX_HISTORY_TURNS]
        message = result_message(result)

    session['running'] = False
    session['progress'] = message
    add_chat(session, "bot", message, err=not ok)
    save_sessions()
    return ok, message, sid

def sync_accepted_source(session):
    """Keep follow-up edits based on the actual glass after a CLI repair/review."""
    if FLASH or not cache_enabled or not session.get('history'):return
    try:
        manifest=json.loads(pipeline.host_sim.ACTIVE.read_text(encoding='utf-8'))
        sha=manifest['source_sha256']
        if sha==session.get('source_sha256') or pipeline.host_sim.digest(pipeline.TARGET)!=sha:return
        reply=pipeline.spec_module.join_reply(pipeline.TARGET.read_text(encoding='utf-8'),pipeline.SPEC_FILE.read_text(encoding='utf-8'))
        for index in range(len(session['history'])-1,-1,-1):
            if session['history'][index][0]=='model':
                session['history'][index]=('model',reply);session['source_sha256']=sha;break
    except (OSError,ValueError,KeyError):return


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _trusted(self) -> bool:
        if self.headers.get("Host") not in ALLOWED_HOSTS:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {f"http://{h}" for h in ALLOWED_HOSTS}

    def do_GET(self):
        if os.environ.get('IOT_TARGET') == 'hardware_capture' and self._trusted() and self.path in ('/hardware', '/api/hardware'):
            import hardware_target
            if self.path == '/hardware':
                return self._send(200, (pipeline.ROOT/'hardware/index.html').read_text(encoding='utf-8'), 'text/html')
            return self._send(200, json.dumps(hardware_target.runtime.status()))
        if self.path == "/" and self._trusted():
            self._send(200, PAGE, "text/html")
        elif self.path == '/api/status' and self._trusted():
            gemini_client.load_dotenv()
            provider=os.environ.get('GENERATOR_PROVIDER','gemini')
            self._send(200,json.dumps({'target':'Real ESP32 / USB screenshots' if os.environ.get('IOT_TARGET')=='hardware_capture' else 'board' if FLASH else 'PC simulator',
                'project':str(pipeline.ROOT),
                'flash':FLASH,'provider':provider,'model':os.environ.get('OPENAI_MODEL' if provider=='openai' else 'GEMINI_MODEL',''),
                'vision_judge':(not FLASH or os.environ.get('IOT_TARGET')=='hardware_capture') and os.environ.get('SIM_VISION_JUDGE','0')!='0',
                'key_configured':bool(os.environ.get('OPENAI_API_KEY' if provider=='openai' else 'GEMINI_API_KEY'))}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path == '/api/hardware/action' and os.environ.get('IOT_TARGET') == 'hardware_capture':
            if not self._trusted() or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self._send(403, json.dumps({'error':'forbidden'}))
            try:
                size=int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2048: raise ValueError('Invalid request size')
                import hardware_target
                result=hardware_target.runtime.action(json.loads(self.rfile.read(size)))
                return self._send(200,json.dumps(result))
            except Exception as exc:
                return self._send(400,json.dumps({'error':str(exc)}))
        if self.path not in ("/api/session", "/api/reset", "/api/generate", "/api/progress") or not self._trusted():
            return self._send(403, json.dumps({"error": "forbidden"}))
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self._send(415, json.dumps({"error": "JSON only"}))
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(min(length, 10_000)))
            if not isinstance(payload, dict):
                raise ValueError
            sid = payload.get("sid")
            sid = sid if isinstance(sid, str) else None
        except (ValueError, TypeError):
            return self._send(400, json.dumps({"error": "bad request"}))

        if self.path == '/api/progress':
            with sessions_lock:
                session = sessions.get(sid, {})
                return self._send(200, json.dumps({'running':session.get('running',False), 'progress':session.get('progress','')}))
        if self.path == "/api/reset":
            with sessions_lock:
                sessions.pop(sid, None)
            save_sessions()
            sid = None
        if self.path in ("/api/session", "/api/reset"):
            sid, session = get_session(sid)
            return self._send(200, json.dumps({"sid": sid, "chat": session["chat"],"can_repair":bool(session.get('repair_history'))}))

        request = payload.get("request")
        if not isinstance(request, str) or not request.strip() or len(request) > MAX_REQUEST_CHARS:
            return self._send(400, json.dumps({"error": f"request must be 1-{MAX_REQUEST_CHARS} characters"}))
        if not busy.acquire(blocking=False):
            return self._send(409, json.dumps({
                "ok": False, "message": "I'm still working on the previous request. Please wait a moment."}))
        try:
            ok, message, sid = handle_generate(sid, request.strip())
            self._send(200, json.dumps({"ok": ok, "message": message, "sid": sid,"can_repair":bool(sessions.get(sid,{}).get('repair_history'))}))
        finally:
            busy.release()

    def log_message(self, fmt, *args):
        if self.path=='/api/progress':return
        sys.stderr.write("[server] " + fmt % args + "\n")


if __name__ == "__main__":
    cache_enabled = True
    restore_sessions()
    provider=os.environ.get('GENERATOR_PROVIDER','gemini')
    if not os.environ.get('OPENAI_API_KEY' if provider=='openai' else 'GEMINI_API_KEY'):
        print('Warning: the selected provider API key is missing; add it to .env.')
    tests = ("PC LVGL + PNG image judge, no camera" if os.environ.get('SIM_VISION_JUDGE','0')!='0' else "PC LVGL, no camera/judge") if not FLASH else "off" if not TESTS else (
        f"on, camera {os.environ['CAMERA_INDEX']}" if os.environ.get("CAMERA_INDEX") else "on, no camera")
    print(f"Screen designer at http://{HOST}:{PORT}  (flash to board: {'on' if FLASH else 'off'}; "
          f"tests: {tests}; Ctrl+C to stop)")
    if os.environ.get('IOT_TARGET') == 'hardware_capture':
        import hardware_target
        hardware_target.runtime.start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
