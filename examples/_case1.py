"""Valid starting trees for three consecutive case-1 recolorings.

Build fixtures directly so the debugger demonstration contains only the final
insertion. The keys along the propagation path are 0 -> 2 -> 6 -> 14.
No tree operation is patched or replaced.
"""

from red_black_trees import Color, Node, Tree


def make_tree(stopping_parent):
    """Return a valid RB tree; inserting 0 runs case 1 exactly three times.

    stopping_parent is "internal", "root", or "nil". The fixtures contain
    45, 29, and 21 nodes respectively, numbered in inorder starting at 1.
    """
    if stopping_parent not in {"internal", "root", "nil"}:
        raise ValueError(f"Unknown stopping parent: {stopping_parent}")
    tree = Tree()

    def node(color, left=None, right=None):
        result = Node(None)  # Assign ordered keys after building the shape.
        result.color = color
        result.left = tree.nil if left is None else left
        result.right = tree.nil if right is None else right
        result.parent = tree.nil
        for child in (result.left, result.right):
            if child is not tree.nil:
                child.parent = result
        return result

    def black_subtree(levels):
        if levels == 0:
            return tree.nil
        return node(Color.BLACK, black_subtree(levels - 1),
                    black_subtree(levels - 1))

    def cascade(levels):
        # Each black grandparent has a red parent and red uncle. Along the
        # left spine, the next cascade has the same black height as its sibling.
        if levels == 1:
            return node(Color.BLACK, node(Color.RED), node(Color.RED))
        parent = node(Color.RED, cascade(levels - 1), black_subtree(levels - 1))
        uncle = node(Color.RED, black_subtree(levels - 1), black_subtree(levels - 1))
        return node(Color.BLACK, parent, uncle)

    top = cascade(3)
    if stopping_parent in {"root", "internal"}:
        top = node(Color.BLACK, top, black_subtree(3))
    if stopping_parent == "internal":
        top = node(Color.BLACK, top, black_subtree(4))
    tree.root = top

    def number_inorder(current, key):
        if current is tree.nil:
            return key
        key = number_inorder(current.left, key)
        current.key = key
        return number_inorder(current.right, key + 1)

    number_inorder(tree.root, 1)
    return tree
