"""Check the three teaching examples through real debugpy stops and snapshots.

Run from the root: python -m visualizer.tests.case1_debug_adapter_smoke
"""

import inspect
import sys

from examples import insert_case1_internal, insert_case1_nil, insert_case1_root
import red_black_trees as rb
from visualizer.tests.debug_adapter_smoke import Adapter, ROOT


def main():
    lines, start = inspect.getsourcelines(rb.insert_fixup)
    guard_line = start + next(i for i, line in enumerate(lines)
                              if "while fix_node.parent.color" in line)
    for example, root_key, parent_key in (
        (insert_case1_internal, "30", "22"),
        (insert_case1_root, "22", "22"),
        (insert_case1_nil, "14", None),
    ):
        adapter = Adapter()
        try:
            source, first = inspect.getsourcelines(example.main)
            ready_line = first + next(i for i, line in enumerate(source)
                                      if line.strip() == "insert(tree, new_node)")
            finished_line = first + next(i for i, line in enumerate(source)
                                         if line.strip() == "finished = True")
            adapter.request("initialize", adapterID="python", clientID="case1-test",
                            linesStartAt1=True, columnsStartAt1=True)
            launch = adapter.send("launch", {
                "module": example.__name__, "cwd": str(ROOT),
                "python": sys.executable, "console": "internalConsole",
                "justMyCode": True,
            })
            adapter.event("initialized")
            adapter.request("setBreakpoints", source={"path": str(ROOT / "red_black_trees.py")},
                            breakpoints=[{"line": guard_line}])
            adapter.request("setBreakpoints", source={"path": example.__file__},
                            breakpoints=[{"line": ready_line}, {"line": finished_line}])
            adapter.request("setExceptionBreakpoints", filters=["uncaught"])
            adapter.request("configurationDone")
            adapter.response(launch)
            stop = adapter.event("stopped")
            state, frame = adapter.snapshot(stop["threadId"])
            assert frame["line"] == ready_line, frame
            assert any(node["key"] == "0" and node["detached"] for node in state["nodes"])

            for key in ("0", "2", "6", "14"):
                adapter.request("continue", threadId=stop["threadId"])
                stop = adapter.event("stopped")
                state, frame = adapter.snapshot(stop["threadId"])
                assert frame["name"] == "insert_fixup" and frame["line"] == guard_line, frame
                fix = next(node for node in state["nodes"] if "fix_node" in node["names"])
                assert fix["key"] == key and fix["color"] == "red", fix
                if key == "14":
                    if parent_key is None:
                        assert fix["parent_is_nil"] and state["root"] == fix["id"]
                    else:
                        parent = next(node for node in state["nodes"] if node["id"] == fix["parent"])
                        assert parent["key"] == parent_key and parent["color"] == "black", parent

            adapter.request("continue", threadId=stop["threadId"])
            stop = adapter.event("stopped")
            state, frame = adapter.snapshot(stop["threadId"])
            assert frame["line"] == finished_line, frame
            root = next(node for node in state["nodes"] if node["id"] == state["root"])
            assert root["key"] == root_key and root["color"] == "black", root
            assert not state["warnings"], state["warnings"]
            adapter.request("continue", threadId=stop["threadId"])
            adapter.event("terminated")
            print(f"PASS: {example.__name__}: setup, four guard stops, parent, final black root, termination")
        finally:
            adapter.process.terminate()
            adapter.process.wait(timeout=10)


if __name__ == "__main__":
    main()
