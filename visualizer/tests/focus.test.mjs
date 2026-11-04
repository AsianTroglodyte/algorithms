// Run from the repository root: node visualizer/tests/focus.test.mjs
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

// Valid BSTs use the ordered layout. Browser smoke tests exercise the bundled
// ELK engine for intermediate pointer graphs without its worker shim in Node.
globalThis.window = {ELK: class {layout() { throw new Error('Unexpected ELK fallback for a valid tree'); }}};
const source = await readFile(new URL('../static/layout.js', import.meta.url), 'utf8');
const {focusSnapshot, layout} = await import(`data:text/javascript;base64,${Buffer.from(source + '\n//# sourceURL=rb-layout.mjs').toString('base64')}`);
delete globalThis.window;

function fixture(count = 127, aliases = {'64': ['fix_node']}) {
  const nodes = [], edges = [];
  for (let n = 1; n <= count; n++) {
    const id = String(n), left = n * 2 <= count ? String(n * 2) : null, right = n * 2 + 1 <= count ? String(n * 2 + 1) : null;
    nodes.push({id, key: id, address: `0x${n}`, names: aliases[id] ?? [], color: n % 2 ? 'red' : 'black',
      parent: n > 1 ? String(n >> 1) : null, parent_is_nil: n === 1, left, right, detached: false, warnings: [],
      nil_children: [['left', left], ['right', right]].filter(([, id]) => !id).map(([side]) => side)});
    for (const [side, target] of [['left', left], ['right', right]]) if (target) edges.push({source: id, target, side, warnings: []});
  }
  return {nodes, edges, root: '1', warnings: []};
}

function assertRoutesClear(geometry) {
  for (const edge of geometry.edges) for (const points of edge.sections) {
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i];
      assert.ok(a.x === b.x || a.y === b.y);
      for (const node of geometry.nodes) {
        const rects = [{x: node.x, y: node.y, width: node.bodyWidth, height: node.bodyHeight}];
        if (node.label) rects.push({...node.label, x: node.x + node.label.x, y: node.y + node.label.y});
        for (const rect of rects) {
          const l = rect.x + .1, r = rect.x + rect.width - .1, t = rect.y + .1, d = rect.y + rect.height - .1;
          const hit = a.x === b.x ? l < a.x && a.x < r && Math.max(a.y, b.y) > t && Math.min(a.y, b.y) < d :
            t < a.y && a.y < d && Math.max(a.x, b.x) > l && Math.min(a.x, b.x) < r;
          assert.ok(!hit, `edge ${edge.id} crosses ${node.id}`);
        }
      }
    }
  }
}

test('focus preserves the active family, context, counts, and source snapshot', async () => {
  const state = fixture(), original = structuredClone(state);
  const view = focusSnapshot(state);
  for (const id of ['64', '32', '16', '33']) assert.equal(view.nodes.find(n => n.id === id)?.detail, 'full');
  assert.equal(view.nodes.find(n => n.id === '1')?.detail, 'compact');
  assert.ok(view.nodes.some(n => n.detail === 'folded'));
  assert.ok(view.nodes.some(n => n.detail === 'compact'));
  assert.equal(view.nodes.filter(n => n.detail !== 'folded').length + view.folded, 127);
  assert.deepEqual(state, original);
  const full = await layout(state.nodes, state.edges, state.root);
  const focused = await layout(view.nodes, view.edges, state.root);
  assert.ok(focused.groups[0].width < full.groups[0].width * .6, [focused.groups[0].width, full.groups[0].width]);
  assertRoutesClear(focused);
  const byId = new Map(focused.nodes.map(n => [n.id, n]));
  for (const edge of view.edges) {
    const a = byId.get(edge.source), b = byId.get(edge.target);
    assert.ok(edge.side === 'left' ? b.x + b.bodyWidth / 2 < a.x + a.bodyWidth / 2 : b.x + b.bodyWidth / 2 > a.x + a.bodyWidth / 2);
  }
  const shared = await layout(view.nodes, view.edges, state.root, {sharedNil: true});
  assert.deepEqual(focused.nodes.filter(n => !n.nil).map(n => [n.id, n.x, n.y]), shared.nodes.filter(n => !n.nil).map(n => [n.id, n.x, n.y]));
  assertRoutesClear(shared);
});

test('pins preserve their ancestor paths and expanding accounts for every subtree node', () => {
  const state = fixture();
  const pinned = focusSnapshot(state, {pinned: new Set(['127'])});
  assert.equal(pinned.nodes.find(n => n.id === '127').detail, 'full');
  for (const id of ['63', '31', '15', '7', '3', '1']) assert.notEqual(pinned.nodes.find(n => n.id === id)?.detail, 'folded');
  const opened = focusSnapshot(state, {expanded: new Set(['3'])});
  const ids = new Set(opened.nodes.filter(n => n.detail !== 'folded').map(n => n.id));
  for (let n = 1; n <= 127; n++) {
    let root = n;
    while (root > 3) root >>= 1;
    if (root === 3) assert.ok(ids.has(String(n)));
  }
});

test('rotation participants and transferred subtree roots stay full size', () => {
  const state = fixture(31, {'4': ['rotate_down'], '9': ['rotate_up']});
  const view = focusSnapshot(state);
  for (const id of ['4', '9', '18', '19']) assert.equal(view.nodes.find(n => n.id === id).detail, 'full');
  assert.equal(view.anchor, '4');
});

test('color and pointer changes remain visible, then recent activity expires', () => {
  const before = fixture(), after = structuredClone(before);
  after.nodes.find(n => n.id === '127').color = 'black';
  const changed = focusSnapshot(after, {previous: before});
  assert.ok(changed.active.includes('127'));
  const recent = focusSnapshot(after, {previous: after, recent: changed.active});
  assert.equal(recent.nodes.find(n => n.id === '127').detail, 'full');
  const expired = focusSnapshot(after, {previous: after, recent: recent.active});
  assert.ok(!expired.nodes.some(n => n.id === '127' && n.detail === 'full'));
  const detached = structuredClone(before);
  detached.edges = detached.edges.filter(e => e.target !== '127');
  detached.nodes.find(n => n.id === '127').parent = null;
  detached.nodes.find(n => n.id === '127').detached = true;
  const pointers = focusSnapshot(detached, {previous: before});
  assert.ok(pointers.active.includes('63') && pointers.active.includes('127'));
});

test('NIL insertion cursor remains attached and inspectable', () => {
  const state = fixture(127, {'64': ['parent_of_new_node']});
  state.nodes.find(n => n.id === '64').nil_labels = {left: ['current_node']};
  const view = focusSnapshot(state);
  assert.equal(view.nodes.find(n => n.id === '64').detail, 'full');
  assert.deepEqual(view.nodes.find(n => n.id === '64').nil_labels, {left: ['current_node']});
});

test('cycles, shared children, and warnings retain the full actual graph', () => {
  const cycle = fixture();
  cycle.edges.push({source: '127', target: '1', side: 'left', warnings: []});
  const shared = fixture();
  shared.edges.push({source: '127', target: '64', side: 'left', warnings: []});
  const warned = fixture();
  warned.nodes[90].warnings.push('Parent mismatch');
  for (const state of [cycle, shared, warned]) {
    const view = focusSnapshot(state);
    assert.equal(view.unsafe, true);
    assert.deepEqual(view.nodes, state.nodes);
    assert.deepEqual(view.edges, state.edges);
  }
});

test('empty snapshots and absent operation locals have a usable fallback', () => {
  assert.equal(focusSnapshot({nodes: [], edges: []}).nodes.length, 0);
  assert.equal(focusSnapshot(fixture(31, {})).anchor, '1');
});

test('an unattached insertion node keeps the root available as search context', () => {
  const state = fixture(31, {'31': ['new_node']});
  state.edges = state.edges.filter(e => e.target !== '31');
  const detached = state.nodes.find(n => n.id === '31');
  detached.parent = null; detached.detached = true;
  const view = focusSnapshot(state);
  assert.equal(view.nodes.find(n => n.id === '1').detail, 'full');
  assert.equal(view.nodes.find(n => n.id === '31').detail, 'full');
});
