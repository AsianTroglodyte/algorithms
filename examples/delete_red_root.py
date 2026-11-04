"""Deletion problem 1: final fixup recoloring repairs a red root; zero cases.

Run: python -m examples.delete_red_root
See delete_final_recolor.md for diagrams and debugger breakpoints.
"""

from examples._delete_final_recolor import make_tree
from red_black_trees import Color, Node, delete as rb_delete
from visualizer.runtime import install_tracking, register_tree, with_deletion_cleanup


def main():
    install_tracking(Node)
    delete = with_deletion_cleanup(rb_delete)
    tree, delete_node, replacement = make_tree('red_root')
    register_tree(tree)

    # Break here. Black root 10 has one red child, 5.
    # In delete_fixup: fix_node is the new root, so the while loop is skipped.
    # Only the final fix_node.color = Color.BLACK repairs property 2.
    delete(tree, delete_node)

    assert tree.root is replacement
    assert replacement.color is Color.BLACK
    assert replacement.parent is tree.nil
    finished = True  # Inspect the repaired black root 5.


if __name__ == '__main__':
    main()
