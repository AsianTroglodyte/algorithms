"""Snapshot semantics and independent HTTP transport regression tests."""

import gc
import inspect
import json
import threading
import unittest
import urllib.error
import urllib.request
import weakref

from red_black_trees import Color, Node, Tree, delete, insert, left_rotate
from visualizer import runtime
from visualizer.server import create_server

runtime.install_tracking(Node)
delete = runtime.with_deletion_cleanup(delete)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        runtime._tree = None
        gc.collect()
        self.tree = Tree()
        runtime.register_tree(self.tree)

    def test_identity_labels_actual_color_and_detached_lifetime(self):
        root, detached = Node(20), Node(10)
        self.tree.root = root
        root.color = Color.BLACK
        state = runtime.snapshot({'root': root, 'alias': root, 'detached': detached})
        self.assertEqual(len(state['nodes']), 2)
        record = next(n for n in state['nodes'] if n['id'] == state['root'])
        self.assertEqual(record['names'], ['alias', 'root'])
        self.assertEqual(record['color'], 'black')
        reference = weakref.ref(detached)
        del detached
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(len(runtime.snapshot({})['nodes']), 1)

    def test_cycle_shared_child_and_parent_mismatch(self):
        a, b, parent = Node(1), Node(2), Node(3)
        self.tree.root = a
        a.left = a.right = b
        b.left = a
        b.parent = parent
        state = runtime.snapshot({})
        warnings = '\n'.join(state['warnings'])
        self.assertEqual(len(state['nodes']), 3)
        for expected in ('Cycle', 'Shared child', "Child's parent", 'does not list'):
            self.assertIn(expected, warnings)

    def test_nil_aliases_follow_the_stopped_frame_values(self):
        node = Node(20)
        insert(self.tree, node)
        state = runtime.snapshot({'current_node': node, 'parent_of_new_node': self.tree.nil})
        self.assertEqual(state['nodes'][0]['names'], ['current_node'])
        self.assertEqual(state['nil_names'], ['parent_of_new_node'])
        self.assertFalse(state['root_is_nil'])

        state = runtime.snapshot({'current_node': self.tree.nil, 'alias': self.tree.nil, 'other': None})
        self.assertEqual(state['nil_names'], ['alias', 'current_node'])
        self.assertEqual(state['nodes'][0]['names'], [])
        self.assertEqual(state['nodes'][0]['nil_children'], ['left', 'right'])
        self.assertEqual(runtime.snapshot({})['nil_names'], [])

        self.tree.root = self.tree.nil
        self.assertTrue(runtime.snapshot({'current_node': self.tree.nil})['root_is_nil'])
        self.tree.root = 'invalid root'
        self.assertFalse(runtime.snapshot({})['root_is_nil'])

    def test_insertion_nil_label_selects_the_actual_empty_child(self):
        parent = Node(20)
        insert(self.tree, parent)
        for key, side in ((10, 'left'), (30, 'right'), (20, 'right')):
            with self.subTest(key=key):
                new_node = Node(key)
                state = runtime.snapshot({'current_node': self.tree.nil, 'new_node': new_node,
                                          'parent_of_new_node': parent, 'other': self.tree.nil})
                record = next(node for node in state['nodes'] if node['id'] == state['root'])
                self.assertEqual(record['nil_labels'], {side: ['current_node']})
                self.assertEqual(state['nil_names'], ['other'])
                self.assertIn(side, record['nil_children'])
                self.assertEqual(record['names'], ['parent_of_new_node'])

        # Once the slot is occupied, current_node still being NIL must not
        # produce a NIL child at that position.
        new_node = Node(10)
        parent.left = new_node
        new_node.parent = parent
        state = runtime.snapshot({'current_node': self.tree.nil, 'new_node': new_node,
                                  'parent_of_new_node': parent})
        record = next(node for node in state['nodes'] if node['id'] == state['root'])
        self.assertEqual(record['nil_labels'], {})
        self.assertNotIn('left', record['nil_children'])
        self.assertEqual(state['nil_names'], ['current_node'])

    def test_nil_context_does_not_invoke_custom_key_comparisons(self):
        class CustomKey:
            def __lt__(self, other):
                raise AssertionError('Snapshot must not compare custom keys')

        parent, new_node = Node(20), Node(CustomKey())
        insert(self.tree, parent)
        state = runtime.snapshot({'current_node': self.tree.nil, 'new_node': new_node,
                                  'parent_of_new_node': parent})
        self.assertEqual(state['nil_names'], ['current_node'])
        self.assertTrue(all(not node['nil_labels'] for node in state['nodes']))

    def test_large_cycle_avoids_recursion(self):
        nodes = [Node(i) for i in range(1500)]
        self.tree.root = nodes[0]
        for a, b in zip(nodes, nodes[1:] + nodes[:1]):
            a.right = b
            b.parent = a
        state = runtime.snapshot({})
        self.assertEqual(len(state['nodes']), 1500)
        self.assertTrue(any('Cycle' in w for w in state['warnings']))

    def test_partial_constructor_and_invalid_pointer(self):
        partial = Node.__new__(Node)
        runtime.track_existing(partial)
        partial.left = 'bad pointer'
        self.assertIn('left is not a Node', '\n'.join(runtime.snapshot({})['warnings']))

    def test_shared_sentinel_is_excluded_from_nodes_and_pointer_warnings(self):
        state = runtime.snapshot({})
        self.assertEqual(state['nodes'], [])
        self.assertEqual(state['edges'], [])
        self.assertEqual(state['warnings'], [])
        self.assertTrue(state['root_is_nil'])
        self.assertEqual(state['nil_address'], hex(id(self.tree.nil)))
        for key in (20, 10, 30, 5):
            insert(self.tree, Node(key))
        state = runtime.snapshot({})
        self.assertEqual(len(state['nodes']), 4)
        self.assertEqual(len(state['edges']), 3)
        self.assertEqual(state['warnings'], [])
        self.assertNotIn(state['nil_address'], [node['address'] for node in state['nodes']])
        root = next(node for node in state['nodes'] if node['id'] == state['root'])
        self.assertTrue(root['parent_is_nil'])

    def test_deleted_node_and_nil_parent_do_not_create_false_edges_or_retain_it(self):
        nodes = [Node(key) for key in (20, 10, 30, 5)]
        for node in nodes:
            insert(self.tree, node)
        removed = nodes.pop(2)  # Removing this black leaf needs NIL's parent.
        delete(self.tree, removed)
        state = runtime.snapshot({'removed': removed, 'fix_node': self.tree.nil})
        self.assertEqual(state['warnings'], [])
        record = next(node for node in state['nodes'] if node['names'] == ['removed'])
        self.assertTrue(record['detached'])
        self.assertEqual(record['nil_children'], ['left', 'right'])
        self.assertIsNone(record['parent'])
        self.assertTrue(record['parent_is_nil'])
        reference = weakref.ref(removed)
        del removed
        gc.collect()
        self.assertIsNone(reference())

    def test_registration_is_weak_and_single(self):
        with self.assertRaises(RuntimeError):
            runtime.register_tree(Tree())
        reference = weakref.ref(self.tree)
        del self.tree
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(runtime.snapshot({})['status'], 'waiting')

    def test_deletion_cleanup_binds_keywords_preserves_result_and_runs_after_success(self):
        removed, child = Node(20), Node(10)
        removed.left = child
        marker = object()

        def operation(tree, delete_node):
            self.assertIs(delete_node.left, child)
            tree.root = tree.nil
            return marker

        wrapped = runtime.with_deletion_cleanup(operation)
        self.assertIs(wrapped.__wrapped__, operation)
        self.assertEqual(inspect.signature(wrapped), inspect.signature(operation))
        self.assertEqual(wrapped.__name__, operation.__name__)
        self.assertIs(runtime.with_deletion_cleanup(wrapped), wrapped)
        self.assertIs(wrapped(delete_node=removed, tree=self.tree), marker)
        for field in ['left', 'right', 'parent']:
            self.assertIs(getattr(removed, field), self.tree.nil)

    def test_failed_deletion_keeps_partial_state_for_debugging(self):
        removed, child = Node(20), Node(10)
        removed.left = child

        def failing(tree, delete_node):
            tree.root = tree.nil
            raise RuntimeError('partial deletion')

        wrapped = runtime.with_deletion_cleanup(failing)
        with self.assertRaisesRegex(RuntimeError, 'partial deletion'):
            wrapped(self.tree, removed)
        self.assertIs(removed.left, child)

    def test_cleanup_does_not_modify_a_different_registered_tree(self):
        other = Tree()
        removed, child = Node(20), Node(10)
        removed.left = child

        def operation(tree, delete_node):
            tree.root = tree.nil

        runtime.with_deletion_cleanup(operation)(other, removed)
        self.assertIs(removed.left, child)

    def test_unwrapped_rb_deletion_keeps_original_node_links(self):
        from red_black_trees import delete as original
        self.assertIs(delete.__wrapped__, original)
        parent, removed, sibling, child = [Node(key) for key in [20, 10, 30, 5]]
        for node in [parent, removed, sibling, child]:
            insert(self.tree, node)
        original(self.tree, removed)
        self.assertIs(removed.left, child)
        self.assertIs(removed.parent, parent)
        self.assertIs(parent.left, child)
        self.assertIs(child.parent, parent)

    def test_healthy_tree_and_real_rotation(self):
        a, b = Node(1), Node(2)
        insert(self.tree, a)
        insert(self.tree, b)
        self.assertEqual(runtime.snapshot({})['warnings'], [])
        left_rotate(self.tree, a)
        state = runtime.snapshot({'rotate_down': a, 'rotate_up': b})
        self.assertEqual(state['warnings'], [])
        self.assertEqual(state['root'], runtime._ids[b])
        self.assertEqual(json.loads(bytes.fromhex(runtime.snapshot_wire({}))), runtime.snapshot({}))


class ServerTests(unittest.TestCase):
    def test_state_transport_and_token(self):
        server, token = create_server()
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}/{token}/'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(base + 'state') as response:
                self.assertEqual(json.load(response)['status'], 'waiting')
            request = urllib.request.Request(base + 'state', json.dumps({'status': 'paused', 'nodes': [{'id': '1'}]}).encode())
            opener.open(request).close()
            opener.open(urllib.request.Request(base + 'state', b'{"status":"ended"}')).close()
            with opener.open(base + 'state') as response:
                state = json.load(response)
                self.assertEqual(state['status'], 'ended')
                self.assertEqual(state['nodes'], [{'id': '1'}])
            with opener.open(base) as response:
                self.assertIn(b'Tree pointer graph', response.read())
            with self.assertRaises(urllib.error.HTTPError) as denied:
                opener.open(f'http://127.0.0.1:{server.server_port}/state')
            self.assertEqual(denied.exception.code, 404)
            denied.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
