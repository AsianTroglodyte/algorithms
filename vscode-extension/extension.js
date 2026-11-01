'use strict';

const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const {DebugBridge} = require('./bridge');
const {Companion} = require('./companion');

let shutdown;

function activate(context) {
  const output = vscode.window.createOutputChannel('Red-black Tree');
  const log = message => output.appendLine(message);
  let companion;
  let bridge;
  let preparing = false;

  const isRepository = folder => folder && fs.existsSync(path.join(folder.uri.fsPath, 'visualizer', 'server.py'));
  const busy = () => preparing || (bridge && !bridge.ended);
  const report = error => {
    log(error.stack || error.message);
    void vscode.window.showErrorMessage(`Red-black Tree: ${error.message}`);
  };
  const open = async () => {
    if (!companion?.url) throw new Error('Start with "Red-black Tree: Debug Demo" first');
    const uri = await vscode.env.asExternalUri(vscode.Uri.parse(companion.url));
    if (!await vscode.env.openExternal(uri)) throw new Error(`Could not open the browser. Open ${uri.toString()} manually`);
  };

  const provider = {
    async resolveDebugConfigurationWithSubstitutedVariables(folder, config) {
      if (!config.rbVisualizer) return config;
      if (busy()) {
        report(new Error('End the current tree debug session before launching another'));
        return undefined;
      }
      preparing = true;
      try {
        if (!isRepository(folder)) throw new Error('Open the red_black_trees repository folder in VS Code first');
        const root = folder.uri.fsPath;
        const configured = vscode.workspace.getConfiguration('rbVisualizer', folder.uri).get('python', '');
        let python = configured || config.python || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
        if (python.startsWith('.')) python = path.resolve(root, python);
        companion?.stop();
        bridge = undefined;
        companion = new Companion(python, root, log, message => report(new Error(message)));
        await companion.start();
        log(`Companion ready: ${companion.url}`);
        await open();
        return {...config, python};
      } catch (error) {
        companion?.stop();
        report(error);
        return undefined;
      } finally {
        preparing = false;
      }
    },
  };

  context.subscriptions.push(
    output,
    vscode.debug.registerDebugConfigurationProvider('debugpy', provider),
    vscode.debug.registerDebugAdapterTrackerFactory('debugpy', {
      createDebugAdapterTracker(session) {
        if (!session.configuration.rbVisualizer || !companion?.url) return undefined;
        const target = companion;
        bridge = new DebugBridge(session, state => target.publish(state), log);
        return bridge.tracker();
      },
    }),
    vscode.debug.onDidTerminateDebugSession(session => {
      if (bridge?.session.id === session.id) bridge.end();
    }),
    vscode.commands.registerCommand('rbVisualizer.debug', async () => {
      try {
        const folders = (vscode.workspace.workspaceFolders || []).filter(isRepository);
        const selected = folders.length > 1 ? await vscode.window.showQuickPick(
          folders.map(folder => ({label: folder.name, folder})),
          {placeHolder: 'Choose the red_black_trees repository'},
        ) : undefined;
        const folder = folders.length === 1 ? folders[0] : selected?.folder;
        if (!folder) {
          if (!folders.length) throw new Error('Open the red_black_trees repository folder in VS Code first');
          return;
        }
        await vscode.debug.startDebugging(folder, {
          type: 'debugpy', request: 'launch', name: 'Red-black tree demo',
          program: path.join(folder.uri.fsPath, 'visualizer_demo.py'),
          cwd: folder.uri.fsPath, console: 'internalConsole', stopOnEntry: true,
          justMyCode: true, rbVisualizer: true,
        });
      } catch (error) { report(error); }
    }),
    vscode.commands.registerCommand('rbVisualizer.open', async () => {
      try { await open(); } catch (error) { report(error); }
    }),
    vscode.commands.registerCommand('rbVisualizer.stop', () => {
      if (busy()) return report(new Error('End the Python debug session before stopping the companion server'));
      companion?.stop();
    }),
    {dispose: () => companion?.stop()},
  );
  shutdown = () => companion?.stop();
  return {getVisualizerUrl: () => companion?.url};
}

function deactivate() { shutdown?.(); }

module.exports = {activate, deactivate};
