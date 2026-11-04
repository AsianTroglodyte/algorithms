import {layout, focusSnapshot} from './layout.js';

const svg = document.querySelector('#canvas');
const viewport = document.querySelector('#viewport');
const ns = 'http://www.w3.org/2000/svg';
let data = {nodes: [], edges: []}, revision = -1;
let transform = {x: 60, y: 85, k: 1};
let bounds = {x: 0, y: 0, width: 400, height: 300};
let previousSnapshot = null, recentActive = [], currentActive = [];
let lastPositions = new Map();
const pinned = new Set(), expanded = new Set();
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
function el(tag, attrs = {}, text) {
  const node = document.createElementNS(ns, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function applyTransform() { viewport.setAttribute('transform', `translate(${transform.x},${transform.y}) scale(${transform.k})`); }
function edgePath(points, rounded) {
  if (!rounded || points.length < 3) return points.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length - 1; ++i) {
    const a = points[i - 1], b = points[i], c = points[i + 1];
    const before = Math.hypot(b.x - a.x, b.y - a.y), after = Math.hypot(c.x - b.x, c.y - b.y);
    const radius = Math.min(10, before / 2, after / 2);
    path += ` L ${b.x + (a.x - b.x) * radius / before} ${b.y + (a.y - b.y) * radius / before}`;
    path += ` Q ${b.x} ${b.y} ${b.x + (c.x - b.x) * radius / after} ${b.y + (c.y - b.y) * radius / after}`;
  }
  return path + ` L ${points.at(-1).x} ${points.at(-1).y}`;
}
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
  const focus = document.querySelector('#view-mode').value === 'focus';
  const projection = focusSnapshot(snapshot, {previous: previousSnapshot, recent: recentActive, pinned, expanded});
  currentActive = projection.active;
  const view = focus ? projection : snapshot;
  const showNil = document.querySelector('#nil').checked;
  const sharedNil = showNil && document.querySelector('#nil-view').value === 'shared';
  let geometry;
  try {
    geometry = await layout(view.nodes ?? [], view.edges ?? [], snapshot.root, {
      sharedNil, rootIsNil: snapshot.root_is_nil, nilNames: snapshot.nil_names,
    });
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
  const positions = new Map(geometry.nodes.map(node => [node.id, {x: node.x + node.bodyWidth / 2, y: node.y + node.bodyHeight / 2}]));
  let cameraShift = {x: 0, y: 0};
  if (focus) {
    const anchor = [projection.anchor, ...projection.active, ...recentActive].find(id => lastPositions.has(id) && positions.has(id));
    if (anchor) {
      cameraShift = {x: lastPositions.get(anchor).x - positions.get(anchor).x, y: lastPositions.get(anchor).y - positions.get(anchor).y};
      transform.x += cameraShift.x * transform.k;
      transform.y += cameraShift.y * transform.k;
    }
  }
  function animateNode(g, node) {
    const old = lastPositions.get(node.id);
    if (!focus || !old || reducedMotion.matches) return;
    const current = positions.get(node.id);
    const dx = old.x - current.x - cameraShift.x, dy = old.y - current.y - cameraShift.y;
    if (dx || dy) g.animate([
      {transform: `translate(${node.x + dx}px, ${node.y + dy}px)`},
      {transform: `translate(${node.x}px, ${node.y}px)`},
    ], {duration: 180, easing: 'ease-out'});
  }
  function makeInteractive(g, node, folded = false) {
    if (!focus) return;
    const record = node.record;
    const action = folded ? `Expand subtree at ${record.key}, ${record.foldedCount} nodes` : `${pinned.has(record.id) ? 'Unpin' : 'Pin'} node ${record.key}`;
    g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button');
    g.setAttribute('aria-label', action);
    interactiveElements.set(record.id, g);
    if (!folded) g.setAttribute('aria-pressed', String(pinned.has(record.id)));
    const activate = () => {
      if (folded) expanded.add(record.id);
      else if (pinned.has(record.id)) pinned.delete(record.id);
      else pinned.add(record.id);
      render();
    };
    // A drag pans the canvas; only a stationary click pins or expands.
    g.addEventListener('click', event => { if (!dragMoved) { event.stopPropagation(); activate(); } });
    g.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); activate(); }
    });
  }
  const content = document.createDocumentFragment(), interactiveElements = new Map();
  for (const group of geometry.groups) {
    const height = showNil ? group.height : Math.max(80, ...geometry.nodes.filter(node => node.group === group.id && (!node.nil || node.referenced)).map(node => node.y + node.height - group.y + 24));
    if (group.id === 'detached') content.append(el('rect', {x: group.x, y: group.y, width: group.width, height, rx: 16, class: 'detached-region'}));
    content.append(el('text', {x: group.x + 24, y: group.y + 26, class: 'group-label'}, {attached: 'ROOTED TREE', detached: 'DETACHED · STILL LIVE'}[group.id]));
  }
  for (const edge of geometry.edges) {
    if (edge.nil && !showNil && !edge.referenced) continue;
    const record = edge.record;
    for (const points of edge.sections) {
      const path = edgePath(points, edge.rounded);
      const line = el('path', {
        d: path, class: `edge${edge.nil ? ' nil-edge' : ''}${edge.parent ? ' parent-edge' : ''} ${record?.warnings.length ? 'warning' : ''}`,
        ...(edge.pointer ? {'data-source': edge.sourceNode, 'data-target': edge.targetNode, 'data-pointer': edge.pointer} : {}),
      });
      line.append(el('title', {}, edge.title || record?.warnings.join('; ') || `${record?.side ?? 'NIL'} child`));
      content.append(line);
    }
    for (const label of edge.labels) content.append(el('text', {x: label.x + label.width / 2, y: label.y + 11, class: `edge-label${edge.parent ? ' parent-label' : ''}`, 'text-anchor': 'middle'}, label.text));
  }
  for (const node of geometry.nodes) {
    if (node.nil) {
      if (!showNil && !node.referenced) continue;
      const width = node.bodyWidth ?? node.width, height = node.bodyHeight ?? node.height;
      const g = el('g', {transform: `translate(${node.x},${node.y})`, class: `nil${node.label ? ' named-nil' : ''}${node.shared ? ' shared-nil' : ''}`, 'data-id': node.id});
      g.append(el('title', {}, `Shared NIL sentinel${snapshot.nil_address ? ' · ' + snapshot.nil_address : ''}`));
      g.append(el('rect', {width, height, rx: node.shared ? 12 : 5}));
      if (node.shared) {
        g.append(el('text', {class: 'nil-name', x: width / 2, y: 27}, 'NIL'), el('text', {class: 'nil-color', x: width / 2, y: 47}, 'BLACK'));
      } else {
        g.append(el('text', {x: width / 2, y: height / 2 + 4}, 'NIL'));
      }
      appendLabel(g, node, node.root);
      content.append(g);
      continue;
    }
    const record = node.record;
    if (record.detail === 'folded') {
      const g = el('g', {transform: `translate(${node.x},${node.y})`, class: 'folded-subtree', 'data-id': record.id, 'data-count': record.foldedCount});
      g.append(el('title', {}, `${record.foldedCount} nodes, rooted at ${record.key}. Click or press Enter to expand.`),
        el('path', {d: `M ${node.bodyWidth / 2} 0 L ${node.bodyWidth} 34 L 0 34 Z`}),
        el('text', {x: node.bodyWidth / 2, y: 26, class: 'folded-key'}, record.key.length > 8 ? record.key.slice(0, 7) + '…' : record.key),
        el('text', {x: node.bodyWidth / 2, y: 51, class: 'folded-count'}, `${record.foldedCount} nodes`));
      makeInteractive(g, node, true); animateNode(g, node); content.append(g);
      continue;
    }
    const incident = (snapshot.edges ?? []).some(edge => (edge.source === record.id || edge.target === record.id) && edge.warnings.length);
    const compact = record.detail === 'compact';
    const g = el('g', {transform: `translate(${node.x},${node.y})`, class: `node ${record.color} ${record.warnings.length || incident ? 'warning' : ''}${compact ? ' compact' : ''}${record.focused ? ' focused' : ''}${record.pinned ? ' pinned' : ''}`, 'data-id': record.id});
    g.append(el('title', {}, `#${record.id} · ${record.address}\n${record.names.join(', ')}\nparent: ${record.parent ? '#'+record.parent : record.parent_is_nil ? 'NIL' : 'None'}\n${record.warnings.join('\n')}`));
    g.append(el('rect', {class: 'node-body', width: node.bodyWidth, height: node.bodyHeight, rx: 12}));
    appendLabel(g, node, record.id === snapshot.root);
    const maxKey = compact ? 5 : 9;
    g.append(el('text', {class: 'key', x: node.bodyWidth / 2, y: compact ? node.bodyHeight / 2 : 26}, record.key.length > maxKey ? record.key.slice(0, maxKey - 1) + '…' : record.key));
    if (!compact) g.append(
      el('text', {class: 'color', x: node.bodyWidth / 2, y: 50}, record.color === 'unknown' ? '?' : record.color === 'red' ? 'RED' : 'BLACK'),
      el('text', {class: 'identity', x: node.bodyWidth / 2, y: 69}, `#${record.id}`),
    );
    makeInteractive(g, node); animateNode(g, node);
    content.append(g);
  }
  const focusedId = document.activeElement?.closest('#viewport [data-id]')?.getAttribute('data-id');
  viewport.replaceChildren(content);
  if (focusedId) interactiveElements.get(focusedId)?.focus({preventScroll: true});
  bounds = viewport.getBBox();
  applyTransform();
  lastPositions = positions;
  document.querySelector('#reset-focus').hidden = !focus;
  const help = document.querySelector('#focus-help');
  help.hidden = !focus;
  help.textContent = projection.unsafe ? 'Pointer inconsistency: showing the full graph.' :
    `${projection.nodes.filter(node => node.detail !== 'folded').length} shown · ${projection.folded} in folded subtrees · ${pinned.size} pinned · Click a node to pin; click a triangle to expand. Tab + Enter also works.`;
  const nodes = snapshot.nodes ?? [];
  document.querySelector('#counts').textContent = `${nodes.length} live nodes · ${nodes.filter(n => n.detached).length} detached · ${(snapshot.warnings ?? []).length} warnings`;
  const warnings = document.querySelector('#warnings');
  warnings.replaceChildren();
  for (const warning of snapshot.warnings ?? []) { const p = document.createElement('p'); p.textContent = '⚠ '+warning; warnings.append(p); }
  warnings.hidden = !snapshot.warnings?.length;
  svg.dataset.revision = snapshot.revision ?? '';
  svg.dataset.nilView = sharedNil ? 'shared' : 'leaves';
  svg.dataset.viewMode = focus ? 'focus' : 'full';
  document.querySelector('#legend').textContent = `Solid edges: child pointers${sharedNil ? ' · Blue: parent → NIL' : ''} · Dashed amber: inconsistency · Node fill: actual color`;
}
function fit() {
  if (!bounds.width || !bounds.height) return;
  const width = svg.clientWidth, height = svg.clientHeight;
  const k = Math.min(2, Math.max(.05, Math.min((width-60)/(bounds.width+60), (height-80)/(bounds.height+60))));
  transform = {k, x: width/2-(bounds.x+bounds.width/2)*k, y: height/2-(bounds.y+bounds.height/2)*k};
  applyTransform();
}
document.querySelector('#fit').addEventListener('click', fit);
document.querySelector('#view-mode').addEventListener('change', render);
document.querySelector('#reset-focus').addEventListener('click', () => { pinned.clear(); expanded.clear(); render(); });
document.querySelector('#nil').addEventListener('change', () => {
  document.querySelector('#nil-view-control').hidden = !document.querySelector('#nil').checked;
  render();
});
document.querySelector('#nil-view').addEventListener('change', render);
svg.addEventListener('wheel', event => {
  event.preventDefault();
  const rect = svg.getBoundingClientRect(), x = event.clientX-rect.left, y = event.clientY-rect.top;
  const k = Math.max(.05, Math.min(5, transform.k * Math.exp(-event.deltaY*.001)));
  transform = {k, x: x-(x-transform.x)*k/transform.k, y: y-(y-transform.y)*k/transform.k};
  applyTransform();
}, {passive: false});
let drag = null, dragMoved = false;
svg.addEventListener('pointerdown', e => {
  if (e.button !== 0) return;
  dragMoved = false;
  drag = {x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY};
  // Keep the click target on nodes; background drags still capture the pointer.
  if (!e.target.closest('[role="button"]')) svg.setPointerCapture(e.pointerId);
});
svg.addEventListener('pointermove', e => {
  if (!drag) return;
  if (Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) > 4) {
    dragMoved = true;
    svg.setPointerCapture(e.pointerId);
  }
  transform.x += e.clientX - drag.x; transform.y += e.clientY - drag.y;
  drag.x = e.clientX; drag.y = e.clientY; applyTransform();
});
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
    if (next.revision !== revision) {
      // Running/ended state updates retain the last paused focus and its history.
      if (next.status === 'paused' || !data.nodes?.length) {
        previousSnapshot = data.nodes?.length ? data : null;
        recentActive = currentActive;
      }
      const liveIds = new Set((next.nodes ?? []).map(node => node.id));
      for (const set of [pinned, expanded]) for (const id of set) if (!liveIds.has(id)) set.delete(id);
      data = next; revision = next.revision; render();
    }
  } catch (_error) {
    document.querySelector('#status').textContent = 'Disconnected';
    document.querySelector('#status').dataset.state = 'error';
    document.querySelector('#notice').textContent = 'Companion server disconnected · displayed state is no longer live';
  } finally { setTimeout(poll, 250); }
}
applyTransform();
poll();
