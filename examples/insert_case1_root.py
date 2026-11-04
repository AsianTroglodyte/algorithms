"""Case 1 three times; stop at black parent 22, which is the root.

Run: python -m examples.insert_case1_root
See insert_case1.md for the trace, invariants, and debugger walkthrough.
"""

from red_black_trees import Node, insert
from visualizer.runtime import install_tracking, register_tree
from examples._case1 import make_tree


def main():
    install_tracking(Node)
    tree = make_tree("root")
    register_tree(tree)
    new_node = Node(0)

    # Break here. Step into insert, then into insert_fixup.
    # fix_node: 0 -> 2 -> 6 -> 14. Parent 22 is the black root.
    insert(tree, new_node)

    # Break here. fix_node stopped BELOW the root; the root stayed black.
    finished = True


if __name__ == "__main__":
    main()
