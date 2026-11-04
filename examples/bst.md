# BST debugger lessons

These use `binary_tree.py` and the same browser companion as the RB tree.
Work through them in this order:

| Lesson | Example module | Break at | What to follow |
| --- | --- | --- | --- |
| 1. Tree minimum | `examples.bst_minimum` | `minimum = tree_minimum(tree.root)` | `node` follows 16 → 8 → 4 → 2 → 1. |
| 2. Insertion | `examples.bst_insertion` | `tree_insert(tree, new_node)` | Search cursor, insertion parent, and the None slot replaced by 0. |
| 3. Transplant | `examples.bst_transplant` | `transplant(tree, old_root, replacement)` | Parent 30 changes its right child from 31 to 32. |
| 4. Deletion | `examples.bst_deletion` | `delete(tree, node_to_delete)` | Minimum and transplant cooperate to replace root 16 with successor 17. |

In **VS Code**, open the repository root and select the corresponding
**BST 1: Tree minimum**, **BST 2: Insertion**, **BST 3: Transplant**, or
**BST 4: Deletion** launch configuration, then press F5. Put a breakpoint on
the operation call above and continue to it. Use F11 to step into the algorithm,
F10 to step over a line, and Shift+F11 to return to its caller. The existing
local extension and Microsoft Python Debugger are required; the RB launch
instructions in the [visualizer guide](../visualizer/README.md) install them.

In **Emacs**, run `M-x rb-visualizer-debug-example` and choose the example
module. Alternatively, open its Python file and run `M-x rb-visualizer-debug`.
The same keyboard commands apply: `dap-breakpoint-toggle`, `dap-continue`,
`dap-step-in`, `dap-next`, and `dap-step-out`.

The initial **Waiting** state is normal before `register_tree(tree)` runs.
Choose **View → Focus mode** in the browser. Full tree, subtree summaries,
click-to-expand, click-to-pin, Reset focus, pan/zoom, and Fit to view work as
they do for RB trees. The camera follows the active operation, and unrelated
branches fold immediately. Minimum focuses on the cursor and its next left
child; insertion on the cursor, new node, and parent; transplant and deletion
on their target, replacement/successor, and relevant parents.

BST nodes have a plain blue fill and a BST label. **Show None links** displays
empty child pointers at their leaf positions. BSTs have no shared sentinel or
red/black color, so the shared-NIL selector does not apply. A minimum lookup on
an empty subtree returns None. The header and notice identify an empty BST.

Snapshots show actual pointers at every pause. Insertion and transplant can
temporarily produce a parent/child warning between assignments; the affected
nodes stay visible. Cycles and shared children show the full graph, following
the RB policy. `transplant` changes the tree's attachment and the replacement's
parent; it leaves the removed root's own links for its caller to handle. The
transplant lesson explicitly clears the old leaf's parent afterward. The
deletion driver wraps `tree_delete` with `with_deletion_cleanup`: after the
algorithm returns successfully, that visualization-only wrapper clears all
three links on the removed node. It remains visible as detached while a local
or debugger reference keeps it alive. The algorithm source has no display
cleanup, and unwrapped calls leave the removed node's own links alone.

Run the examples without a debugger from the repository root:

```sh
.venv/bin/python -m examples.bst_minimum
.venv/bin/python -m examples.bst_insertion
.venv/bin/python -m examples.bst_transplant
.venv/bin/python -m examples.bst_deletion
```

For your own examples:

```python
from binary_tree import Node, Tree, tree_minimum, tree_insert, transplant, tree_delete
from visualizer.runtime import install_tracking, register_tree, with_deletion_cleanup

install_tracking(Node)
delete = with_deletion_cleanup(tree_delete)
tree = Tree()
register_tree(tree)
new_node = Node(10)
tree_insert(tree, new_node)
minimum = tree_minimum(tree.root)
delete(tree, new_node)
```

Use one registered tree and one Node class per debug session. RB and BST
examples run in separate sessions using the same bridge and server.

Focused algorithm and snapshot checks:

```sh
.venv/bin/python -m unittest test_binary_tree visualizer.tests.test_bst_visualizer -v
```
