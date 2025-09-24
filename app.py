from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from datetime import datetime
import string, random

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# -----------------------------
# Multi-Room, per-player state
# -----------------------------
# rooms[room_id] = {
#   'score': int,
#   'round': int,
#   'revealed': bool,
#   'current_term': str,
#   'answers': {'p1': str|None, 'p2': str|None},
#   'terms': [str],
#   'term_i': int
# }
rooms = {}

DEFAULT_TERMS = [
    "Sportart", "Tier", "Stadt", "Frucht", "Land",
    "Beruf", "Film", "Farbe", "Musikinstrument"
]

def ensure_room(room_id: str):
    if not room_id:
        return None
    if room_id not in rooms:
        rooms[room_id] = {
            'score': 0,
            'round': 1,
            'revealed': False,
            'current_term': DEFAULT_TERMS[0],
            'answers': {'p1': None, 'p2': None},
            'terms': DEFAULT_TERMS.copy(),
            'term_i': 1,  # next index
        }
    return rooms[room_id]

def next_term(state: dict):
    if not state['terms']:
        return '—'
    t = state['terms'][state['term_i'] % len(state['terms'])]
    state['term_i'] += 1
    return t

# -----------------------------
# Templates
# -----------------------------
BASE_CSS = """
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>Reveal-Game</title>
  <script src="https://cdn.tailwindcss.com"></script>
"""

PLAYER_PAGE = r"""
<!doctype html><html lang="de"><head>{{base_css|safe}}</head><body class="min-h-screen bg-slate-50 text-slate-800">
<div class="max-w-2xl mx-auto p-6">
  <header class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold">Reveal-Game · Raum {{room}}</h1>
    <div class="text-sm text-slate-500">Spieler: {{player|upper}}</div>
  </header>

  <div class="bg-white shadow rounded-2xl p-5 mb-4">
    <div class="flex items-center justify-between">
      <div>
        <div class="text-xs uppercase tracking-wide text-slate-500">Aktueller Begriff</div>
        <div id="term" class="text-2xl font-semibold mt-1">–</div>
      </div>
      <div class="text-right">
        <div class="text-xs uppercase tracking-wide text-slate-500">Punktestand</div>
        <div id="score" class="text-2xl font-semibold mt-1">0</div>
      </div>
    </div>
  </div>

  <div class="bg-white shadow rounded-2xl p-5">
    <div class="text-sm font-medium text-slate-600 mb-2">Deine Antwort ({{player|upper}})</div>
    <input id="answer" type="text" placeholder="Antwort eingeben" class="w-full border rounded-xl px-3 py-2 focus:outline-none focus:ring" />
  </div>

  <div class="flex flex-wrap gap-3 mt-4">
    <button id="btn-lock" class="px-4 py-2 rounded-xl bg-slate-800 text-white">Antwort sperren &amp; zeigen</button>
    <button id="btn-award" class="px-4 py-2 rounded-xl bg-emerald-600 text-white hidden">+1 Punkt</button>
    <button id="btn-next" class="px-4 py-2 rounded-xl bg-indigo-600 text-white hidden">Nächster Begriff</button>
  </div>

  <div id="reveal" class="mt-6 hidden">
    <div class="bg-white shadow rounded-2xl p-5">
      <div class="text-xs uppercase tracking-wide text-slate-500 mb-3">Antworten</div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div class="text-xs text-slate-500">Spieler 1</div>
          <div id="ans1" class="text-xl font-semibold">–</div>
        </div>
        <div>
          <div class="text-xs text-slate-500">Spieler 2</div>
          <div id="ans2" class="text-xl font-semibold">–</div>
        </div>
      </div>
    </div>
  </div>

  <p class="text-xs text-slate-500 mt-6">Tipp: Teile diese URL mit deinem Mitspieler (p1/p2 austauschen).</p>
</div>

<script>
const room = {{room|tojson}};
const player = {{player|tojson}}; // 'p1' | 'p2'
const $ = (id) => document.getElementById(id);

function render(s){
  document.title = `Reveal-Game · ${room}`;
  $("term").textContent = s.current_term;
  $("score").textContent = s.score;
  // Only show answers after reveal; before reveal, server redacts the other player's answer
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
  $("answer").value = s.answers[player] ?? '';
}

async function getState(){
  const res = await fetch(`/state?room=${encodeURIComponent(room)}&player=${encodeURIComponent(player)}`);
  const s = await res.json();
  render(s);
}

async function postJSON(path, body){
  const res = await fetch(`${path}?room=${encodeURIComponent(room)}&player=${encodeURIComponent(player)}`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body||{})
  });
  return res.json();
}

$("btn-lock").addEventListener('click', async ()=>{
  const text = $("answer").value.trim();
  if(!text) return;
  await postJSON('/answer', {text});
  const s = await postJSON('/reveal');
  render(s);
});

$("btn-award").addEventListener('click', async ()=>{
  const s = await postJSON('/award');
  render(s);
});

$("btn-next").addEventListener('click', async ()=>{
  const s = await postJSON('/next');
  render(s);
  $("answer").focus();
});

$("answer").addEventListener('keydown', (e)=>{
  if(e.key==='Enter') $("btn-lock").click();
});

getState();
setInterval(getState, 1500); // light polling to sync with the other player
</script>
</body></html>
"""

ADMIN_PAGE = r"""
<!doctype html><html lang="de"><head>{{base_css|safe}}</head><body class="min-h-screen bg-slate-50 text-slate-800">
<div class="max-w-3xl mx-auto p-6">
  <header class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold">Reveal-Game · Admin · Raum {{room}}</h1>
    <a href="/play?room={{room}}&player=p1" class="text-sm underline">Zur Spieler-Ansicht</a>
  </header>

  <div class="bg-white shadow rounded-2xl p-5 mb-4">
    <div class="grid grid-cols-3 gap-4">
      <div>
        <div class="text-xs uppercase text-slate-500">Begriff</div>
        <div id="term" class="text-2xl font-semibold">–</div>
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Score</div>
        <div id="score" class="text-2xl font-semibold">0</div>
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Runde</div>
        <div id="round" class="text-2xl font-semibold">1</div>
      </div>
    </div>
  </div>

  <div class="bg-white shadow rounded-2xl p-5 mb-4">
    <div class="grid grid-cols-2 gap-4">
      <div>
        <div class="text-xs text-slate-500">Spieler 1</div>
        <div id="ans1" class="text-xl font-semibold">–</div>
      </div>
      <div>
        <div class="text-xs text-slate-500">Spieler 2</div>
        <div id="ans2" class="text-xl font-semibold">–</div>
      </div>
    </div>
  </div>

  <div class="flex gap-3">
    <button id="btn-award" class="px-4 py-2 rounded-xl bg-emerald-600 text-white">+1 Punkt</button>
    <button id="btn-next" class="px-4 py-2 rounded-xl bg-indigo-600 text-white">Nächster Begriff</button>
  </div>

  <div class="mt-8">
    <h2 class="font-semibold mb-2">Eigene Begriffe setzen</h2>
    <textarea id="customTerms" rows="3" class="w-full border rounded-xl px-3 py-2" placeholder="z.B. Planet, Automarke, Pokémon"></textarea>
    <button id="btn-apply-terms" class="mt-2 px-3 py-2 rounded-xl bg-slate-700 text-white">Übernehmen</button>
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
    # Simple landing that creates/chooses a room and player
    room = request.args.get('room')
    player = request.args.get('player', 'p1')
    if not room:
        # generate a short room code
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
    player = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    # Redact other player's answer until revealed
    out = {
        'score': state['score'],
        'round': state['round'],
        'revealed': state['revealed'],
        'current_term': state['current_term'],
        'answers': {'p1': state['answers']['p1'], 'p2': state['answers']['p2']},
    }
    if not state['revealed'] and player in ('p1','p2'):
        other = 'p2' if player=='p1' else 'p1'
        out['answers'][other] = None
    return jsonify(out)

@app.post('/answer')
def post_answer():
    room = request.args.get('room')
    player = request.args.get('player')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if player not in ('p1','p2'):
        return jsonify({'error':'invalid player'}), 400
    if state['revealed']:
        return jsonify({'error':'already revealed'}), 400
    data = request.get_json(force=True)
    text = (data.get('text') or '').strip()
    state['answers'][player] = text
    return get_state()

@app.post('/reveal')
def reveal():
    room = request.args.get('room')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if not (state['answers']['p1'] and state['answers']['p2']):
        return jsonify({'error':'need both answers'}), 400
    state['revealed'] = True
    return get_state()

@app.post('/award')
def award():
    room = request.args.get('room')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if not state['revealed']:
        return jsonify({'error':'not revealed yet'}), 400
    a1 = (state['answers']['p1'] or '').strip().lower()
    a2 = (state['answers']['p2'] or '').strip().lower()
    if a1 and a1 == a2:
        state['score'] += 1
    return get_state()

@app.post('/next')
def next_round():
    room = request.args.get('room')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    state['round'] += 1
    state['revealed'] = False
    state['answers'] = {'p1': None, 'p2': None}
    state['current_term'] = next_term(state)
    return get_state()

@app.post('/reset')
def reset():
    room = request.args.get('room')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    state['score'] = 0
    state['round'] = 1
    state['revealed'] = False
    state['answers'] = {'p1': None, 'p2': None}
    state['term_i'] = 1
    state['current_term'] = state['terms'][0]
    return get_state()

@app.post('/set_terms')
def set_terms():
    room = request.args.get('room')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    data = request.get_json(force=True)
    terms = data.get('terms') or []
    if not isinstance(terms, list) or not all(isinstance(x, str) and x.strip() for x in terms):
        return jsonify({'error': 'invalid terms'}), 400
    state['terms'] = [t.strip() for t in terms if t.strip()]
    state['term_i'] = 1
    state['current_term'] = state['terms'][0]
    state['round'] = 1
    state['revealed'] = False
    state['answers'] = {'p1': None, 'p2': None}
    return get_state()

if __name__ == '__main__':
    # Bind to all interfaces for hosting on a server.
    app.run(host='0.0.0.0', port=5000, debug=True)
