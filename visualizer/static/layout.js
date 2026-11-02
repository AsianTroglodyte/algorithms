// Lay out the tree first. Shared NIL arrows are routed afterward so they
// cannot influence the positions or ordering of real nodes.
const elk = new window.ELK();
const bodyWidth = 100, bodyHeight = 84, labelGap = 16;
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
      let separation = 80;
      if (left && right) {
        for (let d = 0; d < Math.min(left.right.length, right.left.length); ++d) {
          separation = Math.max(separation, left.right[d] - right.left[d] + 40);
        }
      }
      const shape = {left: [-node.bodyWidth / 2], right: [node.width - node.bodyWidth / 2], branches: []};
      for (const [child, shift] of [[branches.left, right ? -separation / 2 : -60], [branches.right, left ? separation / 2 : 60]]) {
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

export async function layout(nodes, edges, root, {sharedNil = false, rootIsNil = false, nilNames = []} = {}) {
  const geometry = await layoutTree(nodes, edges, root);
  return sharedNil ? withSharedNil(geometry, root, rootIsNil, nilNames) : geometry;
}

async function layoutTree(nodes, edges, root) {
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
    const lines = [...(node.id === root ? ['ROOT'] : []), ...node.names];
    const label = labelFor(lines, bodyWidth, bodyHeight);
    // Reserve the callout as part of the layout footprint so other nodes and
    // child edges cannot pass through it. Ports still attach to the body.
    const width = label ? label.x + label.width : bodyWidth;
    group.children.push({
      id: node.id, width, height: Math.max(bodyHeight, label?.height ?? 0), bodyWidth, bodyHeight, label, record: node,
      layoutOptions: {'elk.portConstraints': 'FIXED_POS'},
      ports: [
        {id: `${node.id}:in`, x: bodyWidth / 2, y: 0, width: 0, height: 0, layoutOptions: {'elk.port.side': 'NORTH'}},
        ...['left', 'right'].map((side, i) => ({
          id: `${node.id}:${side}`, x: bodyWidth * (i ? .75 : .25), y: bodyHeight,
          width: 0, height: 0, layoutOptions: {'elk.port.side': 'SOUTH'},
        })),
      ],
    });
    // Invisible NIL slots still participate in layout. A sole child must keep
    // its left/right meaning, and the NIL toggle must not rearrange the tree.
    for (const side of node.nil_children ?? []) {
      const nilId = `${node.id}:nil:${side}`;
      const label = labelFor(node.nil_labels?.[side] ?? [], 40, 24);
      const referenced = Boolean(label);
      group.children.push({
        id: nilId, width: label ? label.x + label.width : 40, height: Math.max(24, label?.height ?? 0),
        bodyWidth: 40, bodyHeight: 24, nil: true, referenced, label,
        layoutOptions: {'elk.portConstraints': 'FIXED_POS'},
        ports: [{id: `${nilId}:in`, x: 20, y: 0, width: 0, height: 0, layoutOptions: {'elk.port.side': 'NORTH'}}],
      });
      group.edges.push({id: `${nilId}:edge`, sources: [`${node.id}:${side}`], targets: [`${nilId}:in`], nil: true, referenced,
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
      if (node.children) collect(node, x, y);
      else result.nodes.push({...node, group: container.id, x: node.x + x, y: node.y + y});
    }
    for (const edge of container.edges ?? []) {
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
  const center = rootNode ? rootNode.x + bodyWidth / 2 : real.length ? (Math.min(...real.map(n => n.x)) + Math.max(...real.map(n => n.x + bodyWidth))) / 2 : 50;
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
