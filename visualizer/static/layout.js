// Lay out the tree first. Shared NIL arrows are routed afterward so they
// cannot influence the positions or ordering of real nodes.
const elk = new window.ELK();
const bodyWidth = 100, bodyHeight = 84, labelGap = 16;

// Detached objects remain inspectable, but their stale child references must
// not connect the detached area to the rooted tree or distort its layout.
export function displaySnapshot(snapshot) {
  if (!snapshot) return snapshot;
  const nodes = snapshot.nodes ?? [], edges = snapshot.edges ?? [];
  const byId = new Map(nodes.map(node => [node.id, node]));
  const hidden = edges.filter(edge => byId.get(edge.source)?.detached && byId.has(edge.target) && !byId.get(edge.target).detached);
  const hiddenSet = new Set(hidden), hiddenSources = new Set(hidden.map(edge => edge.source));
  for (const node of nodes) if (node.deleting && node.detached) hiddenSources.add(node.id);
  if (!hiddenSources.size) return snapshot;
  const hiddenTargets = new Set(hidden.map(edge => edge.target));
  const kept = edges.filter(edge => !hiddenSet.has(edge));
  const incoming = new Map();
  for (const edge of kept) incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  const summary = (edge, warning) => `#${edge.source} ${edge.side} → #${edge.target}: ${warning}`;
  const suppressed = new Set(hidden.flatMap(edge => (edge.warnings ?? []).map(warning => summary(edge, warning))));
  const displayEdges = kept.map(edge => {
    const warnings = (edge.warnings ?? []).filter(warning => {
      if (warning === 'Shared child (multiple incoming child edges)' && hiddenTargets.has(edge.target) && incoming.get(edge.target) === 1) {
        suppressed.add(summary(edge, warning));
        return false;
      }
      return true;
    });
    return {...edge, warnings};
  });
  const displayNodes = nodes.map(node => {
    if (!hiddenSources.has(node.id)) return node;
    const parent = byId.get(node.parent);
    const warnings = (node.warnings ?? []).filter(warning => {
      if (warning === `Parent #${node.parent} does not list this node as a child` && parent && !parent.detached) {
        suppressed.add(`#${node.id}: ${warning}`);
        return false;
      }
      return true;
    });
    return {...node, warnings, inspectionWarnings: node.warnings,
      hiddenChildPointers: hidden.filter(edge => edge.source === node.id).map(edge => `${edge.side}: #${edge.target}`)};
  });
  return {...snapshot, nodes: displayNodes, edges: displayEdges,
    warnings: (snapshot.warnings ?? []).filter(warning => !suppressed.has(warning))};
}

// Project a snapshot for display only. Never rewrite the debugger's pointer graph.
// Current operation roles determine detail immediately; history is only a
// fallback when the stopped frame has no recognizable operation locals.
export function focusSnapshot(snapshot, {previous = null, pinned = new Set(), expanded = new Set()} = {}) {
  snapshot = displaySnapshot(snapshot);
  previous = displaySnapshot(previous);
  const nodes = snapshot.nodes ?? [], edges = snapshot.edges ?? [];
  const byId = new Map(nodes.map(node => [node.id, node]));
  const children = new Map(nodes.map(node => [node.id, []])), parents = new Map();
  // Local pointer warnings are normal between assignments. Keep their nodes
  // visible below; only ambiguous child topology needs the whole graph.
  const locatedWarnings = nodes.reduce((count, node) => count + (node.warnings?.length ?? 0), 0)
    + edges.reduce((count, edge) => count + (edge.warnings?.length ?? 0), 0);
  let unsafe = (snapshot.warnings?.length ?? 0) > locatedWarnings;
  for (const edge of edges) {
    if (!byId.has(edge.source) || !byId.has(edge.target)) { unsafe = true; continue; }
    if (parents.has(edge.target) || children.get(edge.source).some(child => child.side === edge.side)) unsafe = true;
    parents.set(edge.target, edge.source);
    children.get(edge.source).push({id: edge.target, side: edge.side});
  }
  // A finite traversal also catches malformed fixtures without warning metadata.
  const order = nodes.filter(node => !parents.has(node.id)).map(node => node.id);
  const visited = new Set(order);
  for (let i = 0; i < order.length; i++) for (const child of children.get(order[i])) {
    if (visited.has(child.id)) { unsafe = true; continue; }
    visited.add(child.id); order.push(child.id);
  }
  if (order.length !== nodes.length) unsafe = true;

  const named = name => nodes.filter(node => node.names?.includes(name)).map(node => node.id);
  const bst = snapshot.tree_kind === 'bst';
  const active = new Set(), add = id => { if (byId.has(id)) active.add(id); };
  const parentOf = id => byId.get(id)?.parent ?? parents.get(id);
  const family = (id, insertionParent = null) => {
    add(id);
    const parent = insertionParent ?? parentOf(id), grandparent = parentOf(parent);
    add(parent);
    if (bst) return;
    add(grandparent);
    for (const child of children.get(grandparent) ?? []) add(child.id);
  };
  const rotations = [...named('rotate_down'), ...named('rotate_up')];
  const fixing = named('fix_node');
  const nilFixParent = nodes.find(node => Object.values(node.nil_labels ?? {}).some(names => names.includes('fix_node')));
  const searching = named('current_node');
  const inserting = named('new_node');
  const insertionParent = named('parent_of_new_node')[0];
  const insertionSide = children.get(insertionParent)?.find(child => child.id === inserting[0])?.side
    ?? Object.entries(byId.get(insertionParent)?.nil_labels ?? {}).find(([, names]) => names.includes('current_node'))?.[0];
  const insertion = inserting.length && insertionParent && insertionSide ?
    {nodeId: inserting[0], parentId: insertionParent, side: insertionSide} : null;
  let anchor = rotations[0] ?? fixing[0] ?? searching[0] ?? inserting[0];
  if (bst && named('old_root').length) {
    for (const id of [...named('old_root'), ...named('replacement')]) { add(id); add(parentOf(id)); }
    anchor = parentOf(named('old_root')[0]) ?? named('replacement')[0] ?? named('old_root')[0];
  } else if (bst && named('node_to_delete').length) {
    for (const id of [...named('node_to_delete'), ...named('successor')]) { add(id); add(parentOf(id)); }
    for (const id of named('node_to_delete')) for (const child of children.get(id) ?? []) add(child.id);
    for (const id of named('successor')) for (const child of children.get(id) ?? []) if (child.side === 'right') add(child.id);
    anchor = parentOf(named('node_to_delete')[0]) ?? snapshot.root ?? named('node_to_delete')[0];
  } else if (bst && named('node').length) {
    for (const id of named('node')) {
      add(id);
      add(children.get(id)?.find(child => child.side === 'left')?.id);
    }
    anchor = named('node')[0];
  } else if (rotations.length) {
    for (const id of rotations) {
      add(id); add(parentOf(id));
      // Include transferred subtree roots even before rotate_up is assigned.
      for (const child of children.get(id) ?? []) {
        add(child.id);
        if (id === named('rotate_down')[0]) for (const grandchild of children.get(child.id) ?? []) add(grandchild.id);
      }
    }
  } else if (fixing.length || nilFixParent) {
    fixing.forEach(id => family(id));
    if (nilFixParent) {
      add(nilFixParent.id);
      for (const sibling of children.get(nilFixParent.id) ?? []) {
        add(sibling.id);
        for (const child of children.get(sibling.id) ?? []) add(child.id);
      }
      anchor = nilFixParent.id;
    }
    // grandparent/uncle locals can still refer to the previous iteration just
    // after fix_node moves. Derive its current family from actual pointers.
    for (const id of named('sibling')) {
      const parent = parentOf(id);
      if (fixing.some(fix => parent === parentOf(fix))) add(id);
    }
  } else if (searching.length || inserting.length || named('parent_of_new_node').length) {
    searching.forEach(add); inserting.forEach(add);
    named('parent_of_new_node').forEach(add);
    if (!searching.length) inserting.forEach(id => family(id, insertionParent));
    if (!searching.length && !insertionParent && inserting.some(id => !parentOf(id))) add(snapshot.root);
    // A pending insertion lives in the detached region until the child link is
    // installed. Anchor the rooted family, rather than chasing that region.
    if (insertion) anchor = insertionParent;
  } else {
    for (const name of ['delete_node', 'replacement', 'old_root', 'node', ...(bst ? ['minimum'] : [])]) named(name).forEach(id => family(id));
  }
  const frame = [...active];
  // An insertion cursor at NIL lives on its owning child slot.
  for (const node of nodes) if (Object.values(node.nil_labels ?? {}).some(names => names.length)) add(node.id);
  // Never fold away a warning or the endpoints needed to understand it.
  for (const node of nodes) if (node.warnings?.length) { add(node.id); add(node.parent); }
  for (const edge of edges) if (edge.warnings?.length) {
    add(edge.source); add(edge.target); add(byId.get(edge.target)?.parent);
  }
  if (previous && !frame.length) {
    const before = new Map((previous.nodes ?? []).map(node => [node.id, node]));
    const links = state => {
      const result = new Map();
      for (const edge of state.edges ?? []) result.set(`${edge.source}:${edge.side}`, edge.target);
      return result;
    };
    const oldLinks = links(previous), newLinks = links(snapshot);
    for (const node of nodes) {
      const old = before.get(node.id);
      if (!old || ['color', 'key', 'parent'].some(field => node[field] !== old[field])) add(node.id);
    }
    for (const key of new Set([...oldLinks.keys(), ...newLinks.keys()])) {
      if (oldLinks.get(key) !== newLinks.get(key)) {
        add(key.slice(0, key.lastIndexOf(':'))); add(oldLinks.get(key)); add(newLinks.get(key));
      }
    }
  }
  if (!active.size) add(snapshot.root);
  anchor ??= active.values().next().value;
  if (unsafe) return {nodes, edges, active: [...active], anchor, frame, folded: 0, unsafe: true};

  const full = new Set([...active, ...pinned].filter(id => byId.has(id)));
  const visible = new Set(full);
  if (byId.has(snapshot.root)) visible.add(snapshot.root);
  // Parent paths provide orientation. Other branches become summaries at the
  // first off-path child, rather than exposing another level around each role.
  for (const id of full) {
    const parent = parentOf(id);
    if (byId.has(parent)) visible.add(parent);
  }
  for (const id of expanded) {
    if (!byId.has(id)) continue;
    const pending = [id];
    for (let i = 0; i < pending.length; i++) {
      visible.add(pending[i]);
      for (const child of children.get(pending[i])) pending.push(child.id);
    }
  }
  // Preserve the path back to the root, including paths to manually opened nodes.
  for (const id of [...visible]) {
    let parent = parents.get(id);
    while (parent && !visible.has(parent)) { visible.add(parent); parent = parents.get(parent); }
  }
  const sizes = new Map();
  for (const id of [...order].reverse()) sizes.set(id, 1 + children.get(id).reduce((n, child) => n + sizes.get(child.id), 0));
  const projected = [], kept = new Set();
  let folded = 0;
  for (const id of order) {
    const node = byId.get(id), parent = parents.get(id);
    if (!visible.has(id) && parent && !visible.has(parent)) continue;
    kept.add(id);
    if (!visible.has(id) && sizes.get(id) > 1) {
      folded += sizes.get(id);
      projected.push({...node, names: [], nil_children: [], nil_labels: {}, detail: 'folded', foldedCount: sizes.get(id)});
    } else {
      projected.push({...node, detail: full.has(id) ? 'full' : 'compact', focused: active.has(id), pinned: pinned.has(id)});
    }
  }
  return {nodes: projected, edges: edges.filter(edge => kept.has(edge.source) && kept.has(edge.target)),
    active: [...active], anchor, frame: frame.length ? frame : [...active], insertion, folded, unsafe: false};
}
function labelFor(lines, width, height) {
  if (!lines.length) return null;
  const labelHeight = lines.length * 18 + 10;
  return {
    lines, x: width + labelGap, y: Math.max(0, (height - labelHeight) / 2),
    width: Math.max(52, Math.min(280, Math.max(...lines.map(line => line.length)) * 7 + 20)),
    height: labelHeight,
  };
}
const options = {
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.edgeLabels.placement': 'TAIL',
  'elk.spacing.nodeNode': '40',
  'elk.spacing.componentComponent': '80',
  'elk.layered.spacing.nodeNodeBetweenLayers': '32',
  'elk.layered.spacing.edgeNodeBetweenLayers': '24',
  'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
  'elk.layered.crossingMinimization.forceNodeModelOrder': 'true',
  'elk.layered.nodePlacement.bk.fixedAlignment': 'BALANCED',
  'elk.aspectRatio': '3',
};

// Compact ordered-tree contours keep each left child to the left and each
// right child to the right, while allowing room for external variable labels.
// Graphs with cycles, shared children, or cross-group edges use ELK below.
function layoutOrderedGroups(groups) {
  const models = [];
  for (const group of groups) {
    const ports = new Map(group.children.flatMap(node => node.ports.map(port => [port.id, node])));
    const children = new Map(group.children.map(node => [node.id, {}]));
    const incoming = new Map(group.children.map(node => [node.id, 0]));
    for (const edge of group.edges) {
      const source = ports.get(edge.sources[0]), target = ports.get(edge.targets[0]);
      const side = edge.sources[0].endsWith(':left') ? 'left' : 'right';
      if (!source || !target || children.get(source.id)[side] || incoming.get(target.id)) return null;
      children.get(source.id)[side] = target;
      incoming.set(target.id, 1);
    }
    const roots = group.children.filter(node => !incoming.get(node.id));
    const order = [...roots], depth = new Map(roots.map(node => [node.id, 0]));
    for (let i = 0; i < order.length; ++i) {
      const node = order[i];
      for (const child of Object.values(children.get(node.id))) {
        depth.set(child.id, depth.get(node.id) + 1);
        order.push(child);
      }
    }
    if (order.length !== group.children.length) return null;
    models.push({group, ports, children, roots, order, depth});
  }
  let groupX = 0;
  for (const {group, ports, children, roots, order, depth} of models) {
    const shapes = new Map();
    for (const node of [...order].reverse()) {
      const branches = children.get(node.id);
      const left = branches.left && shapes.get(branches.left.id), right = branches.right && shapes.get(branches.right.id);
      let separation = node.record?.detail ? 48 : 80;
      if (left && right) {
        for (let d = 0; d < Math.min(left.right.length, right.left.length); ++d) {
          separation = Math.max(separation, left.right[d] - right.left[d] + 40);
        }
      }
      const shape = {left: [-node.bodyWidth / 2], right: [node.width - node.bodyWidth / 2], branches: []};
      const singleShift = node.record?.detail ? 40 : 60;
      for (const [child, shift] of [[branches.left, right ? -separation / 2 : -singleShift], [branches.right, left ? separation / 2 : singleShift]]) {
        if (!child) continue;
        const childShape = shapes.get(child.id);
        shape.branches.push({child, shift});
        for (let d = 0; d < childShape.left.length; ++d) {
          shape.left[d + 1] = Math.min(shape.left[d + 1] ?? Infinity, childShape.left[d] + shift);
          shape.right[d + 1] = Math.max(shape.right[d + 1] ?? -Infinity, childShape.right[d] + shift);
        }
      }
      shapes.set(node.id, shape);
    }
    const rowHeights = [];
    for (const node of order) rowHeights[depth.get(node.id)] = Math.max(rowHeights[depth.get(node.id)] ?? 0, node.height);
    const rows = [48];
    rowHeights.forEach((height, d) => { rows[d + 1] = rows[d] + height + 64; });
    let cursor = 24;
    for (const root of roots) {
      const shape = shapes.get(root.id), left = Math.min(...shape.left), right = Math.max(...shape.right);
      const pending = [{node: root, center: cursor - left}];
      while (pending.length) {
        const {node, center} = pending.pop();
        node.x = center - node.bodyWidth / 2;
        node.y = rows[depth.get(node.id)];
        for (const branch of shapes.get(node.id).branches) pending.push({node: branch.child, center: center + branch.shift});
      }
      cursor += right - left + 80;
    }
    for (const edge of group.edges) {
      const source = ports.get(edge.sources[0]), target = ports.get(edge.targets[0]);
      const left = edge.sources[0].endsWith(':left');
      const start = {x: source.x + source.bodyWidth * (left ? .25 : .75), y: source.y + source.bodyHeight};
      const end = {x: target.x + target.bodyWidth / 2, y: target.y};
      const bendY = rows[depth.get(source.id)] + rowHeights[depth.get(source.id)] + 24;
      const points = simplify([start, {x: start.x, y: bendY}, {x: end.x, y: bendY}, end]);
      edge.sections = [{startPoint: points[0], bendPoints: points.slice(1, -1), endPoint: points.at(-1)}];
      edge.labels = edge.labels.map(label => ({...label, x: start.x + (left ? -14 : 4), y: (start.y + bendY) / 2 - 7}));
    }
    group.x = groupX; group.y = 0;
    group.width = Math.max(group.id === 'detached' ? 220 : 160, cursor - 80 + 24);
    group.height = rows.at(-1) - 64 + 24;
    groupX += group.width + 80;
  }
  return {id: 'graph', children: groups};
}

export async function layout(nodes, edges, root, {sharedNil = false, rootIsNil = false, nilNames = [], insertion = null} = {}) {
  const view = displaySnapshot({nodes, edges});
  const geometry = await layoutTree(view.nodes, view.edges, root, insertion);
  return sharedNil ? withSharedNil(geometry, root, rootIsNil, nilNames) : geometry;
}

async function layoutTree(nodes, edges, root, insertion) {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const children = new Map(nodes.map(node => [node.id, []]));
  edges.forEach(edge => children.get(edge.source)?.push(edge));
  children.forEach(list => list.sort((a, b) => (a.side === 'right') - (b.side === 'right')));
  const ordered = [], seen = new Set();
  // Preserve pointer order, never key order: intermediate states can be invalid.
  function visit(start) {
    const stack = [start];
    while (stack.length) {
      const id = stack.pop();
      if (!byId.has(id) || seen.has(id)) continue;
      seen.add(id);
      ordered.push(byId.get(id));
      for (const edge of [...children.get(id)].reverse()) stack.push(edge.target);
    }
  }
  visit(root);
  const incoming = new Set(edges.map(edge => edge.target));
  nodes.filter(node => !incoming.has(node.id)).forEach(node => visit(node.id));
  nodes.forEach(node => visit(node.id));

  const groups = new Map();
  const groupId = node => node.detached ? 'detached' : 'attached';
  for (const node of ordered) {
    const id = groupId(node);
    if (!groups.has(id)) groups.set(id, {
      id, layoutOptions: {...options, 'elk.padding': '[top=48,left=24,bottom=24,right=24]'},
      children: [], edges: [],
    });
    const group = groups.get(id);
    const compact = node.detail === 'compact', folded = node.detail === 'folded';
    const nodeWidth = compact ? 48 : folded ? 88 : bodyWidth;
    const nodeHeight = compact ? 32 : folded ? 60 : bodyHeight;
    const lines = compact || folded ? [] : [...(node.id === root ? ['ROOT'] : []), ...node.names];
    const label = labelFor(lines, nodeWidth, nodeHeight);
    // Reserve the callout as part of the layout footprint so other nodes and
    // child edges cannot pass through it. Ports still attach to the body.
    const width = label ? label.x + label.width : nodeWidth;
    group.children.push({
      id: node.id, width, height: Math.max(nodeHeight, label?.height ?? 0), bodyWidth: nodeWidth, bodyHeight: nodeHeight, label, record: node,
      layoutOptions: {'elk.portConstraints': 'FIXED_POS'},
      ports: [
        {id: `${node.id}:in`, x: nodeWidth / 2, y: 0, width: 0, height: 0, layoutOptions: {'elk.port.side': 'NORTH'}},
        ...['left', 'right'].map((side, i) => ({
          id: `${node.id}:${side}`, x: nodeWidth * (i ? .75 : .25), y: nodeHeight,
          width: 0, height: 0, layoutOptions: {'elk.port.side': 'SOUTH'},
        })),
      ],
    });
    // Invisible NIL slots still participate in layout. A sole child must keep
    // its left/right meaning, and the NIL toggle must not rearrange the tree.
    const nilSlots = new Set(node.nil_children ?? []);
    // Reserve missing links during initialization without drawing a NIL
    // pointer until the debuggee has actually assigned the sentinel.
    if (node.id === insertion?.nodeId) {
      for (const side of ['left', 'right']) if (!children.get(node.id).some(edge => edge.side === side)) nilSlots.add(side);
    }
    for (const side of nilSlots) {
      const reserved = !(node.nil_children ?? []).includes(side);
      const nilId = `${node.id}:nil:${side}`;
      const nilWidth = compact ? 24 : 40, nilHeight = compact ? 18 : 24;
      const label = labelFor(node.nil_labels?.[side] ?? [], nilWidth, nilHeight);
      const referenced = Boolean(label);
      group.children.push({
        id: nilId, width: label ? label.x + label.width : nilWidth, height: Math.max(nilHeight, label?.height ?? 0),
        bodyWidth: nilWidth, bodyHeight: nilHeight, nil: true, referenced, label, reserved,
        layoutOptions: {'elk.portConstraints': 'FIXED_POS'},
        ports: [{id: `${nilId}:in`, x: nilWidth / 2, y: 0, width: 0, height: 0, layoutOptions: {'elk.port.side': 'NORTH'}}],
      });
      group.edges.push({id: `${nilId}:edge`, sources: [`${node.id}:${side}`], targets: [`${nilId}:in`], nil: true, referenced, reserved,
        labels: [{text: side === 'left' ? 'L' : 'R', width: 10, height: 14}]});
    }
  }
  const crossEdges = [];
  edges.forEach((edge, index) => {
    if (!byId.has(edge.source) || !byId.has(edge.target)) return;
    const entry = {
      id: `edge:${index}`, sources: [`${edge.source}:${edge.side}`], targets: [`${edge.target}:in`], record: edge,
      labels: [{text: edge.side === 'left' ? 'L' : 'R', width: 10, height: 14}],
    };
    if (groupId(byId.get(edge.source)) === groupId(byId.get(edge.target))) groups.get(groupId(byId.get(edge.source))).edges.push(entry);
    else crossEdges.push(entry);
  });
  const groupList = ['attached', 'detached'].flatMap(id => groups.has(id) ? [groups.get(id)] : []);
  let graph;
  const orderedGraph = !crossEdges.length && layoutOrderedGroups(groupList);
  if (orderedGraph) {
    graph = orderedGraph;
  } else if (!crossEdges.length) {
    const laidOut = await Promise.all(groupList.map(group => elk.layout(group)));
    let x = 0;
    for (const group of laidOut) {
      group.x = x;
      group.y = 0;
      x += group.width + 80;
    }
    graph = {id: 'graph', children: laidOut};
  } else {
    // Fixed model order is for an ordered tree. Cross-hierarchy routing needs
    // ELK to reorder the temporarily inconsistent graph to avoid crossings.
    const routingOptions = {
      'elk.layered.considerModelOrder.strategy': 'NONE',
      'elk.layered.crossingMinimization.forceNodeModelOrder': 'false',
    };
    groupList.forEach(group => Object.assign(group.layoutOptions, routingOptions));
    graph = await elk.layout({
      id: 'graph',
      // Cross-group pointers during a rotation need a single routing pass.
      layoutOptions: {...options, ...routingOptions, 'elk.hierarchyHandling': 'INCLUDE_CHILDREN'},
      children: groupList,
      edges: crossEdges,
    });
  }
  const result = {nodes: [], edges: [], groups: []};
  function collect(container, ox = 0, oy = 0) {
    const x = ox + (container.x ?? 0), y = oy + (container.y ?? 0);
    if (groups.has(container.id)) result.groups.push({id: container.id, x, y, width: container.width, height: container.height});
    for (const node of container.children ?? []) {
      if (node.reserved) continue;
      if (node.children) collect(node, x, y);
      else result.nodes.push({...node, group: container.id, x: node.x + x, y: node.y + y});
    }
    for (const edge of container.edges ?? []) {
      if (edge.reserved) continue;
      result.edges.push({
        ...edge,
        sections: (edge.sections ?? []).map(section => [section.startPoint, ...(section.bendPoints ?? []), section.endPoint].map(point => ({x: point.x + x, y: point.y + y}))),
        labels: (edge.labels ?? []).map(label => ({...label, x: label.x + x, y: label.y + y})),
      });
    }
  }
  collect(graph);
  return result;
}

function simplify(points) {
  const result = [];
  for (const point of points) {
    const last = result.at(-1), before = result.at(-2);
    if (last && last.x === point.x && last.y === point.y) continue;
    if (before && ((before.x === last.x && last.x === point.x) || (before.y === last.y && last.y === point.y))) result.pop();
    result.push(point);
  }
  return result;
}

// A small orthogonal visibility grid routes around fixed bodies and callouts.
// Each rectangle border is a grid line; A* prefers short paths with few bends.
function router(rectangles, endpoints) {
  const xs = [...new Set([...endpoints.map(p => p.x), ...rectangles.flatMap(r => [r.left, r.right])])].sort((a, b) => a - b);
  const ys = [...new Set([...endpoints.map(p => p.y), ...rectangles.flatMap(r => [r.top, r.bottom])])].sort((a, b) => a - b);
  const xIndex = new Map(xs.map((x, i) => [x, i])), yIndex = new Map(ys.map((y, i) => [y, i]));
  const index = p => yIndex.get(p.y) * xs.length + xIndex.get(p.x);
  const point = id => ({x: xs[id % xs.length], y: ys[Math.floor(id / xs.length)]});
  const validity = new Uint8Array(xs.length * ys.length), segments = new Map();
  const valid = id => {
    if (!validity[id]) {
      const p = point(id);
      validity[id] = rectangles.some(r => p.x > r.left && p.x < r.right && p.y > r.top && p.y < r.bottom) ? 2 : 1;
    }
    return validity[id] === 1;
  };
  const clear = (from, to) => {
    const key = `${Math.min(from, to)}:${Math.max(from, to)}`;
    if (!segments.has(key)) {
      const a = point(from), b = point(to);
      segments.set(key, !rectangles.some(r => a.x === b.x
        ? a.x > r.left && a.x < r.right && Math.max(a.y, b.y) > r.top && Math.min(a.y, b.y) < r.bottom
        : a.y > r.top && a.y < r.bottom && Math.max(a.x, b.x) > r.left && Math.min(a.x, b.x) < r.right));
    }
    return segments.get(key);
  };
  return (start, end) => {
    const first = index(start), last = index(end);
    if (!valid(first) || !valid(last)) throw new Error('NIL route endpoint is inside a node label');
    const distance = new Float64Array(validity.length * 3).fill(Infinity);
    const previous = new Int32Array(distance.length).fill(-1), heap = [];
    const push = entry => {
      heap.push(entry);
      let i = heap.length - 1;
      while (i > 0) {
        const parent = (i - 1) >> 1;
        if (heap[parent].score <= entry.score) break;
        heap[i] = heap[parent]; i = parent;
      }
      heap[i] = entry;
    };
    const pop = () => {
      const best = heap[0], tail = heap.pop();
      if (heap.length) {
        let i = 0;
        while (i * 2 + 1 < heap.length) {
          let child = i * 2 + 1;
          if (child + 1 < heap.length && heap[child + 1].score < heap[child].score) ++child;
          if (tail.score <= heap[child].score) break;
          heap[i] = heap[child]; i = child;
        }
        heap[i] = tail;
      }
      return best;
    };
    distance[first * 3] = 0;
    push({id: first * 3, cost: 0, score: Math.abs(start.x - end.x) + Math.abs(start.y - end.y)});
    while (heap.length) {
      const entry = pop(), current = Math.floor(entry.id / 3), direction = entry.id % 3;
      if (entry.cost !== distance[entry.id]) continue;
      if (current === last) {
        const path = [];
        for (let id = entry.id; id !== -1; id = previous[id]) path.push(point(Math.floor(id / 3)));
        return simplify(path.reverse());
      }
      const x = current % xs.length, y = Math.floor(current / xs.length), a = point(current);
      for (const [nx, ny, nextDirection] of [[x, y + 1, 2], [x - 1, y, 1], [x + 1, y, 1], [x, y - 1, 2]]) {
        if (nx < 0 || nx >= xs.length || ny < 0 || ny >= ys.length) continue;
        const next = ny * xs.length + nx;
        if (!valid(next) || !clear(current, next)) continue;
        const b = point(next), id = next * 3 + nextDirection;
        const cost = entry.cost + Math.abs(a.x - b.x) + Math.abs(a.y - b.y) + (direction && direction !== nextDirection ? 14 : 0);
        if (cost >= distance[id]) continue;
        distance[id] = cost; previous[id] = entry.id;
        push({id, cost, score: cost + Math.abs(b.x - end.x) + Math.abs(b.y - end.y)});
      }
    }
    throw new Error('Unable to route NIL pointer around the tree');
  };
}

function withSharedNil(geometry, root, rootIsNil, nilNames) {
  const real = geometry.nodes.filter(node => !node.nil), nilEdges = geometry.edges.filter(edge => edge.nil);
  if (!rootIsNil && !nilNames.length && !nilEdges.length && !real.some(node => node.record.parent_is_nil)) return geometry;
  const names = new Set(nilNames);
  for (const node of real) for (const aliases of Object.values(node.record.nil_labels ?? {})) for (const name of aliases) names.add(name);
  const label = labelFor([...(rootIsNil ? ['ROOT'] : []), ...[...names].sort()], 100, 64);
  const rootNode = real.find(node => node.id === root);
  const center = rootNode ? rootNode.x + rootNode.bodyWidth / 2 : real.length ? (Math.min(...real.map(n => n.x)) + Math.max(...real.map(n => n.x + n.bodyWidth))) / 2 : 50;
  const sentinel = {
    id: 'nil:shared', nil: true, shared: true, referenced: true, root: rootIsNil,
    x: center - 50, y: Math.max(0, ...real.map(n => n.y + n.height + 96), ...geometry.nodes.filter(n => n.nil).map(n => n.y + 48)),
    bodyWidth: 100, bodyHeight: 64, label,
    width: label ? label.x + label.width : 100, height: Math.max(64, label?.height ?? 0),
  };
  const rectangles = [];
  const obstacle = (x, y, width, height) => rectangles.push({left: x - 12, top: y - 12, right: x + width + 12, bottom: y + height + 12});
  for (const node of [...real, sentinel]) {
    obstacle(node.x, node.y, node.bodyWidth, node.bodyHeight);
    if (node.label) obstacle(node.x + node.label.x, node.y + node.label.y, node.label.width, node.label.height);
  }
  const jobs = nilEdges.map(edge => {
    const prefix = edge.sections.flat(), start = prefix.at(-1);
    const source = real.find(node => edge.sources[0].startsWith(`${node.id}:`));
    return {edge, prefix, start, source, side: edge.sources[0].endsWith(':left') ? 'left' : 'right'};
  }).sort((a, b) => a.start.x - b.start.x || a.start.y - b.start.y);
  jobs.forEach((job, i) => {
    job.end = {x: sentinel.x + 100 * (i + 1) / (jobs.length + 1), y: sentinel.y};
    job.goal = {x: job.end.x, y: sentinel.y - 16};
  });
  const left = Math.min(sentinel.x, ...real.map(n => n.x), ...geometry.groups.map(g => g.x)) - 48;
  const parents = real.filter(node => node.record.parent_is_nil).map((node, i) => ({
    node, start: {x: node.x, y: node.y + node.bodyHeight / 2},
    stub: {x: node.x - 16, y: node.y + node.bodyHeight / 2},
    rail: {x: left - i * 18, y: node.y + node.bodyHeight / 2},
    lower: {x: left - i * 18, y: sentinel.y + 32},
    goal: {x: sentinel.x - 16, y: sentinel.y + 32},
  }));
  const route = router(rectangles, [
    ...jobs.flatMap(job => [job.start, job.goal]),
    ...parents.flatMap(job => [job.stub, job.rail, job.lower, job.goal]),
  ]);
  const sharedEdges = jobs.map(job => ({
    ...job.edge, rounded: true, sourceNode: job.source.id, targetNode: sentinel.id, pointer: job.side,
    title: `#${job.source.id}.${job.side} → tree.nil`,
    sections: [simplify([...job.prefix, ...route(job.start, job.goal), job.end])],
  }));
  for (const job of parents) {
    sharedEdges.push({
      id: `${job.node.id}:nil:parent:edge`, nil: true, parent: true, rounded: true,
      sourceNode: job.node.id, targetNode: sentinel.id, pointer: 'parent',
      title: `${job.node.id === root ? 'Root' : '#' + job.node.id}.parent → tree.nil`,
      sections: [simplify([job.start, ...route(job.stub, job.rail), job.lower, ...route(job.lower, job.goal), {x: sentinel.x, y: sentinel.y + 32}])],
      labels: [{text: 'parent', x: job.rail.x - 48, y: (job.rail.y + job.lower.y) / 2 - 7, width: 42, height: 14}],
    });
  }
  return {
    nodes: [...real, sentinel], edges: [...geometry.edges.filter(edge => !edge.nil), ...sharedEdges],
    groups: geometry.groups.map(group => ({...group, height: Math.max(80, ...real.filter(node => node.group === group.id).map(node => node.y + node.height - group.y + 24))})),
  };
}
