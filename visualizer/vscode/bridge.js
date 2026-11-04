'use strict';

const SNAPSHOT_EXPRESSION = "__import__('visualizer.runtime', fromlist=['snapshot_wire']).snapshot_wire(locals())";
const RESUME_REQUESTS = new Set([
  'continue', 'next', 'stepIn', 'stepOut', 'stepBack', 'reverseContinue', 'restartFrame',
]);

// No editor API here: exercise this same bridge against real debugpy in tests.
class DebugBridge {
  constructor(session, publish, log = () => {}) {
    this.session = session;
    this.publish = publish;
    this.log = log;
    this.generation = 0;
    this.ended = false;
    this.pendingSnapshot = Promise.resolve();
  }

  send(state) {
    return Promise.resolve().then(() => this.publish(state)).catch(error => {
      this.log(`Could not publish tree state: ${error.message}`);
    });
  }

  running() {
    if (this.ended) return;
    ++this.generation;
    void this.send({status: 'running'});
  }

  end() {
    if (this.ended) return;
    this.ended = true;
    ++this.generation;
    void this.send({status: 'ended'});
  }

  async snapshot(threadId) {
    const generation = ++this.generation;
    const current = () => !this.ended && generation === this.generation;
    try {
      if (!Number.isInteger(threadId)) throw new Error('Debugger did not identify a stopped thread');
      const body = await this.session.customRequest('stackTrace', {threadId, startFrame: 0, levels: 1});
      if (!current()) return;
      const frame = body.stackFrames?.[0];
      if (!frame) throw new Error('No stopped frame available');
      const result = await this.session.customRequest('evaluate', {
        frameId: frame.id, context: 'repl', expression: SNAPSHOT_EXPRESSION,
      });
      if (!current()) return;
      const match = /^(['"])([0-9a-f]+)\1$/i.exec(result.result);
      if (!match || match[2].length % 2) throw new Error('Unexpected snapshot response from Python');
      const state = JSON.parse(Buffer.from(match[2], 'hex').toString('utf8'));
      if (!state || !['paused', 'waiting'].includes(state.status)) {
        throw new Error('Invalid tree snapshot');
      }
      await this.send(state);
    } catch (error) {
      if (current()) await this.send({status: 'error', message: error.message});
    }
  }

  tracker() {
    return {
      // Invalidate before the adapter answers a step/continue request as well.
      onWillReceiveMessage: message => {
        if (message.type === 'request' && RESUME_REQUESTS.has(message.command)) this.running();
      },
      onDidSendMessage: message => {
        if (message.type !== 'event' || this.ended) return;
        switch (message.event) {
          case 'stopped':
            this.pendingSnapshot = this.snapshot(message.body?.threadId);
            break;
          case 'continued': this.running(); break;
          case 'terminated':
          case 'exited': this.end(); break;
        }
      },
      onError: error => {
        if (!this.ended) {
          ++this.generation;
          void this.send({status: 'error', message: error.message});
        }
      },
      onExit: () => this.end(),
    };
  }
}

module.exports = {DebugBridge, SNAPSHOT_EXPRESSION};
