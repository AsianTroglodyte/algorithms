"""Intentional uncaught exception for the DAP integration check."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from red_black_trees import Node, Tree, insert
from visualizer.runtime import install_tracking, register_tree

install_tracking(Node)
tree = Tree()
register_tree(tree)
node = alias = Node(42)
insert(tree, node)
raise RuntimeError('Intentional visualizer test exception')
