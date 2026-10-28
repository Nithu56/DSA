const $ = (selector) => document.querySelector(selector);
const stateUrl = '/api/state';
let current = null;
let showingSearch = false;
let searchTimer = null;

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
function notify(message, type = '') {
  const element = $('#notice');
  element.textContent = message;
  element.className = `notice${type ? ` ${type}` : ''}`;
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || 'GET',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: 'no-store'
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
function selectedStart() { return $('#traversal-start').value; }
function stateQuery() {
  const query = new URLSearchParams({ sort: $('#sort').value, status: $('#filter-status').value, start: selectedStart() });
  if (showingSearch) query.set('prefix', $('#search').value.trim());
  return query;
}
async function refresh(message, type = 'success') {
  try {
    current = await api(`${stateUrl}?${stateQuery()}`);
    $('#storage-status').textContent = 'Saved on this computer · Python';
    render(current);
    if (message) notify(message, type);
  } catch (error) {
    $('#storage-status').textContent = 'Python app not connected';
    notify(`${error.message} Start the app with run_windows.bat.`, 'error');
  }
}
function fillSelect(selector, events, desired) {
  const select = $(selector);
  const prior = desired ?? select.value;
  select.innerHTML = events.map((event) => `<option value="${event.id}">${escapeHtml(event.title)} (#${event.id})</option>`).join('') || '<option value="">No events</option>';
  const fallback = selector === '#after' && events.length > 1 ? events[1].id : events[0]?.id;
  const value = prior || fallback;
  if (events.some((event) => String(event.id) === String(value))) select.value = String(value);
}
function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}
function render(data) {
  const allEvents = data.graph.nodes;
  const colors = { scheduled: '#33816d', 'in progress': '#4c7894', completed: '#78a65a', cancelled: '#bd7160' };
  $('#counts').innerHTML = Object.entries(data.counts).map(([status, count]) => `<div class="stat" style="--accent:${colors[status]}"><strong>${count}</strong><span>${escapeHtml(status[0].toUpperCase() + status.slice(1))}</span></div>`).join('');
  const rows = data.events.map((event) => `<tr><td><span class="event-name">${escapeHtml(event.title)}</span><span class="event-description">${escapeHtml(event.description)}</span></td><td>${escapeHtml(formatDate(event.start_time))}<span class="subtle">to ${escapeHtml(formatDate(event.end_time))}</span></td><td>${escapeHtml(event.resource || '—')}</td><td><span class="badge">${event.priority}</span></td><td><span class="status status-${escapeHtml(event.status.replace(' ', '-'))}">${escapeHtml(event.status)}</span></td><td><div class="row-actions"><button class="button button-small" data-action="edit" data-id="${event.id}" type="button">Edit</button><button class="button button-small danger" data-action="delete" data-id="${event.id}" type="button">Delete</button><button class="button button-small button-quiet" data-action="graph" data-id="${event.id}" type="button">Graph</button></div></td></tr>`);
  $('#events').innerHTML = rows.length ? rows.join('') : `<tr><td colspan="6" class="empty-row">${showingSearch && $('#search').value.trim() ? 'No event title matches.' : 'No events match these filters.'}</td></tr>`;
  $('#priority-list').innerHTML = data.priority.length ? data.priority.map((event) => `<li><strong>${escapeHtml(event.title)}</strong> · priority ${event.priority}<span class="subtle">${escapeHtml(formatDate(event.start_time))}</span></li>`).join('') : '<li class="subtle">No active events.</li>';
  $('#waiting-list').innerHTML = data.waiting.length ? data.waiting.map((request) => `<li><strong>${escapeHtml(request.title)}</strong><span class="subtle">${escapeHtml(request.resource || 'No resource')} · waiting</span></li>`).join('') : '<li class="subtle">Queue is empty.</li>';
  fillSelect('#enqueue-event', allEvents);
  fillSelect('#before', allEvents);
  fillSelect('#after', allEvents);
  fillSelect('#traversal-start', allEvents, data.graph.start);
  $('#undo').disabled = !data.history_length;
  $('#enqueue').disabled = !allEvents.length;
  $('#process-queue').disabled = !data.waiting.length;
  $('#add-dependency').disabled = allEvents.length < 2;
  renderGraph(data.graph);
}
function renderGraph(graph) {
  const canvas = $('#graph-canvas');
  if (!graph.nodes.length) {
    canvas.innerHTML = '<div class="graph-empty">Add events to build the dependency graph.</div>';
    $('#graph-output').textContent = 'No events to traverse.';
    return;
  }
  const width = 760, columns = 3, rowHeight = 132;
  const positions = new Map(graph.nodes.map((event, index) => [event.id, { x: 130 + (index % columns) * 250, y: 52 + Math.floor(index / columns) * rowHeight }]));
  const paths = graph.edges.map(([from, to]) => {
    const a = positions.get(from), b = positions.get(to);
    if (!a || !b) return '';
    const direction = b.x >= a.x ? 1 : -1;
    const sx = a.x + direction * 96, tx = b.x - direction * 96;
    const lift = a.y === b.y ? -24 : 0;
    const fromTitle = graph.nodes.find((event) => event.id === from)?.title || `#${from}`;
    const toTitle = graph.nodes.find((event) => event.id === to)?.title || `#${to}`;
    return `<path class="graph-edge" d="M ${sx} ${a.y} C ${sx + direction * 52} ${a.y + lift}, ${tx - direction * 52} ${b.y + lift}, ${tx} ${b.y}" marker-end="url(#graph-arrow)"><title>${escapeHtml(fromTitle)} → ${escapeHtml(toTitle)}</title></path>`;
  }).join('');
  const nodes = graph.nodes.map((event) => {
    const { x, y } = positions.get(event.id);
    const currentClass = event.id === graph.start ? ' current-node' : '';
    const label = event.title.length > 23 ? `${event.title.slice(0, 21)}…` : event.title;
    return `<g class="graph-node${currentClass}"><rect x="${x - 94}" y="${y - 29}" width="188" height="58" rx="12"/><text class="node-title" text-anchor="middle" x="${x}" y="${y - 2}">${escapeHtml(label)}</text><text class="node-meta" text-anchor="middle" x="${x}" y="${y + 16}">#${event.id} · ${escapeHtml(event.status)}</text><title>${escapeHtml(event.title)}</title></g>`;
  }).join('');
  const height = 96 + Math.ceil(graph.nodes.length / columns) * rowHeight;
  canvas.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="presentation" aria-hidden="true"><defs><marker id="graph-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path class="graph-arrow" d="M0,0 L9,4.5 L0,9 Z"/></marker></defs>${paths}${nodes}</svg>`;
  const links = graph.edges.map(([from, to]) => `${graph.nodes.find((event) => event.id === from)?.title || `#${from}`} → ${graph.nodes.find((event) => event.id === to)?.title || `#${to}`}`);
  const startTitle = graph.nodes.find((event) => event.id === graph.start)?.title || 'No starting event';
  $('#graph-output').textContent = `Starting event: ${startTitle}\nBFS  ${graph.bfs.join('  →  ') || 'No reachable events'}\nDFS  ${graph.dfs.join('  →  ') || 'No reachable events'}\nLinks  ${links.join('  ·  ') || 'No dependencies yet'}`;
}
function defaultTimes() {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(start.getHours() + 1);
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  const localValue = (date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  return [localValue(start), localValue(end)];
}
function clearForm() {
  HTMLFormElement.prototype.reset.call($('#event-form'));
  $('#event-id').value = '';
  $('#priority').value = '0';
  $('#form-heading').textContent = 'Create an event';
  $('#save').textContent = 'Save event';
  const [start, end] = defaultTimes();
  $('#start').value = start;
  $('#end').value = end;
}
async function submitAction(path, body, successMessage) {
  try {
    const response = await api(path, { method: 'POST', body });
    await refresh(response.message || successMessage);
    return true;
  } catch (error) {
    notify(error.message, 'error');
    return false;
  }
}

$('#event-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    id: $('#event-id').value || null,
    title: $('#title').value,
    description: $('#description').value,
    start_time: $('#start').value,
    end_time: $('#end').value,
    priority: $('#priority').value,
    status: $('#status').value,
    resource: $('#resource').value
  };
  const saved = await submitAction('/api/events', payload);
  if (saved) { clearForm(); showingSearch = false; $('#search').value = ''; await refresh('Event saved successfully.'); }
});
$('#clear-form').addEventListener('click', () => { clearForm(); notify('Form cleared.'); });
$('#events').addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === 'edit') {
    const item = current.graph.nodes.find((candidate) => candidate.id === id);
    if (!item) return;
    for (const [key, value] of Object.entries({ title: item.title, description: item.description, start: item.start_time, end: item.end_time, priority: item.priority, status: item.status, resource: item.resource || '' })) $(`#${key}`).value = value;
    $('#event-id').value = item.id;
    $('#form-heading').textContent = 'Edit event';
    $('#save').textContent = 'Save changes';
    $('#title').focus();
  } else if (button.dataset.action === 'delete') {
    const item = current.graph.nodes.find((candidate) => candidate.id === id);
    if (!item || !confirm(`Delete “${item.title}”?`)) return;
    await submitAction('/api/delete', { id });
  } else if (button.dataset.action === 'graph') {
    $('#traversal-start').value = String(id);
    await refresh();
    $('#graph-canvas').closest('.panel').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
});
$('#undo').addEventListener('click', async () => { await submitAction('/api/undo', {}); });
$('#sort').addEventListener('change', () => refresh());
$('#filter-status').addEventListener('change', () => refresh());
$('#search-button').addEventListener('click', () => { showingSearch = true; refresh(); });
$('#search').addEventListener('input', () => {
  if (!showingSearch) return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => refresh(), 180);
});
$('#search').addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); showingSearch = true; refresh(); } });
$('#clear-search').addEventListener('click', () => { showingSearch = false; $('#search').value = ''; refresh('Showing all events.'); });
$('#enqueue').addEventListener('click', async () => { await submitAction('/api/queue', { action: 'add', id: Number($('#enqueue-event').value) }); });
$('#process-queue').addEventListener('click', async () => { await submitAction('/api/queue', { action: 'process' }); });
$('#clear-queue').addEventListener('click', async () => { await submitAction('/api/queue', { action: 'clear' }); });
$('#add-dependency').addEventListener('click', async () => {
  const added = await submitAction('/api/dependencies', { before: Number($('#before').value), after: Number($('#after').value) });
  if (added) { $('#traversal-start').value = $('#before').value; await refresh(); $('#graph-canvas').closest('.panel').scrollIntoView({ behavior: 'smooth', block: 'center' }); }
});
$('#traverse').addEventListener('click', async () => { await refresh('BFS and DFS results updated.'); });
$('#export-data').addEventListener('click', async () => {
  try {
    const response = await fetch('/api/export');
    if (!response.ok) throw new Error('Could not export the schedule.');
    const file = await response.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(file);
    link.download = 'event-scheduler-backup.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    notify('Events and dependencies exported as JSON.', 'success');
  } catch (error) { notify(error.message, 'error'); }
});
$('#import-data').addEventListener('click', () => $('#import-file').click());
$('#import-file').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    await submitAction('/api/import', payload);
  } catch (error) { notify(error.message, 'error'); }
  event.target.value = '';
});
$('#demo-data').addEventListener('click', async () => {
  if (!confirm('Replace the current schedule with the five showcase events?')) return;
  const loaded = await submitAction('/api/showcase', {});
  if (loaded) { $('#traversal-start').value = '1'; await refresh(); }
});

clearForm();
refresh();
