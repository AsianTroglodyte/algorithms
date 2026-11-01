"""Binary tree stuff."""
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

    def __init__(self, Node):
        """Initialize the root node."""
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


def tree_minimum(node: Node) -> Node:
    """Search a tree to find the minimum value."""
    while node.left is not None:
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


def transplant(tree: Tree, old_root: Node, replacement: Node):
    """Transplant some subtree with  some other subtree."""
    # To be clear, old_root is the node being replaced

    # we must do two things:
    # 1. connect replacement -> old_root. via .parent attribute.
    # 2. connect old_root -> replacement. via .left or .right attribute.

    # 1. connect replacement -> old_root. via .parent attribute.
    # if the old_root parent's none that must mean that we are
    # replacing the root node with a subtree
    if old_root.parent is None:
        # makeing replacement tree root. Basically, our tree becomes the
        # replacement
        tree.root = replacement
    # If the old_root, node being replaced, is a left child...
    elif old_root == old_root.parent.left:
        # then we change old_root's parent left child to replacement
        old_root.parent.left = replacement
    # If the old_root, node being replaced, is a right child...
    else:
        # then we change old_root's parent right child to replacement
        old_root.parent.right = replacement

    # 2. connect old_root -> replacement. via .left or .right attribute.
    # must change the replacement's parent attribute to new old_root's parent
    if replacement is not None:
        replacement.parent = old_root.parent


def tree_delete(tree: Tree, delete_node: Node):
    """Delete a node from a tree."""
    if delete_node.left is None:
        # replacing node with its right child
        # Note that right child could be None as well which is valid.
        transplant(tree, delete_node, delete_node.right)
    elif delete_node.right is None:
        # replacing node with its left child
        transplant(tree, delete_node, delete_node.left)
    else:
        successor = tree_minimum(delete_node.right)
        # if delete_node.right has no left subchild then the tree_minimum
        # will be delete_node.right. Thus successor == delete_node.right
        if successor != delete_node.right:
            # replace successor with it's right child
            transplant(tree, successor, successor.right)
            successor.right = delete_node.right
            successor.right.parent = successor
        transplant(tree, delete_node, successor)  # replace with successor
        successor.left = delete_node.left  # node's left child to successor
        successor.left.parent = successor


def tree_insert(tree: Tree, new_node: Node):
    """Insert a node into a Tree."""
    # current node is "where we are at" while traversing tree
    current_node = tree.root
    # Keep track of the last node visited; it will be the new node's parent.
    new_node_parent = None

    # Follow the BST ordering until we reach an empty child position.
    while current_node is not None:
        # Remember this node before moving to one of its children.
        new_node_parent = current_node

        # if new node smaller than current_node; move to left child
        if new_node.key < current_node.key:
            current_node = current_node.left
        # if new node larger than current_node; move to right child
        else:
            current_node = current_node.right

    # we must do two things:
    # 1. connect new_node -> parent. via .parent attribute.
    # 2. connect parent -> new_node. via .left or .right attribute.

    # 1. connect new_node -> parent. via .parent attribute.
    # The insertion position is now known. Connect the new node to its parent.
    new_node.parent = new_node_parent

    # When the tree is empty then we make the new node the root
    if new_node_parent is None:
        tree.root = new_node

    # 2. connect parent -> new_node. via .left or .right attribute.
    # When the new node is smaller than its
    # parent then we make it a left child
    elif new_node.key < new_node_parent.key:
        new_node_parent.left = new_node
    # When the new node is larger than its
    # parent then we make it a right child
    else:
        new_node_parent.right = new_node


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


node1 = Node(1)
node2 = Node(2)
node3 = Node(3)

node4 = Node(4)
node5 = Node(5)

# node 4 is the root node
tree = Tree(node4)
tree_insert(tree, node2)
tree_insert(tree, node1)
tree_insert(tree, node3)
tree_insert(tree, node5)


is_valid_bst(node4)


node100 = Node(100)
tree_insert(tree, node100)
node69 = Node(69)
tree_insert(tree, node69)
node124 = Node(124)
tree_insert(tree, node124)
# print(is_valid_bst(node4))


# def get_tree_node_list(node: Node, list: [Node]):
#     """Get list of all tree nodes."""
#     all_nodes = []
#     if (node is not None):
#         left_list = get_tree_node_list(node.left)
#         if left_list is not None:
#             all_nodes
#         right_list = get_tree_node_list(node.right)

# delete testing
all_nodes = [node1, node2, node3, node4, node5, node100, node69, node124]

for node in all_nodes:
    # inorder_tree_walk(tree.root)
    print(f"Deleting {node.key}")
    inorder_tree_walk(tree.root)
    tree_delete(tree, node)
    print(is_valid_bst(node4))
    print("\n")


node10 = Node(10)
node17 = Node(17)
node4 = Node(4)
node21 = Node(21)

tree_minimum(node10)
tree_minimum(node17)
tree_minimum(node4)
tree_minimum(node21)

# found_minimum = tree_minimum_recursive(node4)
# if found_minimum is not None:
#     print(f"min_node_ref: {found_minimum}\n min_node_key: {found_minimum.key}")

# found_maximum = tree_maximum_recursive(node4)
# if found_maximum is not None:
#     print(f"max_node_ref: {found_maximum}\n max_node_key: {found_maximum.key}")

# print("inorder_tree_walk: ")
# inorder_tree_walk(node4)
# print("preorder_tree_walk: ")
# preorder_tree_walk(node4)
# print("postorder_tree_walk: ")
# postorder_tree_walk(node4)
# found_object = tree_search(node4, 2)
# if found_object is not None:
#     print(f"obj_ref: {found_object}\n obj_key: {found_object.key}")

# found_minimum = tree_minimum(node4)
# if found_minimum is not None:
#     print(f"min_node_ref: {found_minimum}\n min_node_key: {found_minimum.key}")

# found_maximum = tree_maximum(node4)
# if found_maximum is not None:
#     print(f"max_node_ref: {found_maximum}\n max_node_key: {found_maximum.key}")
# Is the following valid BST?
#           10
#        /     \
#       4      17
#      / \     / \
#     1   5   16  21
#          \
#           6
