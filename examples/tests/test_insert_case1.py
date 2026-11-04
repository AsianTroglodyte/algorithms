"""Verify actual fix-up iterations, stopping conditions, and RB invariants."""

import inspect
import sys
import unittest
from unittest.mock import patch

import red_black_trees as rb
from examples._case1 import make_tree


def inspect_tree(tree, fix_node=None):
    """Independently check BST/pointers/black heights and the loop invariant.

    During fix-up, allow only a red root at fix_node OR a red-red edge from
    fix_node to its parent. Return the number of black real nodes per path.
    """
    assert tree.nil.color == rb.Color.BLACK
    assert tree.nil.left is tree.nil and tree.nil.right is tree.nil
    assert tree.root.parent is tree.nil
    assert tree.root.color == rb.Color.BLACK or tree.root is fix_node
    seen = set()

    def walk(node, lower, upper):
        if node is tree.nil:
            return 0
        assert node not in seen, "Cycle or shared child"
        seen.add(node)
        assert lower < node.key < upper
        for child in (node.left, node.right):
            if child is not tree.nil:
                assert child.parent is node
                if node.color == child.color == rb.Color.RED:
                    assert child is fix_node
        left = walk(node.left, lower, node.key)
        right = walk(node.right, node.key, upper)
        assert left == right, f"Unequal black heights at {node.key}"
        return left + (node.color == rb.Color.BLACK)

    black_count = walk(tree.root, float("-inf"), float("inf"))
    return black_count, sorted(node.key for node in seen)


class Case1ExamplesTests(unittest.TestCase):
    def test_three_recolorings_and_the_three_stopping_parents(self):
        source, first_line = inspect.getsourcelines(rb.insert_fixup)
        guard_line = first_line + next(i for i, line in enumerate(source)
                                       if "while fix_node.parent.color" in line)
        for kind, count, root_key, depths in (
            ("internal", 45, 30, [8, 6, 4, 2]),
            ("root", 29, 22, [7, 5, 3, 1]),
            ("nil", 21, 14, [6, 4, 2, 0]),
        ):
            with self.subTest(stopping_parent=kind):
                tree = make_tree(kind)
                black_count, keys = inspect_tree(tree)
                self.assertEqual(keys, list(range(1, count + 1)))
                root = tree.root
                self.assertEqual(root.key, root_key)
                guards = []

                def trace(frame, event, arg):
                    if frame.f_code is not rb.insert_fixup.__code__:
                        return None
                    if event == "line" and frame.f_lineno == guard_line:
                        fix = frame.f_locals["fix_node"]
                        parent = fix.parent
                        current = fix
                        depth = 0
                        while current is not tree.root:
                            current = current.parent
                            depth += 1
                        current_black_count, current_keys = inspect_tree(tree, fix)
                        self.assertEqual(current_black_count, black_count)
                        self.assertEqual(current_keys, list(range(count + 1)))
                        self.assertEqual(fix.color, rb.Color.RED)
                        if len(guards) < 3:
                            self.assertEqual(parent.color, rb.Color.RED)
                            grandparent = parent.parent
                            self.assertEqual(grandparent.color, rb.Color.BLACK)
                            uncle = grandparent.right
                            self.assertEqual(uncle.key, [3, 8, 18][len(guards)])
                            self.assertEqual(uncle.color, rb.Color.RED)
                        else:
                            self.assertEqual(parent.color, rb.Color.BLACK)
                        guards.append((fix.key, parent, depth))
                    return trace

                previous_trace = sys.gettrace()
                try:
                    with patch.object(rb, "left_rotate", side_effect=AssertionError("Unexpected case 2/3")), \
                         patch.object(rb, "right_rotate", side_effect=AssertionError("Unexpected case 2/3")):
                        sys.settrace(trace)
                        rb.insert(tree, rb.Node(0))
                finally:
                    sys.settrace(previous_trace)

                self.assertEqual([key for key, _, _ in guards], [0, 2, 6, 14])
                self.assertEqual([depth for _, _, depth in guards], depths)
                self.assertEqual([parent.key for _, parent, _ in guards[:3]], [1, 4, 10])
                stop_parent = guards[-1][1]
                self.assertEqual(stop_parent.color, rb.Color.BLACK)
                if kind == "nil":
                    self.assertIs(stop_parent, tree.nil)
                elif kind == "root":
                    self.assertIs(stop_parent, tree.root)
                    self.assertEqual(stop_parent.key, 22)
                else:
                    self.assertIsNot(stop_parent, tree.root)
                    self.assertIsNot(stop_parent, tree.nil)
                    self.assertEqual(stop_parent.key, 22)
                final_black_count, final_keys = inspect_tree(tree)
                self.assertEqual(final_keys, list(range(count + 1)))
                self.assertEqual(final_black_count, black_count + (kind == "nil"))
                self.assertIs(tree.root, root, "Case 1 must not rotate the tree")


if __name__ == "__main__":
    unittest.main()
