'use strict';

const {spawn} = require('node:child_process');
const http = require('node:http');

class Companion {
  constructor(python, root, log = () => {}, onUnexpectedExit = () => {}) {
    this.python = python;
    this.root = root;
    this.log = log;
    this.onUnexpectedExit = onUnexpectedExit;
    this.queue = Promise.resolve();
    this.url = undefined;
    this.process = undefined;
  }

  async start() {
    const child = spawn(this.python, ['-u', '-m', 'visualizer.server'], {
      cwd: this.root, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    });
    this.process = child;
    child.stderr.on('data', data => this.log(data.toString().trimEnd()));
    child.on('exit', (code, signal) => {
      if (this.process !== child) return;
      const ready = Boolean(this.url);
      this.url = undefined;
      this.process = undefined;
      if (ready) this.onUnexpectedExit(`Tree companion server exited (${signal || code})`);
    });
    try {
      this.url = await new Promise((resolve, reject) => {
        let output = '';
        const timeout = setTimeout(() => finish(new Error('Tree companion server did not start within 10 seconds')), 10000);
        const finish = (error, url) => {
          clearTimeout(timeout);
          child.stdout.off('data', onData);
          child.off('error', onError);
          child.off('exit', onExit);
          if (error) reject(error); else resolve(url);
        };
        const onError = error => finish(new Error(`Could not start ${this.python}: ${error.message}`));
        const onExit = code => finish(new Error(`Tree companion exited before startup (code ${code}); see the Red-black Tree output channel`));
        const onData = data => {
          output = (output + data.toString()).slice(-65536);
          const match = /http:\/\/127\.0\.0\.1:[0-9]+\/[A-Za-z0-9_-]+\//.exec(output);
          if (match) finish(undefined, match[0]);
        };
        child.stdout.on('data', onData);
        child.once('error', onError);
        child.once('exit', onExit);
      });
      // A permanent listener also handles process errors after startup.
      child.on('error', error => this.log(error.message));
      return this.url;
    } catch (error) {
      this.stop();
      throw error;
    }
  }

  publish(state) {
    const url = this.url;
    // Preserve event order even if a POST is still in flight when Python resumes.
    const request = this.queue.then(() => new Promise((resolve, reject) => {
      if (!url || url !== this.url) return reject(new Error('Tree companion server is stopped'));
      const body = Buffer.from(JSON.stringify(state));
      const req = http.request(new URL('state', url), {
        method: 'POST', headers: {'Content-Type': 'application/json', 'Content-Length': body.length},
      }, response => {
        response.resume();
        response.on('end', () => response.statusCode === 200 ? resolve() : reject(new Error(`Companion HTTP ${response.statusCode}`)));
        response.on('error', reject);
      });
      req.setTimeout(2000, () => req.destroy(new Error('Tree companion request timed out')));
      req.on('error', reject);
      req.end(body);
    }));
    this.queue = request.catch(() => {});
    return request;
  }

  stop() {
    const child = this.process;
    this.process = undefined;
    this.url = undefined;
    child?.kill();
  }
}

module.exports = {Companion};
