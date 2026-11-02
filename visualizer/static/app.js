import {layout} from './layout.js';

const svg = document.querySelector('#canvas');
const viewport = document.querySelector('#viewport');
const ns = 'http://www.w3.org/2000/svg';
let data = {nodes: [], edges: []}, revision = -1;
let transform = {x: 60, y: 85, k: 1};
let bounds = {x: 0, y: 0, width: 400, height: 300};
function el(tag, attrs = {}, text) {
  const node = document.createElementNS(ns, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function applyTransform() { viewport.setAttribute('transform', `translate(${transform.x},${transform.y}) scale(${transform.k})`); }
function appendLabel(g, node, isRoot = false) {
  const label = node.label;
  if (!label) return;
  const centerY = node.bodyHeight / 2;
  g.append(el('line', {class: 'label-connector', x1: node.bodyWidth, y1: centerY, x2: label.x, y2: centerY}));
  const tag = el('g', {class: 'node-label', transform: `translate(${label.x},${label.y})`});
  const maxNames = Math.floor((label.width - 20) / 7);
  tag.append(
    el('title', {}, label.lines.join('\n')),
    el('rect', {width: label.width, height: label.height, rx: 7}),
  );
  label.lines.forEach((line, index) => {
    const text = line.length > maxNames ? line.slice(0, maxNames - 1) + '…' : line;
    tag.append(el('text', {
      class: `names${isRoot && index === 0 ? ' root-label' : ''}`,
      x: 10, y: 14 + index * 18,
    }, text));
  });
  g.append(tag);
}
let renderGeneration = 0;
let layoutError = '';
async function render() {
  const generation = ++renderGeneration;
  const snapshot = data;
  let geometry;
  try {
    geometry = await layout(snapshot.nodes ?? [], snapshot.edges ?? [], snapshot.root);
  } catch (error) {
    if (generation === renderGeneration) {
      layoutError = `Unable to lay out pointer graph: ${error.message}`;
      document.querySelector('#notice').textContent = layoutError;
    }
    return;
  }
  // A newer pause or NIL toggle can overtake this asynchronous layout.
  if (generation !== renderGeneration) return;
  layoutError = '';
  const showNil = document.querySelector('#nil').checked;
  const content = document.createDocumentFragment();
  for (const group of geometry.groups) {
    const height = showNil ? group.height : Math.max(80, ...geometry.nodes.filter(node => node.group === group.id && (!node.nil || node.referenced)).map(node => node.y + node.height - group.y + 24));
    if (group.id === 'detached') content.append(el('rect', {x: group.x, y: group.y, width: group.width, height, rx: 16, class: 'detached-region'}));
    content.append(el('text', {x: group.x + 24, y: group.y + 26, class: 'group-label'}, {attached: 'ROOTED TREE', detached: 'DETACHED · STILL LIVE'}[group.id]));
  }
  for (const edge of geometry.edges) {
    if (edge.nil && !showNil && !edge.referenced) continue;
    const record = edge.record;
    for (const points of edge.sections) {
      const path = points.map((point, i) => `${i ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
      const line = el('path', {d: path, class: `edge${edge.nil ? ' nil-edge' : ''} ${record?.warnings.length ? 'warning' : ''}`});
      line.append(el('title', {}, record?.warnings.join('; ') || `${record?.side ?? 'NIL'} child`));
      content.append(line);
    }
    for (const label of edge.labels) content.append(el('text', {x: label.x + label.width / 2, y: label.y + 11, class: 'edge-label', 'text-anchor': 'middle'}, label.text));
  }
  for (const node of geometry.nodes) {
    if (node.nil) {
      if (!showNil && !node.referenced) continue;
      const width = node.bodyWidth ?? node.width, height = node.bodyHeight ?? node.height;
      const g = el('g', {transform: `translate(${node.x},${node.y})`, class: `nil${node.referenced ? ' named-nil' : ''}`, 'data-id': node.id});
      g.append(el('title', {}, `Shared NIL sentinel${snapshot.nil_address ? ' · ' + snapshot.nil_address : ''}`));
      g.append(el('rect', {width, height, rx: 5}), el('text', {x: width / 2, y: 16}, 'NIL'));
      appendLabel(g, node);
      content.append(g);
      continue;
    }
    const record = node.record;
    const incident = (snapshot.edges ?? []).some(edge => (edge.source === record.id || edge.target === record.id) && edge.warnings.length);
    const g = el('g', {transform: `translate(${node.x},${node.y})`, class: `node ${record.color} ${record.warnings.length || incident ? 'warning' : ''}`, 'data-id': record.id});
    g.append(el('title', {}, `#${record.id} · ${record.address}\n${record.names.join(', ')}\nparent: ${record.parent ? '#'+record.parent : record.parent_is_nil ? 'NIL' : 'None'}\n${record.warnings.join('\n')}`));
    g.append(el('rect', {class: 'node-body', width: node.bodyWidth, height: node.bodyHeight, rx: 12}));
    appendLabel(g, node, record.id === snapshot.root);
    g.append(
      el('text', {class: 'key', x: node.bodyWidth / 2, y: 26}, record.key.length > 9 ? record.key.slice(0, 8) + '…' : record.key),
      el('text', {class: 'color', x: node.bodyWidth / 2, y: 50}, record.color === 'unknown' ? '?' : record.color === 'red' ? 'RED' : 'BLACK'),
      el('text', {class: 'identity', x: node.bodyWidth / 2, y: 69}, `#${record.id}`),
    );
    content.append(g);
  }
  viewport.replaceChildren(content);
  bounds = viewport.getBBox();
  applyTransform();
  const nodes = snapshot.nodes ?? [];
  document.querySelector('#counts').textContent = `${nodes.length} live nodes · ${nodes.filter(n => n.detached).length} detached · ${(snapshot.warnings ?? []).length} warnings`;
  const warnings = document.querySelector('#warnings');
  warnings.replaceChildren();
  for (const warning of snapshot.warnings ?? []) { const p = document.createElement('p'); p.textContent = '⚠ '+warning; warnings.append(p); }
  warnings.hidden = !snapshot.warnings?.length;
  svg.dataset.revision = snapshot.revision ?? '';
}
function fit() {
  if (!data.nodes?.length) return;
  const width = svg.clientWidth, height = svg.clientHeight;
  const k = Math.min(2, Math.max(.05, Math.min((width-60)/(bounds.width+60), (height-80)/(bounds.height+60))));
  transform = {k, x: width/2-(bounds.x+bounds.width/2)*k, y: height/2-(bounds.y+bounds.height/2)*k};
  applyTransform();
}
document.querySelector('#fit').addEventListener('click', fit);
document.querySelector('#nil').addEventListener('change', render);
svg.addEventListener('wheel', event => {
  event.preventDefault();
  const rect = svg.getBoundingClientRect(), x = event.clientX-rect.left, y = event.clientY-rect.top;
  const k = Math.max(.05, Math.min(5, transform.k * Math.exp(-event.deltaY*.001)));
  transform = {k, x: x-(x-transform.x)*k/transform.k, y: y-(y-transform.y)*k/transform.k};
  applyTransform();
}, {passive: false});
let drag = null;
svg.addEventListener('pointerdown', e => { drag = {x: e.clientX, y: e.clientY}; svg.setPointerCapture(e.pointerId); });
svg.addEventListener('pointermove', e => { if (!drag) return; transform.x += e.clientX-drag.x; transform.y += e.clientY-drag.y; drag = {x: e.clientX, y: e.clientY}; applyTransform(); });
svg.addEventListener('pointerup', () => { drag = null; });
svg.addEventListener('pointercancel', () => { drag = null; });
async function poll() {
  try {
    const response = await fetch('state', {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const next = await response.json();
    const status = document.querySelector('#status');
    status.textContent = next.status[0].toUpperCase()+next.status.slice(1);
    status.dataset.state = next.status;
    document.querySelector('#notice').textContent = layoutError || ({paused: 'Stopped frame · actual pointer state', running: 'Running · showing the last paused snapshot', ended: 'Session ended · last snapshot retained', waiting: 'Waiting for a registered tree', error: 'Snapshot unavailable'})[next.status] + (next.message ? ' — '+next.message : '');
    if (next.revision !== revision) { data = next; revision = next.revision; render(); }
  } catch (_error) {
    document.querySelector('#status').textContent = 'Disconnected';
    document.querySelector('#status').dataset.state = 'error';
    document.querySelector('#notice').textContent = 'Companion server disconnected · displayed state is no longer live';
  } finally { setTimeout(poll, 250); }
}
applyTransform();
poll();
