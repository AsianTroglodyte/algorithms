"""The actual deletion fixup repairs properties 2/4 without any loop-body line."""

import inspect
import sys
import unittest
from unittest.mock import patch

import red_black_trees as rb
from examples._delete_final_recolor import make_tree


def inspect_tree(tree, extra_black=None):
    """Check real tree pointers/order and collect black counts and red-red edges.

    Counts omit the final NIL (one identical black on every path). An optional
    virtual black at x models the black contribution deletion is restoring.
    """
    assert tree.nil.color is rb.Color.BLACK
    assert tree.nil.left is tree.nil and tree.nil.right is tree.nil
    assert tree.root.parent is tree.nil
    seen, keys, counts, red_pairs = set(), [], [], []

    def walk(node, parent, lo, hi, black):
        if node is tree.nil:
            counts.append(black)
            return
        assert node not in seen
        seen.add(node)
        assert node.parent is parent
        assert lo < node.key < hi
        assert node.color in (rb.Color.RED, rb.Color.BLACK)
        if parent is not tree.nil and node.color is parent.color is rb.Color.RED:
            red_pairs.append((parent.key, node.key))
        black += int(node.color is rb.Color.BLACK) + int(node is extra_black)
        walk(node.left, node, lo, node.key, black)
        keys.append(node.key)
        walk(node.right, node, node.key, hi, black)

    walk(tree.root, tree.nil, float('-inf'), float('inf'), 0)
    return keys, set(counts), red_pairs, seen


class DeleteFinalRecolorTests(unittest.TestCase):
    def test_both_problems_use_only_the_final_fixup_assignment(self):
        source, start = inspect.getsourcelines(rb.delete_fixup)
        guard = start + next(i for i, line in enumerate(source) if line.strip().startswith('while fix_node is not tree.root'))
        recolor = start + next(i for i, line in enumerate(source) if line.strip() == 'fix_node.color = Color.BLACK')
        delete_source, delete_start = inspect.getsourcelines(rb.delete)
        fixup_call = delete_start + next(i for i, line in enumerate(delete_source) if line.strip() == 'delete_fixup(tree, fix_node)')
        for problem, root_key, victim_key, child_key, count in [
            ('red_root', 10, 10, 5, 1), ('red_parent', 20, 5, 2, 2),
        ]:
            with self.subTest(problem=problem):
                tree, victim, child = make_tree(problem)
                original_root, original_parent = tree.root, victim.parent
                before_keys, before_counts, pairs, _ = inspect_tree(tree)
                self.assertEqual(tree.root.key, root_key)
                self.assertIs(tree.root.color, rb.Color.BLACK)
                self.assertEqual(victim.key, victim_key)
                self.assertEqual(victim.color, rb.Color.BLACK)
                self.assertEqual(child.key, child_key)
                self.assertEqual(child.color, rb.Color.RED)
                self.assertEqual(before_counts, {count})
                self.assertEqual(pairs, [])
                executed, entered, exiting, decision = [], [], [], []
                raw_shapes = []

                def trace(frame, event, arg):
                    if frame.f_code is rb.delete.__code__ and event == 'line' and frame.f_lineno == fixup_call:
                        self.assertIs(frame.f_locals['y_original_color'], rb.Color.BLACK)
                        self.assertIs(frame.f_locals['fix_node'], child)
                        decision.append(True)
                    if frame.f_code is rb.delete_fixup.__code__:
                        if event == 'call':
                            entered.append(True)
                        if event == 'line':
                            executed.append(frame.f_lineno)
                            fix = frame.f_locals['fix_node']
                            self.assertIs(fix, child)
                            self.assertIs(fix.color, rb.Color.RED)
                            keys, counts, red_red, nodes = inspect_tree(tree)
                            self.assertEqual(keys, [key for key in before_keys if key != victim_key])
                            self.assertNotIn(victim, nodes)
                            self.assertEqual(inspect_tree(tree, extra_black=fix)[1], before_counts)
                            if problem == 'red_root':
                                self.assertIs(fix, tree.root)
                                self.assertEqual(counts, {count - 1})
                                self.assertEqual(red_red, [])
                            else:
                                self.assertIs(tree.root, original_root)
                                self.assertIs(fix.parent, original_parent)
                                self.assertIs(fix.parent.color, rb.Color.RED)
                                self.assertEqual(red_red, [(10, 2)])
                                self.assertEqual(counts, {count - 1, count})
                            raw_shapes.append({node.key: (node.left, node.right, node.parent) for node in nodes})
                        if event == 'return':
                            exiting.append(True)
                    return trace

                previous_trace = sys.gettrace()
                try:
                    with patch.object(rb, 'left_rotate', side_effect=AssertionError('Unexpected rotation')), \
                         patch.object(rb, 'right_rotate', side_effect=AssertionError('Unexpected rotation')):
                        sys.settrace(trace)
                        rb.delete(tree, victim)
                finally:
                    sys.settrace(previous_trace)
                self.assertEqual(decision, [True])
                self.assertEqual(entered, [True])
                self.assertEqual(executed, [guard, recolor])
                self.assertEqual(exiting, [True])
                keys, counts, pairs, nodes = inspect_tree(tree)
                self.assertIs(child.color, rb.Color.BLACK)
                self.assertIs(tree.root.color, rb.Color.BLACK)
                self.assertEqual(counts, before_counts)
                self.assertEqual(pairs, [])
                self.assertEqual(keys, [key for key in before_keys if key != victim_key])
                self.assertEqual({node.key: (node.left, node.right, node.parent) for node in nodes}, raw_shapes[-1])


if __name__ == '__main__':
    unittest.main()
