"""Exercise each BST lesson through the unchanged, real debugger snapshot bridge."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_adapter_smoke import Adapter, ROOT


def main():
    source = (ROOT / 'binary_tree.py').read_text().splitlines()
    cases = [
        ('minimum', 'tree_minimum', 'while node is not None and node.left is not None:', 'node'),
        ('insertion', 'tree_insert', 'new_node.parent = parent_of_new_node', 'new_node'),
        ('transplant', 'transplant', 'if old_root.parent is None:', 'old_root'),
        ('deletion', 'tree_delete', 'if node_to_delete.left is None:', 'node_to_delete'),
    ]
    for module, function, statement, alias in cases:
        adapter = Adapter()
        try:
            adapter.request('initialize', adapterID='python', clientID='bst-test')
            launch = adapter.send('launch', {'module': f'examples.bst_{module}', 'cwd': str(ROOT),
                                             'python': sys.executable, 'console': 'internalConsole', 'justMyCode': True})
            adapter.event('initialized')
            line = next(i + 1 for i, text in enumerate(source) if text.strip() == statement)
            adapter.request('setBreakpoints', source={'path': str(ROOT / 'binary_tree.py')}, breakpoints=[{'line': line}])
            adapter.request('setExceptionBreakpoints', filters=['uncaught'])
            adapter.request('configurationDone')
            adapter.response(launch)
            thread = adapter.event('stopped')['threadId']
            state, frame = adapter.snapshot(thread)
            assert frame['name'] == function, frame
            assert state['tree_kind'] == 'bst'
            assert any(alias in node['names'] for node in state['nodes'])
            assert all(node['color'] == 'plain' for node in state['nodes'])
            assert not any('color' in warning.lower() for warning in state['warnings'])
            adapter.request('setBreakpoints', source={'path': str(ROOT / 'binary_tree.py')}, breakpoints=[])
            adapter.request('next', threadId=thread)
            thread = adapter.event('stopped')['threadId']
            after, _ = adapter.snapshot(thread)
            assert after['tree_kind'] == 'bst'
            adapter.request('continue', threadId=thread)
            assert adapter.event('exited')['exitCode'] == 0
            adapter.event('terminated')
            print(f'PASS: BST {module}, stopped-frame aliases, line step, successful exit')
        finally:
            adapter.process.terminate()
            adapter.process.wait(timeout=10)


if __name__ == '__main__':
    main()
