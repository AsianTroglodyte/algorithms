# Tree examples

The [RB deletion cases 1–4](delete_cases.md) have four small examples, all in
the left-child branch: **1 → 2**, **2**, **3 → 4**, and **4**. None runs the
mirrored cases 5–8. Select **RB deletion case 1–4: ...** in VS Code or choose
`examples.delete_case1` through `examples.delete_case4` in Emacs.

The [deletion final-recoloring lessons](delete_final_recolor.md) demonstrate
your two deletion problems: a red replacement becoming the root (property 2),
and a red replacement below a red parent (property 4). Both skip the fixup loop
and are repaired by its final `fix_node.color = Color.BLACK`. Run
`examples.delete_red_root` and `examples.delete_red_parent`, or use the two
**Deletion problem ...** debugger launch configurations.

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

For deletion examples, keep display cleanup in the driver rather than in the
algorithm: import `with_deletion_cleanup` from `visualizer.runtime`, then use
`delete = with_deletion_cleanup(delete)` (or wrap BST's `tree_delete`). This
clears the removed node's links after a successful return on the registered
tree so it can be displayed as detached. Plain algorithm calls are unchanged.
