"""Valid RB trees whose black deletion needs only fixup's final recoloring."""

from red_black_trees import Color, Node, Tree


def make_tree(problem):
    """Return (tree, delete_node, replacement) without running setup insertions."""
    if problem == 'red_root':
        #        10B          Delete 10: 5R becomes the root.
        #        /
        #       5R
        records = [(10, Color.BLACK, 5, None), (5, Color.RED, None, None)]
        root_key, delete_key, replacement_key = 10, 10, 5
    elif problem == 'red_parent':
        #          20B        Delete 5: 2R replaces it below red parent 10.
        #         /   \
        #       10R   30B
        #      /   \
        #     5B   15B
        #    /
        #   2R
        records = [(20, Color.BLACK, 10, 30), (10, Color.RED, 5, 15),
                   (30, Color.BLACK, None, None), (5, Color.BLACK, 2, None),
                   (15, Color.BLACK, None, None), (2, Color.RED, None, None)]
        root_key, delete_key, replacement_key = 20, 5, 2
    else:
        raise ValueError(f'Unknown deletion problem: {problem}')
    tree = Tree()
    nodes = {key: Node(key) for key, *_ in records}
    for key, color, left, right in records:
        node = nodes[key]
        node.color = color
        node.parent = tree.nil
        node.left = nodes[left] if left is not None else tree.nil
        node.right = nodes[right] if right is not None else tree.nil
    for node in nodes.values():
        for child in (node.left, node.right):
            if child is not tree.nil:
                child.parent = node
    tree.root = nodes[root_key]
    return tree, nodes[delete_key], nodes[replacement_key]
