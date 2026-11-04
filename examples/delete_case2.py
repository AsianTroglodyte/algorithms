"""Delete black 5: left-child case 2 only. No symmetric case."""

from examples._delete_cases import make_tree
from red_black_trees import Color, Node, delete as rb_delete
from visualizer.runtime import install_tracking, register_tree, with_deletion_cleanup


def main():
    install_tracking(Node)
    delete = with_deletion_cleanup(rb_delete)
    tree, delete_node = make_tree(2)
    register_tree(tree)

    # Break here. x is the left NIL of 10; sibling 15 and both its children
    # are black. Case 2 makes 15 red and moves x to root 10. No rotations.
    delete(tree, delete_node)

    assert tree.root.key == 10 and tree.root.color is Color.BLACK
    assert tree.root.right.key == 15 and tree.root.right.color is Color.RED
    finished = True


if __name__ == '__main__':
    main()
