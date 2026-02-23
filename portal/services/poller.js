const EventEmitter = require('node:events');
const config = require('../config/default');
const github = require('./github');

const POLL_RUN_COUNT = 5;

class ArtifactPoller extends EventEmitter {
  constructor(options = {}) {
    super();
    this.intervalMs = options.intervalMs || config.polling.intervalMs;
    this.lastKnownRunId = null;
    this.timer = null;
    this.running = false;
    this.lastPollTime = null;
    this.lastError = null;
    this.clients = new Set();
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.poll();
    this.timer = setInterval(() => this.poll(), this.intervalMs);
  }

  stop() {
    this.running = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  addClient(res) {
    this.clients.add(res);
    res.on('close', () => this.clients.delete(res));
  }

  broadcast(event, data) {
    const message = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const client of this.clients) {
      try {
        client.write(message);
      } catch {
        this.clients.delete(client);
      }
    }
  }

  async poll() {
    try {
      const data = await github.listWorkflowRuns(1, POLL_RUN_COUNT);
      const runs = data.workflow_runs || [];
      this.lastPollTime = new Date().toISOString();
      this.lastError = null;

      if (runs.length === 0) return;

      const latestRun = runs[0];

      if (this.lastKnownRunId && latestRun.id !== this.lastKnownRunId) {
        const artifactsData = await github.listRunArtifacts(latestRun.id);
        const artifacts = (artifactsData.artifacts || []).map((a) => ({
          id: a.id,
          name: a.name,
          sizeInBytes: a.size_in_bytes,
          expired: a.expired,
          createdAt: a.created_at,
        }));

        const payload = {
          run: {
            id: latestRun.id,
            runNumber: latestRun.run_number,
            status: latestRun.status,
            conclusion: latestRun.conclusion,
            createdAt: latestRun.created_at,
            event: latestRun.event,
            headBranch: latestRun.head_branch,
          },
          artifacts,
          detectedAt: this.lastPollTime,
        };

        this.emit('newRun', payload);
        this.broadcast('newRun', payload);
      }

      this.lastKnownRunId = latestRun.id;
    } catch (err) {
      this.lastError = err.message;
      this.emit('error', err);
    }
  }

  getStatus() {
    return {
      running: this.running,
      lastPollTime: this.lastPollTime,
      lastKnownRunId: this.lastKnownRunId,
      lastError: this.lastError,
      connectedClients: this.clients.size,
      intervalMs: this.intervalMs,
    };
  }
}

const poller = new ArtifactPoller();

module.exports = poller;
