import types
from enum import Enum


class Color(Enum):
    """Enum for node colors."""

    RED = "red"
    BLACK = "black"


class Node:
    """Red black tree Node."""

    def __init__(self, key):
        """Initialize the values of the node."""
        self.color: Color = None
        self.key = key
        self.left = None
        self.right = None
        self.parent = None

# 1. Every node is either red or black.
# 2. The root is black.
# 3. Every leaf (NIL) is black.
# 4. If a node is red, then both its children are black.
# 5. For each node, all simple paths from the node to descendant
# leaves contain the same number of black nodes.


class Tree:
    """Tree that merely contains Root node."""

    def __init__(self, root: Node = None):
        """Initialize the root node."""
        self.root = root


def left_rotate(tree: Tree, rotate_down: Node):
    """Rotate rotate_down left, promoting its right child, rotate_up."""
    rotate_up = rotate_down.right  # just setup

    # Turn rotate_up's left subtree into rotate_down's right subtree.
    rotate_down.right = rotate_up.left
    if rotate_up.left is not None:  # If rotate_up's left subtree is not empty...
        # ...then rotate_down becomes the parent of the subtree's root.
        rotate_up.left.parent = rotate_down

    # rotate_down's parent becomes rotate_up's parent.
    rotate_up.parent = rotate_down.parent
    if rotate_down.parent is None:  # If rotate_down was the root...
        tree.root = rotate_up  # ...then rotate_up becomes the root.
    elif rotate_down == rotate_down.parent.left:
        # Otherwise, if rotate_down was a left child...
        rotate_down.parent.left = rotate_up  # ...rotate_up becomes a left child.
    else:
        # Otherwise, rotate_down was a right child, and now rotate_up is.
        rotate_down.parent.right = rotate_up

    # Make rotate_down become rotate_up's left child.
    rotate_up.left = rotate_down
    rotate_down.parent = rotate_up


def right_rotate(tree: Tree, rotate_down: Node):
    """Rotate rotate_down right, promoting its left child, rotate_up."""
    rotate_up = rotate_down.left

    # Turn rotate_up's right subtree into rotate_down's left subtree.
    rotate_down.left = rotate_up.right
    if rotate_up.right is not None:  # If rotate_up's right subtree is not empty...
        # ...then rotate_down becomes the parent of the subtree's root.
        rotate_up.right.parent = rotate_down

    # rotate_down's parent becomes rotate_up's parent.
    rotate_up.parent = rotate_down.parent
    if rotate_down.parent is None:  # If rotate_down was the root...
        tree.root = rotate_up  # ...then rotate_up becomes the root.
    elif rotate_down == rotate_down.parent.right:
        # Otherwise, if rotate_down was a right child...
        rotate_down.parent.right = rotate_up  # ...rotate_up becomes a right child.
    else:
        # Otherwise, rotate_down was a left child, and now rotate_up is.
        rotate_down.parent.left = rotate_up

    # Make rotate_down become rotate_up's right child.
    rotate_up.right = rotate_down
    rotate_down.parent = rotate_up


def insert(tree: Tree, insert_node: Node):
    """Insert insert_node into tree and restore the red-black properties."""
    parent_node = None
    search_node = tree.root

    # Find the empty leaf position where insert_node belongs.
    while search_node is not None:
        parent_node = search_node
        if insert_node.key < search_node.key:
            search_node = search_node.left
        else:
            search_node = search_node.right

    insert_node.parent = parent_node
    if parent_node is None:
        tree.root = insert_node
    elif insert_node.key < parent_node.key:
        parent_node.left = insert_node
    else:
        parent_node.right = insert_node

    # A new node replaces a black NIL leaf and starts red.
    insert_node.left = None
    insert_node.right = None
    insert_node.color = Color.RED
    insert_fixup(tree, insert_node)


def insert_fixup(tree: Tree, fix_node: Node):
    """Restore red-black properties after inserting fix_node."""
    while fix_node.parent is not None and fix_node.parent.color == Color.RED:
        grandparent = fix_node.parent.parent

        if fix_node.parent == grandparent.left:
            uncle = grandparent.right

            if uncle is not None and uncle.color == Color.RED:
                # A red uncle lets the violation move up to the grandparent.
                fix_node.parent.color = Color.BLACK
                uncle.color = Color.BLACK
                grandparent.color = Color.RED
                fix_node = grandparent
            else:
                if fix_node == fix_node.parent.right:
                    # Rotate the inner child into an outer-child position.
                    fix_node = fix_node.parent
                    left_rotate(tree, fix_node)

                # The outer child can replace its grandparent without a red pair.
                fix_node.parent.color = Color.BLACK
                grandparent = fix_node.parent.parent
                grandparent.color = Color.RED
                right_rotate(tree, grandparent)
        else:
            uncle = grandparent.left

            if uncle is not None and uncle.color == Color.RED:
                # A red uncle lets the violation move up to the grandparent.
                fix_node.parent.color = Color.BLACK
                uncle.color = Color.BLACK
                grandparent.color = Color.RED
                fix_node = grandparent
            else:
                if fix_node == fix_node.parent.left:
                    # Rotate the inner child into an outer-child position.
                    fix_node = fix_node.parent
                    right_rotate(tree, fix_node)

                # The outer child can replace its grandparent without a red pair.
                fix_node.parent.color = Color.BLACK
                grandparent = fix_node.parent.parent
                grandparent.color = Color.RED
                left_rotate(tree, grandparent)

    tree.root.color = Color.BLACK
