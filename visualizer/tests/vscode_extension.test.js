'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

test('extension registers commands, launches only marked sessions, and cleans up', async t => {
  const commands = new Map();
  const registrations = {};
  const starts = [];
  const opened = [];
  const errors = [];
  const companions = [];
  const folder = {name: 'red_black_trees', uri: {fsPath: path.resolve(__dirname, '../..')}};
  const disposable = {dispose() {}};
  class Companion {
    constructor(python, root) { this.python = python; this.root = root; this.states = []; companions.push(this); }
    async start() { this.url = 'http://127.0.0.1:12345/token/'; return this.url; }
    async publish(state) { this.states.push(state); }
    stop() { this.url = undefined; }
  }
  const vscode = {
    window: {
      createOutputChannel: () => ({...disposable, appendLine() {}}),
      showErrorMessage: message => errors.push(message),
    },
    workspace: {workspaceFolders: [folder], getConfiguration: () => ({get: () => ''})},
    commands: {registerCommand: (name, callback) => { commands.set(name, callback); return disposable; }},
    debug: {
      registerDebugConfigurationProvider: (type, provider) => { registrations.provider = provider; assert.equal(type, 'debugpy'); return disposable; },
      registerDebugAdapterTrackerFactory: (type, factory) => { registrations.factory = factory; assert.equal(type, 'debugpy'); return disposable; },
      onDidTerminateDebugSession: callback => { registrations.terminate = callback; return disposable; },
      startDebugging: async (workspace, config) => { starts.push({workspace, config}); return true; },
    },
    Uri: {parse: value => value},
    env: {asExternalUri: async uri => uri, openExternal: async uri => { opened.push(uri); return true; }},
  };
  const original = Module._load;
  Module._load = function(name, parent, isMain) {
    if (name === 'vscode') return vscode;
    if (name === './companion' && parent.filename.endsWith('extension.js')) return {Companion};
    return original.call(this, name, parent, isMain);
  };
  const extensionPath = require.resolve('../vscode/extension');
  delete require.cache[extensionPath];
  const extension = require(extensionPath);
  Module._load = original;
  t.after(() => { delete require.cache[extensionPath]; extension.deactivate(); });
  const context = {subscriptions: []};
  extension.activate(context);
  assert.equal(commands.size, 3);

  const ordinary = {type: 'debugpy', name: 'ordinary Python'};
  assert.equal(await registrations.provider.resolveDebugConfigurationWithSubstitutedVariables(folder, ordinary), ordinary);
  assert.equal(companions.length, 0);
  assert.equal(registrations.factory.createDebugAdapterTracker({configuration: ordinary}), undefined);

  await commands.get('rbVisualizer.debug')();
  assert.equal(starts[0].workspace, folder);
  assert.equal(starts[0].config.rbVisualizer, true);
  assert.equal(starts[0].config.stopOnEntry, true);
  assert.equal(starts[0].config.module, 'examples.visualizer_demo');
  const config = await registrations.provider.resolveDebugConfigurationWithSubstitutedVariables(folder, starts[0].config);
  assert.match(config.python, /\.venv[/\\](bin[/\\]python|Scripts[/\\]python.exe)$/);
  assert.equal(opened.length, 1);
  const session = {id: 'session-1', configuration: config};
  const tracker = registrations.factory.createDebugAdapterTracker(session);
  assert.ok(tracker);
  await commands.get('rbVisualizer.stop')();
  assert.match(errors.pop(), /End the Python debug session/);
  assert.ok(companions[0].url);
  assert.equal(await registrations.provider.resolveDebugConfigurationWithSubstitutedVariables(folder, config), undefined);
  assert.match(errors.pop(), /End the current tree debug session/);
  registrations.terminate({id: 'another-session'});
  assert.equal(companions[0].states.length, 0);
  registrations.terminate(session);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(companions[0].states, [{status: 'ended'}]);
  await commands.get('rbVisualizer.open')();
  assert.equal(opened.length, 2);
  await commands.get('rbVisualizer.stop')();
  assert.equal(companions[0].url, undefined);
  await commands.get('rbVisualizer.open')();
  assert.match(errors.pop(), /Start with/);

  // A new session creates a fresh server and can start after termination.
  await registrations.provider.resolveDebugConfigurationWithSubstitutedVariables(folder, config);
  assert.equal(companions.length, 2);
  extension.deactivate();
  assert.equal(companions[1].url, undefined);
  assert.deepEqual(errors, []);
});
