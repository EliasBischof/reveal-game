from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import string, random

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# -----------------------------
# Begriffslisten
# -----------------------------
DEFAULT_TERMS_SFW = [
    # Allgemein / Harmlos
    "Sportart", "Tier", "Stadt", "Frucht", "Land", "Beruf", "Film",
    "Farbe", "Musikinstrument", "Auto-Marke", "Essen", "Getränk",
    "Kleidungsstück", "YouTuber", "Schauspieler", "Sänger", "Computerspiel",
    "Superheld", "Serie", "Emoji", "Marke", "Planetenname", "Pokémon",
    "Harry-Potter-Charakter", "Disney-Figur",
    # Lustig / Party
    "Trinkspiel", "Beleidigung", "Kindheitsserie", "Schimpfwort",
    "Peinliches Hobby", "Memes", "Instagram-Trend", "Cringe-Song",
    "Ex-Name", "Spitzname", "Schulfach", "Lustige Ausrede"
]

# 18+ / Erwachsene – erweitert
DEFAULT_TERMS_NSFW = [
    "Sexstellung", "Kondom-Marke", "Pornostar", "Erotikfilm",
    "Pickup-Line", "Körperteil", "One-Night-Stand-Ort",
    "Peinlichstes Date", "Fetisch", "Schmutziges Wort",
    "Schlimmster Kater-Ort", "Drogenname", "Stripper-Name",
    "Sexspielzeug", "Anmachspruch", "Rollenspiel-Fantasie",
    "Peinlichster Bettunfall", "Exotische Vorliebe", "Pornotitel",
    "Peinlichster Porno-Suchbegriff", "Dirty Talk Satz", "Verbotene Fantasie",
    "Ort für schnellen Sex", "Codewort fürs Abhauen", "Kink",
    "Schlechtester Anmachspruch", "Safeword", "NSFW-Emoji",
    "Peinlicher Chat-Screenshot", "Dating-App-Opening", "Schlimmstes Date-Ende"
]

# -----------------------------
# Multi-Room State
# -----------------------------
rooms = {}


def _new_state(mode: str = 'SFW'):
    terms = DEFAULT_TERMS_SFW.copy() if mode == 'SFW' else DEFAULT_TERMS_NSFW.copy()
    return {
        'score': 0,
        'round': 1,
        'revealed': False,
        'current_term': terms[0] if terms else '—',
        'answers': {'p1': None, 'p2': None},
        'terms': terms,
        'term_i': 1,  # next index
        'mode': mode  # 'SFW' or 'NSFW'
    }


def ensure_room(room_id: str):
    if not room_id:
        return None
    if room_id not in rooms:
        rooms[room_id] = _new_state('SFW')
    return rooms[room_id]


def next_term(state: dict):
    if not state['terms']:
        return '—'
    t = state['terms'][state['term_i'] % len(state['terms'])]
    state['term_i'] += 1
    return t


def serialize_state(state: dict, requester: str):
    out = {
        'score': state['score'],
        'round': state['round'],
        'revealed': state['revealed'],
        'current_term': state['current_term'],
        'mode': state['mode'],
        'answers': {'p1': state['answers']['p1'], 'p2': state['answers']['p2']},
    }
    # Redact other player's answer until revealed
    if not state['revealed'] and requester in ('p1', 'p2'):
        other = 'p2' if requester == 'p1' else 'p1'
        out['answers'][other] = None
    return out

# -----------------------------
# Templates (Player + Admin)
# -----------------------------
BASE_CSS = """
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>Reveal-Game</title>
  <link href="/assets/style.css" rel="stylesheet">
"""

PLAYER_PAGE = r"""
<!doctype html><html lang=\"de\"><head>{{base_css|safe}}</head><body>
<div class=\"container\">
  <header class=\"header\">
    <h1 class=\"title\">Reveal-Game · Raum {{room}}</h1>
    <div class=\"muted\">Spieler: {{player|upper}} · Modus: <span id=\"mode\">–</span></div>
  </header>

  <div class=\"card\">
    <div class=\"row between\">
      <div>
        <div class=\"label\">Aktueller Begriff</div>
        <div id=\"term\" class=\"value\">–</div>
      </div>
      <div class=\"right\">
        <div class=\"label\">Punktestand</div>
        <div id=\"score\" class=\"value\">0</div>
      </div>
    </div>
  </div>

  <div class=\"card\">
    <div class=\"label\">Deine Antwort ({{player|upper}})</div>
    <input id=\"answer\" type=\"text\" placeholder=\"Antwort eingeben\" class=\"input\" />
  </div>

  <div class=\"actions\">
    <button id=\"btn-lock\" class=\"btn btn-dark\">Antwort sperren &amp; zeigen</button>
    <button id=\"btn-award\" class=\"btn btn-success hidden\">+1 Punkt</button>
    <button id=\"btn-next\" class=\"btn btn-indigo hidden\">Nächster Begriff</button>
  </div>

  <div id=\"reveal\" class=\"card hidden\">
    <div class=\"label\">Antworten</div>
    <div class=\"grid two\">
      <div>
        <div class=\"label small\">Spieler 1</div>
        <div id=\"ans1\" class=\"value\">–</div>
      </div>
      <div>
        <div class=\"label small\">Spieler 2</div>
        <div id=\"ans2\" class=\"value\">–</div>
      </div>
    </div>
  </div>

  <p class=\"hint\">Tipp: Teile diese URL mit deinem Mitspieler (p1/p2 austauschen).</p>
</div>

<script>
const room = {{room|tojson}};
const player = {{player|tojson}};
const $ = (id) => document.getElementById(id);

let lastRound = null;
let submitted = false;

function render(s){
  document.getElementById('mode').textContent = s.mode;
  document.title = `Reveal-Game · ${room}`;
  $("term").textContent = s.current_term;
  $("score").textContent = s.score;

  const input = $("answer");
  const serverVal = s.answers[player] ?? '';
  const focused = document.activeElement === input;
  if (lastRound !== s.round){
    input.value = '';
    submitted = false;
    lastRound = s.round;
  }
  if (submitted && serverVal && input.value !== serverVal){ input.value = serverVal; }
  if (!submitted && serverVal && (!focused || input.value.trim()==='')){ input.value = serverVal; }

  if(s.revealed){
    $("reveal").classList.remove("hidden");
    $("ans1").textContent = s.answers.p1 ?? '—';
    $("ans2").textContent = s.answers.p2 ?? '—';
    $("btn-award").classList.remove("hidden");
    $("btn-next").classList.remove("hidden");
  } else {
    $("reveal").classList.add("hidden");
    $("btn-award").classList.add("hidden");
    $("btn-next").classList.add("hidden");
  }
}

async function getState(){
  const res = await fetch(`/state?room=${encodeURIComponent(room)}&player=${encodeURIComponent(player)}`);
  render(await res.json());
}

async function postJSON(path, body){
  const res = await fetch(`${path}?room=${encodeURIComponent(room)}&player=${encodeURIComponent(player)}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})});
  return res.json();
}

$("btn-lock").addEventListener('click', async ()=>{
  const text = $("answer").value.trim();
  if(!text) return;
  submitted = true;
  await postJSON('/answer', {text});
  const s = await postJSON('/reveal');
  render(s);
});

$("btn-award").addEventListener('click', async ()=>{ render(await postJSON('/award')); });
$("btn-next").addEventListener('click', async ()=>{ render(await postJSON('/next')); $("answer").focus(); });

$("answer").addEventListener('keydown', (e)=>{ if(e.key==='Enter') $("btn-lock").click(); });

getState();
setInterval(getState, 1500);
</script>
</body></html>
"""

ADMIN_PAGE = r"""
<!doctype html><html lang=\"de\"><head>{{base_css|safe}}</head><body>
<div class=\"container\">
  <header class=\"header\">
    <h1 class=\"title\">Reveal-Game · Admin · Raum {{room}}</h1>
    <a href=\"/play?room={{room}}&player=p1\" class=\"link\">Zur Spieler-Ansicht</a>
  </header>

  <div class=\"muted\">Aktueller Modus: <span id=\"mode\">–</span></div>

  <div class=\"actions\">
    <button id=\"btn-sfw\" class=\"btn\">Jugendfrei</button>
    <button id=\"btn-nsfw\" class=\"btn btn-danger\">18+</button>
  </div>

  <div class=\"card\">
    <div class=\"grid three\">
      <div><div class=\"label\">Begriff</div><div id=\"term\" class=\"value\">–</div></div>
      <div><div class=\"label\">Score</div><div id=\"score\" class=\"value\">0</div></div>
      <div><div class=\"label\">Runde</div><div id=\"round\" class=\"value\">1</div></div>
    </div>
  </div>

  <div class=\"card\">
    <div class=\"grid two\">
      <div><div class=\"label small\">Spieler 1</div><div id=\"ans1\" class=\"value\">–</div></div>
      <div><div class=\"label small\">Spieler 2</div><div id=\"ans2\" class=\"value\">–</div></div>
    </div>
  </div>

  <div class=\"actions\">
    <button id=\"btn-award\" class=\"btn btn-success\">+1 Punkt</button>
    <button id=\"btn-next\" class=\"btn btn-indigo\">Nächster Begriff</button>
  </div>

  <div class=\"card\">
    <h2 class=\"subtitle\">Eigene Begriffe setzen</h2>
    <textarea id=\"customTerms\" rows=\"3\" class=\"input\" placeholder=\"z.B. Planet, Automarke, Pokémon\"></textarea>
    <button id=\"btn-apply-terms\" class=\"btn\">Übernehmen</button>
  </div>
</div>
<script>
const room = {{room|tojson}};
const $ = (id) => document.getElementById(id);

function render(s){
  $("term").textContent = s.current_term;
  $("score").textContent = s.score;
  $("round").textContent = s.round;
  $("ans1").textContent = s.answers.p1 ?? '—';
  $("ans2").textContent = s.answers.p2 ?? '—';
  $("mode").textContent = s.mode;
}

async function getState(){
  const res = await fetch(`/state?room=${encodeURIComponent(room)}&player=admin`);
  render(await res.json());
}

async function postJSON(path, body){
  const res = await fetch(`${path}?room=${encodeURIComponent(room)}&player=admin`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})});
  return res.json();
}

$("btn-award").addEventListener('click', async ()=>{ render(await postJSON('/award')); });
$("btn-next").addEventListener('click', async ()=>{ render(await postJSON('/next')); });
$("btn-apply-terms").addEventListener('click', async ()=>{
  const parts = $("customTerms").value.split(',').map(x=>x.trim()).filter(Boolean);
  if(parts.length) render(await postJSON('/set_terms', {terms: parts}));
});

$("btn-sfw").addEventListener('click', async ()=>{ render(await postJSON('/set_mode', {mode:'SFW'})); });
$("btn-nsfw").addEventListener('click', async ()=>{ render(await postJSON('/set_mode', {mode:'NSFW'})); });

getState();
setInterval(getState, 1200);
</script>
</body></html>
"""

# -----------------------------
# Routes
# -----------------------------
@app.get('/')
def home():
    room = request.args.get('room')
    player = request.args.get('player', 'p1')
    if not room:
        room = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(5))
        return redirect(url_for('play', room=room, player='p1'))
    return redirect(url_for('play', room=room, player=player))

@app.get('/play')
def play():
    room = request.args.get('room')
    player = request.args.get('player', 'p1')
    if player not in ('p1','p2'):
        player = 'p1'
    state = ensure_room(room)
    if state is None:
        return "Room required", 400
    return render_template_string(PLAYER_PAGE, base_css=BASE_CSS, room=room, player=player)

@app.get('/admin')
def admin():
    room = request.args.get('room')
    state = ensure_room(room)
    if state is None:
        return "Room required", 400
    return render_template_string(ADMIN_PAGE, base_css=BASE_CSS, room=room)

@app.get('/state')
def get_state():
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    return jsonify(serialize_state(state, requester))

@app.post('/answer')
def post_answer():
    room = request.args.get('room')
    requester = request.args.get('player')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if requester not in ('p1','p2'):
        return jsonify({'error':'invalid player'}), 400
    if state['revealed']:
        return jsonify({'error':'already revealed'}), 400
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    state['answers'][requester] = text if text else None
    return jsonify(serialize_state(state, requester))

@app.post('/reveal')
def reveal():
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if not (state['answers']['p1'] and state['answers']['p2']):
        return jsonify({'error':'need both answers'}), 400
    state['revealed'] = True
    return jsonify(serialize_state(state, requester))

@app.post('/award')
def award():
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if not state['revealed']:
        return jsonify({'error':'not revealed yet'}), 400
    a1 = (state['answers']['p1'] or '').strip().lower()
    a2 = (state['answers']['p2'] or '').strip().lower()
    if a1 and a1 == a2:
        state['score'] += 1
    return jsonify(serialize_state(state, requester))

@app.post('/next')
def next_round():
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    state['round'] += 1
    state['revealed'] = False
    state['answers'] = {'p1': None, 'p2': None}
    state['current_term'] = next_term(state)
    return jsonify(serialize_state(state, requester))

@app.post('/reset')
def reset():
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    mode = state['mode']
    rooms[room] = _new_state(mode)
    return jsonify(serialize_state(rooms[room], requester))

@app.post('/set_terms')
def set_terms():
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    data = request.get_json(force=True, silent=True) or {}
    terms = data.get('terms') or []
    if not isinstance(terms, list) or not all(isinstance(x, str) and x.strip() for x in terms):
        return jsonify({'error': 'invalid terms'}), 400
    state['terms'] = [t.strip() for t in terms]
    state['term_i'] = 1
    state['current_term'] = state['terms'][0]
    state['round'] = 1
    state['revealed'] = False
    state['answers'] = {'p1': None, 'p2': None}
    return jsonify(serialize_state(state, requester))

@app.post('/set_mode')
def set_mode():
    """Nur Spieler 1 (oder Admin) darf den Modus ändern."""
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if requester not in ('p1', 'admin'):
        return jsonify({'error':'only player 1 or admin can change mode'}), 403
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get('mode')
    if mode not in ('SFW', 'NSFW'):
        return jsonify({'error':'invalid mode'}), 400
    # Reset state with selected mode, keep score? design choice: reset round & answers but keep score
    keep_score = state['score']
    rooms[room] = _new_state(mode)
    rooms[room]['score'] = keep_score
    return jsonify(serialize_state(rooms[room], requester))

# -----------------------------
# Local static CSS (single-file deploy)
# -----------------------------
CSS = r"""
:root{--bg:#f8fafc;--fg:#0f172a;--muted:#64748b;--card:#ffffff;--border:#e2e8f0;--shadow:0 6px 20px rgba(0,0,0,.06);}*{box-sizing:border-box}html,body{height:100%}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial,"Noto Sans",sans-serif}.container{max-width:960px;margin:0 auto;padding:24px}.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}.title{font-size:24px;margin:0}.subtitle{font-size:18px;margin:0 0 8px 0}.muted{color:var(--muted);font-size:14px}.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;margin-bottom:16px;box-shadow:var(--shadow)}.row{display:flex;gap:16px}.between{justify-content:space-between}.right{text-align:right}.label{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:6px}.label.small{text-transform:none;font-size:12px;color:var(--muted)}.value{font-size:22px;font-weight:600}.input{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:12px;outline:none}.input:focus{border-color:#6366f1;box-shadow:0 0 0 4px rgba(99,102,241,.15)}.actions{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.btn{appearance:none;border:1px solid transparent;background:#0f172a;color:#fff;border-radius:12px;padding:10px 14px;cursor:pointer;box-shadow:var(--shadow)}.btn:hover{opacity:.95}.btn:disabled{opacity:.5;cursor:not-allowed}.btn-dark{background:#0f172a}.btn-success{background:#10b981}.btn-indigo{background:#6366f1}.btn-danger{background:#e11d48}.link{color:#6366f1;text-decoration:underline}.grid{display:grid;gap:16px}.grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.hidden{display:none}.hint{font-size:12px;color:var(--muted);margin-top:8px}
@media (max-width:720px){.grid.two,.grid.three{grid-template-columns:1fr}}
"""

from flask import Response

@app.get('/assets/style.css')
def style_css():
    return Response(CSS, mimetype='text/css')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
