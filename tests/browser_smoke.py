"""Optional browser check; requires Playwright and a Chromium install."""

import json
import os
from pathlib import Path
import sys
import threading
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from red_black_trees import Node, Tree, insert
from visualizer.runtime import install_tracking, register_tree, snapshot
from visualizer.server import create_server


def main():
    install_tracking(Node)
    tree = Tree()
    register_tree(tree)
    nodes = [Node(key) for key in (30, 20, 10, 25, 28)]
    for node in nodes:
        insert(tree, node)
    detached = Node(99)
    server, token = create_server()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}/{token}/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def publish(state):
        opener.open(urllib.request.Request(base+'state', json.dumps(state).encode())).close()

    try:
        with sync_playwright() as p:
            options = {'headless': True}
            if os.environ.get('RB_TEST_CHROMIUM'):
                options['executable_path'] = os.environ['RB_TEST_CHROMIUM']
            browser = p.chromium.launch(**options)
            page = browser.new_page(viewport={'width': 850, 'height': 850})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)
            page.wait_for_function("() => document.querySelector('#status').textContent === 'Waiting'")
            publish(snapshot({'detached': detached, 'root': tree.root}))
            page.wait_for_function("() => document.querySelectorAll('.node').length === 6")
            assert page.locator('.nil').count() == 0
            page.locator('#nil').check()
            assert page.locator('.nil').count() > 0
            page.locator('#fit').click()
            page.mouse.move(450, 450)
            page.mouse.wheel(0, -180)
            page.mouse.down()
            page.mouse.move(480, 470)
            page.mouse.up()
            before = page.locator('#viewport').get_attribute('transform')
            tree.root.left = tree.root  # Deliberate cycle, visible warning.
            publish(snapshot({'root': tree.root}))
            page.wait_for_function("() => document.querySelector('#warnings').textContent.includes('Cycle')")
            assert page.locator('#viewport').get_attribute('transform') == before
            assert page.locator('.edge.warning').count() > 0
            page.screenshot(path='/tmp/rb-visualizer-preview.png')
            publish({'status': 'running'})
            page.wait_for_function("() => document.querySelector('#status').textContent === 'Running'")
            publish({'status': 'ended'})
            page.wait_for_function("() => document.querySelector('#status').textContent === 'Ended'")
            assert not errors, errors
            browser.close()
            print('PASS: browser rendering, NIL, pan/zoom persistence, cycles, running/ended status')
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
