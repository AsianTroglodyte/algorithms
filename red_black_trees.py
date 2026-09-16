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


def tree_minimum(node: Node):
    """Return the node with the smallest key in node's subtree."""
    while node.left is not None:
        node = node.left
    return node


def transplant(tree: Tree, old_root: Node, replacement: Node):
    """Replace the subtree rooted at old_root with replacement."""
    if old_root.parent is None:
        tree.root = replacement
    elif old_root == old_root.parent.left:
        old_root.parent.left = replacement
    else:
        old_root.parent.right = replacement

    if replacement is not None:
        replacement.parent = old_root.parent


def delete(tree: Tree, delete_node: Node):
    """Delete delete_node from tree and restore the red-black properties."""
    replacement = delete_node
    removed_color = replacement.color

    if delete_node.left is None:
        fix_node = delete_node.right
        fix_parent = delete_node.parent
        transplant(tree, delete_node, delete_node.right)
    elif delete_node.right is None:
        fix_node = delete_node.left
        fix_parent = delete_node.parent
        transplant(tree, delete_node, delete_node.left)
    else:
        # The successor can replace delete_node without changing key order.
        replacement = tree_minimum(delete_node.right)
        removed_color = replacement.color
        fix_node = replacement.right

        if replacement.parent == delete_node:
            fix_parent = replacement
            if fix_node is not None:
                fix_node.parent = replacement
        else:
            fix_parent = replacement.parent
            transplant(tree, replacement, replacement.right)
            replacement.right = delete_node.right
            replacement.right.parent = replacement

        transplant(tree, delete_node, replacement)
        replacement.left = delete_node.left
        replacement.left.parent = replacement
        replacement.color = delete_node.color

    if removed_color == Color.BLACK:
        delete_fixup(tree, fix_node, fix_parent)

    delete_node.left = None
    delete_node.right = None
    delete_node.parent = None


def _node_color(node: Node):
    """Treat an absent node as a black NIL leaf."""
    return Color.BLACK if node is None else node.color


def delete_fixup(tree: Tree, fix_node: Node, parent_node: Node = None):
    """Restore red-black properties after removing a black node."""
    if fix_node is not None:
        parent_node = fix_node.parent

    while fix_node != tree.root and _node_color(fix_node) == Color.BLACK:
        if fix_node == parent_node.left:
            sibling = parent_node.right

            if _node_color(sibling) == Color.RED:
                # A black sibling replaces the red sibling near fix_node.
                sibling.color = Color.BLACK
                parent_node.color = Color.RED
                left_rotate(tree, parent_node)
                sibling = parent_node.right

            if sibling is None:
                fix_node = parent_node
                parent_node = fix_node.parent
                continue

            if (
                _node_color(sibling.left) == Color.BLACK
                and _node_color(sibling.right) == Color.BLACK
            ):
                # Move the extra blackness up when the sibling cannot lend one.
                sibling.color = Color.RED
                fix_node = parent_node
                parent_node = fix_node.parent
            else:
                if _node_color(sibling.right) == Color.BLACK:
                    # Rotate a near red child into the far-child position.
                    if sibling.left is not None:
                        sibling.left.color = Color.BLACK
                    sibling.color = Color.RED
                    right_rotate(tree, sibling)
                    sibling = parent_node.right

                # The far red child supplies the missing black node.
                sibling.color = parent_node.color
                parent_node.color = Color.BLACK
                if sibling.right is not None:
                    sibling.right.color = Color.BLACK
                left_rotate(tree, parent_node)
                fix_node = tree.root
                parent_node = None
        else:
            sibling = parent_node.left

            if _node_color(sibling) == Color.RED:
                # A black sibling replaces the red sibling near fix_node.
                sibling.color = Color.BLACK
                parent_node.color = Color.RED
                right_rotate(tree, parent_node)
                sibling = parent_node.left

            if sibling is None:
                fix_node = parent_node
                parent_node = fix_node.parent
                continue

            if (
                _node_color(sibling.right) == Color.BLACK
                and _node_color(sibling.left) == Color.BLACK
            ):
                # Move the extra blackness up when the sibling cannot lend one.
                sibling.color = Color.RED
                fix_node = parent_node
                parent_node = fix_node.parent
            else:
                if _node_color(sibling.left) == Color.BLACK:
                    # Rotate a near red child into the far-child position.
                    if sibling.right is not None:
                        sibling.right.color = Color.BLACK
                    sibling.color = Color.RED
                    left_rotate(tree, sibling)
                    sibling = parent_node.left

                # The far red child supplies the missing black node.
                sibling.color = parent_node.color
                parent_node.color = Color.BLACK
                if sibling.left is not None:
                    sibling.left.color = Color.BLACK
                right_rotate(tree, parent_node)
                fix_node = tree.root
                parent_node = None

    if fix_node is not None:
        fix_node.color = Color.BLACK
