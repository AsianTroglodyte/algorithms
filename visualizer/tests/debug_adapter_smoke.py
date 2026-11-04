"""Exercise real debugpy pauses and the exact snapshot expression used by Emacs.

Run from the repository root: .venv/bin/python visualizer/tests/debug_adapter_smoke.py
"""

import json
from pathlib import Path
import queue
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]


class Adapter:
    def __init__(self):
        self.process = subprocess.Popen([sys.executable, '-m', 'debugpy.adapter'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.messages = queue.Queue()
        self.pending = []
        self.sequence = 0
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        while True:
            headers = {}
            while line := self.process.stdout.readline():
                if line in (b'\r\n', b'\n'):
                    break
                key, value = line.decode().split(':', 1)
                headers[key.lower()] = value.strip()
            if not headers:
                return
            self.messages.put(json.loads(self.process.stdout.read(int(headers['content-length']))))

    def send(self, command, arguments):
        self.sequence += 1
        message = json.dumps({'seq': self.sequence, 'type': 'request', 'command': command, 'arguments': arguments}).encode()
        self.process.stdin.write(f'Content-Length: {len(message)}\r\n\r\n'.encode() + message)
        self.process.stdin.flush()
        return self.sequence

    def take(self, predicate):
        for i, message in enumerate(self.pending):
            if predicate(message):
                return self.pending.pop(i)
        while True:
            message = self.messages.get(timeout=25)
            if predicate(message):
                return message
            self.pending.append(message)

    def response(self, sequence):
        message = self.take(lambda m: m.get('request_seq') == sequence)
        assert message.get('success'), message
        return message.get('body', {})

    def request(self, command, **arguments):
        return self.response(self.send(command, arguments))

    def event(self, name):
        return self.take(lambda m: m.get('event') == name).get('body', {})

    def snapshot(self, thread):
        frame = self.request('stackTrace', threadId=thread, startFrame=0, levels=1)['stackFrames'][0]
        body = self.request('evaluate', frameId=frame['id'], context='repl', expression="__import__('visualizer.runtime', fromlist=['snapshot_wire']).snapshot_wire(locals())")
        return json.loads(bytes.fromhex(body['result'][1:-1])), frame


def main():
    adapter = Adapter()
    try:
        adapter.request('initialize', adapterID='python', clientID='tree-test', linesStartAt1=True, columnsStartAt1=True)
        launch = adapter.send('launch', {'module': 'examples.visualizer_demo', 'cwd': str(ROOT), 'python': sys.executable, 'console': 'internalConsole', 'stopOnEntry': True, 'justMyCode': True})
        adapter.event('initialized')
        source = (ROOT / 'red_black_trees.py').read_text().splitlines()
        line = next(i+1 for i, text in enumerate(source) if text.strip() == 'rotate_down.parent = rotate_up')
        adapter.request('setBreakpoints', source={'path': str(ROOT / 'red_black_trees.py')}, breakpoints=[{'line': line}])
        adapter.request('setExceptionBreakpoints', filters=['uncaught'])
        adapter.request('configurationDone')
        adapter.response(launch)
        thread = adapter.event('stopped')['threadId']
        state, _ = adapter.snapshot(thread)
        assert state['status'] == 'waiting', state
        adapter.request('continue', threadId=thread)
        thread = adapter.event('stopped')['threadId']
        state, frame = adapter.snapshot(thread)
        assert frame['name'] == 'left_rotate', frame
        assert state['warnings'], 'Expected intermediate pointer inconsistencies'
        assert any('rotate_down' in n['names'] for n in state['nodes'])
        assert any('rotate_up' in n['names'] for n in state['nodes'])
        adapter.request('next', threadId=thread)
        thread = adapter.event('stopped')['threadId']
        after, _ = adapter.snapshot(thread)
        assert len(after['warnings']) < len(state['warnings']), (state, after)
        adapter.request('setBreakpoints', source={'path': str(ROOT / 'red_black_trees.py')}, breakpoints=[])
        adapter.request('continue', threadId=thread)
        adapter.event('terminated')
        print('PASS: waiting, real rotation pause, stopped-frame names, line step, termination')
    finally:
        adapter.process.terminate()
        adapter.process.wait(timeout=10)

    adapter = Adapter()
    try:
        adapter.request('initialize', adapterID='python', clientID='tree-test')
        launch = adapter.send('launch', {'program': str(ROOT / 'visualizer/tests/exception_fixture.py'), 'cwd': str(ROOT), 'python': sys.executable, 'console': 'internalConsole', 'justMyCode': True})
        adapter.event('initialized')
        adapter.request('setExceptionBreakpoints', filters=['uncaught'])
        adapter.request('configurationDone')
        adapter.response(launch)
        stopped = adapter.event('stopped')
        assert stopped['reason'] == 'exception', stopped
        state, _ = adapter.snapshot(stopped['threadId'])
        assert state['nodes'][0]['names'] == ['alias', 'node'], state
        adapter.request('continue', threadId=stopped['threadId'])
        adapter.event('terminated')
        print('PASS: uncaught exception pause and stopped-frame aliases')
    finally:
        adapter.process.terminate()
        adapter.process.wait(timeout=10)


if __name__ == '__main__':
    main()
