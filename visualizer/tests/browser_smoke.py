"""Optional browser check; requires Playwright and a Chromium install."""

import json
import os
from pathlib import Path
import sys
import threading
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from visualizer.server import create_server
from visualizer import runtime
from red_black_trees import Node, Tree, delete, insert

delete = runtime.with_deletion_cleanup(delete)


def fixture(children, detached=()):
    """Wire snapshots keep browser checks independent of algorithm edits."""
    parents = {target: source for source, links in children.items() for target in links if target is not None}
    return {
        'status': 'paused', 'root': '20', 'warnings': [], 'nil_names': [], 'root_is_nil': False, 'nil_address': None,
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
                    # Tall alias lists reserve extra vertical space while the
                    # body keeps its size. Test both visible rectangles.
                    regions = [(node['x'], node['y'], node.get('bodyWidth', node['width']),
                                node.get('bodyHeight', node['height']))]
                    if node.get('label'):
                        label = node['label']
                        regions.append((node['x'] + label['x'], node['y'] + label['y'],
                                        label['width'], label['height']))
                    for x, y, width, height in regions:
                        left, top = x + .1, y + .1
                        right, bottom = x + width - .1, y + height - .1
                        hit = (left < a['x'] < right and max(a['y'], b['y']) > top and min(a['y'], b['y']) < bottom
                               if a['x'] == b['x'] else
                               top < a['y'] < bottom and max(a['x'], b['x']) > left and min(a['x'], b['x']) < right)
                        assert not hit, (edge['id'], node['id'], a, b)


def assert_same_tree(leaves, shared):
    """NIL convergence must never move the BST or reroute its real edges."""
    def positions(view):
        return {node['id']: {key: node[key] for key in ('x', 'y', 'width', 'height', 'bodyWidth', 'bodyHeight', 'label')}
                for node in view['nodes'] if not node.get('nil')}

    def routes(view):
        return {edge['id']: (edge['sections'], [{key: label[key] for key in ('text', 'x', 'y', 'width', 'height')}
                                              for label in edge['labels']])
                for edge in view['edges'] if edge.get('record')}

    assert positions(leaves) == positions(shared), (positions(leaves), positions(shared))
    assert routes(leaves) == routes(shared), (routes(leaves), routes(shared))


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
            assert page.locator('#nil-view-control').is_hidden()
            publish(state)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 6")
            # Names belong to external callouts, with a connector ending at
            # the body boundary. Keys, colors, and identities stay inside.
            assert page.locator('.node-label').count() == len(aliases)
            assert page.locator('.node > .names').count() == 0
            assert page.locator('.node-label').evaluate_all('''labels => labels.every(label => {
                const body = label.parentNode.querySelector('.node-body').getBBox();
                const box = label.querySelector('rect').getBBox();
                const rows = [...label.querySelectorAll('.names')].map(row => row.getBBox());
                const position = label.transform.baseVal.consolidate().matrix;
                const connector = label.parentNode.querySelector('.label-connector');
                return position.e > body.x + body.width && rows.every((row, index) =>
                    row.x >= 0 && row.x + row.width <= box.width &&
                    row.y >= 0 && row.y + row.height <= box.height &&
                    (index === 0 || row.y > rows[index - 1].y + rows[index - 1].height)) &&
                    Number(connector.getAttribute('x1')) === body.x + body.width &&
                    Number(connector.getAttribute('x2')) === position.e &&
                    Number(connector.getAttribute('y1')) === body.height / 2;
            })''')
            assert page.locator('.node[data-id="20"] .names').all_text_contents() == ['ROOT', 'tree_root', 'root_alias']
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
            many_aliases = json.loads(json.dumps(state))
            for node in many_aliases['nodes']:
                node['names'] = [f'alias_{i}' for i in range(10)]
            clrs = fixture({'26': ('17', '41'), '17': ('14', '21'), '14': ('10', '16'),
                            '10': ('7', '12'), '7': ('3', None), '3': (None, None),
                            '12': (None, None), '16': ('15', None), '15': (None, None),
                            '21': ('19', '23'), '19': (None, '20'), '20': (None, None),
                            '23': (None, None), '41': ('30', '47'), '30': ('28', '38'),
                            '28': (None, None), '38': ('35', '39'), '35': (None, None),
                            '39': (None, None), '47': (None, None)})
            clrs['root'] = '26'
            for node in clrs['nodes']:
                node['names'] = []
                node['parent_is_nil'] = node['id'] == '26'
            for sample in (state, fixture({'20': (None, None)}), many_aliases, clrs,
                           fixture({'20': ('10', '40'), '10': (None, '15'),
                                           '15': ('12', None), '12': (None, None),
                                           '40': (None, '50'), '50': (None, None)})):
                if sample is not many_aliases:
                    sample['nodes'][0]['names'] = ['root', 'long_local_variable_alias']
                geometry = page.evaluate('''async state => {
                    const {layout} = await import('./layout.js');
                    return await layout(state.nodes, state.edges, state.root);
                }''', sample)
                assert_clear_routes(geometry)
                shared = page.evaluate('''async state => {
                    const {layout} = await import('./layout.js');
                    return await layout(state.nodes, state.edges, state.root, {sharedNil: true});
                }''', sample)
                assert_same_tree(geometry, shared)
                assert_clear_routes(shared)
                by_id = {n['id']: n for n in geometry['nodes']}
                for edge in sample['edges']:
                    a, b = by_id[edge['source']], by_id[edge['target']]
                    ax, bx = a['x'] + a['bodyWidth']/2, b['x'] + b['bodyWidth']/2
                    assert bx < ax if edge['side'] == 'left' else bx > ax, edge
                    assert b['y'] > a['y'], edge
                groups = {g['id']: g for g in geometry['groups']}
                if 'detached' in groups:
                    assert groups['detached']['x'] > groups['attached']['x'] + groups['attached']['width']
            publish(many_aliases)
            page.wait_for_function("() => document.querySelectorAll('.node[data-id=\"20\"] .names').length === 11")
            assert page.locator('.node[data-id="20"] .names').all_text_contents() == ['ROOT'] + [f'alias_{i}' for i in range(10)]
            assert page.locator('.node-label').evaluate_all('''labels => labels.every(label => {
                const box = label.querySelector('rect').getBBox();
                return [...label.querySelectorAll('.names')].every(row => {
                    const text = row.getBBox();
                    return text.y >= 0 && text.y + text.height <= box.height;
                });
            })''')
            assert page.locator('.node-body').evaluate_all('bodies => bodies.every(body => body.getBBox().height === 84)')
            publish(state)
            page.wait_for_function("() => document.querySelectorAll('.node[data-id=\"20\"] .names').length === 3")
            # None-valued locals do not create a standalone NIL marker.
            none_state = json.loads(json.dumps(state))
            none_state['nil_names'] = ['alias', 'current_node']
            previous_revision = page.locator('#canvas').get_attribute('data-revision')
            publish(none_state)
            page.wait_for_function("revision => document.querySelector('#canvas').dataset.revision !== revision",
                                   arg=previous_revision)
            page.locator('#nil').uncheck()
            page.wait_for_function("() => document.querySelectorAll('.nil').length === 0")
            assert 'NIL · NONE' not in page.locator('#viewport').text_content()
            assert '6 live nodes' in page.locator('#counts').text_content()
            camera = page.locator('#viewport').get_attribute('transform')
            page.locator('#nil').check()
            page.wait_for_function("() => document.querySelectorAll('.nil').length > 0")
            assert page.locator('.nil[data-id="nil:locals"]').count() == 0
            assert page.locator('#viewport').get_attribute('transform') == camera
            page.locator('#nil').uncheck()
            page.wait_for_function("() => document.querySelectorAll('.nil').length === 0")

            # The insertion cursor belongs to a specific NIL child of its
            # parent. Both sides must retain the parent edge with leaves hidden.
            for side in ('left', 'right'):
                insertion = json.loads(json.dumps(state))
                insertion['nil_names'] = ['other_none_local']
                insertion['nodes'][1]['nil_labels'] = {side: ['current_node']}
                insertion['nodes'][1]['names'] = ['parent_of_new_node']
                publish(insertion)
                page.wait_for_function('''id => document.querySelector('.named-nil')?.getAttribute('data-id') === id''',
                                       arg=f'10:nil:{side}')
                assert page.locator('.named-nil').count() == 1
                assert page.locator('.named-nil .names').all_text_contents() == ['current_node']
                assert page.locator('.edge.nil-edge').count() == 1
                assert page.locator('.nil[data-id="nil:locals"]').count() == 0
                geometry = page.evaluate('''async state => {
                    const {layout} = await import('./layout.js');
                    return await layout(state.nodes, state.edges, state.root);
                }''', insertion)
                assert_clear_routes(geometry)
                by_id = {node['id']: node for node in geometry['nodes']}
                parent, child = by_id['10'], by_id[f'10:nil:{side}']
                parent_x = parent['x'] + parent['bodyWidth'] / 2
                child_x = child['x'] + child['bodyWidth'] / 2
                assert child_x < parent_x if side == 'left' else child_x > parent_x
                assert child['y'] > parent['y'] + parent['bodyHeight']
                edge = next(edge for edge in geometry['edges'] if edge['id'] == f'10:nil:{side}:edge')
                assert edge['sections'][-1][-1] == {'x': child_x, 'y': child['y']}
                cursor_position = page.locator('.named-nil').get_attribute('transform')
                page.locator('#nil').check()
                page.wait_for_function("() => document.querySelectorAll('.nil').length > 1")
                assert page.locator('.named-nil').get_attribute('transform') == cursor_position
                page.locator('#nil').uncheck()
                page.wait_for_function("() => document.querySelectorAll('.nil').length === 1")
            page.locator('#fit').click()
            page.screenshot(path='/tmp/rb-visualizer-insertion-nil.png')

            empty = fixture({})
            empty.update(root=None, root_is_nil=True, nil_names=['current_node'])
            publish(empty)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 0")
            assert page.locator('#viewport > *').count() == 0
            camera = page.locator('#viewport').get_attribute('transform')
            page.locator('#fit').click()
            assert page.locator('#viewport').get_attribute('transform') == camera

            restored = json.loads(json.dumps(state))
            restored['nodes'][1]['names'].append('current_node')
            publish(restored)
            page.wait_for_function("() => document.querySelector('.node[data-id=\"10\"]')?.textContent.includes('current_node')")
            assert page.locator('.named-nil').count() == 0
            publish(state)
            page.wait_for_function("() => document.querySelectorAll('.node[data-id=\"10\"] .names').length === 1")
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
            shared_geometry = page.evaluate('''async state => {
                const {layout} = await import('./layout.js');
                return await layout(state.nodes, state.edges, state.root, {sharedNil: true});
            }''', state)
            assert len([node for node in shared_geometry['nodes'] if node.get('shared')]) == 1
            assert len([edge for edge in shared_geometry['edges'] if edge.get('record')]) == len(state['edges'])
            assert_same_tree(geometry, shared_geometry)
            assert_clear_routes(shared_geometry)
            assert page.locator('#viewport').get_attribute('transform') == before
            assert page.locator('.edge.warning').count() > 0
            page.screenshot(path='/tmp/rb-visualizer-preview.png')

            # Reproduce the reported screenshot with actual Python snapshots:
            # the shared black sentinel must never become a cyclic live node.
            runtime.install_tracking(Node)
            tree = Tree()
            runtime.register_tree(tree)
            first, second = Node(30), Node(20)
            insert(tree, first)
            insert(tree, second)
            actual = runtime.snapshot({'first': first, 'second': second})
            assert actual['warnings'] == [], actual
            assert len(actual['nodes']) == 2
            publish(actual)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 2")
            assert page.locator('.node.warning').count() == 0
            assert page.locator('.edge.warning').count() == 0
            assert page.locator('#warnings').is_hidden()
            assert page.locator('.node .key').all_text_contents() == ['30', '20']
            assert page.locator('.node[data-id="' + actual['root'] + '"] > title').text_content().splitlines()[2] == 'parent: NIL'
            page.locator('#nil').check()
            page.wait_for_function("() => document.querySelectorAll('.nil').length === 3")
            nil_titles = page.locator('.nil > title').all_text_contents()
            assert all(title == f"Shared NIL sentinel · {actual['nil_address']}" for title in nil_titles)
            assert page.locator('.nil[data-id="nil:locals"]').count() == 0
            page.locator('#fit').click()
            page.screenshot(path='/tmp/rb-visualizer-sentinel.png')

            # The sub-view draws all three NIL child pointers and root.parent
            # into the same object, without adding a live node or a warning.
            assert page.locator('#nil-view-control').is_visible()
            page.locator('#nil-view').select_option('shared')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'shared'")
            assert page.locator('.nil').count() == 1
            assert page.locator('.shared-nil').count() == 1
            assert page.locator('.node').count() == 2
            assert page.locator('.edge.nil-edge').count() == 4
            assert page.locator(f'.parent-edge[data-source="{actual["root"]}"][data-pointer="parent"]').count() == 1
            assert page.locator('.nil-edge').evaluate_all('edges => edges.every(edge => edge.dataset.target === "nil:shared")')
            assert page.locator('.parent-label').all_text_contents() == ['parent']
            assert page.locator('.node.warning, .edge.warning').count() == 0
            assert '2 live nodes' in page.locator('#counts').text_content()
            assert 'Blue: parent' in page.locator('#legend').text_content()
            shared_geometry = page.evaluate('''async state => {
                const {layout} = await import('./layout.js');
                return await layout(state.nodes, state.edges, state.root, {sharedNil: true});
            }''', actual)
            assert len([node for node in shared_geometry['nodes'] if node.get('nil')]) == 1
            assert_clear_routes(shared_geometry)

            # The reported five-node example must keep 30 to the right of 28.
            # Compare the complete real-node geometry and real-edge routing.
            presentation = fixture({'20': ('10', '28'), '10': (None, None),
                                    '28': ('25', '30'), '25': (None, None), '30': (None, None)})
            aliases = {'20': 'second', '10': 'third', '28': 'fifth', '25': 'fourth', '30': 'first'}
            for node in presentation['nodes']:
                node['names'] = [aliases[node['id']]]
                node['parent_is_nil'] = node['id'] == '20'
                node['color'] = 'red' if node['id'] in ('25', '30') else 'black'
            views = page.evaluate('''async state => {
                const {layout} = await import('./layout.js');
                return [await layout(state.nodes, state.edges, state.root),
                    await layout(state.nodes, state.edges, state.root, {sharedNil: true})];
            }''', presentation)
            assert_same_tree(*views)
            assert_clear_routes(views[1])
            by_key = {node['record']['key']: node for node in views[1]['nodes'] if not node.get('nil')}
            assert by_key['10']['x'] < by_key['20']['x'] < by_key['28']['x']
            assert by_key['25']['x'] < by_key['28']['x'] < by_key['30']['x']
            publish(presentation)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 5")
            page.locator('#fit').click()
            page.screenshot(path='/tmp/rb-visualizer-shared-nil.png')
            publish(actual)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 2")
            camera = page.locator('#viewport').get_attribute('transform')
            page.locator('#nil').uncheck()
            page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'leaves'")
            assert page.locator('.shared-nil, .parent-edge').count() == 0
            assert page.locator('#nil-view-control').is_hidden()
            assert page.locator('#viewport').get_attribute('transform') == camera
            page.locator('#nil').check()
            page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'shared'")
            assert page.locator('.shared-nil').count() == 1
            page.locator('#nil-view').select_option('leaves')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'leaves'")
            assert page.locator('.nil').count() == 3
            assert page.locator('.parent-edge').count() == 0
            assert page.locator('#viewport').get_attribute('transform') == camera

            third = Node(10)
            actual = runtime.snapshot({'current_node': tree.nil, 'cursor_alias': tree.nil,
                                       'parent_of_new_node': second, 'new_node': third})
            parent = next(node for node in actual['nodes'] if node['names'] == ['parent_of_new_node'])
            assert parent['nil_labels'] == {'left': ['current_node']}
            publish(actual)
            page.wait_for_function('''id => document.querySelector('.named-nil')?.getAttribute('data-id') === id''',
                                   arg=f"{parent['id']}:nil:left")
            page.locator('#nil-view').select_option('shared')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'shared'")
            assert page.locator('.nil').count() == 1
            assert page.locator('.shared-nil .names').all_text_contents() == ['current_node', 'cursor_alias']
            assert page.locator('.node.warning, .edge.warning').count() == 0
            page.locator('#nil-view').select_option('leaves')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'leaves'")
            page.locator('#nil').uncheck()
            page.wait_for_function("() => document.querySelectorAll('.nil').length === 1")
            assert page.locator('.named-nil .names').all_text_contents() == ['current_node']
            assert page.locator('.edge.nil-edge').count() == 1
            assert page.locator('.node.warning').count() == 0

            insert(tree, third)
            delete(tree, second)
            actual = runtime.snapshot({'removed': second})
            assert actual['warnings'] == [], actual
            previous_revision = page.locator('#canvas').get_attribute('data-revision')
            publish(actual)
            page.wait_for_function("revision => document.querySelector('#canvas').dataset.revision !== revision",
                                   arg=previous_revision)
            assert page.locator('.node').count() == 3  # Includes the live detached node.
            assert page.locator('.node.warning').count() == 0
            assert page.locator('.edge.warning').count() == 0
            assert page.locator('.named-nil').count() == 0
            page.locator('#nil').check()
            page.locator('#nil-view').select_option('shared')
            page.wait_for_function("() => document.querySelector('#canvas').dataset.nilView === 'shared'")
            assert page.locator('.shared-nil').count() == 1
            # Two rooted nodes and one detached node: five missing children,
            # plus the root and detached node's NIL parent pointers.
            assert page.locator('.edge.nil-edge').count() == 7
            assert page.locator('.parent-edge').count() == 2
            assert page.locator('.node.warning, .edge.warning').count() == 0

            # An empty tree still has its single sentinel in this explicit view.
            empty['nil_address'] = actual['nil_address']
            publish(empty)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 0")
            assert page.locator('.shared-nil').count() == 1
            assert page.locator('.shared-nil .names').all_text_contents() == ['ROOT', 'current_node']
            assert page.locator('.edge').count() == 0
            page.locator('#fit').click()
            assert page.locator('.shared-nil').evaluate('''node => {
                const box = node.getBoundingClientRect();
                const canvas = document.querySelector('#canvas').getBoundingClientRect();
                return box.left >= canvas.left && box.right <= canvas.right &&
                    box.top >= canvas.top && box.bottom <= canvas.bottom;
            }''')
            publish(actual)
            page.wait_for_function("() => document.querySelectorAll('.node').length === 3")
            publish({'status': 'running'})
            page.wait_for_function("() => document.querySelector('#status').textContent === 'Running'")
            publish({'status': 'ended'})
            page.wait_for_function("() => document.querySelector('#status').textContent === 'Ended'")
            assert not errors, errors
            browser.close()
            print('PASS: shared-sentinel sub-view and root.parent, actual snapshots, external alias lists, NIL child labels, ordered tree layout, edge clearance, NIL stability, pan/zoom, malformed graphs, session status')
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
