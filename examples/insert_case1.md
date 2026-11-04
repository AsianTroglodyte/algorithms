# Three case-1 recolorings, three stopping parents

All three examples insert **0** into an already valid red-black tree. They use
the actual `insert()` and `insert_fixup()` functions in `red_black_trees.py`.
Each insertion executes **case 1 exactly three times**, with no case 2, case 3,
or rotations. The starting fixtures are built directly in `_case1.py`; building
them is preparation, rather than part of the insertion being demonstrated.

| Example module | Starting root | Starting nodes | Final `fix_node` | Its stopping parent |
| --- | ---: | ---: | ---: | --- |
| `examples.insert_case1_internal` | 30 | 45 | 14 | 22, black, below the root |
| `examples.insert_case1_root` | 22 | 29 | 14 | 22, the black root |
| `examples.insert_case1_nil` | 14 | 21 | 14 | The black NIL sentinel |

The first example needs more supporting nodes to keep every starting path's
black height equal. Those subtrees are essential even though they never change
during this insertion. Each fixture numbers its existing nodes in sorted order,
so the interesting keys match across examples.

## Debugger walkthrough

In **VS Code**, select one of the three **Case 1 three times: ...** configurations
in Run and Debug, then press `F5`. These use the same browser companion as the
original demo; the **Debug Demo** command continues to launch the original demo.

In **Emacs**, load `visualizer/emacs/rb-visualizer.el`, open the example's Python
file, and run `M-x rb-visualizer-debug RET`. To choose an example from any buffer,
use `M-x rb-visualizer-debug-example RET` and select its module.
Programmatically, `(rb-visualizer-debug-example "examples.insert_case1_nil")`
also works.

1. Open the selected example and set a breakpoint on `insert(tree, new_node)`.
   Continue there to skip fixture construction. The browser now shows the valid
   starting tree. `new_node` is still unlinked and red.
2. Step into `insert`, then step over its search/linking code until the call to
   `insert_fixup`. Observe that the newly attached red 0 has a red parent, 1.
3. Step into `insert_fixup`. At each evaluation of the `while` condition, inspect
   `fix_node` and `fix_node.parent`. Step through the red-uncle branch and watch
   the three color assignments, followed by `fix_node = grandparent`.
4. After the third recoloring, inspect the black parent that makes the loop
   condition false. In the NIL example, enable **Show NIL leaves → NIL view →
   Shared sentinel** to see the root's parent pointer converge on NIL.
5. Step over `tree.root.color = Color.BLACK`, then stop on `finished = True` in
   the example to inspect the final tree. Continue only when finished discussing
   it; the server keeps the final paused graph after the session ends.

Keyboard stepping in Emacs: `dap-step-in`, `dap-next`, `dap-step-out`, and
`dap-continue`; `dap-hydra` provides a menu for these commands.

To run without a debugger/browser, from the repository root:

```sh
.venv/bin/python -m examples.insert_case1_internal
.venv/bin/python -m examples.insert_case1_root
.venv/bin/python -m examples.insert_case1_nil
```

These scripts are deliberately quiet; the teaching trace below describes the
real iterations, which are also checked by the automated tests.

## The shared recoloring trace

At each loop entry, `fix_node` is red, its parent is red, its grandparent is
black, and its uncle is red:

| Iteration | `fix_node` | Red parent | Black grandparent | Red uncle | Case 1 result |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 0 | 1 | 2 | 3 | 1 and 3 become black; 2 becomes red; `fix_node = 2` |
| 2 | 2 | 4 | 6 | 8 | 4 and 8 become black; 6 becomes red; `fix_node = 6` |
| 3 | 6 | 10 | 14 | 18 | 10 and 18 become black; 14 becomes red; `fix_node = 14` |

After iteration 1, the red-red edge is **4 → 2**. After iteration 2, it is
**10 → 6**. Case 1 repairs the old edge but can create a new one two levels up.
After iteration 3, parent 22 is black in the first two examples, so there is no
red-red edge left. In the third example, 14 is the root: there is no red-red
edge left, but the root is temporarily red.

This distinction matters: **propagation can create a new violation, but need
not do so**. Recoloring a grandparent red creates a red-red violation only if
that grandparent has a red parent. Recoloring the root red instead violates the
black-root property (property 2), not the red-parent property (property 4).

## Loop invariant and correctness

State the invariant at the **loop condition**, rather than after each individual
assignment. Intermediate statements may temporarily break other properties.
For these examples, at each condition evaluation:

1. `fix_node` is a red real node.
2. BST order, NIL colors, parent/child links, and equal black heights hold.
3. The only possible RB violation is either a red root at `fix_node`, or a
   red-red edge joining `fix_node` to its parent. There is at most one such
   violation, and these alternatives cannot occur together.

**Initialization.** Inserting a red node at a former NIL position preserves
black heights: the new red node contributes no extra black node to any path.
Its NIL children are black. Here the existing root remains black and only the
new node's red parent can cause a violation.

**Maintenance through case 1.** Before recoloring, the black grandparent and
the chosen red child contribute one black node to each path through that
grandparent's subtree. Afterwards, the grandparent is red and both its children
are black: every such path still gets exactly one black node from these two
levels. Shapes and keys do not change. The old red-red edge is repaired, and
recoloring the parent and uncle black creates no violation below them. The only
possible new violation is at the grandparent, so assigning it to `fix_node`
restores the invariant at the next condition evaluation. If the parent is red
at a loop entry, the invariant also implies that the grandparent exists and is
black, which makes these recolorings valid.

**Termination.** After each case-1 iteration, `fix_node` moves to its grandparent,
exactly **two edges closer to the root**. Its nonnegative depth decreases, so
case 1 cannot repeat indefinitely. The three examples have these depths at
the four condition evaluations:

| Stopping parent | Depths of `fix_node` |
| --- | --- |
| Internal black node | 8 → 6 → 4 → 2 |
| Black root | 7 → 5 → 3 → 1 |
| Black NIL | 6 → 4 → 2 → 0 |

The loop stops whenever the parent is black; that parent need not be the root
or NIL. In the NIL example, **`fix_node` becomes the root, never NIL**. Its
parent is the black sentinel, so the same condition terminates without a
special root check.

**Postcondition.** The black parent at loop exit rules out the red-red edge.
The invariant leaves only the possibility of a red root. The final
`tree.root.color = Color.BLACK` removes that possibility. This assignment is
redundant in the first two examples; in the NIL example it changes the root's
color and adds one black node to **every** root-to-NIL path equally. All RB
properties now hold, including equal black heights.

**Running time.** Each case-1 body does constant work and advances two edges.
From initial depth d, there can be at most floor(d/2) consecutive case-1
iterations. Thus propagation takes O(h) time in a tree of height h, and O(log n)
in a red-black tree. This is a worst-case bound, not a claim that every insertion
needs height-many iterations: a black parent can stop it immediately. Here all
three have exactly three iterations despite their different stopping depths.

## Suggested teaching sequence

- Before running a case, ask students to predict both the next `fix_node` and
  whether another iteration is necessary. Then inspect the parent's color.
- Count black nodes on one path through the parent and one through the uncle
  before/after recoloring. Then explain why the same reasoning covers all paths.
- Compare the root-parent and NIL-parent examples side by side. Ask which
  property, if any, is still broken at loop exit and whether the final root
  assignment changes a color.
- Add a black-parent insertion with **zero** fix-up iterations as a contrast,
  then a one-case-1 example. This separates the stopping rule from the number
  of iterations.
- Once case 1 is clear, present a black uncle: recoloring alone cannot move the
  violation while preserving black heights. That motivates case 3's rotation;
  case 2 then becomes the preliminary rotation that converts an inner shape
  into the outer shape needed by case 3.

Tests trace the actual `insert_fixup` condition, reject any rotation, validate
the starting/final trees, and check the loop invariant and unchanged black
path counts at all four condition evaluations:

```sh
.venv/bin/python -m unittest examples.tests.test_insert_case1 -v
.venv/bin/python -m visualizer.tests.case1_debug_adapter_smoke
RB_TEST_EXAMPLE=examples.insert_case1_nil emacs --batch -Q -l visualizer/tests/emacs_smoke.el
```
