"""Trace the original fixup and require only the exact requested case paths."""

import inspect
import sys
import unittest
from unittest.mock import patch

import red_black_trees as rb
from examples._delete_cases import make_tree, EXPECTED_CASES, EXPECTED_ROOTS
from examples.tests.test_delete_final_recolor import inspect_tree


def case_lines():
    source, start = inspect.getsourcelines(rb.delete_fixup)
    statements = {
        1: 'sibling.color = Color.BLACK',
        2: 'sibling.color = Color.RED',
        3: 'sibling.left.color = Color.BLACK',
        4: 'sibling.color = fix_node.parent.color',
    }
    cases = {case: start + next(i for i, line in enumerate(source) if line.strip() == statement)
             for case, statement in statements.items()}
    mirrored = start + next(i for i, line in enumerate(source) if line.strip() == 'sibling = fix_node.parent.left')
    final = start + next(i for i, line in enumerate(source) if line.strip() == 'fix_node.color = Color.BLACK')
    guard = start + next(i for i, line in enumerate(source) if line.strip().startswith('while fix_node is not tree.root'))
    return cases, mirrored, final, guard


def black_paths_with_nil_debt(tree):
    """Count the extra black at the active left NIL slot, not at every NIL."""
    counts = []

    def walk(node, parent, side, count):
        if node is tree.nil:
            counts.append(count + int(parent is tree.nil.parent and side == 'left'))
        else:
            count += int(node.color is rb.Color.BLACK)
            walk(node.left, node, 'left', count)
            walk(node.right, node, 'right', count)

    walk(tree.root, tree.nil, None, 0)
    return set(counts)


class DeleteCasesTests(unittest.TestCase):
    def test_each_left_child_case_and_no_mirrored_body(self):
        lines, mirrored, final, guard = case_lines()
        by_line = {line: case for case, line in lines.items()}
        rotations_expected = {1: [('left', 10)], 2: [], 3: [('right', 20), ('left', 10)], 4: [('left', 10)]}
        for requested in range(1, 5):
            with self.subTest(case=requested):
                tree, victim = make_tree(requested)
                keys, black_counts, red_pairs, _ = inspect_tree(tree)
                self.assertIs(tree.root.color, rb.Color.BLACK)
                self.assertEqual(black_counts, {2})
                self.assertEqual(red_pairs, [])
                self.assertIs(victim.color, rb.Color.BLACK)
                self.assertIs(victim.parent.left, victim)
                self.assertIs(victim.left, tree.nil)
                self.assertIs(victim.right, tree.nil)
                executed, rotations, guards, finals = [], [], [], []
                left, right = rb.left_rotate, rb.right_rotate

                def turn_left(t, node):
                    rotations.append(('left', node.key))
                    return left(t, node)

                def turn_right(t, node):
                    rotations.append(('right', node.key))
                    return right(t, node)

                def trace(frame, event, arg):
                    if event == 'line' and frame.f_code is rb.delete_fixup.__code__:
                        line = frame.f_lineno
                        self.assertFalse(mirrored <= line < final, 'Entered a mirrored case 5–8')
                        if line == guard:
                            guards.append(frame.f_locals['fix_node'])
                        if line == final:
                            finals.append(True)
                        if line in by_line:
                            case = by_line[line]
                            x, w = frame.f_locals['fix_node'], frame.f_locals['sibling']
                            self.assertIs(x, tree.nil)
                            self.assertIs(x.parent.left, x)
                            self.assertIs(x.parent.right, w)
                            self.assertIs(x.color, rb.Color.BLACK)
                            self.assertEqual(black_paths_with_nil_debt(tree), black_counts)
                            if case == 1:
                                self.assertIs(w.color, rb.Color.RED)
                                self.assertIs(x.parent.color, rb.Color.BLACK)
                            else:
                                self.assertIs(w.color, rb.Color.BLACK)
                            if case == 2:
                                self.assertIs(w.left.color, rb.Color.BLACK)
                                self.assertIs(w.right.color, rb.Color.BLACK)
                            if case == 3:
                                self.assertIs(w.left.color, rb.Color.RED)
                                self.assertIs(w.right.color, rb.Color.BLACK)
                            if case == 4:
                                self.assertIs(w.right.color, rb.Color.RED)
                            executed.append(case)
                    return trace

                previous = sys.gettrace()
                try:
                    with patch.object(rb, 'left_rotate', side_effect=turn_left), patch.object(rb, 'right_rotate', side_effect=turn_right):
                        sys.settrace(trace)
                        rb.delete(tree, victim)
                finally:
                    sys.settrace(previous)
                self.assertEqual(tuple(executed), EXPECTED_CASES[requested])
                self.assertEqual(rotations, rotations_expected[requested])
                self.assertEqual(len(guards), 2, 'Expected one loop iteration and its exit test')
                self.assertEqual(finals, [True])
                after_keys, after_counts, after_pairs, reachable = inspect_tree(tree)
                self.assertNotIn(victim, reachable)
                self.assertEqual(after_keys, [key for key in keys if key != 5])
                self.assertEqual(tree.root.key, EXPECTED_ROOTS[requested])
                self.assertIs(tree.root.color, rb.Color.BLACK)
                self.assertEqual(after_pairs, [])
                self.assertEqual(after_counts, {1} if requested == 2 else {2})


if __name__ == '__main__':
    unittest.main()
