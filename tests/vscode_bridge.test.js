'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {DebugBridge} = require('../vscode-extension/bridge');
const {Companion} = require('../vscode-extension/companion');

const ROOT = path.resolve(__dirname, '..');
const PYTHON = process.env.RB_TEST_PYTHON || path.join(ROOT, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const wire = state => ({result: `'${Buffer.from(JSON.stringify(state)).toString('hex')}'`});
const stopped = threadId => ({type: 'event', event: 'stopped', body: {threadId}});
const tick = () => new Promise(resolve => setImmediate(resolve));

test('late evaluations cannot overwrite running, ended, or a newer pause', async t => {
  for (const action of ['continue', 'ended', 'newer']) {
    await t.test(action, async () => {
      const states = [];
      let release;
      let evaluations = 0;
      const bridge = new DebugBridge({customRequest: async command => {
        if (command === 'stackTrace') return {stackFrames: [{id: 1}]};
        if (++evaluations === 1) return new Promise(resolve => { release = resolve; });
        return wire({status: 'paused', nodes: [{id: 'new'}]});
      }}, state => states.push(state));
      const tracker = bridge.tracker();
      tracker.onDidSendMessage(stopped(1));
      const oldSnapshot = bridge.pendingSnapshot;
      await tick();
      if (action === 'continue') tracker.onWillReceiveMessage({type: 'request', command: 'next'});
      if (action === 'ended') tracker.onExit();
      if (action === 'newer') {
        tracker.onDidSendMessage(stopped(1));
        await bridge.pendingSnapshot;
      }
      release(wire({status: 'paused', nodes: [{id: 'old'}]}));
      await oldSnapshot;
      assert.equal(states.length, 1);
      assert.equal(states[0].status, {continue: 'running', ended: 'ended', newer: 'paused'}[action]);
      if (action === 'newer') assert.equal(states[0].nodes[0].id, 'new');
    });
  }
});

test('resume while obtaining the frame prevents evaluation', async () => {
  let release;
  const commands = [];
  const states = [];
  const bridge = new DebugBridge({customRequest: command => {
    commands.push(command);
    return new Promise(resolve => { release = resolve; });
  }}, state => states.push(state));
  const tracker = bridge.tracker();
  tracker.onDidSendMessage(stopped(3));
  tracker.onDidSendMessage({type: 'event', event: 'continued'});
  release({stackFrames: [{id: 9}]});
  await bridge.pendingSnapshot;
  assert.deepEqual(commands, ['stackTrace']);
  assert.deepEqual(states, [{status: 'running'}]);
});

test('snapshot errors are visible and termination is idempotent', async () => {
  for (const result of [{result: 'not a Python hex string'}, {result: "'a'"}, wire({status: 'running'})]) {
    const states = [];
    const bridge = new DebugBridge({customRequest: async command => command === 'stackTrace' ? {stackFrames: [{id: 5}]} : result}, state => states.push(state));
    const tracker = bridge.tracker();
    tracker.onDidSendMessage(stopped(2));
    await bridge.pendingSnapshot;
    assert.equal(states[0].status, 'error');
    tracker.onDidSendMessage({type: 'event', event: 'terminated'});
    tracker.onExit();
    tracker.onDidSendMessage(stopped(2));
    await tick();
    assert.deepEqual(states.map(state => state.status), ['error', 'ended']);
  }
});

test('publish failures are logged without unhandled rejections', async () => {
  const logs = [];
  const bridge = new DebugBridge({}, async () => { throw new Error('disconnected'); }, message => logs.push(message));
  bridge.running();
  await tick();
  assert.match(logs[0], /disconnected/);
});

// Minimal DAP client: the extension's actual bridge uses this customRequest
// implementation in place of VS Code's, with a real debugpy process underneath.
class Adapter {
  constructor() {
    this.child = spawn(PYTHON, ['-m', 'debugpy.adapter'], {cwd: ROOT, stdio: ['pipe', 'pipe', 'pipe']});
    this.sequence = 0;
    this.buffer = Buffer.alloc(0);
    this.responses = new Map();
    this.events = [];
    this.waiters = [];
    this.stderr = '';
    this.child.stderr.on('data', data => { this.stderr += data; });
    this.child.stdout.on('data', data => this.read(data));
    this.child.on('error', error => this.fail(error));
    this.child.on('exit', () => this.fail(new Error(`debugpy exited: ${this.stderr}`)));
  }

  fail(error) {
    for (const pending of this.responses.values()) pending.reject(error);
    for (const waiter of this.waiters) waiter.reject(error);
    this.responses.clear();
    this.waiters = [];
  }

  read(data) {
    this.buffer = Buffer.concat([this.buffer, data]);
    while (true) {
      const headerEnd = this.buffer.indexOf('\r\n\r\n');
      if (headerEnd < 0) return;
      const length = Number(/Content-Length: (\d+)/i.exec(this.buffer.subarray(0, headerEnd).toString())[1]);
      if (this.buffer.length < headerEnd + 4 + length) return;
      const message = JSON.parse(this.buffer.subarray(headerEnd + 4, headerEnd + 4 + length));
      this.buffer = this.buffer.subarray(headerEnd + 4 + length);
      this.tracker?.onDidSendMessage(message);
      if (message.type === 'response') {
        const pending = this.responses.get(message.request_seq);
        if (!pending) continue;
        this.responses.delete(message.request_seq);
        if (message.success) pending.resolve(message.body || {});
        else pending.reject(new Error(message.message));
      } else if (message.type === 'event') {
        const index = this.waiters.findIndex(waiter => waiter.name === message.event);
        if (index >= 0) this.waiters.splice(index, 1)[0].resolve(message.body || {});
        else this.events.push(message);
      }
    }
  }

  customRequest(command, args = {}) {
    const seq = ++this.sequence;
    const message = {seq, type: 'request', command, arguments: args};
    this.tracker?.onWillReceiveMessage(message);
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(`DAP ${command} timed out: ${this.stderr}`)), 20000);
      this.responses.set(seq, {
        resolve: value => { clearTimeout(timeout); resolve(value); },
        reject: error => { clearTimeout(timeout); reject(error); },
      });
      const body = Buffer.from(JSON.stringify(message));
      this.child.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
      this.child.stdin.write(body);
    });
  }

  event(name) {
    const index = this.events.findIndex(message => message.event === name);
    if (index >= 0) return Promise.resolve(this.events.splice(index, 1)[0].body || {});
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(`DAP event ${name} timed out: ${this.stderr}`)), 20000);
      this.waiters.push({name,
        resolve: value => { clearTimeout(timeout); resolve(value); },
        reject: error => { clearTimeout(timeout); reject(error); },
      });
    });
  }

  async close() {
    if (this.closed) return;
    this.closed = true;
    this.fail(new Error('Test finished'));
    const exit = new Promise(resolve => this.child.once('exit', resolve));
    if (this.child.exitCode === null) {
      this.child.kill();
      await exit;
    }
  }
}

test('real debugpy → VS Code bridge → HTTP: shared NIL, rotation, step, restart, exception, end', {timeout: 90000}, async t => {
  const server = new Companion(PYTHON, ROOT);
  t.after(() => server.stop());
  const url = await server.start();
  const getState = async () => (await fetch(`${url}state`)).json();
  const fs = require('node:fs');
  const lines = fs.readFileSync(path.join(ROOT, 'red_black_trees.py'), 'utf8').split('\n');
  const rotationLine = lines.findIndex(line => line.trim() === 'rotate_down.parent = rotate_up') + 1;
  const insertLine = lines.findIndex(line => line.trim() === 'new_node.parent = parent_of_new_node') + 1;

  for (const fixture of ['visualizer_demo.py', 'tests/exception_fixture.py']) {
    const adapter = new Adapter();
    t.after(() => adapter.close());
    const bridge = new DebugBridge(adapter, state => server.publish(state));
    adapter.tracker = bridge.tracker();
    await server.publish({status: 'waiting', nodes: [], edges: [], warnings: []});
    await adapter.customRequest('initialize', {adapterID: 'python', clientID: 'vscode-tree-test', linesStartAt1: true, columnsStartAt1: true});
    const launch = adapter.customRequest('launch', {
      program: path.join(ROOT, fixture), cwd: ROOT, python: PYTHON,
      console: 'internalConsole', stopOnEntry: fixture === 'visualizer_demo.py', justMyCode: true,
    });
    // Attach the rejection handler immediately while waiting for initialized.
    launch.catch(() => {});
    await adapter.event('initialized');
    if (fixture === 'visualizer_demo.py') {
      await adapter.customRequest('setBreakpoints', {source: {path: path.join(ROOT, 'red_black_trees.py')}, breakpoints: [{line: insertLine}]});
    }
    await adapter.customRequest('setExceptionBreakpoints', {filters: ['uncaught']});
    await adapter.customRequest('configurationDone');
    await launch;
    let stop = await adapter.event('stopped');
    await bridge.pendingSnapshot;
    await server.queue;

    if (fixture === 'visualizer_demo.py') {
      assert.equal((await getState()).status, 'waiting');
      for (const emptyTree of [true, false]) {
        await adapter.customRequest('continue', {threadId: stop.threadId});
        stop = await adapter.event('stopped');
        await bridge.pendingSnapshot;
        await server.queue;
        const insertion = await getState();
        assert.ok(!insertion.nodes.some(node => node.names.includes('current_node')));
        assert.equal(insertion.root_is_nil, emptyTree);
        assert.ok(insertion.nil_address);
        assert.ok(!insertion.nodes.some(node => node.address === insertion.nil_address));
        if (emptyTree) {
          assert.ok(insertion.nil_names.includes('current_node'));
        } else {
          assert.ok(!insertion.nil_names.includes('current_node'));
          const parent = insertion.nodes.find(node => node.names.includes('parent_of_new_node'));
          assert.ok(parent);
          assert.deepEqual(parent.nil_labels, {left: ['current_node']});
          assert.ok(parent.nil_children.includes('left'));
        }
      }
      await adapter.customRequest('setBreakpoints', {source: {path: path.join(ROOT, 'red_black_trees.py')}, breakpoints: [{line: rotationLine}]});
      await adapter.customRequest('continue', {threadId: stop.threadId});
      stop = await adapter.event('stopped');
      await bridge.pendingSnapshot;
      await server.queue;
      const before = await getState();
      assert.equal(before.status, 'paused');
      assert.ok(before.warnings.length > 0);
      assert.ok(before.nodes.some(node => node.names.includes('rotate_down')));
      assert.ok(before.nodes.some(node => node.names.includes('rotate_up')));
      await adapter.customRequest('next', {threadId: stop.threadId});
      stop = await adapter.event('stopped');
      await bridge.pendingSnapshot;
      await server.queue;
      assert.ok((await getState()).warnings.length < before.warnings.length);
      await adapter.customRequest('setBreakpoints', {source: {path: path.join(ROOT, 'red_black_trees.py')}, breakpoints: []});
    } else {
      assert.equal(stop.reason, 'exception');
      assert.deepEqual((await getState()).nodes[0].names, ['alias', 'node']);
    }

    const nodes = (await getState()).nodes;
    await adapter.customRequest('continue', {threadId: stop.threadId});
    await adapter.event('terminated');
    await tick();
    await server.queue;
    assert.equal((await getState()).status, 'ended');
    assert.deepEqual((await getState()).nodes, nodes, 'final graph remains after termination');
    await adapter.close();
  }
});

test('companion startup failure explains a missing interpreter', async () => {
  const server = new Companion(path.join(ROOT, 'nonexistent-python'), ROOT);
  await assert.rejects(server.start(), /Could not start.*nonexistent-python/);
  assert.equal(server.url, undefined);
  assert.equal(server.process, undefined);
});
