from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import string, random

app = Flask(__name__)

# -----------------------------
# Simple terms list
# -----------------------------
import random
TERMS = [
    "Safeword", "Ex-Name", "Lustige Ausrede", "Peinlichstes Date", "Disney-Figur", "Harry-Potter-Charakter", "Farbe", "Peinlichster Porno-Suchbegriff", "Kindheitsserie", "Körperteil", "Peinlicher Chat-Screenshot", "Schimpfwort", "Superheld", "Trinkspiel", "Schlechtester Anmachspruch", "Cringe-Song", "Peinlichster Bettunfall", "Drogenname", "Beruf", "Sänger", "Frucht", "Serie", "Marke", "Ort für schnellen Sex", "Kleidungsstück", "Sportart", "Musikinstrument", "Pornotitel", "Instagram-Trend", "Schlimmster Kater-Ort", "Peinliches Hobby", "Exotische Vorliebe", "Memes", "Computerspiel", "Schulfach", "Schauspieler", "Auto-Marke", "Stadt", "Erotikfilm", "Beleidigung", "Emoji", "Pornostar", "Land", "YouTuber", "One-Night-Stand-Ort", "Schmutziges Wort", "Sexstellung", "Planetenname", "Dirty Talk Satz", "Codewort fürs Abhauen", "NSFW-Emoji", "Schlimmstes Date-Ende", "Peinlichster Chat-Screenshot", "Essen", "Pickup-Line", "Stripper-Name", "Schlechtester Anmachspruch", "Film", "Getränk", "Spitzname", "Verbotene Fantasie", "Lustige Ausrede", "Sexspielzeug", "Kink", "Anmachspruch"
]
random.shuffle(TERMS)

# -----------------------------
# Multi-Room State
# -----------------------------
rooms = {}


def _new_state():
    return {
        'score': 0,
        'round': 1,
        'revealed': False,
        'current_term': TERMS[0],
        'answers': {'p1': None, 'p2': None},
        'term_i': 1
    }


def ensure_room(room_id: str):
    if not room_id:
        return None
    if room_id not in rooms:
        rooms[room_id] = _new_state()
    return rooms[room_id]


def next_term(state: dict):
    t = TERMS[state['term_i'] % len(TERMS)]
    state['term_i'] += 1
    return t


def serialize_state(state: dict, requester: str):
    out = {
        'score': state['score'],
        'round': state['round'],
        'revealed': state['revealed'],
        'current_term': state['current_term'],
        'answers': {'p1': state['answers']['p1'], 'p2': state['answers']['p2']},
    }
    if not state['revealed'] and requester in ('p1', 'p2'):
        other = 'p2' if requester == 'p1' else 'p1'
        out['answers'][other] = None
    return out

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
    <button id="btn-award" class="px-4 py-2 rounded-xl bg-emerald-600 text-white hidden">+1 Punkt (ich entscheide)</button>
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

  if(s.revealed && player==='p1'){
    $("reveal").classList.remove("hidden");
    $("ans1").textContent = s.answers.p1 ?? '—';
    $("ans2").textContent = s.answers.p2 ?? '—';
    $("btn-award").classList.remove("hidden");
    $("btn-next").classList.remove("hidden");
  } else {
    // Spieler 2 sieht nur das Reveal-Panel (ohne Buttons), wenn revealed ist
    if (s.revealed && player==='p2') {
      $("reveal").classList.remove("hidden");
      $("ans1").textContent = s.answers.p1 ?? '—';
      $("ans2").textContent = s.answers.p2 ?? '—';
    } else {
      $("reveal").classList.add("hidden");
    }
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
    if requester != 'p1':
        return jsonify({'error':'only player 1 can award'}), 403
    if not state['revealed']:
        return jsonify({'error':'not revealed yet'}), 400
    # Manuelle Vergabe: Spieler 1 entscheidet, egal ob Antworten exakt sind
    state['score'] += 1
    resp = serialize_state(state, requester)
    resp['_awarded'] = True
    return jsonify(resp)

@app.post('/next')
def next_round():
    room = request.args.get('room')
    requester = request.args.get('player', 'p1')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if requester != 'p1':
        return jsonify({'error':'only player 1 can go next'}), 403
    state['round'] += 1
    state['revealed'] = False
    state['answers'] = {'p1': None, 'p2': None}
    state['current_term'] = next_term(state)
    return jsonify(serialize_state(state, requester))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
