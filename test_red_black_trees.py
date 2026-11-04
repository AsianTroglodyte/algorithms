"""Shared-sentinel structure and red-black invariants after each operation."""

import random
import unittest
from unittest.mock import patch

import red_black_trees as rb


class RedBlackTreeTests(unittest.TestCase):
    def assert_tree(self, tree, expected_keys):
        self.assertEqual(tree.nil.color, rb.Color.BLACK)
        self.assertIs(tree.nil.left, tree.nil)
        self.assertIs(tree.nil.right, tree.nil)
        if tree.root is not tree.nil:
            self.assertIs(tree.root.parent, tree.nil)
            self.assertEqual(tree.root.color, rb.Color.BLACK)

        visited, keys = set(), []

        def walk(node):
            if node is tree.nil:
                return 1
            self.assertIsInstance(node, rb.Node)
            self.assertNotIn(node, visited, 'Cycle or shared non-NIL child')
            visited.add(node)
            for child in (node.left, node.right):
                self.assertIsInstance(child, rb.Node)
                if child is not tree.nil:
                    self.assertIs(child.parent, node)
                if node.color == rb.Color.RED:
                    self.assertEqual(child.color, rb.Color.BLACK)
            left_black_height = walk(node.left)
            keys.append(node.key)
            right_black_height = walk(node.right)
            self.assertEqual(left_black_height, right_black_height)
            return left_black_height + (node.color == rb.Color.BLACK)

        walk(tree.root)
        self.assertEqual(keys, sorted(expected_keys))
        return visited

    def test_one_sentinel_per_tree_and_first_insertion(self):
        tree, other = rb.Tree(), rb.Tree()
        self.assertIsNot(tree.nil, other.nil)
        self.assertIs(tree.root, tree.nil)
        self.assertIs(tree.nil.parent, tree.nil)
        self.assert_tree(tree, [])
        node = rb.Node(10)
        rb.insert(tree, node)
        self.assertIs(tree.root, node)
        self.assertIs(node.left, tree.nil)
        self.assertIs(node.right, tree.nil)
        self.assertIs(node.parent, tree.nil)
        self.assert_tree(tree, [10])

    def test_insertion_cases_and_duplicate_keys(self):
        sequences = ([41, 38, 31, 12, 19, 8], [30, 20, 10, 25, 28],
                     list(range(32)), list(reversed(range(32))), [7] * 32)
        for values in sequences:
            with self.subTest(values=values):
                tree = rb.Tree()
                for index, value in enumerate(values):
                    rb.insert(tree, rb.Node(value))
                    self.assert_tree(tree, values[:index + 1])

    def test_transplant_sets_the_shared_nil_parent(self):
        tree = rb.Tree()
        root, left, right = rb.Node(10), rb.Node(5), rb.Node(15)
        for node in (root, left, right):
            rb.insert(tree, node)
        rb.transplant(tree, left, tree.nil)
        self.assertIs(tree.nil.parent, root)
        self.assertIs(root.left, tree.nil)
        self.assert_tree(tree, [10, 15])

    def test_rotations_leave_the_nil_deletion_parent_alone(self):
        tree = rb.Tree()
        root, right = rb.Node(10), rb.Node(20)
        rb.insert(tree, root)
        rb.insert(tree, right)
        tree.nil.parent = root
        rb.left_rotate(tree, root)
        self.assertIs(tree.root, right)
        self.assertIs(right.parent, tree.nil)
        self.assertIs(root.right, tree.nil)
        self.assertIs(tree.nil.parent, root)
        rb.right_rotate(tree, right)
        self.assertIs(tree.root, root)
        self.assertIs(tree.nil.parent, root)
        self.assert_tree(tree, [10, 20])

    def test_minimum_stops_at_nil(self):
        tree = rb.Tree()
        self.assertIs(rb.tree_minimum(tree, tree.root), tree.nil)
        nodes = [rb.Node(key) for key in (20, 10, 30, 5, 15)]
        for node in nodes:
            rb.insert(tree, node)
        self.assertIs(rb.tree_minimum(tree, tree.root), nodes[3])
        self.assertIs(rb.tree_minimum(tree, nodes[2]), nodes[2])

    def test_deletion_cases_and_random_sequences(self):
        # Check every intermediate result, including root deletion, successors
        # directly below the deleted node, deeper successors, and duplicates.
        cases = [([41, 38, 31, 12, 19, 8], [8, 12, 19, 31, 38, 41]),
                 ([20, 10, 30, 25, 40, 22, 27], [20, 30, 25, 10, 22, 27, 40]),
                 ([2, 1, 3], [2, 1, 3]), ([1], [1]), ([7] * 12, [7] * 12)]
        for seed in range(8):
            rng = random.Random(seed)
            values = list(range(80))
            rng.shuffle(values)
            removals = values.copy()
            rng.shuffle(removals)
            cases.append((values, removals))

        nil_fixups = 0
        original_fixup = rb.delete_fixup

        def inspect_fixup(tree, fix_node):
            nonlocal nil_fixups
            if fix_node is tree.nil and fix_node is not tree.root:
                nil_fixups += 1
                self.assertIsNot(fix_node.parent, tree.nil)
                self.assertTrue(fix_node.parent.left is fix_node or fix_node.parent.right is fix_node)
            original_fixup(tree, fix_node)

        with patch.object(rb, 'delete_fixup', side_effect=inspect_fixup):
            for values, removals in cases:
                with self.subTest(values=values):
                    tree = rb.Tree()
                    nodes = [rb.Node(value) for value in values]
                    for node in nodes:
                        rb.insert(tree, node)
                    remaining = list(values)
                    for value in removals:
                        node = next(node for node in nodes if node.key == value)
                        nodes.remove(node)
                        rb.delete(tree, node)
                        remaining.remove(value)
                        self.assertNotIn(node, self.assert_tree(tree, remaining))
                    self.assertIs(tree.root, tree.nil)
                    self.assertIs(tree.nil.parent, tree.nil)
        self.assertGreater(nil_fixups, 0)


if __name__ == '__main__':
    unittest.main()
