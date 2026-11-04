"""Debugger launch, direct deletion entry, and exact left-child case sequences."""

import importlib
import inspect
import sys

from examples._delete_cases import EXPECTED_CASES, EXPECTED_ROOTS
from examples.tests.test_delete_cases import case_lines
from visualizer.tests.debug_adapter_smoke import Adapter, ROOT


def main():
    cases, mirror, _, _ = case_lines()
    case_at = {line: case for case, line in cases.items()}
    algorithm = ROOT / 'red_black_trees.py'
    for requested in range(1, 5):
        example = importlib.import_module(f'examples.delete_case{requested}')
        lines, start = inspect.getsourcelines(example.main)
        call = start + next(i for i, line in enumerate(lines) if line.strip() == 'delete(tree, delete_node)')
        finished = start + next(i for i, line in enumerate(lines) if line.strip().startswith('finished = True'))
        adapter = Adapter()
        try:
            adapter.request('initialize', adapterID='python', clientID='delete-cases')
            launch = adapter.send('launch', {'module': example.__name__, 'cwd': str(ROOT), 'python': sys.executable,
                'console': 'internalConsole', 'justMyCode': True,
                'rules': [{'path': str(ROOT / 'visualizer/runtime.py'), 'include': False}]})
            adapter.event('initialized')
            adapter.request('setBreakpoints', source={'path': example.__file__}, breakpoints=[{'line': call}, {'line': finished}])
            adapter.request('setExceptionBreakpoints', filters=['uncaught'])
            adapter.request('configurationDone')
            adapter.response(launch)
            thread = adapter.event('stopped')['threadId']
            state, frame = adapter.snapshot(thread)
            assert frame['line'] == call and not state['warnings'], (frame, state['warnings'])
            adapter.request('stepIn', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            _, frame = adapter.snapshot(thread)
            assert frame['name'] == 'delete' and frame['source']['path'] == str(algorithm), frame
            adapter.request('setBreakpoints', source={'path': str(algorithm)},
                breakpoints=[{'line': line} for line in [*cases.values(), mirror]])
            observed = []
            for expected in EXPECTED_CASES[requested]:
                adapter.request('continue', threadId=thread)
                thread = adapter.event('stopped')['threadId']
                state, frame = adapter.snapshot(thread)
                assert frame['name'] == 'delete_fixup' and case_at.get(frame['line']) == expected, frame
                observed.append(case_at[frame['line']])
                # x is the left NIL in these examples, with its named leaf
                # slot in the snapshot instead of a fabricated real x node.
                parent = next(node for node in state['nodes'] if node['nil_labels'].get('left') == ['fix_node'])
                assert parent['key'] == '10', parent
                left = adapter.request('evaluate', frameId=frame['id'], context='repl', expression='fix_node is fix_node.parent.left')
                assert left['result'] == 'True', left
                nil = adapter.request('evaluate', frameId=frame['id'], context='repl', expression='fix_node is tree.nil')
                assert nil['result'] == 'True', nil
            adapter.request('continue', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            after, frame = adapter.snapshot(thread)
            assert frame['line'] == finished and frame['source']['path'] == example.__file__, frame
            root = next(node for node in after['nodes'] if node['id'] == after['root'])
            assert root['key'] == str(EXPECTED_ROOTS[requested]) and root['color'] == 'black', root
            assert not after['warnings'], after['warnings']
            adapter.request('continue', threadId=thread)
            assert adapter.event('exited')['exitCode'] == 0
            adapter.event('terminated')
            print(f'PASS: {example.__name__}: {observed}, no mirrored cases, direct Step Into, NIL cursor, clean exit')
        finally:
            adapter.process.terminate()
            adapter.process.wait(timeout=10)


if __name__ == '__main__':
    main()
