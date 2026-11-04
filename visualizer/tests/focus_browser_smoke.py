"""Focus controls and snapshot stepping; no imports from the algorithm under edit.

Run from the repository root with Playwright installed:
    python visualizer/tests/focus_browser_smoke.py
Set RB_TEST_CHROMIUM to use an existing Chromium executable.
"""

import copy
import json
import os
from pathlib import Path
import sys
import threading
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from visualizer.server import create_server


def fixture(count=127, active='64'):
    nodes, edges = [], []
    for n in range(1, count + 1):
        key = str(n)
        links = [(side, str(child) if child <= count else None)
                 for side, child in [('left', n * 2), ('right', n * 2 + 1)]]
        nodes.append(dict(id=key, key=key, address=hex(n), parent=str(n // 2) if n > 1 else None,
                          names=['fix_node'] if key == active else [], color='red' if n % 2 else 'black',
                          parent_is_nil=n == 1, nil_children=[side for side, child in links if child is None],
                          detached=False, warnings=[]))
        edges.extend(dict(source=key, target=child, side=side, warnings=[])
                     for side, child in links if child is not None)
    return dict(status='paused', root='1', nodes=nodes, edges=edges, warnings=[], nil_names=[])


def main():
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
            page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)

            def publish(state):
                revision = page.locator('#canvas').get_attribute('data-revision')
                opener.open(urllib.request.Request(base + 'state', json.dumps(state).encode())).close()
                page.wait_for_function("before => document.querySelector('#canvas').dataset.revision !== before",
                                       arg=revision)

            state = fixture()
            publish(state)
            assert page.locator('.node').count() == 127
            full_width = page.locator('#viewport').evaluate('(g) => g.getBBox().width')
            page.locator('#view-mode').select_option('focus')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'focus'")
            assert page.locator('.folded-subtree').count() > 0
            assert page.locator('.node.compact').count() > 0
            assert page.locator('#viewport').evaluate('(g) => g.getBBox().width') < full_width * .6
            for key in ['64', '32', '16', '33']:
                assert 'compact' not in page.locator(f'.node[data-id="{key}"]').get_attribute('class')
            page.locator('#fit').click()
            page.screenshot(path='/tmp/rb-focus-mode.png')

            # Keyboard pins compact nodes; pointer clicks can unpin them.
            root = page.locator('.node[data-id="1"]')
            root.focus()
            root.press('Enter')
            page.wait_for_function("() => document.querySelector('.node[data-id=\"1\"]')?.classList.contains('pinned')")
            assert page.locator('.node[data-id="1"]').evaluate('(node) => node === document.activeElement')
            assert page.locator('.node[data-id="1"] .root-label').count() == 1
            page.locator('.node[data-id="1"]').click(force=True)
            page.wait_for_function("() => !document.querySelector('.node[data-id=\"1\"]')?.classList.contains('pinned')")

            # Expand via pointer, then reset both manual expansion and pins.
            triangle = page.locator('.folded-subtree').first
            triangle_id = triangle.get_attribute('data-id')
            triangle.click(force=True)
            page.wait_for_function("id => !!document.querySelector(`.node[data-id=\"${id}\"]`)", arg=triangle_id)
            assert page.locator(f'.folded-subtree[data-id="{triangle_id}"]').count() == 0
            page.locator('#reset-focus').click()
            page.wait_for_function("id => !!document.querySelector(`.folded-subtree[data-id=\"${id}\"]`)", arg=triangle_id)

            # Reflow anchors the same active node and preserves zoom.
            def center(key):
                return page.locator(f'.node[data-id="{key}"] .node-body').evaluate('''node => {
                    const r = node.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2};
                }''')

            before = center('64')
            page.locator('.node[data-id="1"]').focus()
            page.locator('.node[data-id="1"]').press('Space')
            page.wait_for_function("() => document.querySelector('.node[data-id=\"1\"]')?.classList.contains('pinned')")
            after = center('64')
            assert abs(before['x'] - after['x']) < 1 and abs(before['y'] - after['y']) < 1, (before, after)
            page.locator('#reset-focus').click()

            # NIL toggles and shared-sentinel routing preserve the focused BST.
            positions = page.locator('.node').evaluate_all('(nodes) => nodes.map(n => [n.dataset.id, n.getAttribute("transform")])')
            page.locator('#nil').check()
            page.wait_for_function("() => document.querySelectorAll('.nil').length > 0")
            page.locator('#nil-view').select_option('shared')
            page.wait_for_function("() => document.querySelector('.shared-nil') !== null")
            assert positions == page.locator('.node').evaluate_all('(nodes) => nodes.map(n => [n.dataset.id, n.getAttribute("transform")])')
            assert page.locator('.parent-edge').count() == 1
            page.locator('#nil').uncheck()

            # Stepping moves focus upward, retains the old family for one pause,
            # and pointer/color changes outside that family remain visible.
            moved = fixture(active='16')
            publish(moved)
            assert page.locator('.node[data-id="64"]:not(.compact)').count() == 1
            publish(moved)
            assert page.locator('.node[data-id="64"]:not(.compact)').count() == 0
            changed = copy.deepcopy(moved)
            changed['nodes'][-1]['color'] = 'black'
            publish(changed)
            assert page.locator('.node[data-id="127"]:not(.compact)').count() == 1

            # Invalid intermediate pointer states reveal every actual node.
            malformed = copy.deepcopy(changed)
            malformed['nodes'][90]['warnings'] = ['Parent mismatch']
            malformed['warnings'] = ['#91: Parent mismatch']
            publish(malformed)
            assert page.locator('.node').count() == 127
            assert 'full graph' in page.locator('#focus-help').text_content()
            assert page.locator('.node.warning').count() >= 1
            publish(moved)

            # Dragging a node pans without pinning it.
            page.locator('#fit').click()
            box = page.locator('.node[data-id="16"] .node-body').bounding_box()
            page.mouse.move(box['x'] + 10, box['y'] + 10)
            page.mouse.down()
            page.mouse.move(box['x'] + 60, box['y'] + 30, steps=5)
            page.mouse.up()
            assert page.locator('.node.pinned').count() == 0
            camera = page.locator('#viewport').get_attribute('transform')
            publish(dict(status='running'))
            assert page.locator('#viewport').get_attribute('transform') == camera
            publish(dict(status='ended'))
            assert page.locator('#viewport').get_attribute('transform') == camera

            # Full mode restores all dimensions, names, and the complete graph.
            page.locator('#view-mode').select_option('full')
            page.wait_for_function("() => document.querySelectorAll('.node').length === 127")
            assert page.locator('.folded-subtree').count() == 0
            assert page.locator('.compact').count() == 0
            assert page.locator('.node-body').evaluate_all('(nodes) => nodes.every(n => n.getBBox().width === 100 && n.getBBox().height === 84)')
            assert page.locator('#focus-help').is_hidden()
            # Exercise the animation path too, including rapid view toggles.
            page.emulate_media(reduced_motion='no-preference')
            page.locator('#view-mode').select_option('focus')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'focus'")
            page.locator('#view-mode').select_option('full')
            page.locator('#view-mode').select_option('focus')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.viewMode === 'focus'")
            page.wait_for_timeout(220)
            assert page.locator('.folded-subtree').count() > 0
            assert not errors, errors
            browser.close()
        print('PASS: focus compression, pins, expansion/reset, keyboard, anchoring, NIL stability, stepping, warnings, drag, full view')
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
