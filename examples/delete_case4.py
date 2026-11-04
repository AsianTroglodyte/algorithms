"""Delete black 5: left-child case 4 (far red child) directly. No mirrors."""

from examples._delete_cases import make_tree
from red_black_trees import Color, Node, delete as rb_delete
from visualizer.runtime import install_tracking, register_tree, with_deletion_cleanup


def main():
    install_tracking(Node)
    delete = with_deletion_cleanup(rb_delete)
    tree, delete_node = make_tree(4)
    register_tree(tree)

    # Break here. Sibling 20 is black and its far child 25 is red.
    # Case 4 recolors and rotates left at 10, then moves x to root 20.
    delete(tree, delete_node)

    assert tree.root.key == 20 and tree.root.color is Color.BLACK
    assert tree.root.right.key == 25 and tree.root.right.color is Color.BLACK
    finished = True


if __name__ == '__main__':
    main()
