"""Debug this ordinary sequence through M-x rb-visualizer-debug."""

from red_black_trees import Node, Tree, delete, insert
from visualizer.runtime import install_tracking, register_tree

install_tracking(Node)
tree = Tree()
register_tree(tree)

# Put a breakpoint here, then step into insert/fixup/rotations.
first = Node(30)
insert(tree, first)
second = Node(20)
insert(tree, second)
third = Node(10)
insert(tree, third)  # Right rotation: 20 replaces 30 at the root.
fourth = Node(25)
insert(tree, fourth)
fifth = Node(28)
insert(tree, fifth)  # Inner and outer rotations.

delete(tree, second)  # `second` stays visible as a detached, live node.
del second  # Once debugger references are released, it can disappear.
delete(tree, third)
del third

# Break here to examine the final tree before continuing to session end.
finished = True
