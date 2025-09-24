from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from datetime import datetime
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

DEFAULT_TERMS_NSFW = [
    # 18+ / Erwachsene
    "Sexstellung", "Kondom-Marke", "Pornostar", "Erotikfilm",
    "Pickup-Line", "Körperteil", "One-Night-Stand-Ort",
    "Peinlichstes Date", "Fetisch", "Schmutziges Wort",
    "Schlimmster Kater-Ort", "Drogenname", "Stripper-Name",
    "Sexspielzeug", "Anmachspruch", "Rollenspiel-Fantasie",
    "Peinlichster Bettunfall", "Exotische Vorliebe", "Pornotitel",
    "Kuscheltier mit schmutzigem Namen", "Peinlichster Porno-Suchbegriff",
    "Dirty Talk Satz", "Verbotene Fantasie"
]

# -----------------------------
# Multi-Room, per-player state
# -----------------------------
rooms = {}

def ensure_room(room_id: str):
    if not room_id:
        return None
    if room_id not in rooms:
        rooms[room_id] = {
            'score': 0,
            'round': 1,
            'revealed': False,
            'current_term': DEFAULT_TERMS_SFW[0],
            'answers': {'p1': None, 'p2': None},
            'terms': DEFAULT_TERMS_SFW.copy(),
            'term_i': 1,
            'mode': 'SFW'  # or 'NSFW'
        }
    return rooms[room_id]

def next_term(state: dict):
    if not state['terms']:
        return '—'
    t = state['terms'][state['term_i'] % len(state['terms'])]
    state['term_i'] += 1
    return t

# -----------------------------
# Templates (Player + Admin)
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
const player = {{player|tojson}};
const $ = (id) => document.getElementById(id);

let lastRound = null;
let submitted = false;

function render(s){
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
<!doctype html><html lang="de"><head>{{base_css|safe}}</head><body class="min-h-screen bg-slate-50 text-slate-800">
<div class="max-w-3xl mx-auto p-6">
  <header class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold">Reveal-Game · Admin · Raum {{room}}</h1>
    <a href="/play?room={{room}}&player=p1" class="text-sm underline">Zur Spieler-Ansicht</a>
  </header>

  <div class="mb-4 text-sm">Aktueller Modus: <span id="mode">–</span></div>

  <div class="flex gap-3 mb-6">
    <button id="btn-sfw" class="px-3 py-2 rounded-xl bg-slate-700 text-white">Jugendfrei</button>
    <button id="btn-nsfw" class="px-3 py-2 rounded-xl bg-rose-700 text-white">18+</button>
  </div>

  <div class="bg-white shadow rounded-2xl p-5 mb-4">
    <div class="grid grid-cols-3 gap-4">
      <div><div class="text-xs uppercase text-slate-500">Begriff</div><div id="term" class="text-2xl font-semibold">–</div></div>
      <div><div class="text-xs uppercase text-slate-500">Score</div><div id="score" class="text-2xl font-semibold">0</div></div>
      <div><div class="text-xs uppercase text-slate-500">Runde</div><div id="round" class="text-2xl font-semibold">1</div></div>
    </div>
  </div>

  <div class="bg-white shadow rounded-2xl p-5 mb-4">
    <div class="grid grid-cols-2 gap-4">
      <div><div class="text-xs text-slate-500">Spieler 1</div><div id="ans1" class="text-xl font-semibold">–</div></div>
      <div><div class="text-xs text-slate-500">Spieler 2</div><div id="ans2" class="text-xl font-semibold">–</div></div>
    </div>
  </div>

  <div class="flex gap-3 mb-4">
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
    player = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    out = {
        'score': state['score'],
        'round': state['round'],
        'revealed': state['revealed'],
        'current_term': state['current_term'],
        'answers': {'p1': state['answers']['p1'], 'p2': state['answers']['p2']},
        'mode': state['mode']
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
    data = request.get_json(force=True
