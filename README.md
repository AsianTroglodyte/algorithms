# Red-black trees

Python red-black and binary search tree implementations with a shared browser
companion for stepping through actual pointer state from Emacs or VS Code.

## Project layout

```text
red_black_trees.py           Tree implementation
binary_tree.py               Binary tree implementation
examples/                   Runnable examples
visualizer/
  runtime.py                Node tracking and snapshots
  server.py                 Local HTTP server
  static/                   Browser interface and bundled layout library
  emacs/                    dap-mode bridge
  vscode/                   VS Code extension
  scripts/                  Extension packaging
  tests/                    Visualizer unit and integration checks
  requirements.txt          Debugger dependency
  README.md                 Setup, controls, architecture, and verification
test_red_black_trees.py      Tree correctness checks
test_time_complexity.py      Complexity checks
presentation/               Presentation material
figures/                    Presentation figures
```

See the [visualizer guide](visualizer/README.md) for Emacs and VS Code setup,
and the [examples guide](examples/README.md) for running or adding examples.
Open this repository root in your editor.

The [BST lessons](examples/bst.md) cover minimum, insertion, transplant, and
deletion, in that order, using the same presentation, subtree folding, and
camera policies. BSTs use None links and plain nodes; RB trees use their
shared black NIL sentinel and actual node colors.

## Tree representation

Each `Tree` owns one black sentinel, `tree.nil`, following CLRS. An empty
tree has `tree.root is tree.nil`. In an inserted node, every missing child
points to that same sentinel, and the root's parent is also `tree.nil`.
`Node(key)` creates an unlinked node; `insert(tree, node)` installs its NIL
children and parent before insertion fix-up.

Insertion fix-up therefore needs only:

```python
while fix_node.parent.color == Color.RED:
```

The root's parent is black, so reaching the root ends the loop. Uncle and
sibling colors can also be read directly. Deletion uses the CLRS root/black
loop condition and updates NIL's parent when it replaces a subtree; NIL's
left and right links continue to point to itself. The sentinel is shared
within one tree. Separate trees have separate sentinels.

The helpers use explicit tree arguments, including `tree_minimum(tree, node)`.
The visualizer's deletion drivers use `with_deletion_cleanup` to clear a
removed node's links after a successful deletion, so a live reference can be
inspected separately. This display cleanup lives outside the algorithms;
ordinary deletion calls leave the removed node's own links alone.

## Checks

```sh
.venv/bin/python -m unittest discover -v
```

The [visualizer guide](visualizer/README.md#verification-and-limitations) also
lists the debugger and browser integration checks.
