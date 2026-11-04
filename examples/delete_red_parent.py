"""Deletion problem 2: final fixup recoloring repairs a red-red edge; zero cases.

Run: python -m examples.delete_red_parent
See delete_final_recolor.md for diagrams and debugger breakpoints.
"""

from examples._delete_final_recolor import make_tree
from red_black_trees import Color, Node, delete as rb_delete
from visualizer.runtime import install_tracking, register_tree, with_deletion_cleanup


def main():
    install_tracking(Node)
    delete = with_deletion_cleanup(rb_delete)
    tree, delete_node, replacement = make_tree('red_parent')
    register_tree(tree)
    parent = delete_node.parent

    # Break here. Black 5 has red child 2 and red parent 10.
    # In delete_fixup: fix_node is red, so the while loop is skipped.
    # The final recoloring repairs the red-red edge and the missing black.
    delete(tree, delete_node)

    assert parent.left is replacement
    assert parent.color is Color.RED
    assert replacement.color is Color.BLACK
    assert replacement.parent is parent
    assert tree.root.key == 20 and tree.root.color is Color.BLACK
    finished = True  # Inspect black 2 below red 10; root 20 never changed.


if __name__ == '__main__':
    main()
