'use strict';

// Run inside a real VS Code extension host; see README for the CLI command.
const vscode = require('vscode');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

async function until(description, predicate) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    const value = await predicate();
    if (value) return value;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out: ${description}`);
}

async function run() {
  const root = vscode.workspace.workspaceFolders[0].uri.fsPath;
  const source = path.join(root, 'red_black_trees.py');
  const line = fs.readFileSync(source, 'utf8').split('\n').findIndex(text => text.trim() === 'rotate_down.parent = rotate_up');
  const breakpoint = new vscode.SourceBreakpoint(new vscode.Location(vscode.Uri.file(source), new vscode.Position(line, 0)));
  const extension = vscode.extensions.getExtension('rb-tree-local.rb-tree-visualizer');
  assert.ok(extension, 'Local extension is available');
  const api = await extension.activate();
  let session;
  const listener = vscode.debug.onDidStartDebugSession(started => {
    if (started.configuration.rbVisualizer) session = started;
  });
  const state = async () => {
    const url = api.getVisualizerUrl();
    assert.ok(url, 'Companion is running');
    return (await fetch(`${url}state`)).json();
  };
  vscode.debug.addBreakpoints([breakpoint]);
  try {
    await vscode.commands.executeCommand('rbVisualizer.debug');
    await until('debug session starts', () => session);
    await until('entry frame is suspended', async () => {
      const threads = await session.customRequest('threads');
      for (const thread of threads.threads) {
        try {
          const trace = await session.customRequest('stackTrace', {threadId: thread.id, levels: 1});
          if (trace.stackFrames?.length) return true;
        } catch { /* The entry stop may still be arriving. */ }
      }
      return false;
    });
    assert.equal((await state()).status, 'waiting');
    const {threads} = await session.customRequest('threads');
    await session.customRequest('continue', {threadId: threads[0].id});
    const before = await until('rotation snapshot in companion', async () => {
      const next = await state();
      return next.status === 'paused' && next.nodes.some(node => node.names.includes('rotate_down')) && next;
    });
    assert.ok(before.warnings.length);
    assert.ok(before.nodes.some(node => node.names.includes('rotate_up')));
    await session.customRequest('next', {threadId: threads[0].id});
    await until('step updates graph', async () => {
      const next = await state();
      return next.status === 'paused' && next.revision > before.revision && next.warnings.length < before.warnings.length;
    });
    const nodes = (await state()).nodes;
    await vscode.debug.stopDebugging(session);
    await until('ended status', async () => (await state()).status === 'ended');
    assert.deepEqual((await state()).nodes, nodes);
    await vscode.commands.executeCommand('rbVisualizer.stop');
    assert.equal(api.getVisualizerUrl(), undefined);
    console.log('PASS: real VS Code command, Python launch, breakpoint, graph POST, step, termination, server cleanup');
  } finally {
    listener.dispose();
    vscode.debug.removeBreakpoints([breakpoint]);
    if (session) await vscode.debug.stopDebugging(session);
    await vscode.commands.executeCommand('rbVisualizer.stop');
  }
}

module.exports = {run};
