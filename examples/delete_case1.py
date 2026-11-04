"""Delete black 5: left-child case 1 (red sibling), then case 2. No mirrors."""

from examples._delete_cases import make_tree
from red_black_trees import Color, Node, delete as rb_delete
from visualizer.runtime import install_tracking, register_tree, with_deletion_cleanup


def main():
    install_tracking(Node)
    delete = with_deletion_cleanup(rb_delete)
    tree, delete_node = make_tree(1)
    register_tree(tree)

    # Break here. x becomes the left NIL of 10; its sibling is red 20.
    # Case 1 rotates left at 10; case 2 then moves x to red 10.
    # The final recoloring makes 10 black. New root: 20B.
    delete(tree, delete_node)

    assert tree.root.key == 20 and tree.root.color is Color.BLACK
    finished = True


if __name__ == '__main__':
    main()
