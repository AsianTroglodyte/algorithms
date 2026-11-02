"""Snapshot semantics and independent HTTP transport regression tests."""

import gc
import json
import threading
import unittest
import urllib.error
import urllib.request
import weakref

from red_black_trees import Color, Node, Tree, insert, left_rotate
from visualizer import runtime
from visualizer.server import create_server

runtime.install_tracking(Node)


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

    def test_none_aliases_follow_the_stopped_frame_values(self):
        node = Node(20)
        self.tree.root = node
        state = runtime.snapshot({'current_node': node, 'parent_of_new_node': None})
        self.assertEqual(state['nodes'][0]['names'], ['current_node'])
        self.assertEqual(state['nil_names'], ['parent_of_new_node'])
        self.assertFalse(state['root_is_none'])

        state = runtime.snapshot({'current_node': None, 'alias': None, 'other': 0})
        self.assertEqual(state['nil_names'], ['alias', 'current_node'])
        self.assertEqual(state['nodes'][0]['names'], [])
        self.assertEqual(state['nodes'][0]['nil_children'], ['left', 'right'])
        self.assertEqual(runtime.snapshot({})['nil_names'], [])

        self.tree.root = None
        self.assertTrue(runtime.snapshot({'current_node': None})['root_is_none'])
        self.tree.root = 'invalid root'
        self.assertFalse(runtime.snapshot({})['root_is_none'])

    def test_insertion_none_label_selects_the_actual_empty_child(self):
        parent = Node(20)
        self.tree.root = parent
        for key, side in ((10, 'left'), (30, 'right'), (20, 'right')):
            with self.subTest(key=key):
                new_node = Node(key)
                state = runtime.snapshot({'current_node': None, 'new_node': new_node,
                                          'parent_of_new_node': parent, 'other': None})
                record = next(node for node in state['nodes'] if node['id'] == state['root'])
                self.assertEqual(record['nil_labels'], {side: ['current_node']})
                self.assertEqual(state['nil_names'], ['other'])
                self.assertIn(side, record['nil_children'])
                self.assertEqual(record['names'], ['parent_of_new_node'])

        # Once the slot is occupied, current_node still being None must not
        # produce a NIL child at that position.
        new_node = Node(10)
        parent.left = new_node
        new_node.parent = parent
        state = runtime.snapshot({'current_node': None, 'new_node': new_node,
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
        self.tree.root = parent
        state = runtime.snapshot({'current_node': None, 'new_node': new_node,
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

    def test_registration_is_weak_and_single(self):
        with self.assertRaises(RuntimeError):
            runtime.register_tree(Tree())
        reference = weakref.ref(self.tree)
        del self.tree
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(runtime.snapshot({})['status'], 'waiting')

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
