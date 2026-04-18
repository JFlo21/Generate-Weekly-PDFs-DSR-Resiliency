/**
 * Minimal in-memory LRU cache with optional TTL.
 *
 * Used by:
 *   - services/artifactCache.js  (parsed GitHub artifact zips)
 *   - services/searchIndex.js    (tokenized content index over recent runs)
 *
 * No external dependency — we deliberately keep this in-process so the entire
 * search/preview path lives inside the Render Web Service (per the transition
 * plan, docs/railway-to-render-transition-plan.md § "Search / preview backend").
 */

class LRUCache {
  /**
   * @param {object} [opts]
   * @param {number} [opts.max=100]   maximum entries
   * @param {number} [opts.ttlMs=0]   per-entry TTL in ms; 0 = no expiry
   */
  constructor({ max = 100, ttlMs = 0 } = {}) {
    this.max = max;
    this.ttlMs = ttlMs;
    // Map preserves insertion order, which we use as the recency order.
    this.store = new Map();
  }

  _expired(entry) {
    return this.ttlMs > 0 && Date.now() - entry.t > this.ttlMs;
  }

  get(key) {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (this._expired(entry)) {
      this.store.delete(key);
      return undefined;
    }
    // Refresh recency — delete then reinsert.
    this.store.delete(key);
    this.store.set(key, entry);
    return entry.v;
  }

  has(key) {
    const entry = this.store.get(key);
    if (!entry) return false;
    if (this._expired(entry)) {
      this.store.delete(key);
      return false;
    }
    return true;
  }

  set(key, value) {
    if (this.store.has(key)) {
      this.store.delete(key);
    } else if (this.store.size >= this.max) {
      // Drop least-recently-used — first key in insertion order.
      const oldest = this.store.keys().next().value;
      if (oldest !== undefined) this.store.delete(oldest);
    }
    this.store.set(key, { v: value, t: Date.now() });
    return value;
  }

  delete(key) {
    return this.store.delete(key);
  }

  clear() {
    this.store.clear();
  }

  get size() {
    return this.store.size;
  }

  keys() {
    return Array.from(this.store.keys());
  }

  stats() {
    return {
      size: this.store.size,
      max: this.max,
      ttlMs: this.ttlMs,
    };
  }
}

module.exports = { LRUCache };
