"""Weak node tracking and finite snapshots, evaluated in the stopped frame."""

import functools
import json
import weakref

_nodes = weakref.WeakValueDictionary()
_tree = None
_node_type = None
_serial = 0
_ids = weakref.WeakKeyDictionary()


def _track(node):
    global _serial
    if node not in _ids:
        _serial += 1
        _ids[node] = str(_serial)
    _nodes[_ids[node]] = node
    return _ids[node]


def install_tracking(node_type):
    """Install once, before construction. No tree operation is modified."""
    global _node_type
    if _node_type is node_type:
        return
    if _node_type is not None:
        raise RuntimeError("Only one Node class is supported per session")
    _node_type = node_type
    original = node_type.__init__

    @functools.wraps(original)
    def initialize(self, *args, **kwargs):
        _track(self)  # A pause inside __init__ can show a partially initialized node.
        original(self, *args, **kwargs)

    node_type.__init__ = initialize


def register_tree(tree):
    """Register one tree weakly; discover existing connected nodes on snapshots.

    Preexisting detached nodes cannot be discovered unless explicitly tracked
    with track_existing. New nodes are tracked by the constructor wrapper.
    """
    global _tree
    if _node_type is None:
        raise RuntimeError("Call install_tracking(Node) before registration")
    if _tree is not None and _tree() is not tree:
        raise RuntimeError("Only one registered tree is supported per session")
    _tree = weakref.ref(tree)


def track_existing(node):
    """Explicitly enroll a live node constructed before tracking was installed."""
    if _node_type is None or not isinstance(node, _node_type):
        raise TypeError("Expected an instance of the tracked Node class")
    _track(node)


def _insertion_nil_slot(frame_locals):
    """Locate insert's empty child slot using its stopped-frame search context."""
    if "current_node" not in frame_locals or frame_locals["current_node"] is not None:
        return None
    parent = frame_locals.get("parent_of_new_node")
    new_node = frame_locals.get("new_node")
    if not isinstance(parent, _node_type) or not isinstance(new_node, _node_type):
        return None
    parent_id = _ids.get(parent)
    if parent_id is None:
        return None
    key, parent_key = getattr(new_node, "key", None), getattr(parent, "key", None)
    # Mirror insert's comparison for primitive keys without invoking user code.
    primitives = (int, float, str, bool)
    if type(key) not in primitives or type(parent_key) not in primitives:
        return None
    try:
        side = "left" if key < parent_key else "right"
    except TypeError:
        return None
    if hasattr(parent, side) and getattr(parent, side) is None:
        return parent_id, side
    return None


def snapshot(frame_locals):
    """Return JSON-safe values only; never retain a frame or strong node reference."""
    tree = _tree() if _tree is not None else None
    if tree is None:
        return {"status": "waiting", "message": "Waiting for a registered tree", "nodes": [], "edges": [], "warnings": [], "nil_names": [], "root_is_none": False}
    root = getattr(tree, "root", None)
    live = dict(_nodes.items())
    pending = list(live.values())
    if isinstance(root, _node_type):
        pending.append(root)
    # Follow parent links too: otherwise a malformed parent could be hidden.
    seen = set()
    while pending:
        node = pending.pop()
        ident = _track(node)
        if ident in seen:
            continue
        seen.add(ident)
        live[ident] = node
        for field in ("left", "right", "parent"):
            other = getattr(node, field, None)
            if isinstance(other, _node_type):
                pending.append(other)
    names, nil_names = {}, []
    for name, value in frame_locals.items():
        if value is None:
            nil_names.append(str(name))
        elif isinstance(value, _node_type) and value in _ids:
            names.setdefault(_ids[value], []).append(str(name))
    nil_slot = _insertion_nil_slot(frame_locals)
    if nil_slot is not None:
        nil_names.remove("current_node")
    nodes, edges, warnings = [], [], []
    incoming = {}
    for ident, node in live.items():
        issues = []
        record = {"id": ident, "address": hex(id(node)), "names": sorted(names.get(ident, [])), "warnings": issues}
        key = getattr(node, "key", "<uninitialized>")
        # Demo keys are integers. Avoid arbitrary user __repr__ side effects.
        record["key"] = str(key) if type(key) in (int, float, str, bool) else f"<{type(key).__name__}>"
        color = getattr(node, "color", None)
        record["color"] = getattr(color, "value", None)
        record["nil_children"] = [side for side in ("left", "right") if hasattr(node, side) and getattr(node, side) is None]
        record["nil_labels"] = {nil_slot[1]: ["current_node"]} if nil_slot and nil_slot[0] == ident else {}
        if record["color"] not in ("red", "black"):
            record["color"] = "unknown"
            issues.append("Unknown or uninitialized color")
        for field in ("left", "right", "parent"):
            target = getattr(node, field, None)
            record[field] = _ids.get(target) if isinstance(target, _node_type) else None
            if target is not None and not isinstance(target, _node_type):
                issues.append(f"{field} is not a Node or None")
            if not hasattr(node, field):
                issues.append(f"{field} is not initialized")
        parent = getattr(node, "parent", None)
        if isinstance(parent, _node_type) and node is not getattr(parent, "left", None) and node is not getattr(parent, "right", None):
            issues.append(f"Parent #{record['parent']} does not list this node as a child")
        for side in ("left", "right"):
            target = getattr(node, side, None)
            if isinstance(target, _node_type):
                edge_issues = []
                if getattr(target, "parent", None) is not node:
                    edge_issues.append("Child's parent does not point back")
                edge = {"source": ident, "target": _ids[target], "side": side, "warnings": edge_issues}
                edges.append(edge)
                incoming.setdefault(_ids[target], []).append(edge)
        nodes.append(record)
    for shared in incoming.values():
        if len(shared) > 1:
            for edge in shared:
                edge["warnings"].append("Shared child (multiple incoming child edges)")
    # Iterative DFS marks back edges without recursion or duplicate identities.
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], []).append(edge)
    state = {}
    for ident in live:
        if state.get(ident):
            continue
        state[ident] = 1
        stack = [(ident, iter(adjacency.get(ident, [])))]
        while stack:
            current, iterator = stack[-1]
            edge = next(iterator, None)
            if edge is None:
                state[current] = 2
                stack.pop()
            elif state.get(edge["target"]) == 1:
                edge["warnings"].append("Cycle (back edge)")
            elif not state.get(edge["target"]):
                state[edge["target"]] = 1
                stack.append((edge["target"], iter(adjacency.get(edge["target"], []))))
    root_id = _ids.get(root) if isinstance(root, _node_type) else None
    reachable, pending_ids = set(), [root_id] if root_id else []
    while pending_ids:
        ident = pending_ids.pop()
        if ident in reachable:
            continue
        reachable.add(ident)
        pending_ids.extend(edge["target"] for edge in adjacency.get(ident, []))
    for node in nodes:
        node["detached"] = node["id"] not in reachable
        if node["id"] == root_id and node["parent"] is not None:
            node["warnings"].append("Root has a parent")
        warnings.extend(f"#{node['id']}: {issue}" for issue in node["warnings"])
    warnings.extend(f"#{e['source']} {e['side']} → #{e['target']}: {issue}" for e in edges for issue in e["warnings"])
    if root is not None and root_id is None:
        warnings.append("Root is not a tracked Node")
    return {"status": "paused", "root": root_id, "nodes": nodes, "edges": edges, "warnings": warnings,
            "nil_names": sorted(nil_names), "root_is_none": root is None}


def snapshot_wire(frame_locals):
    """Hex keeps DAP's Python string repr independent of JSON quoting rules."""
    return json.dumps(snapshot(frame_locals), ensure_ascii=True).encode().hex()
