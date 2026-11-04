"""Case 1 three times; fix_node becomes root 14 and its parent is NIL.

Run: python -m examples.insert_case1_nil
See insert_case1.md for the trace, invariants, and debugger walkthrough.
"""

from red_black_trees import Node, insert
from visualizer.runtime import install_tracking, register_tree
from examples._case1 import make_tree


def main():
    install_tracking(Node)
    tree = make_tree("nil")
    register_tree(tree)
    new_node = Node(0)

    # Break here. Step into insert, then into insert_fixup.
    # fix_node: 0 -> 2 -> 6 -> 14. The root becomes red after case 1 #3.
    insert(tree, new_node)

    # Break here. The black NIL parent ended the loop; the final assignment
    # tree.root.color = Color.BLACK repaired the red root.
    finished = True


if __name__ == "__main__":
    main()
