# Tree examples

The [BST lessons](bst.md) cover **tree minimum → insertion → transplant →
deletion**, in that order. They use `binary_tree.py` and share the RB browser's
focus, folding, pinning, and camera controls. VS Code has four ordered **BST**
launch configurations; Emacs's example picker lists the four modules.

The [case-1 insertion lesson](insert_case1.md) contains three examples where
case 1 executes exactly three times, stopping at an internal black parent,
the black root, or black NIL. It includes debugger launch instructions, the
exact recoloring trace, a loop-invariant proof, and teaching prompts. The
modules are `examples.insert_case1_internal`, `examples.insert_case1_root`,
and `examples.insert_case1_nil`.

Run examples as modules from the repository root so both the tree implementation
and visualizer package are importable:

```sh
.venv/bin/python -m examples.visualizer_demo
```

`visualizer_demo.py` demonstrates insertions, rotations, deletion, and detached
nodes. To watch the tree at each
pause, use **Red-black Tree: Debug Demo** in VS Code. In Emacs, open the Python
file and run `M-x rb-visualizer-debug`, or use `M-x rb-visualizer-debug-example`
to choose an example from any buffer. See the
[visualizer guide](../visualizer/README.md) for setup and stepping controls.
The guide also records the existing deletion error that currently interrupts
the demo.
The three case-1 examples use insertion only and do not encounter that error.

Add new examples here as ordinary Python scripts. For debugger visualization,
install tracking before constructing nodes and register the tree to display:

```python
from red_black_trees import Node, Tree, insert
from visualizer.runtime import install_tracking, register_tree

install_tracking(Node)
tree = Tree()
register_tree(tree)

node = Node(10)
insert(tree, node)
```

For a file named `examples/insertion_cases.py`, run
`.venv/bin/python -m examples.insertion_cases`. In VS Code, copy the configuration
in `.vscode/launch.json`, set `"module": "examples.insertion_cases"`, and keep
`"rbVisualizer": true` to use the browser companion.
