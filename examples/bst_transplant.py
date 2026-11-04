"""BST lesson 3: replace the subtree rooted at 31 with a new node, 32."""

from binary_tree import Node, transplant
from examples._bst import make_tree
from visualizer.runtime import install_tracking, register_tree


def main():
    install_tracking(Node)
    tree, nodes = make_tree()
    register_tree(tree)
    old_root = nodes[31]
    replacement = Node(32)

    # Break here; step into transplant to follow the parent/child assignments.
    transplant(tree, old_root, replacement)
    # CLRS transplant replaces a pointer, leaving old_root's own links alone.
    # Finish detaching this removed leaf; it stays visible while referenced.
    old_root.parent = None
    assert nodes[30].right is replacement
    finished = True


if __name__ == '__main__':
    main()
