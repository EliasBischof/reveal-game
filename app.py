from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import string, random

app = Flask(__name__)

# -----------------------------
# Terms (einmal mischen)
# -----------------------------
TERMS = [
    "Safeword", "Ex-Name", "Lustige Ausrede", "Peinlichstes Date", "One-Piece-Figur",
    "Farbe", "Peinlichster Porno-Suchbegriff", "Kindheitsserie", "Körperteil", "Peinlicher Chat-Screenshot",
    "Schimpfwort", "Superheld", "Trinkspiel", "Schlechtester Anmachspruch", "Cringe-Song", "Peinlichster Bettunfall",
    "Drogenname", "Beruf", "Sänger", "Frucht", "Serie", "Marke", "Ort für schnellen Sex", "Kleidungsstück", "Sportart",
    "Musikinstrument", "Pornotitel", "Instagram-Trend", "Schlimmster Kater-Ort", "Peinliches Hobby", "Exotische Vorliebe",
    "Memes", "Computerspiel", "Schulfach", "Schauspieler", "Auto-Marke", "Stadt", "Erotikfilm", "Beleidigung", "Emoji", "Pornostar",
    "Land", "YouTuber", "One-Night-Stand-Ort", "Schmutziges Wort", "Sexstellung", "Planetenname", "Dirty Talk Satz", "Codewort fürs Abhauen",
    "NSFW-Emoji", "Schlimmstes Date-Ende", "Peinlichster Chat-Screenshot", "Essen", "Pickup-Line", "Stripper-Name", "Schlechtester Anmachspruch",
    "Film", "Getränk", "Spitzname", "Verbotene Fantasie", "Lustige Ausrede", "Sexspielzeug", "Kink", "Anmachspruch"
]
random.shuffle(TERMS)

# -----------------------------
# State
# -----------------------------
rooms = {}

def _new_state():
    max_rounds = min(5, len(TERMS))  # ← Testweise 5
    term_order = random.sample(range(len(TERMS)), k=max_rounds)
    return {
        'score': 0,
        'round': 1,                   # 1-basiert
        'max_rounds': max_rounds,
        'revealed': False,
        'game_over': False,
        'term_order': term_order,     # Reihenfolge (Indizes in TERMS)
        'term_i': 0,                  # Zeiger in term_order (0-basiert)
        'current_term': TERMS[term_order[0]],
        'answers': {'p1': None, 'p2': None},
        'names': {'p1': None, 'p2': None},
        'rounds': []                  # History: [{term, a1, a2, awarded}]
    }

def ensure_room(room_id: str):
    if not room_id:
        return None
    if room_id not in rooms:
        rooms[room_id] = _new_state()
    return rooms[room_id]

def next_term(state: dict):
    """Geht zum nächsten Begriff, falls vorhanden. Setzt KEIN game_over."""
    if state['term_i'] >= len(state['term_order']) - 1:
        return state['current_term']
    state['term_i'] += 1
    next_idx = state['term_order'][state['term_i']]
    return TERMS[next_idx]

def serialize_state(state: dict, requester: str):
    out = {
        'score': state['score'],
        'round': state['round'],
        'max_rounds': state['max_rounds'],
        'revealed': state['revealed'],
        'game_over': state['game_over'],
        'current_term': state['current_term'],
        'answers': {'p1': state['answers']['p1'], 'p2': state['answers']['p2']},
        'names': state['names']
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
    <div class="text-sm text-slate-500">Spieler: <span id="who">–</span></div>
  </header>

  <!-- Name Setup -->
  <div id="name-setup" class="bg-white shadow rounded-2xl p-5 mb-4 hidden">
    <div class="text-sm text-slate-600 mb-2">Bitte gib deinen Namen ein, bevor ihr startet:</div>
    <div class="flex gap-2">
      <input id="name-input" type="text" maxlength="25" placeholder="Dein Name" class="flex-1 border rounded-xl px-3 py-2 focus:outline-none focus:ring" />
      <button id="btn-setname" class="px-4 py-2 rounded-xl bg-slate-800 text-white">OK</button>
    </div>
    <p class="text-xs text-slate-500 mt-2">Dein Mitspieler macht das auf seiner Seite auch. Danach könnt ihr loslegen.</p>
  </div>

  <!-- Game Area -->
  <div id="game-area" class="hidden">
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
      <div class="mt-3 flex items-center gap-4">
        <div class="text-xs uppercase tracking-wide text-slate-500">Runde</div>
        <div><span id="round">1</span>/<span id="maxrounds">5</span></div>
      </div>
    </div>

    <div class="bg-white shadow rounded-2xl p-5">
      <div class="text-sm font-medium text-slate-600 mb-2">Deine Antwort (<span id="me-label">{{player|upper}}</span>)</div>
      <input id="answer" type="text" placeholder="Antwort eingeben" class="w-full border rounded-xl px-3 py-2 focus:outline-none focus:ring" />
    </div>

    <div class="flex flex-wrap gap-3 mt-4">
      <button id="btn-lock" class="px-4 py-2 rounded-xl bg-slate-800 text-white">Antwort sperren &amp; zeigen</button>
      <button id="btn-award" class="px-4 py-2 rounded-xl bg-emerald-600 text-white hidden">+1 Punkt (ich entscheide)</button>
      <button id="btn-next" class="px-4 py-2 rounded-xl bg-indigo-600 text-white hidden">Nächster Begriff</button>
      <button id="btn-finish" class="px-4 py-2 rounded-xl bg-rose-600 text-white hidden">Spiel beenden</button>
    </div>

    <div id="reveal" class="mt-6 hidden">
      <div class="bg-white shadow rounded-2xl p-5">
        <div class="text-xs uppercase tracking-wide text-slate-500 mb-3">Antworten</div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div class="text-xs text-slate-500" id="p1-label">Spieler 1</div>
            <div id="ans1" class="text-xl font-semibold">–</div>
          </div>
          <div>
            <div class="text-xs text-slate-500" id="p2-label">Spieler 2</div>
            <div id="ans2" class="text-xl font-semibold">–</div>
          </div>
        </div>
      </div>
    </div>

    <p class="text-xs text-slate-500 mt-6">Tipp: Teile diese URL mit deinem Mitspieler (p1/p2 austauschen).</p>
  </div>
</div>

<script>
const room = {{room|tojson}};
const player = {{player|tojson}};
const $ = (id) => document.getElementById(id);

let lastRound = null;
let submitted = false;

function applyNamesUI(s){
  const me = player;
  $("who").textContent = s.names[me] || me.toUpperCase();
  $("me-label").textContent = s.names[me] || me.toUpperCase();
  $("p1-label").textContent = s.names.p1 || 'Spieler 1';
  $("p2-label").textContent = s.names.p2 || 'Spieler 2';
}

function render(s){
  // Finish-Screen (separat via /finish gerendert) -> hier nur normal rendern
  if (!s.names || !s.names[player]){
    $("name-setup").classList.remove("hidden");
    $("game-area").classList.add("hidden");
  } else {
    $("name-setup").classList.add("hidden");
    $("game-area").classList.remove("hidden");
  }

  applyNamesUI(s);

  $("term").textContent = s.current_term;
  $("score").textContent = s.score;
  $("round").textContent = s.round;
  $("maxrounds").textContent = s.max_rounds;

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
    if (s.round >= s.max_rounds) {
      $("btn-award").classList.remove("hidden");
      $("btn-next").classList.add("hidden");
      $("btn-finish").classList.remove("hidden");
    } else {
      $("btn-award").classList.remove("hidden");
      $("btn-next").classList.remove("hidden");
      $("btn-finish").classList.add("hidden");
    }
  } else {
    if (s.revealed && player==='p2') {
      $("reveal").classList.remove("hidden");
      $("ans1").textContent = s.answers.p1 ?? '—';
      $("ans2").textContent = s.answers.p2 ?? '—';
    } else {
      $("reveal").classList.add("hidden");
    }
    $("btn-award").classList.add("hidden");
    $("btn-next").classList.add("hidden");
    $("btn-finish").classList.add("hidden");
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
$("btn-finish").addEventListener('click', ()=>{ window.location.href = `/finish?room=${encodeURIComponent(room)}`; });

$("answer").addEventListener('keydown', (e)=>{ if(e.key==='Enter') $("btn-lock").click(); });

// Name setup
$("btn-setname").addEventListener('click', async ()=>{
  const name = ($("name-input").value || '').trim();
  if(!name) return;
  await postJSON('/set_name', {name});
  getState();
});
$("name-input").addEventListener('keydown', (e)=>{ if(e.key==='Enter') $("btn-setname").click(); });

getState();
setInterval(getState, 1500);
</script>
</body></html>
"""

RESULTS_PAGE = r"""
<!doctype html><html lang="de"><head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Ergebnis</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head><body class="min-h-screen bg-slate-50 text-slate-800">
<div class="max-w-3xl mx-auto p-6">
  <h1 class="text-2xl font-bold mb-4">Ergebnis – Raum {{room}}</h1>
  <div class="mb-4">Punkte: <span class="font-semibold">{{score}}</span> / {{max_rounds}}</div>
  <div class="bg-white shadow rounded-2xl overflow-hidden">
    <table class="w-full text-left">
      <thead class="bg-slate-100">
        <tr><th class="p-3">#</th><th class="p-3">Begriff</th><th class="p-3">{{n1}}</th><th class="p-3">{{n2}}</th><th class="p-3">Punkt</th></tr>
      </thead>
      <tbody>
        {% for i, r in enumerate(rounds, start=1) %}
        <tr class="border-t">
          <td class="p-3">{{i}}</td>
          <td class="p-3">{{r.term}}</td>
          <td class="p-3">{{r.a1 or '—'}}</td>
          <td class="p-3">{{r.a2 or '—'}}</td>
          <td class="p-3">{{'✓' if r.awarded else '—'}}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <div class="mt-6"><a class="px-4 py-2 rounded-xl bg-slate-800 text-white" href="/">Neues Spiel starten</a></div>
</div>
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

@app.post('/set_name')
def set_name():
    room = request.args.get('room')
    requester = request.args.get('player')
    state = ensure_room(room)
    if state is None:
        return jsonify({'error':'room not found'}), 404
    if requester not in ('p1','p2'):
        return jsonify({'error':'invalid player'}), 400
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name or len(name) > 25:
        return jsonify({'error':'invalid name (1-25 chars)'}), 400
    state['names'][requester] = name
    return jsonify({'ok': True, 'names': state['names']})

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
    # Rundendaten in History eintragen/aktualisieren
    current = {'term': state['current_term'], 'a1': state['answers']['p1'], 'a2': state['answers']['p2'], 'awarded': False}
    idx = state['round'] - 1
    if idx < len(state['rounds']):
        state['rounds'][idx].update(current)
    else:
        state['rounds'].append(current)
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
    # Pro Runde nur einmal werten
    idx = state['round'] - 1
    if idx < len(state['rounds']) and state['rounds'][idx].get('awarded'):
        return jsonify(serialize_state(state, requester))
    state['score'] += 1
    if idx < len(state['rounds']):
        state['rounds'][idx]['awarded'] = True
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
    # nicht über die Maximalrunde hinaus
    if state['round'] >= state['max_rounds']:
        return jsonify(serialize_state(state, requester))
    state['round'] += 1
    state['revealed'] = False
    state['answers'] = {'p1': None, 'p2': None}
    state['current_term'] = next_term(state)
    return jsonify(serialize_state(state, requester))

@app.get('/finish')
def finish():
    room = request.args.get('room')
    state = ensure_room(room)
    if state is None:
        return "Room required", 400
    state['game_over'] = True
    # sicherstellen, dass die letzte Runde geloggt ist
    idx = state['round'] - 1
    if idx >= 0:
        if idx >= len(state['rounds']):
            state['rounds'].append({'term': state['current_term'], 'a1': state['answers']['p1'], 'a2': state['answers']['p2'], 'awarded': False})
        else:
            state['rounds'][idx].update({'term': state['current_term'], 'a1': state['answers']['p1'], 'a2': state['answers']['p2']})
    n1 = state['names'].get('p1') or 'Spieler 1'
    n2 = state['names'].get('p2') or 'Spieler 2'
    return render_template_string(RESULTS_PAGE,
                                  room=room,
                                  score=state['score'],
                                  max_rounds=state['max_rounds'],
                                  rounds=state['rounds'],
                                  n1=n1, n2=n2)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
