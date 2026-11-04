"""BST lesson 4: delete a two-child root using its successor and transplant."""

from binary_tree import Node, tree_delete
from examples._bst import make_tree
from visualizer.runtime import install_tracking, register_tree


def main():
    install_tracking(Node)
    tree, nodes = make_tree()
    register_tree(tree)
    node_to_delete = tree.root

    # Break here; step into deletion, minimum, and transplant. 17 replaces 16.
    tree_delete(tree, node_to_delete)
    assert tree.root is nodes[17]
    finished = True  # The removed 16 is detached, with three None links.


if __name__ == '__main__':
    main()
