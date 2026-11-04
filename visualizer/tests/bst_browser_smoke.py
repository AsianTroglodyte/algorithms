"""Replay actual BST instruction snapshots through the shared SVG renderer."""

import gc
import json
import os
from pathlib import Path
import sys
import threading
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import binary_tree as bst
from examples._bst import make_tree
from visualizer import runtime
from visualizer.server import create_server


def operation_snapshots(operation):
    runtime._tree = None
    gc.collect()
    tree, nodes = make_tree()
    runtime.register_tree(tree)
    context = {}
    if operation == 'minimum':
        action = lambda: bst.tree_minimum(tree.root)
    elif operation == 'insertion':
        context = {'new_node': bst.Node(0)}
        action = lambda: bst.tree_insert(tree, context['new_node'])
    elif operation == 'transplant':
        context = {'old_root': nodes[31], 'replacement': bst.Node(32)}
        action = lambda: bst.transplant(tree, **context)
    else:
        context = {'node_to_delete': tree.root}
        action = lambda: bst.tree_delete(tree, context['node_to_delete'])
    rows = [runtime.snapshot(context)]
    codes = {fn.__code__ for fn in [bst.tree_minimum, bst.tree_insert, bst.transplant, bst.tree_delete]}

    def trace(frame, event, arg):
        if event == 'line' and frame.f_code in codes:
            state = runtime.snapshot(frame.f_locals)
            state['test_function'] = frame.f_code.co_name
            rows.append(state)
        return trace

    previous_trace = sys.gettrace()
    sys.settrace(trace)
    try:
        result = action()
    finally:
        sys.settrace(previous_trace)
    if operation == 'minimum':
        context['minimum'] = result
    elif operation == 'transplant':
        context['old_root'].parent = None
    rows.append(runtime.snapshot(context))
    return rows


def main():
    runtime.install_tracking(bst.Node)
    server, token = create_server()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}/{token}/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with sync_playwright() as p:
            options = {'headless': True}
            if os.environ.get('RB_TEST_CHROMIUM'):
                options['executable_path'] = os.environ['RB_TEST_CHROMIUM']
            browser = p.chromium.launch(**options)
            page = browser.new_page(viewport={'width': 1200, 'height': 850}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)

            def publish(state):
                revision = page.locator('#canvas').get_attribute('data-revision')
                opener.open(urllib.request.Request(base + 'state', json.dumps(state).encode())).close()
                page.wait_for_function("before => document.querySelector('#canvas').dataset.revision !== before", arg=revision)

            for operation in ['minimum', 'insertion', 'transplant', 'deletion']:
                rows = operation_snapshots(operation)
                publish(rows[0])
                page.reload()
                page.wait_for_function("() => document.querySelector('#canvas').dataset.treeKind === 'bst'")
                assert page.locator('h1').text_content() == 'Binary search tree'
                assert page.locator('.node.plain').count() == len(rows[0]['nodes'])
                assert page.locator('.node.warning').count() == 0
                assert page.locator('#empty-label').text_content() == 'Show None links'
                page.locator('#nil').check()
                page.wait_for_function("() => document.querySelectorAll('.empty-none').length > 0")
                assert page.locator('#nil-view-control').is_hidden()
                assert page.locator('.shared-nil, .parent-edge').count() == 0
                assert set(page.locator('.nil > text').all_text_contents()) == {'None'}
                page.locator('#view-mode').select_option('focus')
                page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'focus'")
                page.locator('#nil').uncheck()
                assert page.locator('.folded-subtree').count() > 0
                for state in rows[1:]:
                    publish(state)
                    assert page.locator('#canvas').get_attribute('data-tree-kind') == 'bst'
                    assert not page.locator('#notice').text_content().startswith('Unable to lay out')
                    assert not any(text in {'RED', 'BLACK', '?'} for text in page.locator('.node .color').all_text_contents())
                    if not state['warnings']:
                        assert page.locator('.node.warning, .edge.warning').count() == 0
                    if state.get('test_function') == 'tree_minimum':
                        cursor = next(node for node in state['nodes'] if 'node' in node['names'])
                        assert page.locator(f'.node[data-id="{cursor["id"]}"]:not(.compact)').count() == 1
                    if operation == 'insertion':
                        assert page.locator('.folded-subtree').count() > 0
                        if any(node['nil_labels'] for node in state['nodes']):
                            assert page.locator('.named-nil > text').all_text_contents() == ['None']
                final = rows[-1]
                assert not final['warnings'], final['warnings']
                page.locator('#fit').click()
                page.screenshot(path=f'/tmp/bst-{operation}.png')
                # Shared presentation controls work with plain BST nodes too.
                target = page.locator('.node').first
                ident = target.get_attribute('data-id')
                target.focus()
                target.press('Enter')
                page.wait_for_function("id => document.querySelector(`.node[data-id=\"${id}\"]`)?.classList.contains('pinned')", arg=ident)
                page.locator('#reset-focus').click()
                page.locator('#view-mode').select_option('full')
                page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'full'")
                assert page.locator('.node').count() == len(final['nodes'])
                print(f'PASS: BST {operation}, {len(rows)} real snapshots, None links, focus, pins, full view')
            empty = {'status': 'paused', 'tree_kind': 'bst', 'root': None, 'root_is_empty': True,
                     'root_is_nil': False, 'nil_names': [], 'nodes': [], 'edges': [], 'warnings': []}
            publish(empty)
            assert page.locator('.node, .shared-nil').count() == 0
            assert 'root is None' in page.locator('#notice').text_content()
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
