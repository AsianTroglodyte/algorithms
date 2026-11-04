"""BST lesson 2: search for an empty child and link a new node."""

from binary_tree import Node, tree_insert
from examples._bst import make_tree
from visualizer.runtime import install_tracking, register_tree


def main():
    install_tracking(Node)
    tree, nodes = make_tree()
    register_tree(tree)
    new_node = Node(0)

    # Break here; step into tree_insert. None marks the empty left child of 1.
    tree_insert(tree, new_node)
    assert nodes[1].left is new_node
    finished = True


if __name__ == '__main__':
    main()
