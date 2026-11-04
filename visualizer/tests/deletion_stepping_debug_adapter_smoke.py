"""Actual Step Into at every deletion example skips instrumentation frames."""

from pathlib import Path
import sys

from visualizer.tests.debug_adapter_smoke import Adapter, ROOT


def main():
    runtime_path = ROOT / 'visualizer/runtime.py'
    rb_lines = (ROOT / 'red_black_trees.py').read_text().splitlines()
    guard = next(i + 1 for i, line in enumerate(rb_lines) if line.strip().startswith('while fix_node is not tree.root'))
    recolor = next(i + 1 for i, line in enumerate(rb_lines) if line.strip() == 'fix_node.color = Color.BLACK')
    fixup_call = next(i + 1 for i, line in enumerate(rb_lines) if line.strip() == 'delete_fixup(tree, fix_node)')
    cases = [('delete_red_root', 'delete(tree, delete_node)', 'delete', 'red_black_trees.py'),
             ('delete_red_parent', 'delete(tree, delete_node)', 'delete', 'red_black_trees.py'),
             ('bst_deletion', 'delete(tree, node_to_delete)', 'tree_delete', 'binary_tree.py'),
             ('visualizer_demo', 'delete(tree, second)', 'delete', 'red_black_trees.py')]
    for example, statement, function, filename in cases:
        source = ROOT / f'examples/{example}.py'
        lines = source.read_text().splitlines()
        call = next(i + 1 for i, line in enumerate(lines) if line.strip().startswith(statement))
        finished = next((i + 1 for i, line in enumerate(lines) if line.strip().startswith('finished = True')), None)
        adapter = Adapter()
        try:
            adapter.request('initialize', adapterID='python', clientID='deletion-stepping')
            launch = adapter.send('launch', {'module': f'examples.{example}', 'cwd': str(ROOT),
                'python': sys.executable, 'console': 'internalConsole', 'justMyCode': True,
                'rules': [{'path': str(runtime_path), 'include': False}]})
            adapter.event('initialized')
            breakpoints = [{'line': call}]
            if finished is not None:
                breakpoints.append({'line': finished})
            adapter.request('setBreakpoints', source={'path': str(source)}, breakpoints=breakpoints)
            adapter.request('setExceptionBreakpoints', filters=['uncaught'])
            adapter.request('configurationDone')
            adapter.response(launch)
            thread = adapter.event('stopped')['threadId']
            _, frame = adapter.snapshot(thread)
            assert frame['line'] == call, frame

            # No breakpoint in delete can mask the bug: this is a genuine
            # Step Into from the wrapped function call in the example driver.
            adapter.request('stepIn', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            _, frame = adapter.snapshot(thread)
            assert frame['name'] == function, frame
            assert Path(frame['source']['path']).name == filename, frame
            adapter.request('next', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            _, frame = adapter.snapshot(thread)
            assert Path(frame['source']['path']).name == filename, frame

            if example in ['delete_red_root', 'delete_red_parent']:
                adapter.request('setBreakpoints', source={'path': str(ROOT / filename)}, breakpoints=[{'line': fixup_call}])
                adapter.request('continue', threadId=thread)
                thread = adapter.event('stopped')['threadId']
                adapter.request('stepIn', threadId=thread)
                thread = adapter.event('stopped')['threadId']
                state, frame = adapter.snapshot(thread)
                assert frame['name'] == 'delete_fixup' and frame['line'] == guard, frame
                fix = next(node for node in state['nodes'] if 'fix_node' in node['names'])
                adapter.request('next', threadId=thread)
                thread = adapter.event('stopped')['threadId']
                _, frame = adapter.snapshot(thread)
                assert frame['line'] == recolor, frame
                adapter.request('next', threadId=thread)
                thread = adapter.event('stopped')['threadId']
                state, frame = adapter.snapshot(thread)
                # debugpy can stop on delete's call-return line once before
                # returning to the driver, but never in the cleanup wrapper.
                for _ in range(3):
                    assert Path(frame['source']['path']) != runtime_path, frame
                    if Path(frame['source']['path']) == source:
                        break
                    assert Path(frame['source']['path']) == ROOT / filename, frame
                    adapter.request('next', threadId=thread)
                    thread = adapter.event('stopped')['threadId']
                    state, frame = adapter.snapshot(thread)
                assert Path(frame['source']['path']) == source, frame
                assert next(node for node in state['nodes'] if node['id'] == fix['id'])['color'] == 'black'
            elif example == 'bst_deletion':
                bst_lines = (ROOT / filename).read_text().splitlines()
                minimum = next(i + 1 for i, line in enumerate(bst_lines) if line.strip() == 'successor = tree_minimum(node_to_delete.right)')
                adapter.request('setBreakpoints', source={'path': str(ROOT / filename)}, breakpoints=[{'line': minimum}])
                adapter.request('continue', threadId=thread)
                thread = adapter.event('stopped')['threadId']
                adapter.request('stepIn', threadId=thread)
                thread = adapter.event('stopped')['threadId']
                _, frame = adapter.snapshot(thread)
                assert frame['name'] == 'tree_minimum' and Path(frame['source']['path']).name == filename, frame
            else:
                # This regression covers entry into the original demo's delete;
                # its separate two-child algorithm error is outside this fix.
                adapter.request('disconnect', terminateDebuggee=True)
                print(f'PASS: {example}: Step Into -> {function}; Step Over stays in algorithm')
                continue

            adapter.request('setBreakpoints', source={'path': str(ROOT / filename)}, breakpoints=[])
            adapter.request('continue', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            after, frame = adapter.snapshot(thread)
            assert frame['line'] == finished, frame
            assert not after['warnings'], after['warnings']
            removed = next(node for node in after['nodes'] if any(name in node['names'] for name in ['delete_node', 'node_to_delete']))
            assert removed['detached'] and removed['nil_children'] == ['left', 'right']
            adapter.request('continue', threadId=thread)
            assert adapter.event('exited')['exitCode'] == 0
            adapter.event('terminated')
            print(f'PASS: {example}: direct algorithm entry, nested calls, direct return, cleanup preserved')
        finally:
            adapter.process.terminate()
            adapter.process.wait(timeout=10)


if __name__ == '__main__':
    main()
