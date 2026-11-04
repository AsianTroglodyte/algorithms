"""Real insertion pauses: bounded motion, leaf initialization, and camera follow.

Run from the repository root with Playwright installed:
    python visualizer/tests/focus_camera_smoke.py
Set RB_TEST_CHROMIUM to use an existing Chromium executable.
"""

import gc
import json
import os
from pathlib import Path
import sys
import threading
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from examples._case1 import make_tree
from red_black_trees import Color, Node, Tree, insert, insert_fixup
from visualizer import runtime
from visualizer.server import create_server


def balanced_tree():
    tree = Tree()

    def branch(lo, hi, parent):
        if lo > hi:
            return tree.nil
        mid = (lo + hi) // 2
        node = Node(mid)
        node.color, node.parent = Color.BLACK, parent
        node.left = branch(lo, mid - 1, node)
        node.right = branch(mid + 1, hi, node)
        return node

    tree.root = branch(1, 127, tree.nil)
    return tree


def snapshots(tree, key, include_fixup=False):
    runtime._tree = None
    gc.collect()
    runtime.register_tree(tree)
    new_node = Node(key)
    result = []

    def trace(frame, event, arg):
        insertion = (event == 'line' and frame.f_code is insert.__code__
                and 'parent_of_new_node' in frame.f_locals
                and frame.f_locals.get('current_node') is tree.nil)
        fixing = include_fixup and event == 'line' and frame.f_code is insert_fixup.__code__
        returning = include_fixup and event == 'return' and frame.f_code is insert.__code__
        if insertion or fixing or returning:
            state = runtime.snapshot(frame.f_locals)
            state['test_function'] = frame.f_code.co_name
            result.append(state)
        return trace

    previous_trace = sys.gettrace()
    sys.settrace(trace)
    try:
        insert(tree, new_node)
    finally:
        sys.settrace(previous_trace)
    return result


def main():
    runtime.install_tracking(Node)
    server, token = create_server()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}/{token}/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    max_shift = 0
    try:
        with sync_playwright() as p:
            options = {'headless': True}
            if os.environ.get('RB_TEST_CHROMIUM'):
                options['executable_path'] = os.environ['RB_TEST_CHROMIUM']
            browser = p.chromium.launch(**options)
            page = browser.new_page(viewport={'width': 1100, 'height': 800})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)

            def publish(state):
                revision = page.locator('#canvas').get_attribute('data-revision')
                opener.open(urllib.request.Request(base + 'state', json.dumps(state).encode())).close()
                page.wait_for_function("before => document.querySelector('#canvas').dataset.revision !== before", arg=revision)

            def centers():
                return page.locator('.node .node-body').evaluate_all('''bodies => Object.fromEntries(bodies.map(body => {
                    const r = body.getBoundingClientRect(); return [body.parentNode.dataset.id, [r.x+r.width/2, r.y+r.height/2]];
                }))''')

            def assert_visible(ids):
                for ident in ids:
                    assert page.locator(f'.node[data-id="{ident}"]').evaluate('''node => {
                        const box = node.getBoundingClientRect(), canvas = document.querySelector('#canvas').getBoundingClientRect();
                        return box.left >= canvas.left + 20 && box.right <= canvas.right - 20 &&
                            box.top >= canvas.top + 20 && box.bottom <= canvas.bottom - 20;
                    }'''), ident

            for motion in ['reduce', 'no-preference']:
                page.emulate_media(reduced_motion=motion)
                for name, builder, key in [('internal', lambda: make_tree('internal'), 0),
                                           ('left', balanced_tree, 0), ('right', balanced_tree, 128), ('root', Tree, 0)]:
                    rows = snapshots(builder(), key)
                    assert len(rows) >= 5
                    page.locator('#view-mode').select_option('full')
                    publish(rows[0])
                    # Each example represents a fresh debugger session. Start
                    # its focus history afresh instead of retaining the prior
                    # tree's "all nodes newly created" activity for a pause.
                    page.reload()
                    page.wait_for_function("() => document.querySelector('#canvas').dataset.revision")
                    page.locator('#view-mode').select_option('focus')
                    page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'focus'")
                    previous = centers()
                    old_attached = {n['id'] for n in rows[0]['nodes'] if not n['detached']}
                    for state in rows[1:]:
                        publish(state)
                        current = centers()
                        attached = {n['id'] for n in state['nodes'] if not n['detached']}
                        important = [n['id'] for n in state['nodes'] if not n['detached']
                                     and any(alias in n['names'] for alias in ['new_node', 'parent_of_new_node'])]
                        assert_visible(important)
                        for ident in old_attached & attached & previous.keys() & current.keys():
                            shift = sum((a - b) ** 2 for a, b in zip(previous[ident], current[ident])) ** .5
                            max_shift = max(max_shift, shift)
                            assert shift <= 80, (motion, name, ident, shift)
                        previous, old_attached = current, attached
                    if name == 'internal':
                        page.screenshot(path='/tmp/rb-focus-camera.png')
                    if name == 'right':
                        # A manual pan stays put while running; the next pause
                        # brings the active family back into the visible area.
                        canvas = page.locator('#canvas').bounding_box()
                        page.mouse.move(canvas['x'] + 100, canvas['y'] + 100)
                        page.mouse.down()
                        page.mouse.move(canvas['x'] + 900, canvas['y'] + 100, steps=4)
                        page.mouse.up()
                        camera = page.locator('#viewport').get_attribute('transform')
                        publish({'status': 'running'})
                        assert page.locator('#viewport').get_attribute('transform') == camera
                        publish(rows[-1])
                        assert_visible(important)
            # Reproduce the screenshot's case-1 cascade, including the return
            # to insert's locals after stepping over the entire fixup call.
            rows = snapshots(make_tree('internal'), 0, include_fixup=True)
            page.emulate_media(reduced_motion='reduce')
            publish(rows[0])
            page.reload()
            page.wait_for_function("() => document.querySelector('#canvas').dataset.revision")
            page.locator('#view-mode').select_option('focus')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'focus'")
            families = []
            for state in rows[1:]:
                publish(state)
                by_id = {node['id']: node for node in state['nodes']}
                fix = next((node for node in state['nodes'] if 'fix_node' in node['names']), None)
                if not fix:
                    continue
                parent = by_id.get(fix['parent'])
                grandparent = by_id.get(parent['parent']) if parent else None
                family = {node['id'] for node in [fix, parent, grandparent] if node}
                if grandparent:
                    family.update(edge['target'] for edge in state['edges'] if edge['source'] == grandparent['id'])
                full = set(page.locator('.node:not(.compact)').evaluate_all('(nodes) => nodes.map(n => n.dataset.id)'))
                assert full == family, (fix['key'], full, family)
                if not families or families[-1] != fix['key']:
                    families.append(fix['key'])
            assert families == ['0', '2', '6', '14'], families
            final = rows[-1]
            by_key = {node['key']: node['id'] for node in final['nodes']}
            assert page.locator(f'.folded-subtree[data-id="{by_key["38"]}"][data-count="15"]').count() == 1
            assert page.locator(f'.folded-subtree[data-id="{by_key["18"]}"][data-count="7"]').count() == 1
            assert set(page.locator('.node:not(.compact) .key').all_text_contents()) == {'0', '1', '2', '3'}
            assert set(page.locator('.node .key').all_text_contents()) == {'0', '1', '2', '3', '4', '5', '6', '10', '14', '22', '30'}
            page.locator('#fit').click()
            page.screenshot(path='/tmp/rb-focus-subtrees.png')
            assert not errors, errors
            browser.close()
        print(f'PASS: real insertion pauses, immediate family folding through case 1, whole off-path subtrees, both motion preferences, camera follow; max rooted shift {max_shift:.1f}px')
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
