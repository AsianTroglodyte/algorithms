"""A balanced starting BST so debugger lessons show only the chosen operation."""

from binary_tree import Node, Tree


def make_tree():
    tree = Tree()
    nodes = {}

    def branch(lo, hi, parent):
        if lo > hi:
            return None
        key = (lo + hi) // 2
        node = nodes[key] = Node(key)
        node.parent = parent
        node.left = branch(lo, key - 1, node)
        node.right = branch(key + 1, hi, node)
        return node

    tree.root = branch(1, 31, None)
    return tree, nodes
