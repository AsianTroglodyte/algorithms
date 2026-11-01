// ELK owns geometry; the SVG renderer owns appearance and the camera.
const elk = new window.ELK();
const bodyWidth = 100, bodyHeight = 84, labelGap = 16;
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

export async function layout(nodes, edges, root) {
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
    const heading = [node.id === root ? 'ROOT' : '', node.names.join(', ')].filter(Boolean).join(' · ');
    const label = heading ? {
      text: heading, x: bodyWidth + labelGap, y: 28,
      width: Math.max(52, Math.min(280, heading.length * 7 + 20)), height: 28,
    } : null;
    // Reserve the callout as part of the layout footprint so other nodes and
    // child edges cannot pass through it. Ports still attach to the body.
    const width = label ? label.x + label.width : bodyWidth;
    group.children.push({
      id: node.id, width, height: bodyHeight, bodyWidth, label, record: node,
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
      group.children.push({id: nilId, width: 40, height: 24, nil: true});
      group.edges.push({id: `${nilId}:edge`, sources: [`${node.id}:${side}`], targets: [nilId], nil: true,
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
  if (!crossEdges.length) {
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
