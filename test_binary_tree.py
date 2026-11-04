"""BST operations preserve ordering, identity, parents, and detached nodes."""

import random
import subprocess
import sys
import unittest

import binary_tree as bst


class BinaryTreeTests(unittest.TestCase):
    def make_tree(self, keys):
        tree = bst.Tree()
        nodes = [bst.Node(key) for key in keys]
        for node in nodes:
            bst.tree_insert(tree, node)
        return tree, nodes

    def assert_tree(self, tree, keys):
        visited, actual = set(), []

        def walk(node, parent):
            if node is None:
                return
            self.assertNotIn(node, visited)
            visited.add(node)
            self.assertIs(node.parent, parent)
            walk(node.left, node)
            actual.append(node.key)
            walk(node.right, node)

        walk(tree.root, None)
        self.assertEqual(actual, sorted(keys))

    def test_import_has_no_demo_side_effects(self):
        result = subprocess.run([sys.executable, '-B', '-c', 'import binary_tree'], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '')

    def test_minimum_empty_singleton_and_subtree(self):
        self.assertIsNone(bst.tree_minimum(None))
        tree, nodes = self.make_tree([20, 10, 30, 25, 40, 22])
        self.assertIs(bst.tree_minimum(tree.root), nodes[1])
        self.assertIs(bst.tree_minimum(nodes[2]), nodes[5])
        self.assertIs(bst.tree_minimum(nodes[4]), nodes[4])

    def test_insertion_paths_duplicates_and_legacy_constructor(self):
        self.assertIsNone(bst.Tree(bst.Node).root)
        for keys in [[20, 10, 30, 5, 15], list(range(40)), list(range(40, 0, -1)), [7] * 10]:
            tree = bst.Tree()
            for index, key in enumerate(keys):
                bst.tree_insert(tree, bst.Node(key))
                self.assert_tree(tree, keys[:index + 1])
        self.assertIs(bst.insert, bst.tree_insert)
        self.assertIs(bst.delete, bst.tree_delete)

    def test_transplant_left_right_root_and_none(self):
        for key, replacement_key in [(10, 12), (30, 35), (20, 50)]:
            tree, nodes = self.make_tree([20, 10, 30])
            old = next(node for node in nodes if node.key == key)
            replacement = bst.Node(replacement_key)
            parent = old.parent
            bst.transplant(tree, old, replacement)
            self.assertIs(replacement.parent, parent)
            self.assertIs(tree.root if parent is None else parent.left if key == 10 else parent.right, replacement)
        for key in [10, 30, 20]:
            tree, nodes = self.make_tree([20, 10, 30])
            old = next(node for node in nodes if node.key == key)
            parent = old.parent
            bst.transplant(tree, old, None)
            self.assertIsNone(tree.root if parent is None else parent.left if key == 10 else parent.right)

    def test_all_deletion_cases_and_random_orders(self):
        cases = [[1], [2, 1], [2, 3], [2, 1, 3], [20, 10, 30, 25, 40, 22, 27], [7] * 8]
        for seed in range(5):
            keys = list(range(50))
            random.Random(seed).shuffle(keys)
            cases.append(keys)
        for keys in cases:
            tree, nodes = self.make_tree(keys)
            random.Random(42).shuffle(nodes)
            remaining = list(keys)
            for node in nodes:
                bst.tree_delete(tree, node)
                remaining.remove(node.key)
                self.assert_tree(tree, remaining)
                self.assertIsNone(node.left)
                self.assertIsNone(node.right)
                self.assertIsNone(node.parent)


if __name__ == '__main__':
    unittest.main()
