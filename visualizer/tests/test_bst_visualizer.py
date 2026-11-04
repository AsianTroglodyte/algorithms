"""The shared runtime supports None-based BSTs without RB color/sentinel rules."""

import gc
import importlib.util
import json
from pathlib import Path
import unittest
import weakref

from binary_tree import Node, Tree, tree_insert, tree_delete

# RB and BST debug sessions are separate processes. Use an isolated instance
# here so unittest discovery can also run the RB runtime tests in this process.
spec = importlib.util.spec_from_file_location('bst_test_runtime', Path(__file__).resolve().parents[1] / 'runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
runtime.install_tracking(Node)


class BSTSnapshotTests(unittest.TestCase):
    def setUp(self):
        runtime._tree = None
        gc.collect()
        self.tree = Tree()
        runtime.register_tree(self.tree)

    def test_empty_tree_and_plain_nodes(self):
        state = runtime.snapshot({})
        self.assertEqual(state['tree_kind'], 'bst')
        self.assertTrue(state['root_is_empty'])
        self.assertFalse(state['root_is_nil'])
        self.assertIsNone(state['nil_address'])
        self.assertEqual(state['warnings'], [])
        node = Node(10)
        tree_insert(self.tree, node)
        state = runtime.snapshot({'node': node, 'alias': node, 'unrelated_none': None})
        self.assertEqual(state['nodes'][0]['names'], ['alias', 'node'])
        self.assertEqual(state['nodes'][0]['color'], 'plain')
        self.assertEqual(state['nodes'][0]['nil_children'], ['left', 'right'])
        self.assertFalse(state['nodes'][0]['parent_is_nil'])
        self.assertEqual(state['nil_names'], [])
        self.assertEqual(state['warnings'], [])
        self.assertEqual(json.loads(bytes.fromhex(runtime.snapshot_wire({'node': node}))), runtime.snapshot({'node': node}))

    def test_none_cursor_is_local_to_the_actual_insertion_slot(self):
        parent = Node(20)
        tree_insert(self.tree, parent)
        for key, side in [(10, 'left'), (30, 'right'), (20, 'right')]:
            new_node = Node(key)
            state = runtime.snapshot({'current_node': None, 'parent_of_new_node': parent, 'new_node': new_node})
            record = next(node for node in state['nodes'] if node['id'] == state['root'])
            self.assertEqual(record['nil_labels'], {side: ['current_node']})
            self.assertEqual(state['nil_names'], [])
        state = runtime.snapshot({'parent_of_new_node': parent, 'new_node': new_node})
        self.assertTrue(all(not node['nil_labels'] for node in state['nodes']))

    def test_parent_then_child_assignment_is_a_local_warning(self):
        parent, new_node = Node(20), Node(10)
        tree_insert(self.tree, parent)
        new_node.parent = parent
        state = runtime.snapshot({'new_node': new_node, 'parent_of_new_node': parent})
        self.assertEqual(len(state['warnings']), 1)
        self.assertIn('does not list this node', state['warnings'][0])
        parent.left = new_node
        self.assertEqual(runtime.snapshot({})['warnings'], [])

    def test_deleted_node_is_detached_and_weakly_tracked(self):
        nodes = [Node(key) for key in [20, 10, 30, 25]]
        for node in nodes:
            tree_insert(self.tree, node)
        removed = nodes.pop(0)
        tree_delete(self.tree, removed)
        state = runtime.snapshot({'removed': removed})
        self.assertEqual(state['warnings'], [])
        record = next(node for node in state['nodes'] if node['names'] == ['removed'])
        self.assertTrue(record['detached'])
        self.assertIsNone(record['parent'])
        self.assertEqual(record['nil_children'], ['left', 'right'])
        ref = weakref.ref(removed)
        del removed
        gc.collect()
        self.assertIsNone(ref())

    def test_malformed_pointers_remain_finite_and_reported(self):
        a, b, parent = Node(1), Node(2), Node(3)
        self.tree.root = a
        a.left = a.right = b
        b.left = a
        b.parent = parent
        state = runtime.snapshot({})
        for warning in ['Cycle', 'Shared child', 'does not list']:
            self.assertIn(warning, '\n'.join(state['warnings']))
        self.assertFalse(any('color' in warning.lower() for warning in state['warnings']))


if __name__ == '__main__':
    unittest.main()
