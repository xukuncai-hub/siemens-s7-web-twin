(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const QS = (sel) => Array.from(document.querySelectorAll(sel));
  const LS_URL = 'tiaTwin.wsUrl';
  const LS_TOKEN = 'tiaTwin.token';
  const DEFAULT_URL = 'ws://127.0.0.1:8765/ws';

  const C = {
    bg: '#061019', panel: '#0a1824', line: '#1b3346', text: '#dfeef7', soft: '#b4cad8',
    dim: '#7e97aa', faint: '#4e697d', cyan: '#3dd6f5', cyanDim: '#1d7d95',
    green: '#54e6a1', amber: '#ffb454', orange: '#ff7a45', red: '#ff5d63',
  };

  class MockPlc {
    constructor(manifest) {
      this.tags = new Map(manifest.tags.map((t) => [t.id, t]));
      this.values = {};
      this.tags.forEach((t) => {
        this.values[t.id] = t.mockInit !== undefined ? t.mockInit
          : (t.type === 'bool' ? false : (t.type === 'real' ? 0.0 : 0));
      });
      this.values['line.speed'] = 0.0;
      this.subs = new Set();
      this.cylTimer = null;
    }

    getAll() { return Object.assign({}, this.values); }

    subscribe(fn) {
      this.subs.add(fn);
      return () => this.subs.delete(fn);
    }

    _emit(changed) {
      if (!Object.keys(changed).length) return;
      this.subs.forEach((fn) => {
        try { fn(Object.assign({}, changed)); } catch (e) { console.error(e); }
      });
    }

    _set(changed, id, value) {
      if (this.values[id] !== value) {
        this.values[id] = value;
        changed[id] = value;
      }
    }

    _stopCylinder(changed, timer = true) {
      if (timer && this.cylTimer) { clearTimeout(this.cylTimer); this.cylTimer = null; }
      this._set(changed, 'out.cyl', false);
    }

    write(tag, value) {
      if (!this.tags.has(tag)) return;
      const prev = this.values[tag];
      const changed = {};
      this._set(changed, tag, value);
      if (tag === 'cmd.start' && value) {
        this._stopCylinder(changed);
        this._set(changed, 'line.fault', false);
        this._set(changed, 'line.running', true);
        this._set(changed, 'line.speed', 0.15);
        this._set(changed, 'stack.green', true);
        this._set(changed, 'stack.red', false);
      } else if (tag === 'cmd.stop' && value) {
        this._stopCylinder(changed);
        this._set(changed, 'line.running', false);
        this._set(changed, 'line.speed', 0.0);
        this._set(changed, 'stack.green', false);
      } else if (tag === 'cmd.reset' && value) {
        this._stopCylinder(changed);
        this._set(changed, 'line.fault', false);
        this._set(changed, 'stack.red', false);
        const running = !!this.values['line.running'];
        this._set(changed, 'stack.green', running);
        this._set(changed, 'line.speed', running ? 0.15 : 0.0);
      } else if (tag === 'cmd.estop' && value) {
        this._stopCylinder(changed);
        this._set(changed, 'line.fault', true);
        this._set(changed, 'line.running', false);
        this._set(changed, 'line.speed', 0.0);
        this._set(changed, 'stack.green', false);
        this._set(changed, 'stack.red', true);
      } else if (tag === 'sensor.pe1' && value && !prev
                 && this.values['line.running'] && !this.values['line.fault']) {
        this._set(changed, 'box.count', (Number(this.values['box.count']) || 0) + 1);
        this._set(changed, 'out.cyl', true);
        this._set(changed, 'stack.green', true);
        if (this.cylTimer) clearTimeout(this.cylTimer);
        this.cylTimer = setTimeout(() => {
          const ch = {};
          this._set(ch, 'out.cyl', false);
          this._emit(ch);
        }, 700);
      }
      this._emit(changed);
    }

    pulse(tag, ms) {
      this.write(tag, true);
      setTimeout(() => this.write(tag, false), ms || 150);
    }
  }

  class PlantScene {
    constructor(canvas, twin) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.twin = twin;
      this.boxes = [];
      this.boxSeq = 0;
      this.spawnIn = 0.6;
      this.beltOffset = 0;
      this.pusher = 0;
      this.sensor = false;
      this.feedback = false;
      this.autoSensor = true;
      this.plcReady = true;
      this.lastSensor = null;
      this.lastFeedback = null;
      this.syncIn = 0;
      this.time = 0;
      this.lastSim = performance.now();
      this.simTimer = setInterval(() => {
        const now = performance.now();
        const dt = Math.min(0.5, (now - this.lastSim) / 1000);
        this.lastSim = now;
        this.update(dt);
      }, 50);
      this.resize();
      window.addEventListener('resize', () => this.resize());
    }

    resize() {
      const rect = this.canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.canvas.width = Math.max(1, Math.round(rect.width * dpr));
      this.canvas.height = Math.max(1, Math.round(rect.height * dpr));
      this.scaleX = this.canvas.width / 1600;
      this.scaleY = this.canvas.height / 900;
    }

    forceSync() { this.lastSensor = null; this.lastFeedback = null; }

    get running() { return !!this.twin.get('line.running'); }
    get fault() { return !!this.twin.get('line.fault'); }

    update(dt) {
      this.time += dt;
      const running = this.running && !this.fault;
      const speed = Number(this.twin.get('line.speed') || 0);
      this.beltOffset += (running ? 110 + speed * 620 : 0) * dt;

      if (running) {
        this.spawnIn -= dt;
        if (this.spawnIn <= 0) {
          this.spawnIn = 2.35;
          this.boxSeq += 1;
          this.boxes.push({ id: this.boxSeq, x: 170, y: 552, mode: 'belt', rot: 0, vy: 0, born: this.time });
        }
      }

      this.boxes.forEach((b) => {
        if (b.mode === 'belt' && running) b.x += (85 + speed * 520) * dt;
        if (b.mode === 'fall') {
          b.vy += 420 * dt;
          b.y += b.vy * dt;
          b.x += 22 * dt;
          b.rot += dt * 2.2;
        }
      });
      this.boxes = this.boxes.filter((b) => !(b.mode === 'fall' && b.y > 760) && b.x < 1400);

      const prevSensor = this.sensor;
      if (this.autoSensor) {
        this.sensor = this.boxes.some((b) => b.mode === 'belt' && Math.abs(b.x - 800) < 24);
      } else {
        this.sensor = !!this.twin.get('sensor.pe1');
      }
      if (this.sensor && !prevSensor) this.sensorRises = (this.sensorRises || 0) + 1;
      const cmd = !!this.twin.get('out.cyl');
      const target = cmd && !this.fault ? 1 : 0;
      this.pusher += (target - this.pusher) * Math.min(1, dt * 10);
      if (this.pusher < 0.03) this.pusher = 0;

      for (const b of this.boxes) {
        if (b.mode === 'belt' && b.x > 820 && b.x < 970 && this.pusher > 0.25) {
          b.mode = 'fall';
          b.vy = 60;
        }
      }

      const ext = this.pusher > 0.9;
      if (ext !== this.feedback) this.feedback = ext;

      this.syncIn += dt;
      if (this.syncIn >= 0.1) {
        this.syncIn = 0;
        this.syncBits();
      }
    }

    syncBits() {
      if (!this.autoSensor || !this.plcReady) return;
      const patch = {};
      if (this.lastSensor !== this.sensor) { this.lastSensor = this.sensor; patch['sensor.pe1'] = this.sensor; }
      if (this.lastFeedback !== this.feedback) { this.lastFeedback = this.feedback; patch['cyl.extended'] = this.feedback; }
      if (!Object.keys(patch).length) return;
      if (this.twin.status !== 'mock' && this.twin.status !== 'online') return;
      this.twin.writeMany(patch).catch(() => {});
    }

    rr(x, y, w, h, r) {
      const c = this.ctx;
      const m = Math.min(r, w / 2, h / 2);
      c.beginPath();
      c.moveTo(x + m, y);
      c.lineTo(x + w - m, y);
      c.arcTo(x + w, y, x + w, y + m, m);
      c.lineTo(x + w, y + h - m);
      c.arcTo(x + w, y + h, x + w - m, y + h, m);
      c.lineTo(x + m, y + h);
      c.arcTo(x, y + h, x, y + h - m, m);
      c.lineTo(x, y + m);
      c.arcTo(x, y, x + m, y, m);
      c.closePath();
    }

    dot(x, y, r, color, alpha = 1) {
      this.ctx.beginPath();
      this.ctx.arc(x, y, r, 0, Math.PI * 2);
      this.ctx.fillStyle = color;
      this.ctx.globalAlpha = alpha;
      this.ctx.fill();
      this.ctx.globalAlpha = 1;
    }

    text(s, x, y, size, color, align = 'left', weight = 500, mono = false) {
      const c = this.ctx;
      c.font = `${weight} ${size}px ${mono ? '"JetBrains Mono", monospace' : '"PingFang SC", "Microsoft YaHei", sans-serif'}`;
      c.fillStyle = color;
      c.textAlign = align;
      c.textBaseline = 'middle';
      c.fillText(s, x, y);
    }

    drawBackground() {
      const c = this.ctx;
      const g = c.createLinearGradient(0, 0, 0, 900);
      g.addColorStop(0, '#081420');
      g.addColorStop(1, '#050d14');
      c.fillStyle = g;
      c.fillRect(0, 0, 1600, 900);
      c.strokeStyle = 'rgba(61,214,245,0.035)';
      c.lineWidth = 1;
      for (let x = 40; x < 1600; x += 40) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, 900); c.stroke(); }
      for (let y = 40; y < 900; y += 40) { c.beginPath(); c.moveTo(0, y); c.lineTo(1600, y); c.stroke(); }
      c.strokeStyle = 'rgba(61,214,245,0.075)';
      for (let x = 200; x < 1600; x += 200) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, 900); c.stroke(); }
      for (let y = 200; y < 900; y += 200) { c.beginPath(); c.moveTo(0, y); c.lineTo(1600, y); c.stroke(); }
      const vg = c.createRadialGradient(800, 500, 100, 800, 450, 950);
      vg.addColorStop(0, 'rgba(0,0,0,0)');
      vg.addColorStop(1, 'rgba(0,0,0,0.55)');
      c.fillStyle = vg;
      c.fillRect(0, 0, 1600, 900);
      // floor
      c.strokeStyle = '#152b3b';
      c.lineWidth = 1.2;
      c.beginPath(); c.moveTo(0, 790); c.lineTo(1600, 790); c.stroke();
      c.strokeStyle = 'rgba(61,214,245,0.08)';
      for (let x = -200; x < 1800; x += 90) {
        c.beginPath(); c.moveTo(x, 790); c.lineTo(x + 180, 900); c.stroke();
      }
    }

    drawLabels() {
      this.text('CELL 01 / SORTING LINE', 30, 34, 13, C.cyanDim, 'left', 600, true);
      const plcCfg = this.twin.manifest.plc || {};
      this.text(`${plcCfg.family || 'S7'}  ·  ${plcCfg.dbName || 'TwinIO'}  ·  DB${plcCfg.db ?? '?'}`, 1570, 34, 11, C.faint, 'right', 500, true);
      this.text('DIGITAL TWIN / PLANT MODEL', 30, 56, 10, C.faint, 'left', 500, true);
      this.text('SIMULATION ONLY — NOT A SAFETY DEVICE', 1570, 56, 10, C.faint, 'right', 500, true);
      // cell heading fills the empty upper-left area
      this.text('分拣单元', 30, 105, 30, C.text, 'left', 600);
      this.text('CONVEYOR · PE1 · PUSHER CYLINDER', 30, 136, 12, C.dim, 'left', 500, true);
      const chips = [['24V DC', C.cyanDim], [`DB${plcCfg.db ?? '?'} / ${plcCfg.dbName || 'TwinIO'}`, C.faint], [`${(this.twin.manifest.plc || {}).defaultPollHz || 10} Hz`, C.faint], ['S7COMM', C.faint]];
      let cx = 30;
      chips.forEach(([label, color]) => {
        const w = 18 + label.length * 7.2;
        this.rr(cx, 158, w, 24, 3);
        this.ctx.fillStyle = 'rgba(10,24,36,0.8)'; this.ctx.fill();
        this.ctx.strokeStyle = '#244054'; this.ctx.lineWidth = 1; this.ctx.stroke();
        this.text(label, cx + w / 2, 170, 9, color, 'center', 500, true);
        cx += w + 8;
      });
      // signal flow legend
      const sensorTag = this.twin.tagOf('pe1', 'blocked') || 'sensor.pe1';
      const pusherTag = this.twin.tagOf('pusher', 'command') || 'out.cyl';
      this.text('PE1', 778, 452, 12, this.sensor ? C.red : C.cyanDim, 'center', 600, true);
      this.text(sensorTag, 778, 468, 9, C.faint, 'center', 500, true);
      this.text(pusherTag, 1010, 252, 12, C.amber, 'left', 600, true);
      this.text('5/2 VALVE', 1010, 268, 9, C.faint, 'left', 500, true);
    }

    drawConveyor() {
      const c = this.ctx;
      const y = 590, h = 68;
      // legs
      [250, 470, 700, 1010, 1210, 1340].forEach((x) => {
        c.fillStyle = '#0c1b27'; c.strokeStyle = '#284154'; c.lineWidth = 1.2;
        c.fillRect(x - 7, y + h, 14, 92); c.strokeRect(x - 7, y + h, 14, 92);
        c.fillStyle = '#193245'; c.fillRect(x - 14, y + h + 86, 28, 8);
      });
      // frame / belt segments
      const segs = [[180, 840], [940, 1380]];
      segs.forEach(([x0, x1]) => {
        c.fillStyle = '#0b1925'; c.strokeStyle = '#35566c'; c.lineWidth = 2;
        c.beginPath(); c.rect(x0, y, x1 - x0, h); c.fill(); c.stroke();
        c.save();
        c.beginPath(); c.rect(x0 + 4, y + 4, x1 - x0 - 8, h - 8); c.clip();
        c.strokeStyle = 'rgba(139,169,186,0.33)'; c.lineWidth = 2;
        const off = this.beltOffset % 42;
        for (let x = x0 - 42 + off; x < x1 + 42; x += 42) {
          c.beginPath(); c.moveTo(x, y + 6); c.lineTo(x - 24, y + h - 6); c.stroke();
        }
        c.restore();
        c.strokeStyle = 'rgba(61,214,245,0.18)'; c.lineWidth = 1;
        c.beginPath(); c.moveTo(x0, y + 5); c.lineTo(x1, y + 5); c.stroke();
        c.beginPath(); c.moveTo(x0, y + h - 5); c.lineTo(x1, y + h - 5); c.stroke();
      });
      // gap edges
      c.strokeStyle = C.amber; c.lineWidth = 2;
      c.beginPath(); c.moveTo(840, y); c.lineTo(840, y + h); c.stroke();
      c.beginPath(); c.moveTo(940, y); c.lineTo(940, y + h); c.stroke();
      this.text('SORT GATE', 890, y + h + 78, 10, C.faint, 'center', 500, true);
      this.text('BELT  v = ' + Number(this.twin.get('line.speed') || 0).toFixed(2) + ' m/s', 200, y + h + 24, 11, C.faint, 'left', 500, true);
    }

    drawBoxes() {
      this.boxes.forEach((b) => {
        const c = this.ctx;
        c.save();
        c.translate(b.x, b.y + 19);
        c.rotate(b.rot || 0);
        const col = b.id % 2 ? C.cyan : C.amber;
        this.rr(-24, -19, 48, 38, 3);
        c.fillStyle = '#102533'; c.fill();
        c.strokeStyle = col; c.lineWidth = 1.6; c.stroke();
        c.fillStyle = 'rgba(61,214,245,0.10)';
        c.fillRect(-24, -19, 48, 7);
        this.text(String(b.id).padStart(3, '0'), 0, 2, 13, C.soft, 'center', 600, true);
        c.restore();
      });
    }

    drawSensor() {
      const c = this.ctx;
      const x = 800;
      // emitter / receiver posts
      c.fillStyle = '#0b1a26'; c.strokeStyle = '#3b5b70'; c.lineWidth = 1.4;
      c.fillRect(x - 18, 470, 36, 38); c.strokeRect(x - 18, 470, 36, 38);
      c.fillRect(x - 16, 680, 32, 30); c.strokeRect(x - 16, 680, 32, 30);
      this.dot(x, 489, 4, this.sensor ? C.red : C.green, 1);
      this.dot(x, 695, 3.2, this.sensor ? C.red : C.cyanDim, 1);
      c.save();
      c.setLineDash([7, 6]);
      c.lineWidth = 2;
      c.strokeStyle = this.sensor ? 'rgba(255,93,99,0.8)' : 'rgba(61,214,245,0.5)';
      c.beginPath(); c.moveTo(x, 508); c.lineTo(x, 680); c.stroke();
      c.restore();
      this.text('PE1', x, 458, 13, this.sensor ? C.red : C.cyanDim, 'center', 600, true);
      this.text(this.sensor ? 'BLOCKED' : 'CLEAR', x, 730, 10, this.sensor ? C.red : C.faint, 'center', 500, true);
    }

    drawPusher() {
      const c = this.ctx;
      const x = 890;
      // gantry
      c.strokeStyle = '#2b485b'; c.lineWidth = 2;
      c.beginPath(); c.moveTo(830, 300); c.lineTo(950, 300); c.stroke();
      c.beginPath(); c.moveTo(842, 300); c.lineTo(842, 590); c.stroke();
      c.beginPath(); c.moveTo(938, 300); c.lineTo(938, 590); c.stroke();
      // cylinder body
      this.rr(852, 252, 76, 128, 4);
      c.fillStyle = '#0d1d29'; c.fill();
      c.strokeStyle = this.pusher > 0.1 ? C.amber : '#3b5b70'; c.lineWidth = 1.8; c.stroke();
      for (let k = 0; k < 4; k++) {
        c.strokeStyle = 'rgba(255,180,84,' + (0.22 + this.pusher * 0.35) + ')';
        c.lineWidth = 1.2;
        c.beginPath(); c.arc(890, 292 + k * 22, 24, Math.PI * 1.1, Math.PI * 1.9); c.stroke();
      }
      // rod + plate
      const ext = this.pusher;
      c.fillStyle = '#8da7b6';
      c.fillRect(x - 7, 380, 14, 60 + ext * 118);
      this.rr(x - 44, 438 + ext * 118, 88, 12, 3);
      c.fillStyle = ext > 0.5 ? C.amber : '#5e7788'; c.fill();
      c.strokeStyle = '#d0e0e8'; c.lineWidth = 1; c.stroke();
      const ptag = this.twin.tagOf('pusher', 'command') || 'out.cyl';
      this.text(ptag.toUpperCase() + ' / PUSHER', x, 236, 12, this.pusher > 0.1 ? C.amber : C.faint, 'center', 600, true);
      this.text(ext > 0.9 ? 'EXTENDED' : (ext < 0.05 ? 'RETRACTED' : 'MOVING'), x, 566, 9, ext > 0.9 ? C.amber : C.faint, 'center', 500, true);
    }

    drawBin() {
      const c = this.ctx;
      // chute
      c.fillStyle = 'rgba(255,180,84,0.04)';
      c.beginPath();
      c.moveTo(840, 658); c.lineTo(940, 658); c.lineTo(975, 726); c.lineTo(805, 726); c.closePath();
      c.fill();
      c.strokeStyle = 'rgba(255,180,84,0.32)'; c.lineWidth = 1.2; c.stroke();
      // bin
      this.rr(790, 720, 220, 78, 4);
      c.fillStyle = '#0a1823'; c.fill();
      c.strokeStyle = '#3a566a'; c.lineWidth = 1.6; c.stroke();
      const count = Number(this.twin.get('box.count') || 0);
      for (let k = 0; k < Math.min(5, count % 6); k++) {
        c.fillStyle = k % 2 ? 'rgba(61,214,245,0.35)' : 'rgba(255,180,84,0.35)';
        c.fillRect(812 + k * 37, 772, 30, 16);
        c.strokeStyle = k % 2 ? C.cyanDim : C.amber; c.lineWidth = 1; c.strokeRect(812 + k * 37, 772, 30, 16);
      }
      this.text('OK BIN', 900, 740, 13, C.soft, 'center', 600);
      this.text(String(count).padStart(3, '0') + ' PCS', 995, 780, 11, C.amber, 'right', 600, true);
      // reject chute at end
      this.text('END / REJECT', 1380, 740, 8, C.faint, 'center', 500, true);
    }

    drawCabinet() {
      const c = this.ctx;
      this.rr(110, 638, 230, 150, 5);
      c.fillStyle = '#0a1722'; c.fill();
      c.strokeStyle = '#3a566a'; c.lineWidth = 1.6; c.stroke();
      this.text('PLC / ' + ((this.twin.manifest.plc || {}).dbName || 'TwinIO'), 125, 656, 12, C.soft, 'left', 600);
      for (let k = 0; k < 4; k++) {
        this.rr(126 + k * 50, 674, 40, 82, 3);
        c.fillStyle = '#102434'; c.fill();
        c.strokeStyle = '#2b485b'; c.lineWidth = 1; c.stroke();
        for (let j = 0; j < 4; j++) {
          c.fillStyle = j === 0 ? C.green : '#294556';
          c.fillRect(132 + k * 50, 686 + j * 13, 4, 4);
        }
      }
      this.text('24V DC', 126, 772, 8, C.cyanDim, 'left', 500, true);
      // cable to sensor/pusher
      c.save();
      c.setLineDash([5, 7]);
      c.strokeStyle = 'rgba(61,214,245,0.35)';
      c.lineWidth = 1.2;
      c.beginPath(); c.moveTo(340, 710); c.lineTo(380, 710); c.lineTo(380, 600); c.lineTo(780, 600); c.stroke();
      c.strokeStyle = 'rgba(255,180,84,0.3)';
      c.beginPath(); c.moveTo(340, 730); c.lineTo(400, 730); c.lineTo(400, 330); c.lineTo(850, 330); c.stroke();
      c.restore();
    }

    drawStackLight() {
      const c = this.ctx;
      const x = 1450, y = 330;
      c.strokeStyle = '#335166'; c.lineWidth = 4;
      c.beginPath(); c.moveTo(x, y + 62); c.lineTo(x, 560); c.stroke();
      c.fillStyle = '#102330'; c.strokeStyle = '#3a566a'; c.lineWidth = 1.2;
      c.fillRect(x - 38, 552, 76, 10); c.strokeRect(x - 38, 552, 76, 10);
      const running = this.running && !this.fault;
      const lamps = [
        { cy: y, color: C.red, on: this.fault },
        { cy: y + 44, color: C.amber, on: false },
        { cy: y + 88, color: C.green, on: running },
      ];
      lamps.forEach((l) => {
        this.rr(x - 22, l.cy, 44, 34, 5);
        c.fillStyle = l.on ? l.color : '#0c1c28';
        c.globalAlpha = l.on ? 0.9 : 1;
        c.fill();
        c.globalAlpha = 1;
        c.strokeStyle = l.on ? l.color : '#2c4557'; c.lineWidth = 1.2; c.stroke();
        if (l.on) {
          c.strokeStyle = l.color; c.globalAlpha = 0.25; c.lineWidth = 8;
          c.stroke(); c.globalAlpha = 1;
        }
      });
      this.text('STACK', x, y + 142, 8, C.faint, 'center', 500, true);
    }

    draw() {
      const c = this.ctx;
      c.setTransform(this.scaleX, 0, 0, this.scaleY, 0, 0);
      c.clearRect(0, 0, 1600, 900);
      this.drawBackground();
      this.drawLabels();
      this.drawConveyor();
      this.drawBin();
      this.drawSensor();
      this.drawBoxes();
      this.drawPusher();
      this.drawCabinet();
      this.drawStackLight();
      // state ribbon
      const st = this.fault ? 'FAULT' : (this.running ? 'RUNNING' : 'STOPPED');
      const col = this.fault ? C.red : (this.running ? C.green : C.dim);
      this.text(st, 30, 840, 11, col, 'left', 600, true);
      this.text((this.twin.status || 'idle').toUpperCase(), 1570, 840, 9, this.twin.status === 'mock' ? C.amber : C.faint, 'right', 500, true);
    }
  }

  let twin = null;
  let mockPlc = null;
  let scene = null;
  let manifest = null;
  let commandGuard = 0;
  let mode = 'offline';
  let gatewayUrl = new URLSearchParams(location.search).get('ws') || 'ws://127.0.0.1:8765/ws';
  let gatewayToken = new URLSearchParams(location.search).get('token') || '';
  let plcTarget = null;
  let configuredSocket = false;
  let lastPlc = { state: 'unknown', message: '' };

  function lsKey(name) {
    return 'tiaTwin.' + ((manifest && manifest.project) || 'default') + '.' + name;
  }

  function fmt(tag, v) {
    if (v === undefined || v === null) return '—';
    if (tag.type === 'bool') return v ? '1' : '0';
    if (tag.type === 'real') return Number(v).toFixed(3);
    return String(v);
  }

  function setControls(on) {
    QS('[data-cmd]').forEach((btn) => { btn.disabled = !on; });
  }

  function showWait(text) {
    $('#waitText').textContent = text;
    $('#waitOverlay').classList.remove('hidden');
  }
  function hideWait() {
    $('#waitOverlay').classList.add('hidden');
  }

  function setOnlineState(text, cls = '') {
    const el = $('#onlineState');
    el.textContent = text;
    el.style.color = cls === 'ok' ? '#54e6a1' : cls === 'error' ? '#ff5d63' : '';
  }
  function setOnlineMsg(text, cls = '') {
    const el = $('#onlineMsg');
    el.textContent = text;
    el.className = 'hint' + (cls ? ' ' + cls : '');
  }

  function setOpState() {
    const el = $('#opState');
    if (mode === 'offline') { el.textContent = 'OFFLINE'; el.style.color = '#ffb454'; return; }
    if (lastPlc.state === 'connected') { el.textContent = 'PLC ONLINE'; el.style.color = '#54e6a1'; }
    else { el.textContent = 'PLC WAIT'; el.style.color = '#ff5d63'; }
  }

  function buildSimRows() {
    const box = $('#simRows');
    box.innerHTML = '';
    manifest.tags.filter((t) => !t.id.startsWith('cmd.')).forEach((t) => {
      const row = document.createElement('div');
      row.className = 'sim-row';
      row.dataset.tag = t.id;
      const meta = document.createElement('div');
      meta.className = 'sim-meta';
      const name = document.createElement('div');
      name.className = 'sim-name';
      name.textContent = t.desc || t.id;
      const id = document.createElement('div');
      id.className = 'sim-id';
      id.textContent = t.id;
      meta.appendChild(name); meta.appendChild(id);
      const ctl = document.createElement('div');
      ctl.className = 'sim-control';
      let input;
      if (t.type === 'bool') {
        input = document.createElement('input');
        input.type = 'checkbox';
        input.addEventListener('change', () => {
          if (mode !== 'offline') return;
          mockPlc.write(t.id, input.checked);
        });
      } else {
        input = document.createElement('input');
        input.type = 'number';
        input.step = t.type === 'real' ? '0.01' : '1';
        input.addEventListener('change', () => {
          if (mode !== 'offline') return;
          const n = t.type === 'real' ? Number(input.value) : parseInt(input.value, 10);
          if (Number.isFinite(n)) mockPlc.write(t.id, n);
        });
      }
      ctl.appendChild(input);
      row.appendChild(meta); row.appendChild(ctl);
      box.appendChild(row);
    });
  }

  function updateSimRows() {
    if (!twin) return;
    manifest.tags.filter((t) => !t.id.startsWith('cmd.')).forEach((t) => {
      const row = document.querySelector(`.sim-row[data-tag="${t.id}"]`);
      if (!row) return;
      const input = row.querySelector('input');
      if (!input || document.activeElement === input) return;
      const v = twin.get(t.id);
      if (t.type === 'bool') input.checked = !!v;
      else if (v !== undefined && document.activeElement !== input) input.value = v;
    });
  }

  function updateHud() {
    if (!twin) return;
    const count = twin.get('box.count');
    const pe = twin.get('sensor.pe1');
    const q = twin.get('out.cyl');
    const running = twin.get('line.running');
    const fault = twin.get('line.fault');
    $('#hudCount').textContent = count === undefined ? '—' : String(count);
    $('#hudPe').textContent = pe ? '1' : '0';
    $('#hudPe').style.color = pe ? '#ff5d63' : '';
    $('#hudQ').textContent = q ? '1' : '0';
    $('#hudQ').style.color = q ? '#ffb454' : '';
    const st = $('#hudState');
    st.textContent = fault ? 'FAULT' : (running ? 'RUNNING' : 'STOPPED');
    st.style.color = fault ? '#ff5d63' : (running ? '#54e6a1' : '#7f97aa');
  }

  function setMode(next) {
    mode = next;
    const offline = mode === 'offline';
    $('#modeOffline').classList.toggle('active', offline);
    $('#modeOnline').classList.toggle('active', !offline);
    $('#modeOffline').setAttribute('aria-selected', String(offline));
    $('#modeOnline').setAttribute('aria-selected', String(!offline));
    $('#offlinePane').classList.toggle('hidden', !offline);
    $('#onlinePane').classList.toggle('hidden', offline);
    $('#workspaceHint').textContent = offline ? '离线仿真：可修改本地数据' : '在线模式：输入 PLC 地址后连接';
    setOpState();
    if (!twin) return;
    if (offline) {
      configuredSocket = false;
      twin.useMock(mockPlc);
      if (scene) { scene.autoSensor = $('#autoSensor').checked; scene.plcReady = true; }
      hideWait();
      setControls(true);
      setOnlineState('未连接');
      setOnlineMsg('输入 PLCSIM Advanced 虚拟 PLC 的 IP 地址。');
    } else {
      twin.useMock(null);
      if (scene) { scene.autoSensor = true; scene.plcReady = false; }
      setControls(false);
      setOnlineState('未连接');
      setOnlineMsg('输入 PLC 地址后点击连接。');
      showWait('输入 PLC 地址后连接');
    }
  }

  function sendPlcConfig() {
    if (!plcTarget || mode !== 'online') return;
    setOnlineState('连接中');
    setOnlineMsg(`正在连接 ${plcTarget.ip} …`);
    showWait('正在连接 PLC…');
    setControls(false);
    twin.configurePlc(plcTarget).then(() => {
      setOnlineState('连接中');
    }).catch((err) => {
      configuredSocket = false;
      setOnlineState('失败', 'error');
      setOnlineMsg('连接失败：' + err.message, 'error');
      showWait('PLC 连接失败，请检查地址');
      setControls(false);
    });
  }

  function connectPlc() {
    const ip = $('#plcIp').value.trim();
    if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip)) {
      setOnlineState('地址错误', 'error');
      setOnlineMsg('请输入正确的 IPv4 地址，例如 192.168.0.1。', 'error');
      return;
    }
    const rack = parseInt($('#plcRack').value, 10) || 0;
    const slot = parseInt($('#plcSlot').value, 10);
    plcTarget = { ip, rack, slot: Number.isFinite(slot) ? slot : 1 };
    localStorage.setItem(lsKey('plcIp'), ip);
    localStorage.setItem(lsKey('plcRack'), String(rack));
    localStorage.setItem(lsKey('plcSlot'), String(plcTarget.slot));
    lastPlc = { state: 'unknown', message: '' };
    configuredSocket = false;
    setOnlineState('连接中');
    setOnlineMsg(`正在连接 ${ip} …`);
    showWait('正在连接 PLC…');
    setControls(false);
    twin.url = gatewayUrl;
    twin.token = gatewayToken;
    if (twin.status === 'online') {
      configuredSocket = true;
      sendPlcConfig();
    } else {
      twin.connect();
    }
  }

  async function pulseCommand(cmd) {
    const now = performance.now();
    if (now - commandGuard < 220) return;
    commandGuard = now;
    try {
      await twin.pulse(cmd, 150);
    } catch (err) {
      setOnlineMsg('命令失败：' + err.message, 'error');
    }
  }

  function wireUI() {
    QS('[data-cmd]').forEach((b) => b.addEventListener('click', () => pulseCommand(b.dataset.cmd)));
    $('#modeOffline').addEventListener('click', () => { if (mode !== 'offline') setMode('offline'); });
    $('#modeOnline').addEventListener('click', () => { if (mode !== 'online') setMode('online'); });
    $('#btnPlcConnect').addEventListener('click', connectPlc);
    $('#btnRetry').addEventListener('click', connectPlc);
    $('#autoSensor').addEventListener('change', () => {
      if (scene) {
        scene.autoSensor = $('#autoSensor').checked;
        if (scene.autoSensor) scene.forceSync();
      }
    });
    const savedIp = localStorage.getItem(lsKey('plcIp'));
    const savedRack = localStorage.getItem(lsKey('plcRack'));
    const savedSlot = localStorage.getItem(lsKey('plcSlot'));
    $('#plcIp').value = savedIp || manifest.plc.ip || '192.168.0.1';
    $('#plcRack').value = savedRack ?? manifest.plc.rack ?? 0;
    $('#plcSlot').value = savedSlot ?? manifest.plc.slot ?? 1;
  }

  function attachEvents() {
    twin.on('status', ({ state, error }) => {
      if (mode !== 'online') return;
      if (state === 'online') {
        if (plcTarget && !configuredSocket) {
          configuredSocket = true;
          sendPlcConfig();
        }
      } else if (state === 'offline') {
        configuredSocket = false;
        if (scene) scene.plcReady = false;
        setOnlineState('网关断开', 'error');
        setOnlineMsg('本地网关未连接，请确认 run_twin.py 正在运行。', 'error');
        showWait('等待本地网关');
        setControls(false);
      } else if (state === 'connecting') {
        showWait('正在连接本地网关…');
      } else if (state === 'idle') {
        showWait('输入 PLC 地址后连接');
      }
      if (error && state === 'offline') {
        setOnlineMsg('网关错误：' + error, 'error');
      }
    });
    twin.on('plc', (plc) => {
      lastPlc = plc || { state: 'unknown', message: '' };
      setOpState();
      if (mode !== 'online') return;
      if (lastPlc.state === 'connected') {
        if (scene) scene.plcReady = true;
        hideWait();
        setControls(true);
        $('#workspaceHint').textContent = '在线模式：PLC 已连接';
        setOnlineState('已连接', 'ok');
        setOnlineMsg(plc.message === 'mock backend' ? 'PLC 已连接。' : 'PLC 已连接，开始实时仿真。', 'ok');
      } else if (lastPlc.state === 'error') {
        if (scene) scene.plcReady = false;
        showWait('PLC 通信异常，请检查地址');
        setControls(false);
        $('#workspaceHint').textContent = '在线模式：PLC 通信异常';
        setOnlineState('通信错误', 'error');
        setOnlineMsg('PLC 通信失败：' + (plc.message || '检查地址、PUT/GET 和非优化 DB'), 'error');
      } else if (lastPlc.state === 'waiting') {
        if (scene) scene.plcReady = false;
        showWait('正在连接 PLC…');
        setControls(false);
        setOnlineState('连接中');
        setOnlineMsg(plc.message || '正在连接 PLC…');
      }
    });
    twin.on('values', () => { updateSimRows(); updateHud(); });
    twin.on('error', (e) => {
      if (mode === 'online') setOnlineMsg('协议错误：' + (e.message || e.code), 'error');
    });
  }

  function loop() {
    if (!scene) return;
    scene.draw();
    updateHud();
    requestAnimationFrame(loop);
  }

  async function boot() {
    try {
      manifest = await TiaTwin.loadManifest('./twin.manifest.json');
      document.title = manifest.title + ' · 数字孪生';
      $('#projectTitle').textContent = manifest.title;
      $('#footerProject').textContent = 'DIGITAL TWIN · ' + (manifest.project || '').toUpperCase();
      mockPlc = new MockPlc(manifest);
      twin = await TiaTwin.create({ manifest, url: gatewayUrl, token: gatewayToken, mock: mockPlc });
      buildSimRows();
      wireUI();
      attachEvents();
      setMode('offline');
      updateSimRows();
      updateHud();
      scene = new PlantScene($('#scene'), twin);
      scene.autoSensor = $('#autoSensor').checked;
      if (new URLSearchParams(location.search).has('debug')) {
        window.__twinDebug = { get twin() { return twin; }, get scene() { return scene; }, get mock() { return mockPlc; } };
      }
      requestAnimationFrame(loop);
    } catch (err) {
      console.error(err);
      const el = document.createElement('div');
      el.style.cssText = 'position:fixed;inset:0;display:grid;place-items:center;background:#071019;color:#ff9ca0;font:14px monospace;z-index:99;padding:30px;text-align:center;';
      el.textContent = '页面启动失败：' + err.message + ' — 请通过 run_twin.py 或静态 HTTP 服务打开。';
      document.body.appendChild(el);
    }
  }

  boot();
})();
