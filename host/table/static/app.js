const log = document.querySelector('#log');
const banner = document.querySelector('#banner');
const form = document.querySelector('#composer');
const field = document.querySelector('#line');
const statePill = document.querySelector('#state-pill');
const modelPill = document.querySelector('#model-pill');
const areaLine = document.querySelector('#area-line');
const adventureLine = document.querySelector('#adventure-line');
const characterLine = document.querySelector('#character-line');
const beginBtn = document.querySelector('#begin');
const baseUrl = document.querySelector('#base-url');
const modelName = document.querySelector('#model-name');
const apiKey = document.querySelector('#api-key');
const warning = document.querySelector('#model-warning');

const tools = document.querySelector('#tools');
if (window.matchMedia('(min-width: 960px)').matches) tools.open = true;

let state = null;

function pill(el, text) { el.textContent = text; }

function render(next) {
  state = next;
  const model = next.model || {};
  pill(statePill, next.state || 'unmounted');
  pill(modelPill, model.configured ? (model.name || 'voice') : 'no voice');
  const area = next.view && next.view.area;
  areaLine.textContent = area ? area : 'No scene open';
  const adventure = next.adventure;
  adventureLine.textContent = adventure && adventure.title
    ? adventure.title + ' · ' + (adventure.readiness || '')
    : 'No adventure imported';
  characterLine.textContent = next.character && next.character.name
    ? next.character.name
    : 'No character sheet';
  beginBtn.disabled = !next.can_begin;
  if (!model.configured) {
    banner.hidden = false;
    banner.textContent = 'The rules engine is running on this device. Her voice is not connected. Turns are not invented. The opening can still be the book\'s own read-aloud.';
  } else if (model.warning) {
    banner.hidden = false;
    banner.textContent = model.warning;
  } else {
    banner.hidden = true;
  }
  warning.textContent = model.warning || '';
  if (!baseUrl.value) baseUrl.value = model.base_url || '';
  if (!modelName.value) modelName.value = model.name || '';
  draw(next.transcript || []);
}

function draw(rows) {
  log.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    const title = document.createElement('h2');
    title.textContent = 'Pull up a chair.';
    const copy = document.createElement('p');
    copy.textContent = 'Import an adventure and a character sheet, connect a voice if you have one, then begin. Hidden facts stay in the save on this tablet.';
    empty.append(title, copy);
    log.append(empty);
    return;
  }
  for (const row of rows) {
    const item = document.createElement('div');
    item.className = 'bubble ' + (row.role || 'note');
    item.textContent = row.text;
    log.append(item);
  }
  log.scrollTop = log.scrollHeight;
}

async function api(path, body, method) {
  const response = await fetch(path, {
    method: method || (body ? 'POST' : 'GET'),
    headers: body ? {'Content-Type': 'application/json'} : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (data.state) render(data.state);
  return data;
}

async function refresh() {
  const response = await fetch('/api/state');
  render(await response.json());
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = field.value.trim();
  if (!text) return;
  field.value = '';
  const data = await api('/api/message', {
    text,
    table_talk: document.querySelector('#table-talk').checked,
  });
  if (!data.ok && data.note) {
    const item = document.createElement('div');
    item.className = 'bubble note';
    item.textContent = data.note;
    log.append(item);
  }
});

beginBtn.addEventListener('click', () => api('/api/begin', {table: 'solo'}));

document.querySelector('#save').addEventListener('click', async () => {
  const data = await api('/api/save', {});
  if (data.download) {
    window.location = '/api/save/download?token=' + encodeURIComponent(data.download);
  }
  if (data.note) alert(data.note);
  if (data.ask_player) alert(data.ask_player);
});

document.querySelector('#abandon').addEventListener('click', () => api('/api/abandon', {}));
document.querySelector('#fresh').addEventListener('click', async () => {
  if (!confirm('Archive this campaign and start a new one on the tablet?')) return;
  await api('/api/campaign/new', {});
  await refresh();
});

document.querySelector('#import-text').addEventListener('click', async () => {
  const text = document.querySelector('#adventure').value;
  const data = await api('/api/import', {text});
  if (!data.ok && data.note) alert(data.note);
});

document.querySelector('#adventure-file').addEventListener('change', async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
    const response = await fetch('/api/import', {
      method: 'POST',
      headers: {'Content-Type': 'application/pdf'},
      body: await file.arrayBuffer(),
    });
    const data = await response.json();
    if (data.state) render(data.state);
    if (!data.ok && data.note) alert(data.note);
    return;
  }
  document.querySelector('#adventure').value = await file.text();
});

document.querySelector('#sheet-file').addEventListener('change', async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  let sheet;
  try {
    sheet = JSON.parse(await file.text());
  } catch (err) {
    alert('That file is not a JSON character sheet.');
    return;
  }
  const data = await api('/api/sheet', {sheet});
  if (!data.ok && data.note) alert(data.note);
});

document.querySelector('#settings').addEventListener('submit', async (event) => {
  event.preventDefault();
  const body = {base_url: baseUrl.value.trim(), name: modelName.value.trim()};
  if (apiKey.value.trim()) body.api_key = apiKey.value.trim();
  const data = await api('/api/settings', body);
  apiKey.value = '';
  if (data.model && data.model.warning) warning.textContent = data.model.warning;
  await refresh();
});

document.querySelector('#clear-key').addEventListener('click', async () => {
  await api('/api/settings', {base_url: baseUrl.value.trim(), name: modelName.value.trim(), api_key: ''});
  await refresh();
});

refresh();
