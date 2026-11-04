"""Case 1 three times; stop at black parent 22 below root 30.

Run: python -m examples.insert_case1_internal
See insert_case1.md for the trace, invariants, and debugger walkthrough.
"""

from red_black_trees import Node, insert
from visualizer.runtime import install_tracking, register_tree
from examples._case1 import make_tree


def main():
    install_tracking(Node)
    tree = make_tree("internal")
    register_tree(tree)
    new_node = Node(0)

    # Break here. Step into insert, then into insert_fixup.
    # fix_node: 0 -> 2 -> 6 -> 14. Parent 22 is black and is NOT root 30.
    insert(tree, new_node)

    # Break here to inspect the repaired tree. No rotations were needed.
    finished = True


if __name__ == "__main__":
    main()
