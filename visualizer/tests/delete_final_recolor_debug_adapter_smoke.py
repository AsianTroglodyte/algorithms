"""Real debugpy stepping: guard -> final recoloring, then repaired tree."""

import inspect
import sys

import red_black_trees as rb
from examples import delete_red_parent, delete_red_root
from visualizer.tests.debug_adapter_smoke import Adapter, ROOT


def main():
    lines, start = inspect.getsourcelines(rb.delete_fixup)
    guard = start + next(i for i, line in enumerate(lines) if line.strip().startswith('while fix_node is not tree.root'))
    recolor = start + next(i for i, line in enumerate(lines) if line.strip() == 'fix_node.color = Color.BLACK')
    body = start + next(i for i, line in enumerate(lines) if line.strip() == 'if fix_node is fix_node.parent.left:')
    for example, key, root_key in [(delete_red_root, '5', '5'), (delete_red_parent, '2', '20')]:
        adapter = Adapter()
        try:
            source, first = inspect.getsourcelines(example.main)
            ready = first + next(i for i, line in enumerate(source) if line.strip() == 'delete(tree, delete_node)')
            finished = first + next(i for i, line in enumerate(source) if line.strip().startswith('finished = True'))
            adapter.request('initialize', adapterID='python', clientID='delete-final-recolor', linesStartAt1=True, columnsStartAt1=True)
            launch = adapter.send('launch', {'module': example.__name__, 'cwd': str(ROOT), 'python': sys.executable,
                                             'console': 'internalConsole', 'justMyCode': True})
            adapter.event('initialized')
            adapter.request('setBreakpoints', source={'path': example.__file__}, breakpoints=[{'line': ready}, {'line': finished}])
            adapter.request('setBreakpoints', source={'path': str(ROOT / 'red_black_trees.py')},
                            breakpoints=[{'line': guard}, {'line': body}, {'line': recolor}])
            adapter.request('setExceptionBreakpoints', filters=['uncaught'])
            adapter.request('configurationDone')
            adapter.response(launch)
            thread = adapter.event('stopped')['threadId']
            before, frame = adapter.snapshot(thread)
            assert frame['line'] == ready, frame
            assert not before['warnings'], before['warnings']
            adapter.request('continue', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            state, frame = adapter.snapshot(thread)
            assert frame['name'] == 'delete_fixup' and frame['line'] == guard, frame
            fix = next(node for node in state['nodes'] if 'fix_node' in node['names'])
            assert fix['key'] == key and fix['color'] == 'red'
            if example is delete_red_root:
                assert fix['id'] == state['root'] and fix['parent_is_nil']
            else:
                parent = next(node for node in state['nodes'] if node['id'] == fix['parent'])
                assert parent['key'] == '10' and parent['color'] == 'red'
                assert fix['id'] != state['root']
            frames = adapter.request('stackTrace', threadId=thread)['stackFrames']
            deletion = next(frame for frame in frames if frame['name'] == 'delete')
            decision = adapter.request('evaluate', frameId=deletion['id'], context='repl', expression='y_original_color.value')
            assert decision['result'].strip("'\"") == 'black', decision
            adapter.request('next', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            state, frame = adapter.snapshot(thread)
            assert frame['name'] == 'delete_fixup' and frame['line'] == recolor, frame
            assert next(node for node in state['nodes'] if node['id'] == fix['id'])['color'] == 'red'
            adapter.request('next', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            state, _ = adapter.snapshot(thread)
            assert next(node for node in state['nodes'] if node['id'] == fix['id'])['color'] == 'black'
            adapter.request('continue', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            after, frame = adapter.snapshot(thread)
            assert frame['line'] == finished, frame
            root = next(node for node in after['nodes'] if node['id'] == after['root'])
            assert root['key'] == root_key and root['color'] == 'black'
            assert not after['warnings'], after['warnings']
            removed = next(node for node in after['nodes'] if 'delete_node' in node['names'])
            assert removed['detached'] and removed['nil_children'] == ['left', 'right']
            adapter.request('continue', threadId=thread)
            assert adapter.event('exited')['exitCode'] == 0
            adapter.event('terminated')
            print(f'PASS: {example.__name__}, BLACK decision, zero loop cases, final recolor, detached cleanup')
        finally:
            adapter.process.terminate()
            adapter.process.wait(timeout=10)


if __name__ == '__main__':
    main()
