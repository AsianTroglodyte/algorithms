# Deletion: two repairs with zero loop iterations

These two examples use the actual `delete` and `delete_fixup` functions in
`red_black_trees.py`. Both start with valid RB trees, remove a black node with
one red child, and execute **none of fixup's cases 1–4**. The final assignment
`fix_node.color = Color.BLACK` performs the repair.

| Problem | Module | Delete | Replacement `fix_node` | Final root |
| --- | --- | --- | --- | --- |
| 1. Red root (property 2) | `examples.delete_red_root` | Black root 10 | Red 5, now the root | Black 5 |
| 2. Red child and parent (property 4) | `examples.delete_red_parent` | Black 5 | Red 2 below red parent 10 | Black 20, unchanged |

`B` and `R` indicate black and red. All omitted children are the shared black
NIL sentinel. The starting trees are built directly in
`_delete_final_recolor.py`, so setup does not run any insertion fixups.

## Problem 1: a red child becomes the root

Before deletion:

```text
     10B  ← delete_node
     /
    5R    ← replacement
```

`delete` replaces 10 with 5 and sets 5's parent to NIL. Immediately before
fixup's final recoloring:

```text
    5R    ← tree.root and fix_node
```

The removed node `y` was black, so `y_original_color` is BLACK and `delete`
calls fixup. The first part of its guard, `fix_node is not tree.root`, is false.
The loop is skipped. The final assignment makes 5 black, restoring property 2.
It also restores the black contribution of the old root. There is no red-red
edge and no rotation; the entire reachable tree is the replacement node.

## Problem 2: a red child replaces a black node below a red parent

Before deletion:

```text
            20B
           /   \
         10R   30B
        /   \
       5B   15B
      /
     2R
```

This tree satisfies all RB properties, including equal black counts. Delete
black 5. After the structural change and before the final recoloring:

```text
            20B
           /   \
         10R   30B
        /   \
       2R   15B
       ↑
    fix_node
```

Again `y_original_color` is BLACK, so fixup is called. Here `fix_node` is not
the root, but `fix_node.color == BLACK` is false. The loop is skipped. The
final assignment turns 2 black. Parent 10 stays red and root 20 stays black.
The red-red edge 10 → 2 disappears, restoring property 4.

Paths through 2 have also lost one black node during structural deletion.
Thinking of that missing contribution as an extra black on `fix_node` keeps
the usual fixup accounting consistent. Recoloring 2 black supplies that
contribution in its actual color, restoring property 5. Before that assignment,
ordinary color counts on those paths are one short; the tree is not yet a
valid RB tree merely because the loop guard is false.

## Debugger walkthrough

In **VS Code**, select **Deletion problem 1: red root (zero loop cases)** or
**Deletion problem 2: red parent (zero loop cases)** in Run and Debug and press
F5. In **Emacs**, run `M-x rb-visualizer-debug-example` and choose
`examples.delete_red_root` or `examples.delete_red_parent`; opening the file
and running `M-x rb-visualizer-debug` also works.

Set these breakpoints:

1. `delete(tree, delete_node)` in the selected example. Continue here to skip
   fixture construction and inspect the valid starting tree.
2. The `while fix_node is not tree.root ...` line in `delete_fixup`. Continue
   here to inspect the structure after deletion and confirm that `fix_node`
   is red. In problem 1 it is the root; in problem 2 its parent is red.
3. The final `fix_node.color = Color.BLACK` line. One Step Over from the guard
   should land directly here. A breakpoint anywhere in cases 1–4 will not hit.
   At this point the color change has **not** executed yet.
4. `finished = True` in the example. Step over the final recoloring, then
   continue here to inspect the repaired tree and detached removed node.

Inside `delete`, inspect `y_original_color` just before `delete_fixup` is
called: it is BLACK in both examples. Inside fixup, inspect `fix_node`,
`fix_node.parent`, and `tree.root`. The root example's parent points to NIL;
**Show NIL leaves → NIL view → Shared sentinel** can show that pointer.

Emacs keyboard commands: `dap-continue`, `dap-next`, `dap-step-in`, and
`dap-step-out`. The debugger launch rules skip visualization instrumentation:
Step Into on the example's deletion call enters `delete` directly, and Step
Into on `delete_fixup(tree, fix_node)` enters fixup directly. Reload the Emacs
bridge after updating it and start a fresh debug session to use those rules.

The driver uses `with_deletion_cleanup` outside the algorithm source. While
fixup is running, the removed node can still have stale pointers into the
reachable tree. Those arrows and their secondary warnings are hidden from the
diagram so the rooted tree stays clear; hover over the detached node to inspect
its actual left, right, and parent pointers. The Python objects are unchanged.
After a successful deletion returns, the wrapper clears the removed node's
links and it remains inspectable under **Detached · still live**. The cleanup
does not perform either color repair.

Run without a debugger from the repository root:

```sh
.venv/bin/python -m examples.delete_red_root
.venv/bin/python -m examples.delete_red_parent
```

Both examples are quiet and assert the expected result. Automated checks trace
the original functions, verify the black-color decision, reject rotations,
require precisely the guard and final recoloring line to execute in fixup,
and check ordering, pointers, red-red edges, and black path counts:

```sh
.venv/bin/python -m unittest examples.tests.test_delete_final_recolor -v
.venv/bin/python -m visualizer.tests.delete_final_recolor_debug_adapter_smoke
```
