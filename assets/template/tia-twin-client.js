/* TIA Web Twin browser client — WebSocket JSON <-> gateway <-> S7comm.
 * No dependencies. Mock mode uses a page-provided mock with the same tag contract.
 * Protocol: tia-web-twin/1 (see references/contract.md).
 */
(function (global) {
  'use strict';

  const PROTOCOL = 'tia-web-twin/1';
  const VERSION = '1.0.0';

  function bindingsMap(manifest) {
    const m = new Map();
    (manifest.bindings || []).forEach((b) => m.set(b.object + '.' + b.property, b.tag));
    return m;
  }

  class TiaTwinClient {
    constructor(opts = {}) {
      if (!opts.manifest) throw new Error('TiaTwinClient: manifest is required');
      this.manifest = opts.manifest;
      this.tags = new Map((this.manifest.tags || []).map((t) => [t.id, t]));
      this.bindingMap = bindingsMap(this.manifest);
      this.url = opts.url || 'ws://127.0.0.1:8765/ws';
      this.token = opts.token || '';
      this.autoReconnect = opts.autoReconnect !== false;
      this.mock = null;
      this._mockUnsub = null;
      this._listeners = new Map();
      this._pending = new Map();
      this._nextId = 0;
      this._closed = false;
      this._mockMode = false;
      this._reconnectTimer = null;
      this._heartbeatTimer = null;
      this._retry = 0;
      this._ws = null;
      this.values = {};
      this.status = 'idle';
      this.lastError = '';
      this.latencyMs = null;
      this.plcStatus = { state: 'unknown', message: '' };
      this.hello = null;
      this.seq = 0;
      if (opts.mock) this.useMock(opts.mock);
    }

    static async loadManifest(src) {
      if (src && typeof src === 'object') return src;
      const res = await fetch(src, { cache: 'no-store' });
      if (!res.ok) throw new Error('manifest HTTP ' + res.status);
      const data = await res.json();
      if (data.schema !== 'tia-web-twin/manifest@1') {
        throw new Error('不是 tia-web-twin/manifest@1 清单');
      }
      return data;
    }

    on(event, fn) {
      if (!this._listeners.has(event)) this._listeners.set(event, new Set());
      this._listeners.get(event).add(fn);
      return () => this._listeners.get(event).delete(fn);
    }

    _emit(event, data) {
      const set = this._listeners.get(event);
      if (!set) return;
      set.forEach((fn) => {
        try { fn(data, this); } catch (e) { console.error('[tia-twin] listener', event, e); }
      });
    }

    _setStatus(state, error = '') {
      const changed = state !== this.status || error !== this.lastError;
      this.status = state;
      this.lastError = error;
      if (changed) this._emit('status', { state, error });
    }

    _applyValues(values, source) {
      if (!values) return;
      if (source === 'snapshot') {
        this.values = Object.assign({}, values);
        this._emit('values', { values: this.values, changed: this.values, source });
        Object.keys(this.values).forEach((tag) => this._emit('tag:' + tag, this.values[tag]));
        return;
      }
      const changed = {};
      let any = false;
      Object.keys(values).forEach((k) => {
        if (this.values[k] !== values[k]) any = true;
        changed[k] = values[k];
        this.values[k] = values[k];
      });
      if (any) {
        this._emit('values', { values: this.values, changed, source });
        Object.keys(changed).forEach((tag) => this._emit('tag:' + tag, changed[tag]));
      }
    }

    useMock(mock) {
      this._teardownSocket();
      if (this._mockUnsub) { try { this._mockUnsub(); } catch (e) {} this._mockUnsub = null; }
      this.mock = mock || null;
      this._mockMode = !!mock;
      this.values = {};
      if (!mock) {
        this._setStatus('idle');
        this._emit('values', { values: {}, changed: {}, source: 'reset' });
        return;
      }
      this._closed = false;
      this.values = {};
      this._setStatus('mock');
      this.plcStatus = { state: 'mock', message: '本地模拟（不连 PLC）' };
      this._emit('plc', this.plcStatus);
      const initial = mock.getAll ? mock.getAll() : {};
      this._applyValues(initial, 'snapshot');
      if (mock.subscribe) {
        this._mockUnsub = mock.subscribe((changed) => this._applyValues(changed, 'mock'));
      }
    }

    setEndpoint(url, token) {
      this.url = url || this.url;
      this.token = token || '';
      if (!this._mockMode) {
        this.disconnect();
        this.connect();
      }
    }

    _url() {
      let url = this.url.trim();
      if (!/^wss?:\/\//i.test(url)) url = 'ws://' + url;
      if (!/\/ws(?:[?#]|$)/.test(url)) url = url.replace(/\/+$/, '') + '/ws';
      if (this.token) {
        const sep = url.indexOf('?') >= 0 ? '&' : '?';
        url += sep + 'token=' + encodeURIComponent(this.token);
      }
      return url;
    }

    connect() {
      if (this._mockMode) {
        this._setStatus('mock');
        return;
      }
      if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) return;
      this._closed = false;
      this._setStatus('connecting');
      let ws;
      try { ws = new WebSocket(this._url()); } catch (e) { this._setStatus('offline', String(e)); this._scheduleReconnect(); return; }
      this._ws = ws;
      ws.onopen = () => {
        this._retry = 0;
        this._setStatus('online');
        this._sendRaw({ type: 'hello', client: 'tia-web-twin-js/' + VERSION, protocol: PROTOCOL, project: this.manifest.project });
        this._startHeartbeat();
      };
      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch (e) { return; }
        this._onMessage(msg);
      };
      ws.onerror = () => {
        this._setStatus('offline', 'WebSocket 错误');
      };
      ws.onclose = (ev) => {
        this._stopHeartbeat();
        this._ws = null;
        this._rejectAll(new Error('gateway closed'));
        if (this._closed) { this._setStatus('idle'); return; }
        this._setStatus('offline', ev.reason || ('关闭码 ' + ev.code));
        this.plcStatus = { state: 'unknown', message: 'gateway 未连接' };
        this._emit('plc', this.plcStatus);
        this._scheduleReconnect();
      };
    }

    disconnect() {
      this._closed = true;
      this._stopHeartbeat();
      if (this._reconnectTimer) { clearTimeout(this._reconnectTimer); this._reconnectTimer = null; }
      if (this._ws) {
        try { this._ws.close(1000, 'client disconnect'); } catch (e) {}
        this._ws = null;
      }
      this._rejectAll(new Error('disconnected'));
      this._setStatus(this._mockMode ? 'mock' : 'idle');
    }

    _teardownSocket() {
      this._closed = true;
      this._stopHeartbeat();
      if (this._reconnectTimer) { clearTimeout(this._reconnectTimer); this._reconnectTimer = null; }
      if (this._ws) {
        try { this._ws.close(1000); } catch (e) {}
        this._ws = null;
      }
      this._rejectAll(new Error('switched to mock'));
    }

    _scheduleReconnect() {
      if (!this.autoReconnect || this._closed || this._mockMode) return;
      if (this._reconnectTimer) return;
      const delay = Math.min(10000, 600 * Math.pow(2, this._retry++));
      this._emit('reconnect', { delay });
      this._reconnectTimer = setTimeout(() => {
        this._reconnectTimer = null;
        if (!this._closed && !this._mockMode) this.connect();
      }, delay);
    }

    _startHeartbeat() {
      this._stopHeartbeat();
      const tick = () => {
        if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return;
        this._sendRaw({ type: 'ping', ts: Date.now() });
      };
      this._heartbeatTimer = setInterval(tick, 5000);
      tick();
    }

    _stopHeartbeat() {
      if (this._heartbeatTimer) { clearInterval(this._heartbeatTimer); this._heartbeatTimer = null; }
    }

    _sendRaw(obj) {
      if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return false;
      this._ws.send(JSON.stringify(obj));
      return true;
    }

    _onMessage(msg) {
      if (!msg || !msg.type) return;
      if (msg.type === 'hello') {
        this.hello = msg;
        this._emit('hello', msg);
        this._setStatus('online');
      } else if (msg.type === 'snapshot' || msg.type === 'delta' || msg.type === 'diff') {
        this.seq = msg.seq || this.seq;
        this._applyValues(msg.values || {}, msg.type === 'diff' ? 'delta' : msg.type);
      } else if (msg.type === 'status') {
        this.plcStatus = { state: msg.plc, message: msg.message || '' };
        this._emit('plc', this.plcStatus);
      } else if (msg.type === 'ack') {
        const p = this._pending.get(msg.id);
        if (p) {
          clearTimeout(p.timer);
          this._pending.delete(msg.id);
          p.resolve(msg);
        }
        this._emit('ack', msg);
      } else if (msg.type === 'error') {
        const p = msg.id ? this._pending.get(msg.id) : null;
        if (p) {
          clearTimeout(p.timer);
          this._pending.delete(msg.id);
          p.reject(Object.assign(new Error(msg.message || msg.code), msg));
        }
        this._emit('error', msg);
      } else if (msg.type === 'pong') {
        if (msg.echo) this.latencyMs = Math.max(0, Date.now() - msg.echo);
        this._emit('latency', this.latencyMs);
      }
    }

    _rejectAll(err) {
      this._pending.forEach((p) => { clearTimeout(p.timer); p.reject(err); });
      this._pending.clear();
    }

    _request(type, payload, timeoutMs = 5000) {
      return new Promise((resolve, reject) => {
        if (this._mockMode) return reject(new Error('mock mode'));
        if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return reject(new Error('gateway 未连接'));
        const id = 'w' + (++this._nextId);
        const timer = setTimeout(() => {
          this._pending.delete(id);
          reject(new Error('gateway 写超时'));
        }, timeoutMs);
        this._pending.set(id, { resolve, reject, timer });
        this._ws.send(JSON.stringify(Object.assign({ type, id }, payload)));
      });
    }

    _tag(tag) {
      const t = this.tags.get(tag);
      if (!t) throw new Error('未知 tag: ' + tag);
      if (t.access !== 'w' && t.access !== 'rw') throw new Error(tag + ' 是只读 tag');
      return t;
    }

    configurePlc(config) {
      if (this._mockMode) return Promise.reject(new Error('本地模拟模式不能配置 PLC'));
      return this._request('plc.configure', config, 12000);
    }

    write(tag, value) {
      this._tag(tag);
      if (this._mockMode) {
        this.mock.write(tag, value);
        return Promise.resolve({ type: 'ack', tag, ok: true, mock: true });
      }
      return this._request('write', { tag, value });
    }

    pulse(tag, ms) {
      const t = this._tag(tag);
      if (t.type !== 'bool') throw new Error('pulse 只支持 bool');
      const duration = Math.max(30, Math.min(2000, ms || t.pulseMs || 150));
      if (this._mockMode) {
        this.mock.pulse(tag, duration);
        return Promise.resolve({ type: 'ack', tag, ok: true, pulseMs: duration, mock: true });
      }
      return this._request('pulse', { tag, ms: duration });
    }

    writeMany(values) {
      const prepared = {};
      Object.keys(values || {}).forEach((tag) => {
        if (this.tags.has(tag)) { this._tag(tag); prepared[tag] = values[tag]; }
      });
      if (!Object.keys(prepared).length) return Promise.resolve({ type: 'ack', ok: true, count: 0 });
      if (this._mockMode) {
        Object.keys(prepared).forEach((k) => this.mock.write(k, prepared[k]));
        return Promise.resolve({ type: 'ack', ok: true, count: Object.keys(prepared).length, mock: true });
      }
      return this._request('writeMany', { values: prepared });
    }

    get(tag) { return this.values[tag]; }
    tagOf(object, property) { return this.bindingMap.get(object + '.' + property) || null; }
    bind(object, property) {
      const tag = this.tagOf(object, property);
      return tag ? this.get(tag) : undefined;
    }
    snapshot() { return Object.assign({}, this.values); }
  }

  async function create(opts = {}) {
    const manifest = await TiaTwinClient.loadManifest(opts.manifest || opts.manifestUrl || './twin.manifest.json');
    const client = new TiaTwinClient(Object.assign({}, opts, { manifest }));
    if (opts.mock && opts.connectMock !== false) client.useMock(opts.mock);
    else if (opts.autoConnect) client.connect();
    return client;
  }

  global.TiaTwin = { create, loadManifest: TiaTwinClient.loadManifest, TiaTwinClient, version: VERSION, protocol: PROTOCOL };
})(window);
