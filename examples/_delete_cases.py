"""Valid small RB trees for deletion fixup's left-child cases 1 through 4."""

from red_black_trees import Color, Node, Tree

EXPECTED_CASES = {1: (1, 2), 2: (2,), 3: (3, 4), 4: (4,)}
EXPECTED_ROOTS = {1: 20, 2: 10, 3: 15, 4: 20}


def make_tree(case):
    """Return (tree, black leaf to delete). All examples delete the left 5."""
    black, red = Color.BLACK, Color.RED
    if case == 1:
        #        10B             Red sibling: case 1 -> case 2.
        #       /   \
        #      5B   20R
        #          /   \
        #         15B  25B
        records = [(10, black, 5, 20), (5, black, None, None),
                   (20, red, 15, 25), (15, black, None, None), (25, black, None, None)]
    elif case == 2:
        #        10B             Black sibling, two black children: case 2.
        #       /   \
        #      5B   15B
        records = [(10, black, 5, 15), (5, black, None, None), (15, black, None, None)]
    elif case == 3:
        #        10B             Near red child, far black child: case 3 -> 4.
        #       /   \
        #      5B   20B
        #          /
        #         15R
        records = [(10, black, 5, 20), (5, black, None, None),
                   (20, black, 15, None), (15, red, None, None)]
    elif case == 4:
        #        10B             Far red child: case 4 directly.
        #       /   \
        #      5B   20B
        #              \
        #              25R
        records = [(10, black, 5, 20), (5, black, None, None),
                   (20, black, None, 25), (25, red, None, None)]
    else:
        raise ValueError(f'Expected deletion case 1, 2, 3, or 4; got {case}')

    tree = Tree()
    nodes = {key: Node(key) for key, *_ in records}
    for key, color, left, right in records:
        node = nodes[key]
        node.color, node.parent = color, tree.nil
        node.left = tree.nil if left is None else nodes[left]
        node.right = tree.nil if right is None else nodes[right]
    for node in nodes.values():
        for child in (node.left, node.right):
            if child is not tree.nil:
                child.parent = node
    tree.root = nodes[10]
    return tree, nodes[5]
