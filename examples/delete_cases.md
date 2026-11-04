# RB deletion fixup: cases 1–4

Each example starts with a valid RB tree and deletes **black leaf 5**, the left
child of 10. Its replacement `x` (`fix_node` in the Python code) is the shared
black NIL sentinel. The deletion assigns NIL's parent so fixup can inspect 10
and the right-hand sibling `w`.

All case handling stays in **`x is x.parent.left`**, using the original
`delete` and `delete_fixup`. No example enters the mirrored branch (cases 5–8).

| Module | Initial case | Complete case trace | Rotations | Final root |
| --- | --- | --- | --- | --- |
| `examples.delete_case1` | Red sibling | **1 → 2** | Left at 10 | 20B |
| `examples.delete_case2` | Black sibling, both children black | **2** | None | 10B |
| `examples.delete_case3` | Black sibling, near child red, far child black | **3 → 4** | Right at 20, left at 10 | 15B |
| `examples.delete_case4` | Black sibling, far child red | **4** | Left at 10 | 20B |

Case 1 changes the situation into another case in the **same loop iteration**;
this fixture then takes case 2. Case 3 changes the situation into case 4, also
within the same iteration. Consequently a valid standalone deletion cannot
execute case 1 alone or case 3 alone. These fixtures all execute exactly one
loop iteration, followed by the exit test and final black assignment.

The diagrams omit black NIL children. `B` means black and `R` means red.

## Case 1: red sibling

```text
       10B
      /   \
     5B   20R
         /   \
        15B  25B
```

After deleting 5, `x` is the left NIL of 10 and `w` is red 20. Case 1 makes
20 black, makes 10 red, and rotates left at 10. The new sibling of `x` is
black 15, whose children are both black NILs. Case 2 makes 15 red and moves
`x` to red 10. The loop stops and the final recoloring makes 10 black.

```text
        20B
       /   \
      10B  25B
         \
         15R
```

## Case 2: black sibling with two black children

```text
       10B
      /   \
     5B   15B
```

After deleting 5, `w` is black 15 with two black NIL children. Case 2 makes
15 red and moves `x` up to 10. Here 10 is the root, so fixup stops. No rotation
is needed, and the final black assignment leaves 10 black.

```text
       10B
          \
          15R
```

The extra black is absorbed at the root. Every root-to-NIL path has one fewer
real black node than before deletion, but all such paths still have equal
black counts, as required by property 5.

## Case 3: near red child, far black child

```text
       10B
      /   \
     5B   20B
         /
        15R
```

For a right-hand sibling, its **near child is its left child** and its **far
child is its right child**. Here the near child is red 15 and the far child
is black NIL. Case 3 makes 15 black, makes 20 red, and rotates right at 20.
The new sibling is black 15 with far red child 20, which is case 4. Case 4
recolors and rotates left at 10, then sets `x` to the root to terminate.

```text
       15B
      /   \
     10B  20B
```

## Case 4: far red child

```text
       10B
      /   \
     5B   20B
             \
             25R
```

After deleting 5, the black sibling 20 already has a far red child, 25. Case 4
runs directly: the sibling takes its parent's color, parent 10 becomes black,
far child 25 becomes black, and a left rotation at 10 finishes the repair.
Assigning `x = tree.root` ends the loop.

```text
       20B
      /   \
     10B  25B
```

## Debugging

In **VS Code**, choose an **RB deletion case 1–4: ...** launch configuration and
press F5. In **Emacs**, run `M-x rb-visualizer-debug-example` and choose
`examples.delete_case1`, `examples.delete_case2`, `examples.delete_case3`, or
`examples.delete_case4`. Opening an example and running
`M-x rb-visualizer-debug` also works.

1. Break at `delete(tree, delete_node)` in the example and continue there to
   inspect the valid starting tree. Step Into enters the original algorithm
   directly, skipping the visualization wrapper.
2. In `delete`, observe that `y_original_color` is BLACK and `fix_node` is NIL.
   Step Into the `delete_fixup(tree, fix_node)` call.
3. At the loop guard, `x` is black, is not the root, and is its parent's left
   child. In the browser, its specific NIL slot is labeled **fix_node**, even
   with other NIL leaves hidden. Focus mode emphasizes the parent, sibling,
   and real near/far children. **Show NIL leaves** reveals the other black NIL
   children when comparing cases 2 and 3.
4. Step through the selected case(s). The following first statements make
   useful breakpoints in the left-child branch of `delete_fixup`:

| Case | First executed statement in its body |
| --- | --- |
| 1 | `sibling.color = Color.BLACK` |
| 2 | `sibling.color = Color.RED` |
| 3 | `sibling.left.color = Color.BLACK` |
| 4 | `sibling.color = fix_node.parent.color` |

5. Inspect `finished = True` in the driver. The final rooted tree is valid,
   and removed 5 remains separately inspectable. Its stale parent reference
   does not produce an amber warning while the instrumented deletion runs.

For Emacs, use `dap-step-in`, `dap-next`, `dap-step-out`, and `dap-continue`.
The standard subtree-folding, pinning, NIL-view, and camera policies apply.
The fixtures and visualization setup are outside the algorithm source.

Run from the repository root:

```sh
.venv/bin/python -m examples.delete_case1
.venv/bin/python -m examples.delete_case2
.venv/bin/python -m examples.delete_case3
.venv/bin/python -m examples.delete_case4
```

Verification traces the original code, checks each case's preconditions and
exact rotation sequence, rejects every line in the mirrored branch, and
validates ordering, pointers, root color, red-red edges, and black path counts.
The NIL extra black is counted only at the active child slot, not at every
occurrence of the shared sentinel.

```sh
.venv/bin/python -m unittest examples.tests.test_delete_cases -v
.venv/bin/python -m visualizer.tests.delete_cases_debug_adapter_smoke
```
