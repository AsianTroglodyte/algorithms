"""Replay real case-entry snapshots: visible NIL x, no stale warnings, no mirrors."""

import gc
import json
import os
from pathlib import Path
import sys
import threading
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import red_black_trees as rb
from examples._delete_cases import make_tree, EXPECTED_CASES
from examples.tests.test_delete_cases import case_lines
from visualizer import runtime
from visualizer.server import create_server


def snapshots(case):
    runtime._tree = None
    gc.collect()
    tree, victim = make_tree(case)
    runtime.register_tree(tree)
    rows = [('ready', runtime.snapshot({'delete_node': victim}))]
    lines, mirrored, final, _ = case_lines()
    case_at = {line: number for number, line in lines.items()}

    def trace(frame, event, arg):
        if event == 'line' and frame.f_code is rb.delete_fixup.__code__:
            assert not mirrored <= frame.f_lineno < final
            if frame.f_lineno in case_at:
                rows.append((case_at[frame.f_lineno], runtime.snapshot(frame.f_locals)))
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        runtime.with_deletion_cleanup(rb.delete)(tree, victim)
    finally:
        sys.settrace(previous)
    rows.append(('finished', runtime.snapshot({'delete_node': victim})))
    return rows


def main():
    runtime.install_tracking(rb.Node)
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
            page = browser.new_page(viewport={'width': 1100, 'height': 850}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)

            def publish(state):
                revision = page.locator('#canvas').get_attribute('data-revision')
                opener.open(urllib.request.Request(base + 'state', json.dumps(state).encode())).close()
                page.wait_for_function("old => document.querySelector('#canvas').dataset.revision !== old", arg=revision)

            for requested in range(1, 5):
                rows = snapshots(requested)
                assert tuple(stage for stage, _ in rows if isinstance(stage, int)) == EXPECTED_CASES[requested]
                publish(rows[0][1])
                page.reload()
                page.wait_for_function("() => document.querySelector('#canvas').dataset.revision")
                page.locator('#view-mode').select_option('focus')
                page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'focus'")
                for stage, state in rows[1:]:
                    publish(state)
                    assert 'Unable to lay out' not in page.locator('#notice').text_content()
                    assert page.locator('#warnings').is_hidden()
                    assert page.locator('.node.warning, .edge.warning').count() == 0
                    if isinstance(stage, int):
                        assert page.locator('.named-nil').count() == 1
                        assert page.locator('.named-nil .names').all_text_contents() == ['fix_node']
                        assert page.locator('.named-nil > text').all_text_contents() == ['NIL']
                        assert page.locator('.named-nil').evaluate('''node => {
                            const box = node.getBoundingClientRect(), canvas = document.querySelector('#canvas').getBoundingClientRect();
                            return box.left >= canvas.left && box.right <= canvas.right && box.top >= canvas.top && box.bottom <= canvas.bottom;
                        }''')
                        page.screenshot(path=f'/tmp/rb-delete-case{requested}-entry{stage}.png')
                        # Switching NIL views must preserve real node geometry.
                        positions = page.locator('.node').evaluate_all('(nodes) => nodes.map(n => [n.dataset.id, n.getAttribute("transform")])')
                        page.locator('#nil').check()
                        page.locator('#nil-view').select_option('shared')
                        page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'shared'")
                        assert 'fix_node' in page.locator('.shared-nil .names').all_text_contents()
                        assert positions == page.locator('.node').evaluate_all('(nodes) => nodes.map(n => [n.dataset.id, n.getAttribute("transform")])')
                        page.locator('#nil-view').select_option('leaves')
                        page.locator('#nil').uncheck()
                assert not rows[-1][1]['warnings']
                print(f'PASS: case {requested}, trace {EXPECTED_CASES[requested]}, visible NIL x, stable views, clean detached node')
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
