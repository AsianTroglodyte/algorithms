"""Pointer-based binary search trees with None for empty child links."""

import math


class Node:
    """Binary Search Tree Node."""

    def __init__(self, key):
        """Initialize the values of the node."""
        self.left: Node | None = None
        self.right: Node | None = None
        self.parent: Node | None = None
        self.key: int = key


class Tree:
    """Tree that merely contains Root node."""

    def __init__(self, Node=None):
        """Create an empty tree (the legacy optional argument is ignored)."""
        self.root: Node | None = None


def inorder_tree_walk(node: Node) -> None:
    """Do an inorder walk of the binary tree."""
    if (node is not None):
        inorder_tree_walk(node.left)
        print(node.key)
        inorder_tree_walk(node.right)


def preorder_tree_walk(node: Node) -> None:
    """Do an preorderwalk of the binary tree."""
    if (node is not None):
        print(node.key)
        inorder_tree_walk(node.left)
        inorder_tree_walk(node.right)


def postorder_tree_walk(node: Node) -> None:
    """Do an postorder walk of the binary tree."""
    if (node is not None):
        inorder_tree_walk(node.left)
        inorder_tree_walk(node.right)
        print(node.key)


def tree_search(node: Node, key: int) -> Node:
    """Search a binary search tree and return the node if it is found."""
    if node is None or key == node.key:
        return node
    if key < node.key:
        return tree_search(node.left, key)
    else:
        return tree_search(node.right, key)


def tree_minimum(node: Node | None) -> Node | None:
    """Return the leftmost node, or None for an empty subtree."""
    while node is not None and node.left is not None:
        node = node.left
    return node


def tree_maximum(node: Node) -> Node:
    """Search a binary search tree to find the minimum value."""
    while node.right is not None:
        node = node.right
    return node


def tree_minimum_recursive(node: Node) -> Node:
    """Search a binary search tree to find the minimum value using recursion."""
    if (node.left is not None):
        return tree_minimum(node.left)
    return node


def tree_maximum_recursive(node: Node) -> Node:
    """Search a binary search tree to find the maximum value using recursion."""
    if (node.right is not None):
        return tree_minimum(node.right)
    return node


def tree_successor(node: Node) -> Node:
    """Find the next node that is visited in inorder traversal."""
    if node.right is not None:
        """If there is right node, then its smallest val is successor """
        return tree_minimum(node.right)
    else:
        """If no right node, then next visit is ancestor that has the inputted
        node on it's left subtree."""
        parent_node = node.parent
        while parent_node is not None and node == parent_node.right:
            node = parent_node
            parent_node = parent_node.parent
        return parent_node


def transplant(tree: Tree, old_root: Node, replacement: Node | None):
    """Transplant some subtree with a some other subtree."""
    if old_root.parent is None:
        tree.root = replacement
    elif old_root is old_root.parent.left:
        old_root.parent.left = replacement
    else:
        old_root.parent.right = replacement
    if replacement is not None:
        replacement.parent = old_root.parent


def tree_delete(tree: Tree, node_to_delete: Node):
    """Delete a node from a tree."""
    if node_to_delete.left is None:
        # replacing node with its right child
        # Note that right child could be None as well which is valid.
        transplant(tree, node_to_delete, node_to_delete.right)
    elif node_to_delete.right is None:
        # replacing node with its left child
        transplant(tree, node_to_delete, node_to_delete.left)
    else:
        successor = tree_minimum(node_to_delete.right)
        if successor is not node_to_delete.right:  # is succesor farther down tree?
            # replace successor by it's right child
            transplant(tree, successor, successor.right)
            successor.right = node_to_delete.right
            successor.right.parent = successor
        transplant(tree, node_to_delete, successor)  # replace node by its successor
        successor.left = node_to_delete.left  # node's left child to successor
        successor.left.parent = successor

    # Like the RB tree, retain a deleted node as a detached object while a
    # debugger/local still refers to it, without stale links into the tree.
    node_to_delete.left = None
    node_to_delete.right = None
    node_to_delete.parent = None


def tree_insert(tree: Tree, new_node: Node):
    """Insert a node into a Tree."""
    current_node = tree.root
    parent_of_new_node = None

    # search through tree, finding
    while current_node is not None:
        parent_of_new_node = current_node
        if new_node.key < current_node.key:
            current_node = current_node.left
        else:
            current_node = current_node.right

    new_node.parent = parent_of_new_node
    if parent_of_new_node is None:
        tree.root = new_node
    elif new_node.key < parent_of_new_node.key:
        parent_of_new_node.left = new_node
    else:
        parent_of_new_node.right = new_node


def is_valid_bst(node, lower_bound=-math.inf, upper_bound=math.inf):
    """Check if the BST is a valid BST."""
    if node is None:
        return True

    if not lower_bound < node.key < upper_bound:
        return False

    return (
        is_valid_bst(node.left, lower_bound, node.key)
        and
        is_valid_bst(node.right, node.key, upper_bound)
    )


# Match the RB module's operation names without breaking existing BST callers.
insert = tree_insert
delete = tree_delete


if __name__ == "__main__":
    tree = Tree()
    nodes = [Node(key) for key in (4, 2, 1, 3, 5, 100, 69, 124)]
    for node in nodes:
        tree_insert(tree, node)
    print("Minimum:", tree_minimum(tree.root).key)
    for node in nodes:
        print(f"Deleting {node.key}")
        tree_delete(tree, node)
        inorder_tree_walk(tree.root)
        print("Valid BST:", is_valid_bst(tree.root))
