# Debugger visualizer

Browser companion for inspecting the tree while debugging in Emacs or VS Code.
Run the commands below from the repository root.

The Python runtime and server live directly in `visualizer/`, browser assets in
`static/`, editor bridges in `emacs/` and `vscode/`, packaging in `scripts/`, and
checks in `tests/`. Runnable tree examples live in [`../examples/`](../examples/README.md).

After upgrading from the earlier layout, reinstall the VS Code extension using
the commands below, then run **Developer: Reload Window**. In Emacs, load
`visualizer/emacs/rb-visualizer.el` from its new location before launching.

## Launch from VS Code

Requires Python 3.10+, VS Code 1.85+, the Microsoft **Python Debugger**
extension (`ms-python.debugpy`), and a modern browser. The local bridge is
packaged from this repository; no npm installation or publishing account is
needed.

From the repository root, set up Python if you have not already:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r visualizer/requirements.txt
```

Build and install the local extension:

```sh
python3 visualizer/scripts/package_vscode.py
code --install-extension dist/rb-tree-visualizer-0.1.1.vsix
```

Open **this repository folder** in VS Code. If it was open during installation,
run **Developer: Reload Window**. Then:

1. Open the Command Palette (`Ctrl+Shift+P`) and run **Red-black Tree: Debug Demo**.
   The graph opens in your browser, and Python stops at entry.
2. Set a breakpoint at `first = Node(30)` in `examples/visualizer_demo.py`, then continue
   (`F5`). The initial **Waiting** state is normal before the tree is registered.
3. Use normal **Step Into** (`F11`), **Step Over** (`F10`), **Step Out**
   (`Shift+F11`), and breakpoints. Step into insertions or rotations to watch
   actual pointer changes. Place the browser beside VS Code.
4. End debugging (`Shift+F5`). The browser keeps the final graph. Run
   **Red-black Tree: Stop Visualizer Server** when finished.

You can also select **Red-black tree demo** in Run and Debug and press `F5`;
the supplied `.vscode/launch.json` starts the same companion automatically.
**Red-black Tree: Open Visualizer** reopens the current graph if you close its
browser tab. Only one tree debug session can run at a time.

The interpreter defaults to this folder's `.venv/bin/python`. On Windows,
create the environment with `py -m venv .venv` and use
`.venv\Scripts\python.exe` for the install command above; the extension uses
that Windows interpreter path automatically. To use another interpreter,
set **Rb Visualizer: Python** (`rbVisualizer.python`) in workspace settings,
for example:

```json
{"rbVisualizer.python": "/absolute/path/to/python"}
```

A `python` value in the debug configuration is also supported; the setting
takes precedence. Paths beginning with `.` resolve against the repository.
For another instrumented example in this repository, copy the demo launch
configuration, change `module` (for example, `examples.insertion_cases`), and
retain `"rbVisualizer": true`. Module names omit the `.py` extension.
Ordinary, unmarked Python sessions do not start the companion.

Startup errors appear in **View → Output → Red-black Tree**. The extension
requires a trusted workspace and stops its server when its VS Code extension
host closes. It uses the same browser controls and tracking constraints
described below for Emacs.

## Launch from Emacs

Requires Python 3.10+, Emacs with `dap-mode` and its dependencies installed,
and a modern browser. The browser bundles ELK.js locally for graph layout;
there is no JavaScript installation or build step. The HTTP server uses the
Python standard library; the Python debugger uses `debugpy`.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r visualizer/requirements.txt
```

In Emacs, run `M-x load-file` and select `visualizer/emacs/rb-visualizer.el`
in the repository. Open the Python example you want to run, then use
**`M-x rb-visualizer-debug`**. This command saves the current Python file, starts
the local server, opens your default browser, and launches that file through
`dap-python` using debugpy. It stops at the entry point. Place the browser
beside Emacs; window placement is left to your window manager.

Use **`M-x rb-visualizer-debug-example`** to choose an example from a completion
list instead. It works from any buffer and remembers the last choice as the
default. From Lisp, `(rb-visualizer-debug-example "examples.insert_case1_nil")`
launches a specific example.

Both commands run with the repository root as the working directory and include
it on Python's import path. As in the examples, the program must call
`install_tracking(Node)` before creating nodes and `register_tree(tree)` to
select the displayed tree. Until registration, the browser shows **Waiting**.

If dap-mode reports `dap--buffers-w-breakpoints: Wrong type argument: markerp,
nil`, reload `visualizer/emacs/rb-visualizer.el` with `M-x load-file`, then start
a fresh session. The bridge includes a compatibility fix for refreshing saved
breakpoints in closed files; it preserves their locations and conditions.

Use normal `dap-breakpoint-toggle`, `dap-next`, `dap-step-in`, `dap-step-out`,
and `dap-continue` commands. Put a breakpoint at `first = Node(30)` in the demo,
or inside `left_rotate` / `right_rotate` in `red_black_trees.py`. Step into the
third insertion to see a right rotation; the fifth insertion exercises an
inner rotation. `delete(tree, second)` leaves `second` detached but live until
its reference is deleted. The comments in the demo suggest stopping points.
For exceptions, use dap-mode's normal exception breakpoint controls in
`dap-ui-breakpoints`; every received exception stop also triggers a snapshot.

End the Python session using the usual dap-mode controls. The browser shows
**Ended** and retains the final snapshot for discussion. Run
`M-x rb-visualizer-stop` to close the companion server, or launch another demo
after ending the previous session. Closing Emacs also closes the server.
Closing the browser does not stop Python.

After the program finishes, stepping cannot continue: run
`M-x rb-visualizer-debug` from the Python example, or
`M-x rb-visualizer-debug-example` from any buffer, to start again. Set a
breakpoint at `insert(tree, new_node)` in the case-1 examples to pause after
tree registration; continuing past the last breakpoint lets the program finish.
While Python is running, wait for a breakpoint before stepping.

Earlier bridge versions printed `Debug session process exited with status:
killed` even on a successful exit, because dap-mode kills its adapter during
normal cleanup. Reload `visualizer/emacs/rb-visualizer.el` to get explicit
completion messages (including Python's exit code) and a useful restart message
when stepping an ended session. Unexpected adapter exits still report an error
and identify the output buffers to inspect.

For the case-1 teaching examples, open the example and run `rb-visualizer-debug`,
or choose it using `rb-visualizer-debug-example`. VS Code exposes these
examples as separate **Case 1 three times: ...** F5 configurations. See the
[case-1 lesson](../examples/insert_case1.md) for the walkthrough and invariants.

If you use a different virtual environment, set `rb-visualizer-python` to its
absolute interpreter path after loading the Lisp file. No changes to your Emacs
configuration are made by this project.

## Browser controls and interpretation

- Drag the background to pan; scroll to zoom around the pointer.
- **Fit to view** explicitly fits all known nodes. Camera position and scale
  persist across pauses and NIL toggles; updates never auto-fit.
- **Show NIL leaves** displays black placeholders for sentinel children. Every
  placeholder represents the same `tree.nil` object; hover to see its address.
- With NIL leaves enabled, choose **NIL view → Shared sentinel** to draw one
  black NIL object. All NIL child pointers converge on it, and blue arrows
  labeled **parent** show NIL parent pointers, including the root's parent.
  **Leaf positions** restores the usual diagram. The shared view updates with
  each pause and keeps variable aliases attached to the sentinel. Both views
  use identical tree positions and child edges; only NIL arrows are rerouted
  around the fixed tree to converge below it.
- During insertion, `current_node is tree.nil` labels the left or right **NIL** child
  of `parent_of_new_node` selected by the new node's key. The labeled NIL and its
  child edge remain visible with NIL leaves hidden.
- Node fill and RED/BLACK labels show the actual color. `#` labels are stable
  session identities; hover for Python object addresses and parent information.
- Labels attached outside each node name direct local variables referring to it in the
  frame where execution stopped. Multiple aliases appear one per line. Selecting a different
  stack frame in your editor does not change the browser labels.
- Child edges are labeled L/R. Dashed amber edges, warning outlines, tooltips,
  and a warning list identify parent mismatches, shared children, and cycles.
  Parent pointers appear in tooltips and warnings; the shared-sentinel view also
  draws parent pointers that reference NIL.
- Nodes unreachable by child links from `tree.root` appear separately under
  **Detached · still live**. Inconsistent states are displayed as they stand.
- While Python runs, the last paused snapshot remains visible and is explicitly
  marked **Running**. Waiting, ended, error, and disconnected states are distinct.

## Architecture and constraints

`visualizer.runtime.install_tracking(Node)` wraps only `Node.__init__`, before
the demo constructs any nodes. `register_tree(tree)` explicitly selects one
tree. Both tree registration and node tracking use weak references. Snapshot
values contain only strings, numbers, booleans, and containers; neither the
server nor the snapshot retains Python nodes or frames. Session IDs are
monotonic, so reused Python memory addresses do not alias an earlier node.

Existing nodes connected through root/child/parent links are discovered during
snapshots. For a detached node created before instrumentation, explicitly call
`track_existing(node)` while it is available. Undiscoverable preexisting
detached nodes cannot be recovered. The wrapper is installed once per Python
process; launching a new debugger session creates fresh tracking state.

The editor bridge observes DAP stopped/continued events, requests the top stopped
frame, and evaluates `snapshot_wire(locals())` through debugpy. It then posts the
serialized result to a separate Python server. Emacs uses `visualizer/emacs/rb-visualizer.el`;
VS Code uses the small JavaScript extension in `visualizer/vscode/`, with the
public debugger tracker and `DebugSession.customRequest` APIs. No background thread in the
suspended debuggee is required. Generation checks discard snapshot responses
that arrive after resume, termination, or a newer pause. The browser polls the
server every 250 ms and renders only published pauses; step-over and continue
retain their normal meaning.

The server listens only on `127.0.0.1`, uses an OS-assigned port, and gives each
launch an unpredictable URL path. It remains available after Python exits.
There is no external service, CDN, browser debugger UI, or operation-entry UI.
Node tracking does not modify the tree operation functions.

## Verification and limitations

The snapshot and HTTP checks pass after the file reorganization. Full demo and
debugger smoke runs currently encounter an existing deletion error at
`red_black_trees.py:199`: `tree_minimum()` receives an unsupported `replacement`
keyword. This also occurs in the original demo before the reorganization.

Earlier verification used Python 3.14, debugpy 1.8.22, Emacs 30.2, the installed
dap-mode (0.8, including its February 2026 package), and headless Chromium.
The VS Code integration was also verified in a real VS Code 1.144 extension
host with the installed Microsoft Python Debugger: command launch, a rotation
breakpoint, graph publication, line stepping, termination, and server cleanup.
The Emacs integration observes the internal `dap--on-event` function and uses
`dap--send-message` / `dap--make-request`, so a future dap-mode API change may
require updating the small Lisp bridge. The upstream sources are
[dap-mode.el](https://github.com/emacs-lsp/dap-mode/blob/master/dap-mode.el) and
[dap-python.el](https://github.com/emacs-lsp/dap-mode/blob/master/dap-python.el).

The automated Emacs launch test intercepts browser opening; the actual browser
rendering and controls are checked separately. Desktop window arrangement and
the default browser handoff still need your presentation-machine check.

Debuggers can themselves retain references through variable inspection or
exception frames. Weak tracking does not prevent collection, but cannot force
collection while the debugger or program still owns a node. Multiple program
threads mutating the tree while only one is suspended are outside this demo's
scope. Rendering places ordered trees with fixed left/right child positions and
reserved NIL slots. Shared-sentinel arrows route around those fixed nodes and
their labels. ELK handles cycles, shared children, and cross-group pointers;
malformed graphs retain their actual edges. Detached nodes are grouped
separately. It reports pointer inconsistencies, not every red-black
invariant violation. Nonprimitive keys display their type
without invoking arbitrary user-defined `__repr__` code.

Run the core checks from the repository root:

```sh
.venv/bin/python -m unittest test_red_black_trees visualizer.tests.test_visualizer test_time_complexity -v
.venv/bin/python visualizer/tests/debug_adapter_smoke.py
emacs --batch -Q -l visualizer/tests/emacs_smoke.el
node --test visualizer/tests/vscode_bridge.test.js visualizer/tests/vscode_extension.test.js
```

The VS Code checks need Node.js 18+ and the Python environment above. They
exercise the extension's bridge against real debugpy and the HTTP server:
rotation pauses, stopped-frame aliases, stepping, exception stops, final-state
retention, a second session, and responses arriving after resume or termination.
They also check command/configuration registration and server cleanup with a
stub of the VS Code API.

For the optional real VS Code smoke test, run the following with the Microsoft
Python and Python Debugger extensions installed. It opens a temporary VS Code
window and browser, runs the demo, and closes the test window when finished:

```sh
code --new-window --disable-workspace-trust \
  --user-data-dir /tmp/rb-vscode-test \
  --extensionDevelopmentPath "$PWD/visualizer/vscode" \
  --extensionTestsPath "$PWD/visualizer/tests/vscode_host_smoke.js" "$PWD"
```

The Emacs smoke test locates packages in the local ELPA and Straight build
directories used on this machine. On another setup, supply your installed
package directories on Emacs's load path. The optional
`visualizer/tests/browser_smoke.py` needs Playwright and its Chromium installation in your
test environment; `RB_TEST_CHROMIUM` can select an existing Chromium executable.
It checks rendering, NIL leaves, camera persistence, malformed graphs, and
status transitions, including snapshots from the actual sentinel implementation.
It writes previews to `/tmp/rb-visualizer-preview.png` and
`/tmp/rb-visualizer-sentinel.png`.
