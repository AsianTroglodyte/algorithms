"""Optional browser check; requires Playwright and a Chromium install."""

import json
import os
from pathlib import Path
import sys
import threading
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visualizer.server import create_server


def fixture(children, detached=()):
    """Wire snapshots keep browser checks independent of algorithm edits."""
    parents = {target: source for source, links in children.items() for target in links if target is not None}
    return {
        'status': 'paused', 'root': '20', 'warnings': [],
        'nodes': [dict(id=key, key=key, address='0x'+key, parent=parents.get(key),
                       color='black' if key == '20' else 'red', names=['root'] if key == '20' else [],
                       detached=key in detached, warnings=[],
                       nil_children=[side for side, target in zip(('left', 'right'), links) if target is None])
                  for key, links in children.items()],
        'edges': [dict(source=source, target=target, side=side, warnings=[])
                  for source, links in children.items()
                  for side, target in zip(('left', 'right'), links) if target is not None],
    }


def assert_clear_routes(geometry):
    for edge in geometry['edges']:
        for points in edge['sections']:
            for a, b in zip(points, points[1:]):
                assert a['x'] == b['x'] or a['y'] == b['y'], (a, b)
                for node in geometry['nodes']:
                    left, top = node['x'] + .1, node['y'] + .1
                    right, bottom = node['x'] + node['width'] - .1, node['y'] + node['height'] - .1
                    hit = (left < a['x'] < right and max(a['y'], b['y']) > top and min(a['y'], b['y']) < bottom
                           if a['x'] == b['x'] else
                           top < a['y'] < bottom and max(a['x'], b['x']) > left and min(a['x'], b['x']) < right)
                    assert not hit, (edge['id'], node['id'], a, b)


def main():
    state = fixture({'20': ('10', '28'), '10': (None, None), '28': ('25', '30'),
                     '25': (None, None), '30': (None, None), '99': (None, None)}, detached=('99',))
    aliases = {'20': ['tree_root', 'root_alias'], '10': ['rotate_down'],
               '28': ['rotate_up'], '99': ['detached_node']}
    for node in state['nodes']:
        node['names'] = aliases.get(node['id'], [])
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
            publish(state)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 6")
            # Names belong to external callouts, with a connector ending at
            # the body boundary. Keys, colors, and identities stay inside.
            assert page.locator('.node-label').count() == len(aliases)
            assert page.locator('.node > .names').count() == 0
            assert page.locator('.node-label').evaluate_all('''labels => labels.every(label => {
                const body = label.parentNode.querySelector('.node-body').getBBox();
                const text = label.querySelector('.names').getBBox();
                const position = label.transform.baseVal.consolidate().matrix;
                const connector = label.parentNode.querySelector('.label-connector');
                return position.e > body.x + body.width && text.x >= 0 &&
                    text.x + text.width <= label.querySelector('rect').width.baseVal.value &&
                    Number(connector.getAttribute('x1')) === body.x + body.width &&
                    Number(connector.getAttribute('x2')) === position.e &&
                    Number(connector.getAttribute('y1')) === position.f + 14;
            })''')
            page.locator('#fit').click()
            page.screenshot(path='/tmp/rb-visualizer-default.png')
            positions = page.locator('.node').evaluate_all('(nodes) => nodes.map(node => node.getAttribute("transform"))')
            assert page.locator('.nil').count() == 0
            page.locator('#nil').check()
            page.wait_for_function("() => document.querySelectorAll('.nil').length > 0")
            assert page.locator('.nil').count() > 0
            assert page.locator('.node').evaluate_all('(nodes) => nodes.map(node => node.getAttribute("transform"))') == positions
            # Asymmetric trees, one-child chains and long aliases must preserve
            # pointer sides and keep every routed segment out of other nodes.
            for sample in (state, fixture({'20': (None, None)}),
                           fixture({'20': ('10', '40'), '10': (None, '15'),
                                           '15': ('12', None), '12': (None, None),
                                           '40': (None, '50'), '50': (None, None)})):
                sample['nodes'][0]['names'] = ['root', 'long_local_variable_alias']
                geometry = page.evaluate('''async state => {
                    const {layout} = await import('./layout.js');
                    return await layout(state.nodes, state.edges, state.root);
                }''', sample)
                assert_clear_routes(geometry)
                by_id = {n['id']: n for n in geometry['nodes']}
                for edge in sample['edges']:
                    a, b = by_id[edge['source']], by_id[edge['target']]
                    ax, bx = a['x'] + a['bodyWidth']/2, b['x'] + b['bodyWidth']/2
                    assert bx < ax if edge['side'] == 'left' else bx > ax, edge
                    assert b['y'] > a['y'], edge
                groups = {g['id']: g for g in geometry['groups']}
                if 'detached' in groups:
                    assert groups['detached']['x'] > groups['attached']['x'] + groups['attached']['width']
            page.locator('#fit').click()
            page.screenshot(path='/tmp/rb-visualizer-layout.png')
            page.mouse.move(450, 450)
            page.mouse.wheel(0, -180)
            page.mouse.down()
            page.mouse.move(480, 470)
            page.mouse.up()
            before = page.locator('#viewport').get_attribute('transform')
            # Cycles, shared children, parallel edges, and a detached pointer
            # back into the rooted tree retain one rendered node per identity.
            state['warnings'] = ['Cycle detected', 'Shared child']
            for source, target in (('20', '20'), ('30', '10'), ('99', '25')):
                state['edges'].append(dict(source=source, target=target, side='left', warnings=['Cycle or shared child']))
            state['edges'].append(dict(source='28', target='25', side='right', warnings=['Shared child']))
            publish(state)
            page.wait_for_function("() => document.querySelector('#warnings').textContent.includes('Cycle')")
            assert page.locator('.node').count() == 6
            geometry = page.evaluate('''async state => {
                const {layout} = await import('./layout.js');
                return await layout(state.nodes, state.edges, state.root);
            }''', state)
            assert len([e for e in geometry['edges'] if e.get('record')]) == len(state['edges'])
            assert_clear_routes(geometry)
            assert page.locator('#viewport').get_attribute('transform') == before
            assert page.locator('.edge.warning').count() > 0
            page.screenshot(path='/tmp/rb-visualizer-preview.png')
            publish({'status': 'running'})
            page.wait_for_function("() => document.querySelector('#status').textContent === 'Running'")
            publish({'status': 'ended'})
            page.wait_for_function("() => document.querySelector('#status').textContent === 'Ended'")
            assert not errors, errors
            browser.close()
            print('PASS: external attached labels, ordered tree layout, edge clearance, NIL stability, pan/zoom, malformed graphs, session status')
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
