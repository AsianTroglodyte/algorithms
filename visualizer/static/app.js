const svg = document.querySelector('#canvas');
const viewport = document.querySelector('#viewport');
const ns = 'http://www.w3.org/2000/svg';
let data = {nodes: [], edges: []}, revision = -1, positions = new Map();
let transform = {x: 60, y: 85, k: 1};
let bounds = {x: 0, y: 0, width: 400, height: 300};
function el(tag, attrs = {}, text) {
  const node = document.createElementNS(ns, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function applyTransform() { viewport.setAttribute('transform', `translate(${transform.x},${transform.y}) scale(${transform.k})`); }
function layout(nodes, edges, root) {
  const byId = new Map(nodes.map(n => [n.id, n]));
  const adjacency = new Map(nodes.map(n => [n.id, []]));
  edges.forEach(e => adjacency.get(e.source)?.push(e));
  const result = new Map();
  let offset = 0;
  // Each identity gets a single position. A spanning forest lays out even cycles.
  function component(start) {
    const levels = [], stack = [[start, 0]];
    while (stack.length) {
      const [id, depth] = stack.pop();
      if (!byId.has(id) || result.has(id)) continue;
      result.set(id, null);
      (levels[depth] ??= []).push(id);
      const children = adjacency.get(id) ?? [];
      for (let i = children.length - 1; i >= 0; i--) stack.push([children[i].target, depth + 1]);
    }
    const width = Math.max(1, ...levels.map(l => l.length)) * 145;
    levels.forEach((level, depth) => level.forEach((id, i) => result.set(id, {x: offset + (i + .5) * width / level.length, y: depth * 135})));
    offset += width + 65;
  }
  if (root) component(root);
  const detachedStart = offset;
  const detached = nodes.filter(n => n.detached);
  // Prefer detached roots so normal detached subtrees retain a natural shape.
  const incoming = new Set(edges.filter(e => byId.get(e.source)?.detached).map(e => e.target));
  [...detached.filter(n => !incoming.has(n.id)), ...nodes].forEach(n => { if (!result.has(n.id)) component(n.id); });
  return {result, detachedStart};
}
function render() {
  viewport.replaceChildren();
  const {nodes = [], edges = [], root} = data;
  const layoutResult = layout(nodes, edges, root);
  positions = layoutResult.result;
  if (root && positions.has(root)) viewport.append(el('text', {x: positions.get(root).x, y: -58, 'text-anchor': 'middle', class: 'group-label'}, 'ROOT'));
  if (nodes.some(n => n.detached)) viewport.append(el('text', {x: layoutResult.detachedStart, y: -58, class: 'group-label'}, 'DETACHED · STILL LIVE'));
  for (const edge of edges) {
    const a = positions.get(edge.source), b = positions.get(edge.target);
    if (!a || !b) continue;
    const group = el('g');
    let path;
    if (a === b) path = `M ${a.x+20} ${a.y-20} C ${a.x+100} ${a.y-110}, ${a.x+100} ${a.y+110}, ${a.x+23} ${a.y+20}`;
    else {
      const dx = b.x - a.x, dy = b.y - a.y, length = Math.hypot(dx, dy) || 1;
      const x1 = a.x + dx/length*33, y1 = a.y + dy/length*33;
      const x2 = b.x - dx/length*37, y2 = b.y - dy/length*37;
      const bend = edge.side === 'left' ? -12 : 12;
      path = `M ${x1} ${y1} Q ${(x1+x2)/2 + bend} ${(y1+y2)/2} ${x2} ${y2}`;
    }
    const line = el('path', {d: path, class: `edge ${edge.warnings.length ? 'warning' : ''}`});
    line.append(el('title', {}, edge.warnings.join('; ') || `${edge.side} child`));
    group.append(line, el('text', {x: (a.x+b.x)/2 + (edge.side === 'left' ? -14 : 14), y: (a.y+b.y)/2 - 5, class: 'edge-label'}, edge.side === 'left' ? 'L' : 'R'));
    viewport.append(group);
  }
  for (const node of nodes) {
    const p = positions.get(node.id);
    const incident = edges.some(e => (e.source === node.id || e.target === node.id) && e.warnings.length);
    const g = el('g', {transform: `translate(${p.x},${p.y})`, class: `node ${node.color} ${node.warnings.length || incident ? 'warning' : ''}`});
    g.append(el('title', {}, `#${node.id} · ${node.address}\nparent: ${node.parent ? '#'+node.parent : 'None'}\n${node.warnings.join('\n')}`));
    g.append(el('circle', {r: 32}), el('text', {class: 'key', y: -3}, node.key.length > 9 ? node.key.slice(0,8)+'…' : node.key), el('text', {class: 'color', y: 21}, node.color === 'unknown' ? '?' : node.color === 'red' ? 'R' : 'B'));
    g.append(el('text', {class: 'names', y: -43}, node.names.join(', ')), el('text', {class: 'identity', y: 49}, `#${node.id}`));
    viewport.append(g);
    if (document.querySelector('#nil').checked) {
      for (const [side, dx] of [['left', -45], ['right', 45]]) {
        if (!node.nil_children?.includes(side)) continue;
        viewport.append(el('path', {d: `M ${p.x+dx/2} ${p.y+25} L ${p.x+dx} ${p.y+75}`, class: 'edge'}));
        const nil = el('g', {transform: `translate(${p.x+dx},${p.y+85})`, class: 'nil'});
        nil.append(el('rect', {x: -16, y: -9, width: 32, height: 18, rx: 3}), el('text', {y: 3}, 'NIL'));
        viewport.append(nil);
      }
    }
  }
  bounds = viewport.getBBox();
  applyTransform();
  document.querySelector('#counts').textContent = `${nodes.length} live nodes · ${nodes.filter(n => n.detached).length} detached · ${(data.warnings ?? []).length} warnings`;
  const warnings = document.querySelector('#warnings');
  warnings.replaceChildren();
  for (const warning of data.warnings ?? []) { const p = document.createElement('p'); p.textContent = '⚠ '+warning; warnings.append(p); }
  warnings.hidden = !data.warnings?.length;
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
    document.querySelector('#notice').textContent = ({paused: 'Stopped frame · actual pointer state', running: 'Running · showing the last paused snapshot', ended: 'Session ended · last snapshot retained', waiting: 'Waiting for a registered tree', error: 'Snapshot unavailable'})[next.status] + (next.message ? ' — '+next.message : '');
    if (next.revision !== revision) { data = next; revision = next.revision; render(); }
  } catch (_error) {
    document.querySelector('#status').textContent = 'Disconnected';
    document.querySelector('#status').dataset.state = 'error';
    document.querySelector('#notice').textContent = 'Companion server disconnected · displayed state is no longer live';
  } finally { setTimeout(poll, 250); }
}
applyTransform();
poll();
