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
    rotate_up = rotate_down.right

    # Turn rotate_up's left subtree into rotate_down's right subtree.
    rotate_down.right = rotate_up.left

    # remaining conditions handle setting the parents attributes appropriately
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

    # remaining conditions handle setting the parents attributes appropriately
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
