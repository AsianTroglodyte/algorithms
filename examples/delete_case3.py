"""Delete black 5: left-child case 3 (near red child), then case 4. No mirrors."""

from examples._delete_cases import make_tree
from red_black_trees import Color, Node, delete as rb_delete
from visualizer.runtime import install_tracking, register_tree, with_deletion_cleanup


def main():
    install_tracking(Node)
    delete = with_deletion_cleanup(rb_delete)
    tree, delete_node = make_tree(3)
    register_tree(tree)

    # Break here. Sibling 20 is black, near child 15 red, far child NIL black.
    # Case 3 rotates right at 20. Case 4 then rotates left at 10.
    # New root: 15B, with black children 10 and 20.
    delete(tree, delete_node)

    assert tree.root.key == 15 and tree.root.color is Color.BLACK
    finished = True


if __name__ == '__main__':
    main()
