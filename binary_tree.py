import types


class Node:
    """Binary Search Tree Node."""

    def __init__(self,
                 key,
                 left_node=None,
                 right_node=None,
                 parent_node=None):
        """Initialize the values of the node."""
        self.left: Node = None
        self.right: Node = None
        self.parent: Node = None
        self.key: int = key


node1 = Node(1)
node2 = Node(2)
node3 = Node(3)

node4 = Node(4)
node5 = Node(5)

node4.left = node2
node2.left = node1
node2.right = node3

node4.right = node5


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


def tree_search(node: Node, key: int) -> None:
    """Search a binary search tree and return the node if it is found."""
    if node is None or key == node.key:
        return node
    if key < node.key:
        return tree_search(node.left, key)
    else:
        return tree_search(node.right, key)


def tree_minimum(node: Node) -> None:
    """Search a binary search tree to find the minimum value."""
    while node.left is not None:
        node = node.left
    return node


def tree_maximum(node: Node) -> Node:
    """Search a binary search tree to find the minimum value."""
    while node.right is not None:
        node = node.right
    return node


def tree_successor(node: Node):
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


print("inorder_tree_walk: ")
inorder_tree_walk(node4)
print("preorder_tree_walk: ")
preorder_tree_walk(node4)
print("postorder_tree_walk: ")
postorder_tree_walk(node4)
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
