# Red-black trees

Python red-black tree implementation and a browser companion for stepping
through its actual pointer state from Emacs.

## Launch the visualizer

Requires Python 3.10+, Emacs with `dap-mode` and its dependencies installed,
and a modern browser. The browser and HTTP server have no third-party runtime
dependencies; the Python debugger uses `debugpy`.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-visualizer.txt
```

In Emacs, run `M-x load-file` and select `rb-visualizer.el` in this directory.
Then run **`M-x rb-visualizer-debug`**. This one command starts the local server,
opens your default browser, and launches `visualizer_demo.py` through
`dap-python` using debugpy. It stops at the entry point. Place the browser
beside Emacs; window placement is left to your window manager.

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

If you use a different virtual environment, set `rb-visualizer-python` to its
absolute interpreter path after loading the Lisp file. No changes to your Emacs
configuration are made by this project.

## Browser controls and interpretation

- Drag the background to pan; scroll to zoom around the pointer.
- **Fit to view** explicitly fits all known nodes. Camera position and scale
  persist across pauses and NIL toggles; updates never auto-fit.
- **Show NIL leaves** displays black placeholders for actual `None` children.
- Node fill and R/B labels show the actual color. `#` labels are stable session
  identities; hover for Python object addresses and parent information.
- Blue labels name direct local variables referring to that node in the frame
  where execution stopped. Multiple aliases are shown. Selecting a different
  stack frame in Emacs does not change the browser labels.
- Child edges are labeled L/R. Dashed amber edges, warning outlines, tooltips,
  and a warning list identify parent mismatches, shared children, and cycles.
  Parent pointers appear in tooltips and warnings rather than as ordinary edges.
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

Emacs observes DAP stopped/continued events, requests the top stopped frame,
and evaluates `snapshot_wire(locals())` through debugpy. It then posts the
serialized result to a separate Python server. No background thread in the
suspended debuggee is required. Generation checks discard snapshot responses
that arrive after resume, termination, or a newer pause. The browser polls the
server every 250 ms and renders only published pauses; step-over and continue
retain their normal meaning.

The server listens only on `127.0.0.1`, uses an OS-assigned port, and gives each
launch an unpredictable URL path. It remains available after Python exits.
There is no external service, CDN, browser debugger UI, or operation-entry UI.
The operation functions in `red_black_trees.py` are unchanged.

## Verification and limitations

Verified locally with Python 3.14, debugpy 1.8.22, Emacs 30.2, the installed
dap-mode (0.8, including its February 2026 package), and headless Chromium.
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
scope. Rendering uses a finite spanning forest for malformed graphs and draws
the remaining actual child edges across it. It reports pointer inconsistencies,
not every red-black invariant violation. Nonprimitive keys display their type
without invoking arbitrary user-defined `__repr__` code.

Run the core checks from the repository root:

```sh
.venv/bin/python -m unittest test_visualizer test_time_complexity -v
.venv/bin/python tests/debug_adapter_smoke.py
emacs --batch -Q -l tests/emacs_smoke.el
```

The Emacs smoke test locates packages in the local ELPA and Straight build
directories used on this machine. On another setup, supply your installed
package directories on Emacs's load path. The optional
`tests/browser_smoke.py` needs Playwright and its Chromium installation in your
test environment; `RB_TEST_CHROMIUM` can select an existing Chromium executable.
It checks rendering, NIL leaves, camera persistence, malformed graphs, and
status transitions, and writes a preview to `/tmp/rb-visualizer-preview.png`.
