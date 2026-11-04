"""BST lesson 1: step down the left spine to find the minimum node."""

from binary_tree import Node, tree_minimum
from examples._bst import make_tree
from visualizer.runtime import install_tracking, register_tree


def main():
    install_tracking(Node)
    tree, nodes = make_tree()
    register_tree(tree)

    # Break here; step into tree_minimum. Cursor: 16 -> 8 -> 4 -> 2 -> 1.
    minimum = tree_minimum(tree.root)
    assert minimum is nodes[1]
    finished = True  # Inspect minimum before ending the session.


if __name__ == '__main__':
    main()
