from enum import Enum


class Color(Enum):
    """Enum for node colors."""

    RED = "red"
    BLACK = "black"


class Node:
    """Red black tree Node."""

    def __init__(self, key):
        """Initialize the values of the node."""
        self.color: Color = Color.RED
        self.key: int = key
        # insert installs the tree's NIL sentinel in these temporary links.
        self.left: Node | None = None
        self.right: Node | None = None
        self.parent: Node | None = None


class Tree:
    """Red-black tree with one shared black NIL sentinel."""

    def __init__(self):
        """Initialize an empty tree and its sentinel."""
        self.nil = Node(None)
        self.nil.color = Color.BLACK
        self.nil.left = self.nil
        self.nil.right = self.nil
        self.nil.parent = self.nil
        self.root: Node = self.nil


def left_rotate(tree: Tree, rotate_down: Node):
    """Rotate rotate_down left, promoting its right child, rotate_up."""
    rotate_up = rotate_down.right  # just setup

    # Turn rotate_up's left subtree into rotate_down's right subtree.
    rotate_down.right = rotate_up.left
    if rotate_up.left is not tree.nil:  # If rotate_up's left subtree is not empty...
        # ...then rotate_down becomes the parent of the subtree's root.
        rotate_up.left.parent = rotate_down

    # rotate_down's parent becomes rotate_up's parent.
    rotate_up.parent = rotate_down.parent
    if rotate_down.parent is tree.nil:  # If rotate_down was the root...
        tree.root = rotate_up  # ...then rotate_up becomes the root.
    elif rotate_down is rotate_down.parent.left:
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
    if rotate_up.right is not tree.nil:  # If rotate_up's right subtree is not empty...
        # ...then rotate_down becomes the parent of the subtree's root.
        rotate_up.right.parent = rotate_down

    # rotate_down's parent becomes rotate_up's parent.
    rotate_up.parent = rotate_down.parent
    if rotate_down.parent is tree.nil:  # If rotate_down was the root...
        tree.root = rotate_up  # ...then rotate_up becomes the root.
    elif rotate_down is rotate_down.parent.right:
        # Otherwise, if rotate_down was a right child...
        rotate_down.parent.right = rotate_up  # ...rotate_up becomes a right child.
    else:
        # Otherwise, rotate_down was a left child, and now rotate_up is.
        rotate_down.parent.left = rotate_up

    # Make rotate_down become rotate_up's right child.
    rotate_up.right = rotate_down
    rotate_down.parent = rotate_up


def insert(tree: Tree, new_node: Node):
    """Insert new_node into tree and restore the red-black properties."""
    current_node = tree.root
    parent_of_new_node = tree.nil

    # Find the empty leaf position where new_node belongs.
    while current_node is not tree.nil:
        parent_of_new_node = current_node
        if new_node.key < current_node.key:
            current_node = current_node.left
        else:
            current_node = current_node.right

    new_node.parent = parent_of_new_node
    if parent_of_new_node is tree.nil:
        tree.root = new_node
    elif new_node.key < parent_of_new_node.key:
        parent_of_new_node.left = new_node
    else:
        parent_of_new_node.right = new_node

    # A new node replaces a black NIL leaf and starts red.
    new_node.left = tree.nil
    new_node.right = tree.nil
    new_node.color = Color.RED
    insert_fixup(tree, new_node)


def insert_fixup(tree: Tree, fix_node: Node):
    """Restore red-black properties after inserting fix_node."""
    while fix_node.parent.color == Color.RED:
        grandparent = fix_node.parent.parent

        if fix_node.parent is grandparent.left:
            uncle = grandparent.right

            if uncle.color == Color.RED:
                # A red uncle lets the violation move up to the grandparent.
                fix_node.parent.color = Color.BLACK
                uncle.color = Color.BLACK
                grandparent.color = Color.RED
                fix_node = grandparent
            else:
                if fix_node is fix_node.parent.right:
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

            if uncle.color == Color.RED:
                # A red uncle lets the violation move up to the grandparent.
                fix_node.parent.color = Color.BLACK
                uncle.color = Color.BLACK
                grandparent.color = Color.RED
                fix_node = grandparent
            else:
                if fix_node is fix_node.parent.left:
                    # Rotate the inner child into an outer-child position.
                    fix_node = fix_node.parent
                    right_rotate(tree, fix_node)

                # The outer child can replace its grandparent without a red pair.
                fix_node.parent.color = Color.BLACK
                grandparent = fix_node.parent.parent
                grandparent.color = Color.RED
                left_rotate(tree, grandparent)

    tree.root.color = Color.BLACK


def tree_minimum(tree: Tree, node: Node):
    """Return the node with the smallest key in node's subtree."""
    while node.left is not tree.nil:
        node = node.left
    return node


def transplant(tree: Tree, old_root: Node, replacement: Node):
    """Replace the subtree rooted at old_root with replacement."""
    if old_root.parent is tree.nil:
        tree.root = replacement
    elif old_root is old_root.parent.left:
        old_root.parent.left = replacement
    else:
        old_root.parent.right = replacement

    # NIL also needs this parent when deletion fix-up starts at an empty child.
    replacement.parent = old_root.parent


def delete(tree: Tree, delete_node: Node):
    """Delete delete_node from tree and restore the red-black properties."""
    replacement = delete_node
    removed_color = replacement.color

    if delete_node.left is tree.nil:
        fix_node = delete_node.right
        transplant(tree, delete_node, delete_node.right)
    elif delete_node.right is tree.nil:
        fix_node = delete_node.left
        transplant(tree, delete_node, delete_node.left)
    else:
        # The successor can replace delete_node without changing key order.
        replacement = tree_minimum(tree, delete_node.right)
        removed_color = replacement.color
        fix_node = replacement.right

        if replacement.parent is delete_node:
            fix_node.parent = replacement
        else:
            transplant(tree, replacement, replacement.right)
            replacement.right = delete_node.right
            replacement.right.parent = replacement

        transplant(tree, delete_node, replacement)
        replacement.left = delete_node.left
        replacement.left.parent = replacement
        replacement.color = delete_node.color

    if removed_color == Color.BLACK:
        delete_fixup(tree, fix_node)

    # Keep a deleted but still referenced node detached for inspection.
    delete_node.left = tree.nil
    delete_node.right = tree.nil
    delete_node.parent = tree.nil


def delete_fixup(tree: Tree, fix_node: Node):
    """Restore red-black properties after removing a black node."""
    while fix_node is not tree.root and fix_node.color == Color.BLACK:
        if fix_node is fix_node.parent.left:
            sibling = fix_node.parent.right

            if sibling.color == Color.RED:
                # A black sibling replaces the red sibling near fix_node.
                sibling.color = Color.BLACK
                fix_node.parent.color = Color.RED
                left_rotate(tree, fix_node.parent)
                sibling = fix_node.parent.right

            if (
                sibling.left.color == Color.BLACK
                and sibling.right.color == Color.BLACK
            ):
                # Move the extra blackness up when the sibling cannot lend one.
                sibling.color = Color.RED
                fix_node = fix_node.parent
            else:
                if sibling.right.color == Color.BLACK:
                    # Rotate a near red child into the far-child position.
                    sibling.left.color = Color.BLACK
                    sibling.color = Color.RED
                    right_rotate(tree, sibling)
                    sibling = fix_node.parent.right

                # The far red child supplies the missing black node.
                sibling.color = fix_node.parent.color
                fix_node.parent.color = Color.BLACK
                sibling.right.color = Color.BLACK
                left_rotate(tree, fix_node.parent)
                fix_node = tree.root
        else:
            sibling = fix_node.parent.left

            if sibling.color == Color.RED:
                # A black sibling replaces the red sibling near fix_node.
                sibling.color = Color.BLACK
                fix_node.parent.color = Color.RED
                right_rotate(tree, fix_node.parent)
                sibling = fix_node.parent.left

            if (
                sibling.right.color == Color.BLACK
                and sibling.left.color == Color.BLACK
            ):
                # Move the extra blackness up when the sibling cannot lend one.
                sibling.color = Color.RED
                fix_node = fix_node.parent
            else:
                if sibling.left.color == Color.BLACK:
                    # Rotate a near red child into the far-child position.
                    sibling.right.color = Color.BLACK
                    sibling.color = Color.RED
                    left_rotate(tree, sibling)
                    sibling = fix_node.parent.left

                # The far red child supplies the missing black node.
                sibling.color = fix_node.parent.color
                fix_node.parent.color = Color.BLACK
                sibling.left.color = Color.BLACK
                right_rotate(tree, fix_node.parent)
                fix_node = tree.root

    fix_node.color = Color.BLACK
