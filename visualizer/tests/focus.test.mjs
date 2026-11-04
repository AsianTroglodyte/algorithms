// Run from the repository root: node visualizer/tests/focus.test.mjs
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

// Valid BSTs use the ordered layout. Browser smoke tests exercise the bundled
// ELK engine for intermediate pointer graphs without its worker shim in Node.
globalThis.window = {ELK: class {layout() { throw new Error('Unexpected ELK fallback for a valid tree'); }}};
const source = await readFile(new URL('../static/layout.js', import.meta.url), 'utf8');
const {focusSnapshot, layout, displaySnapshot} = await import(`data:text/javascript;base64,${Buffer.from(source + '\n//# sourceURL=rb-layout.mjs').toString('base64')}`);
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

test('frames without operation locals use changes for one snapshot only', () => {
  const before = fixture(127, {}), after = structuredClone(before);
  after.nodes.find(n => n.id === '127').color = 'black';
  const changed = focusSnapshot(after, {previous: before});
  assert.ok(changed.active.includes('127'));
  const expired = focusSnapshot(after, {previous: after});
  assert.ok(!expired.nodes.some(n => n.id === '127' && n.detail === 'full'));
  const detached = structuredClone(before);
  detached.edges = detached.edges.filter(e => e.target !== '127');
  detached.nodes.find(n => n.id === '127').parent = null;
  detached.nodes.find(n => n.id === '127').detached = true;
  const pointers = focusSnapshot(detached, {previous: before});
  assert.ok(pointers.active.includes('63') && pointers.active.includes('127'));
});

test('current roles override earlier recolor activity and fold off-path branches at their root', () => {
  const before = fixture(), after = structuredClone(before);
  after.nodes.find(n => n.id === '127').color = 'black';
  const view = focusSnapshot(after, {previous: before});
  assert.ok(!view.active.includes('127'));
  // The root's whole unrelated branch is one summary, not a compact root
  // with its children exposed at yet another level.
  assert.equal(view.nodes.find(n => n.id === '3').detail, 'folded');
  assert.equal(view.nodes.find(n => n.id === '3').foldedCount, 63);
  assert.ok(!view.nodes.some(n => ['6', '7', '127'].includes(n.id)));
});

test('moving fix_node folds the old family immediately despite stale uncle locals', () => {
  const before = fixture();
  const after = fixture(127, {'16': ['fix_node', 'grandparent'], '33': ['uncle']});
  const view = focusSnapshot(after, {previous: before});
  for (const id of ['16', '8', '4', '9']) assert.equal(view.nodes.find(n => n.id === id).detail, 'full');
  assert.equal(view.nodes.find(n => n.id === '32').detail, 'folded');
  assert.equal(view.nodes.find(n => n.id === '33').detail, 'folded');
  assert.ok(!view.nodes.some(n => n.id === '64'));
});

test('NIL insertion cursor remains attached and inspectable', () => {
  const state = fixture(127, {'64': ['parent_of_new_node']});
  state.nodes.find(n => n.id === '64').nil_labels = {left: ['current_node']};
  const view = focusSnapshot(state);
  assert.equal(view.nodes.find(n => n.id === '64').detail, 'full');
  assert.deepEqual(view.nodes.find(n => n.id === '64').nil_labels, {left: ['current_node']});
});

test('cycles, shared children, and unlocated warnings retain the full actual graph', () => {
  const cycle = fixture();
  cycle.edges.push({source: '127', target: '1', side: 'left', warnings: []});
  const shared = fixture();
  shared.edges.push({source: '127', target: '64', side: 'left', warnings: []});
  const warned = fixture();
  warned.warnings.push('Root is not a tracked Node');
  for (const state of [cycle, shared, warned]) {
    const view = focusSnapshot(state);
    assert.equal(view.unsafe, true);
    assert.deepEqual(view.nodes, state.nodes);
    assert.deepEqual(view.edges, state.edges);
  }
});

test('local parent warnings reveal affected nodes without unfolding unrelated branches', () => {
  const state = fixture();
  const node = state.nodes.find(n => n.id === '127');
  node.parent = '90';
  node.warnings = ['Parent #90 does not list this node as a child'];
  state.warnings = [`#127: ${node.warnings[0]}`];
  const view = focusSnapshot(state);
  assert.equal(view.unsafe, false);
  assert.ok(view.folded > 0);
  for (const id of ['127', '90']) assert.equal(view.nodes.find(n => n.id === id).detail, 'full');
  assert.deepEqual(view.nodes.find(n => n.id === '127').warnings, node.warnings);
});

test('warning edges and both claimed parents remain visible with their actual pointers', () => {
  const state = fixture();
  state.nodes.find(n => n.id === '127').parent = '90';
  const edge = state.edges.find(e => e.target === '127');
  edge.warnings = ["Child's parent does not point back"];
  state.warnings = [`#${edge.source} ${edge.side} → #${edge.target}: ${edge.warnings[0]}`];
  const view = focusSnapshot(state);
  assert.equal(view.unsafe, false);
  assert.ok(view.folded > 0);
  for (const id of ['63', '127', '90']) assert.equal(view.nodes.find(n => n.id === id).detail, 'full');
  assert.deepEqual(view.edges.find(e => e.target === '127'), edge);
});

test('focus and rooted positions stay steady through insertion and leaf initialization', async () => {
  for (const side of ['left', 'right']) {
    const before = fixture(127, {'64': ['parent_of_new_node']});
    before.nodes.find(n => n.id === '64').nil_labels = {[side]: ['current_node']};
    const incoming = {id: '128', key: '128', address: '0x128', names: ['new_node'], color: 'red',
      parent: null, left: null, right: null, nil_children: [], detached: true, warnings: []};
    before.nodes.push(incoming);
    const parentOnly = structuredClone(before);
    const pending = parentOnly.nodes.find(n => n.id === '128');
    pending.parent = '64';
    pending.warnings = ['Parent #64 does not list this node as a child'];
    parentOnly.warnings = [`#128: ${pending.warnings[0]}`];
    const linked = structuredClone(parentOnly);
    linked.nodes.find(n => n.id === '128').warnings = [];
    linked.nodes.find(n => n.id === '128').detached = false;
    linked.nodes.find(n => n.id === '64').nil_children = ['left', 'right'].filter(s => s !== side);
    linked.nodes.find(n => n.id === '64').nil_labels = {};
    linked.edges.push({source: '64', target: '128', side, warnings: []});
    linked.warnings = [];
    const leftSet = structuredClone(linked), initialized = structuredClone(linked);
    leftSet.nodes.find(n => n.id === '128').nil_children = ['left'];
    initialized.nodes.find(n => n.id === '128').nil_children = ['left', 'right'];
    let previous = null, oldPositions = null;
    for (const state of [before, parentOnly, linked, leftSet, initialized]) {
      const view = focusSnapshot(state, {previous});
      assert.equal(view.unsafe, false);
      assert.ok(view.folded > 0);
      for (const id of ['64', '128']) assert.equal(view.nodes.find(n => n.id === id).detail, 'full');
      assert.equal(view.nodes.filter(n => n.detail !== 'folded').length + view.folded, 128);
      assert.equal(view.anchor, '64');
      for (const id of ['32', '65']) assert.equal(view.nodes.find(n => n.id === id).detail, 'full');
      const geometry = await layout(view.nodes, view.edges, state.root, {insertion: view.insertion});
      assertRoutesClear(geometry);
      const parent = geometry.nodes.find(n => n.id === '64');
      const positions = new Map(geometry.nodes.filter(n => !n.nil && !n.record.detached).map(n =>
        [n.id, [n.x + n.bodyWidth / 2 - parent.x - parent.bodyWidth / 2, n.y - parent.y]]));
      if (oldPositions) for (const [id, [x, y]] of positions) {
        if (!oldPositions.has(id)) continue;
        const [oldX, oldY] = oldPositions.get(id);
        assert.ok(Math.hypot(x - oldX, y - oldY) < 80, `${side} insertion shifts ${id}`);
        if (state === leftSet || state === initialized) assert.deepEqual([x, y], [oldX, oldY]);
      }
      // Reserved layout slots must never masquerade as actual NIL assignments.
      for (const n of geometry.nodes.filter(n => n.nil && n.id.startsWith('128:'))) {
        assert.ok(state.nodes.find(n => n.id === '128').nil_children.includes(n.id.split(':').at(-1)));
      }
      oldPositions = positions;
      previous = state;
    }
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

test('BST minimum follows the cursor and next left child, folding old paths immediately', () => {
  const state = {...fixture(127, {'1': ['node']}), tree_kind: 'bst'};
  const first = focusSnapshot(state);
  assert.deepEqual(new Set(first.active), new Set(['1', '2']));
  assert.equal(first.nodes.find(n => n.id === '3').detail, 'folded');
  const next = {...fixture(127, {'4': ['node']}), tree_kind: 'bst'};
  const view = focusSnapshot(next, {previous: state});
  assert.deepEqual(new Set(view.active), new Set(['4', '8']));
  assert.equal(view.nodes.find(n => n.id === '1').detail, 'compact');
  assert.equal(view.nodes.find(n => n.id === '5').detail, 'folded');
});

test('BST insertion keeps its parent anchored without expanding an RB grandparent family', () => {
  const state = {...fixture(127, {'64': ['new_node'], '32': ['parent_of_new_node']}), tree_kind: 'bst'};
  const view = focusSnapshot(state);
  assert.equal(view.anchor, '32');
  assert.deepEqual(new Set(view.active), new Set(['64', '32']));
  assert.equal(view.nodes.find(n => n.id === '16').detail, 'compact');
  assert.equal(view.nodes.find(n => n.id === '33').detail, 'folded');
});

test('BST transplant and deletion expose their target, replacement/successor, and relevant parents', () => {
  const transplant = {...fixture(127, {'32': ['old_root'], '64': ['replacement']}), tree_kind: 'bst'};
  const swapping = focusSnapshot(transplant);
  assert.deepEqual(new Set(swapping.active), new Set(['32', '16', '64']));
  const deletion = {...fixture(127, {'32': ['node_to_delete'], '66': ['successor']}), tree_kind: 'bst'};
  const removing = focusSnapshot(deletion);
  for (const id of ['32', '16', '64', '65', '66', '33']) assert.ok(removing.active.includes(id));
  assert.equal(removing.nodes.find(n => n.id === '3').detail, 'folded');
});

function staleDeletedPointer() {
  const state = fixture();
  const shared = 'Shared child (multiple incoming child edges)';
  state.nodes.push({id: '999', key: '999', names: ['delete_node', 'y'], address: '0x999', color: 'black',
    parent: '32', left: '64', right: null, detached: true, nil_children: ['right'],
    warnings: ['Parent #32 does not list this node as a child']});
  state.edges.find(edge => edge.target === '64').warnings = [shared];
  state.edges.push({source: '999', target: '64', side: 'left', warnings: ["Child's parent does not point back", shared]});
  state.warnings = [
    '#999: Parent #32 does not list this node as a child',
    `#32 left → #64: ${shared}`, `#999 left → #64: Child's parent does not point back`, `#999 left → #64: ${shared}`,
  ];
  return state;
}

test('stale detached references disappear from presentation without changing actual pointers', async () => {
  const state = staleDeletedPointer(), original = structuredClone(state);
  const view = displaySnapshot(state);
  assert.ok(!view.edges.some(edge => edge.source === '999' && edge.target === '64'));
  assert.deepEqual(view.edges.find(edge => edge.source === '32' && edge.target === '64').warnings, []);
  assert.deepEqual(view.warnings, []);
  const detached = view.nodes.find(node => node.id === '999');
  assert.equal(detached.left, '64');
  assert.equal(detached.parent, '32');
  assert.deepEqual(detached.hiddenChildPointers, ['left: #64']);
  assert.deepEqual(detached.inspectionWarnings, original.nodes.at(-1).warnings);
  assert.deepEqual(detached.warnings, []);
  assert.deepEqual(state, original);
  assert.equal(focusSnapshot(state).unsafe, false);
  const geometry = await layout(state.nodes, state.edges, state.root);
  assert.ok(!geometry.edges.some(edge => edge.record?.source === '999' && edge.record?.target === '64'));
  const ordinary = fixture();
  const expected = await layout(ordinary.nodes, ordinary.edges, ordinary.root);
  const rootedPositions = g => g.nodes.filter(node => node.group === 'attached' && !node.nil).map(node => [node.id, node.x, node.y]);
  assert.deepEqual(rootedPositions(geometry), rootedPositions(expected));
  assertRoutesClear(geometry);
});

test('real rooted shared children and pointer mismatches stay visible', () => {
  const state = staleDeletedPointer();
  state.edges.push({source: '3', target: '64', side: 'left', warnings: ["Child's parent does not point back", 'Shared child (multiple incoming child edges)']});
  const view = displaySnapshot(state);
  assert.ok(view.edges.find(edge => edge.source === '32' && edge.target === '64').warnings.some(warning => warning.startsWith('Shared child')));
  assert.ok(view.edges.find(edge => edge.source === '3' && edge.target === '64').warnings.some(warning => warning.startsWith("Child's parent")));
  assert.ok(view.warnings.some(warning => warning.startsWith('#32 left')));
  assert.equal(focusSnapshot(state).unsafe, true);
});

test('detached subtree internal edges remain intact', () => {
  const state = staleDeletedPointer();
  state.nodes.push({id: '1000', key: '1000', names: [], address: '0x1000', color: 'black',
    parent: '999', left: null, right: null, detached: true, nil_children: ['left', 'right'], warnings: []});
  state.nodes.find(node => node.id === '999').right = '1000';
  state.edges.push({source: '999', target: '1000', side: 'right', warnings: []});
  const view = displaySnapshot(state);
  assert.ok(view.edges.some(edge => edge.source === '999' && edge.target === '1000'));
  assert.ok(!view.edges.some(edge => edge.source === '999' && edge.target === '64'));
});

test('a removed black leaf stays inspectable without a stale parent warning', () => {
  const state = fixture();
  state.nodes.push({id: '999', key: '999', names: [], parent: '32', left: null, right: null,
    color: 'black', deleting: true, detached: true, nil_children: ['left', 'right'],
    warnings: ['Parent #32 does not list this node as a child']});
  state.warnings = ['#999: Parent #32 does not list this node as a child'];
  const view = displaySnapshot(state);
  assert.deepEqual(view.warnings, []);
  assert.deepEqual(view.nodes.at(-1).warnings, []);
  assert.equal(view.nodes.at(-1).parent, '32');
  assert.deepEqual(view.nodes.at(-1).inspectionWarnings, state.nodes.at(-1).warnings);
});

test('NIL fixup focuses on its parent, sibling, near child, and far child', () => {
  const state = fixture(255, {});
  const parent = state.nodes.find(node => node.id === '32');
  parent.left = null;
  parent.nil_children = ['left'];
  parent.nil_labels = {left: ['fix_node']};
  state.edges = state.edges.filter(edge => edge.target !== '64');
  for (const node of state.nodes) if (['64', '128', '129'].includes(node.id)) node.detached = true;
  state.nodes.find(node => node.id === '64').deleting = true;
  const view = focusSnapshot(state);
  assert.equal(view.anchor, '32');
  for (const id of ['32', '65', '130', '131']) assert.ok(view.active.includes(id));
  assert.ok(!view.active.includes('64'));
  assert.equal(view.nodes.find(node => node.id === '3').detail, 'folded');
});
