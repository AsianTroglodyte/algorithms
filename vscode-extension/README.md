# Red-black Tree Visualizer

Local VS Code debugger bridge for this repository's browser visualizer.
Requires VS Code 1.85+, the Microsoft Python Debugger extension, and this
repository open as a trusted workspace folder.

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-visualizer.txt
python3 scripts/package_vscode.py
code --install-extension dist/rb-tree-visualizer-0.1.0.vsix
```

Reload the VS Code window after installation if it is already open. Run
**Red-black Tree: Debug Demo** from the Command Palette. The graph opens in
your browser and Python stops at entry. Use ordinary breakpoints, Continue,
Step Over, Step Into, and Step Out in VS Code. The graph updates at each stop.
The repository's **Red-black tree demo** F5 configuration does the same thing.

The graph initially says **Waiting** until the demo registers its tree. Set a
breakpoint at `first = Node(30)` in `visualizer_demo.py` and continue to it,
then step into insertions or rotations. Put the browser beside VS Code.

Ending the debug session retains the last graph. **Red-black Tree: Open
Visualizer** reopens the browser. **Red-black Tree: Stop Visualizer Server**
stops the companion after you end debugging. Closing VS Code also stops it.

The interpreter defaults to the repository's `.venv/bin/python`, or
`.venv\Scripts\python.exe` on Windows. Set **Rb Visualizer: Python**
(`rbVisualizer.python`) to use another executable. A `python` value in the
debug configuration is also supported; the setting takes precedence.
Paths beginning with `.` resolve against the repository.

For another instrumented Python script in this repository, copy the demo's
launch configuration, change `program`, and keep `"rbVisualizer": true`.
Unmarked Python debug sessions are unaffected. One tree debug session is
supported at a time. See the repository README for tracking requirements and
the meaning of graph warnings.

If startup fails, open **View → Output → Red-black Tree** for details.
The extension has no npm runtime dependencies and uses VS Code's debugger
tracker and request APIs. The browser, server, and snapshot format are shared
with the Emacs integration.
