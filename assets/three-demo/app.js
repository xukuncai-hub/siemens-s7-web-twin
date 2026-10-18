import * as THREE from 'three';

const $ = (s) => document.querySelector(s);
const QS = (s) => Array.from(document.querySelectorAll(s));

const C = {
  bg: 0x050d14,
  cyan: 0x3dd6f5,
  cyanDim: 0x1d7d95,
  green: 0x54e6a1,
  amber: 0xffb454,
  red: 0xff5d63,
  steel: 0x7695a8,
  steelDark: 0x223c4d,
  belt: 0x0f222e,
  frame: 0x1b3749,
};

const LS_URL = 'tiaTwin.wsUrl';
const LS_TOKEN = 'tiaTwin.token';

// ==============================================================================
// 1. 本地离线仿真 PLC (MockPlc3D)
// ==============================================================================
class MockPlc3D {
  constructor(manifest) {
    this.tags = new Map(manifest.tags.map((t) => [t.id, t]));
    this.values = {};
    this.tags.forEach((t) => {
      this.values[t.id] = t.mockInit !== undefined
        ? t.mockInit
        : (t.type === 'bool' ? false : 0);
    });
    this.subs = new Set();
    this.timer = null;
  }

  getAll() { return Object.assign({}, this.values); }
  subscribe(fn) { this.subs.add(fn); return () => this.subs.delete(fn); }

  _emit(changed) {
    if (Object.keys(changed).length) {
      this.subs.forEach((f) => f(Object.assign({}, changed)));
    }
  }

  _set(c, id, v) {
    if (this.values[id] !== v) {
      this.values[id] = v;
      c[id] = v;
    }
  }

  write(tag, val) {
    if (!this.tags.has(tag)) return;
    const c = {};
    const prev = this.values[tag];
    this._set(c, tag, val);

    // 离线闭环业务逻辑
    if (tag === 'cmd.start' && val) {
      this._set(c, 'line.running', true);
      this._set(c, 'stack.green', true);
    } else if (tag === 'cmd.stop' && val) {
      this._set(c, 'line.running', false);
      this._set(c, 'stack.green', false);
      this._set(c, 'out.cyl', false);
    } else if (tag === 'cmd.reset' && val) {
      this._set(c, 'out.cyl', false);
      const running = !!this.values['line.running'];
      this._set(c, 'stack.green', running);
    } else if (tag === 'cmd.estop' && val) {
      this._set(c, 'line.running', false);
      this._set(c, 'stack.green', false);
      this._set(c, 'out.cyl', false);
    } else if (tag === 'sensor.pe1' && val && !prev && this.values['line.running']) {
      // 光电检测到工件到位：PLC 延时启动推料气缸电磁阀，并累加计数
      setTimeout(() => {
        if (!this.values['line.running']) return;
        const pushChange = {};
        this._set(pushChange, 'out.cyl', true);
        this._set(pushChange, 'box.count', (Number(this.values['box.count']) || 0) + 1);
        this._emit(pushChange);

        // 气缸推料 600ms 后自动复位缩回
        setTimeout(() => {
          const retChange = {};
          this._set(retChange, 'out.cyl', false);
          this._emit(retChange);
        }, 600);
      }, 250);
    }

    this._emit(c);
  }

  pulse(tag, ms = 150) {
    this.write(tag, true);
    setTimeout(() => this.write(tag, false), ms);
  }
}

// ==============================================================================
// 2. 3D 三段式输送线模型与物理渲染 (Line3D)
// ==============================================================================
class Line3D {
  constructor(el, twin) {
    this.el = el;
    this.twin = twin;
    this.boxes = [];
    this.seq = 0;
    this.spawnTimer = 0.8;
    this.sensor = false;
    this.autoSensor = true;
    this.plcReady = true;
    this.pusherPos = 0; // 0..1 气缸行程
    this.beltOffset = 0;
    this.syncCooldown = 0;

    // 摄像机轨道参数
    this.yaw = 0.75;
    this.pitch = 0.38;
    this.radius = 14.5;
    this.target = new THREE.Vector3(0, 1.1, 0);
    this.dragging = false;
    this.lastPointer = { x: 0, y: 0 };

    this.initScene();
    this.initControls();

    this.lastTick = performance.now();
    this.simTimer = setInterval(() => {
      const now = performance.now();
      const dt = Math.min(0.2, (now - this.lastTick) / 1000);
      this.lastTick = now;
      this.step(dt);
    }, 40);

    requestAnimationFrame(this.renderLoop);
  }

  mat(color, opts = {}) {
    return new THREE.MeshStandardMaterial(Object.assign({
      color,
      roughness: 0.45,
      metalness: 0.55,
    }, opts));
  }

  initScene() {
    const w = this.el.clientWidth, h = this.el.clientHeight;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.el.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(C.bg);
    this.scene.fog = new THREE.FogExp2(C.bg, 0.018);

    this.camera = new THREE.PerspectiveCamera(44, w / h, 0.1, 120);

    // 灯光配置
    const hemi = new THREE.HemisphereLight(0xafd8f2, 0x09151e, 1.2);
    this.scene.add(hemi);

    const mainLight = new THREE.DirectionalLight(0xffffff, 2.2);
    mainLight.position.set(7, 14, 9);
    mainLight.castShadow = true;
    mainLight.shadow.mapSize.set(2048, 2048);
    mainLight.shadow.camera.near = 1;
    mainLight.shadow.camera.far = 36;
    mainLight.shadow.camera.left = -12;
    mainLight.shadow.camera.right = 12;
    mainLight.shadow.camera.top = 10;
    mainLight.shadow.camera.bottom = -8;
    this.scene.add(mainLight);

    const cyanRim = new THREE.PointLight(C.cyan, 25, 20, 2);
    cyanRim.position.set(-7, 5, -5);
    this.scene.add(cyanRim);

    const warmFill = new THREE.PointLight(C.amber, 14, 15, 2);
    warmFill.position.set(6, 4, 4);
    this.scene.add(warmFill);

    // 工业车间地面与网格
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(60, 60),
      new THREE.MeshStandardMaterial({ color: 0x06111a, roughness: 0.88, metalness: 0.15 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);

    const grid = new THREE.GridHelper(60, 60, 0x1b4458, 0x0b212d);
    grid.position.y = 0.005;
    grid.material.transparent = true;
    grid.material.opacity = 0.4;
    this.scene.add(grid);

    // 构建三段式输送线、光电传感器、推料气缸、收集料斗与立柱塔灯
    this.buildThreeStageConveyors();
    this.buildPhotoSensor();
    this.buildPusherCylinder();
    this.buildSortingChute();
    this.buildStackLight();
    this.buildCabinet();

    window.addEventListener('resize', () => this.onResize());
  }

  initControls() {
    const dom = this.renderer.domElement;
    dom.style.touchAction = 'none';

    dom.addEventListener('pointerdown', (e) => {
      this.dragging = true;
      this.lastPointer = { x: e.clientX, y: e.clientY };
      dom.setPointerCapture(e.pointerId);
    });

    dom.addEventListener('pointermove', (e) => {
      if (!this.dragging) return;
      const dx = e.clientX - this.lastPointer.x;
      const dy = e.clientY - this.lastPointer.y;
      this.lastPointer = { x: e.clientX, y: e.clientY };
      this.yaw -= dx * 0.006;
      this.pitch = THREE.MathUtils.clamp(this.pitch + dy * 0.004, 0.12, 0.95);
    });

    dom.addEventListener('pointerup', (e) => {
      this.dragging = false;
      try { dom.releasePointerCapture(e.pointerId); } catch (_) {}
    });

    dom.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.radius = THREE.MathUtils.clamp(this.radius + e.deltaY * 0.012, 8, 26);
    }, { passive: false });
  }

  onResize() {
    const w = this.el.clientWidth, h = this.el.clientHeight;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  // 1. 核心构建：三段独立输送线
  buildThreeStageConveyors() {
    this.conveyorTextures = [];

    // 生成工业输送带防滑纹理
    const makeBeltTex = () => {
      const c = document.createElement('canvas');
      c.width = 256; c.height = 64;
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#0a1d29';
      ctx.fillRect(0, 0, 256, 64);
      ctx.strokeStyle = 'rgba(70, 140, 175, 0.3)';
      ctx.lineWidth = 4;
      for (let i = -64; i < 320; i += 32) {
        ctx.beginPath();
        ctx.moveTo(i, 64);
        ctx.lineTo(i + 48, 0);
        ctx.stroke();
      }
      const tex = new THREE.CanvasTexture(c);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(4, 1);
      tex.colorSpace = THREE.SRGBColorSpace;
      return tex;
    };

    const sections = [
      { name: '段1: 入料输送线', x: -4.0, length: 3.8, color: 0x1f465c },
      { name: '段2: 检测与分拣主线', x: 0.0, length: 3.9, color: 0x245873 },
      { name: '段3: 出料直通线', x: 4.0, length: 3.8, color: 0x1f465c },
    ];

    sections.forEach((sec, idx) => {
      const g = new THREE.Group();
      g.position.set(sec.x, 0, 0);

      // 皮带床身
      const bed = new THREE.Mesh(
        new THREE.BoxGeometry(sec.length, 0.16, 1.34),
        this.mat(0x102432, { roughness: 0.75, metalness: 0.3 })
      );
      bed.position.set(0, 0.92, 0);
      bed.castShadow = true; bed.receiveShadow = true;
      g.add(bed);

      // 顶部输送带带面
      const tex = makeBeltTex();
      this.conveyorTextures.push(tex);
      const topBelt = new THREE.Mesh(
        new THREE.PlaneGeometry(sec.length, 1.32),
        new THREE.MeshStandardMaterial({
          map: tex,
          roughness: 0.8,
          metalness: 0.2,
          color: 0xc4d8e2,
        })
      );
      topBelt.rotation.x = -Math.PI / 2;
      topBelt.position.set(0, 1.005, 0);
      g.add(topBelt);

      // 两侧不锈钢导向护栏
      for (const z of [-0.7, 0.7]) {
        // 如果是段 2 的分拣口位置，分拣侧留出缺口
        if (idx === 1 && z === -0.7) {
          // 分拣推料口：分成两半，留出中间 0.9m 推料出料口
          const halfL = (sec.length - 1.0) / 2;
          const r1 = new THREE.Mesh(new THREE.BoxGeometry(halfL, 0.22, 0.06), this.mat(0x3e6178, { metalness: 0.8 }));
          r1.position.set(-sec.length / 2 + halfL / 2, 1.04, z);
          g.add(r1);
          const r2 = new THREE.Mesh(new THREE.BoxGeometry(halfL, 0.22, 0.06), this.mat(0x3e6178, { metalness: 0.8 }));
          r2.position.set(sec.length / 2 - halfL / 2, 1.04, z);
          g.add(r2);
        } else {
          const rail = new THREE.Mesh(
            new THREE.BoxGeometry(sec.length, 0.22, 0.06),
            this.mat(0x3e6178, { metalness: 0.8, roughness: 0.3 })
          );
          rail.position.set(0, 1.04, z);
          rail.castShadow = true;
          g.add(rail);
        }
      }

      // 支撑支腿
      for (const lx of [-sec.length * 0.4, sec.length * 0.4]) {
        for (const lz of [-0.5, 0.5]) {
          const leg = new THREE.Mesh(
            new THREE.BoxGeometry(0.12, 0.88, 0.12),
            this.mat(0x274152, { metalness: 0.75 })
          );
          leg.position.set(lx, 0.44, lz);
          leg.castShadow = true;
          g.add(leg);
        }
      }

      // 端部导向辊轴
      for (const rx of [-sec.length / 2 + 0.1, sec.length / 2 - 0.1]) {
        const roller = new THREE.Mesh(
          new THREE.CylinderGeometry(0.14, 0.14, 1.3, 16),
          this.mat(0x7c97a8, { metalness: 0.9, roughness: 0.25 })
        );
        roller.rotation.x = Math.PI / 2;
        roller.position.set(rx, 0.92, 0);
        g.add(roller);
      }

      // 独立驱动电机减速箱模型
      const motorGroup = new THREE.Group();
      motorGroup.position.set(sec.length * 0.35, 0.78, 0.82);
      const motorBody = new THREE.Mesh(
        new THREE.CylinderGeometry(0.16, 0.16, 0.42, 16),
        this.mat(0x193b4f, { metalness: 0.8 })
      );
      motorBody.rotation.z = Math.PI / 2;
      motorGroup.add(motorBody);
      const gearBox = new THREE.Mesh(
        new THREE.BoxGeometry(0.28, 0.32, 0.26),
        this.mat(0x142f3f, { metalness: 0.7 })
      );
      gearBox.position.set(-0.24, 0, 0);
      motorGroup.add(gearBox);
      g.add(motorGroup);

      this.scene.add(g);
    });
  }

  // 2. 光电传感器 PE1 龙门检测架
  buildPhotoSensor() {
    const x = -0.5; // 安装在第 2 段输送带的前半程
    const g = new THREE.Group();
    g.position.set(x, 0, 0);

    for (const z of [-0.82, 0.82]) {
      const post = new THREE.Mesh(
        new THREE.BoxGeometry(0.14, 1.45, 0.14),
        this.mat(0x27495d, { metalness: 0.75 })
      );
      post.position.set(0, 1.65, z);
      post.castShadow = true;
      g.add(post);

      const eye = new THREE.Mesh(
        new THREE.SphereGeometry(0.065, 16, 12),
        new THREE.MeshStandardMaterial({
          color: 0x133244,
          emissive: C.cyan,
          emissiveIntensity: 1.5,
        })
      );
      eye.position.set(0, 1.42, z);
      g.add(eye);
      if (z > 0) this.sensorEyeMat = eye.material;
    }

    // 龙门横梁
    const beamTop = new THREE.Mesh(
      new THREE.BoxGeometry(0.22, 0.08, 1.76),
      this.mat(0x1c3a4d, { metalness: 0.7 })
    );
    beamTop.position.set(0, 2.38, 0);
    g.add(beamTop);

    // 激光红外光束
    const laserMat = new THREE.MeshBasicMaterial({
      color: C.cyan,
      transparent: true,
      opacity: 0.65,
    });
    const laser = new THREE.Mesh(
      new THREE.CylinderGeometry(0.012, 0.012, 1.6, 8),
      laserMat
    );
    laser.rotation.x = Math.PI / 2;
    laser.position.set(0, 1.42, 0);
    g.add(laser);

    this.laser = laser;
    this.laserMat = laserMat;
    this.sensorPosX = x;
    this.scene.add(g);
  }

  // 3. 推料气缸机构 (Pusher Cylinder)
  buildPusherCylinder() {
    const x = 0.6; // 安装在光电传感器下游
    const g = new THREE.Group();
    g.position.set(x, 0, 0);

    // 气缸安装架
    const bracket = new THREE.Mesh(
      new THREE.BoxGeometry(0.65, 0.12, 0.7),
      this.mat(0x2b4a5d, { metalness: 0.85 })
    );
    bracket.position.set(0, 1.75, 1.25);
    bracket.castShadow = true;
    g.add(bracket);

    // 气缸缸筒 (Cylinder Body)
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.2, 0.2, 0.95, 24),
      this.mat(C.steel, { metalness: 0.88, roughness: 0.2 })
    );
    body.rotation.x = Math.PI / 2;
    body.position.set(0, 1.28, 1.2);
    body.castShadow = true;
    g.add(body);

    // 活塞杆 (Piston Rod)
    const rod = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05, 0.05, 0.9, 16),
      this.mat(0xe2edf4, { metalness: 0.96, roughness: 0.08 })
    );
    rod.rotation.x = Math.PI / 2;
    rod.position.set(0, 1.28, 0.8);
    g.add(rod);

    // 推料板 (Pusher Plate)
    const plate = new THREE.Mesh(
      new THREE.BoxGeometry(0.55, 0.44, 0.08),
      this.mat(0x42687f, { metalness: 0.85, roughness: 0.3 })
    );
    plate.position.set(0, 1.28, 0.6);
    plate.castShadow = true;
    g.add(plate);

    this.pusherRod = rod;
    this.pusherPlate = plate;
    this.pusherPosX = x;
    this.scene.add(g);
  }

  // 4. 侧向分拣收集滑槽与料斗 (Sorting Chute & Bin)
  buildSortingChute() {
    const g = new THREE.Group();
    g.position.set(0.6, 0, -1.8);

    // 倾斜滑槽
    const chuteMat = this.mat(0x28495d, { metalness: 0.75, roughness: 0.4 });
    const chute = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.05, 1.4), chuteMat);
    chute.rotation.x = 0.32;
    chute.position.set(0, 0.74, 0.55);
    chute.receiveShadow = true;
    g.add(chute);

    // 收集料斗 (Collection Bin)
    const bin = new THREE.Mesh(
      new THREE.BoxGeometry(1.4, 0.65, 1.1),
      this.mat(0x193749, { metalness: 0.65, roughness: 0.4 })
    );
    bin.position.set(0, 0.33, -0.4);
    bin.castShadow = true;
    bin.receiveShadow = true;
    g.add(bin);

    this.scene.add(g);
  }

  // 5. 工业立柱三色塔灯 (Stack Light)
  buildStackLight() {
    const g = new THREE.Group();
    g.position.set(-5.6, 0, -1.8);

    const pole = new THREE.Mesh(
      new THREE.CylinderGeometry(0.04, 0.04, 2.2, 12),
      this.mat(0x385568, { metalness: 0.85 })
    );
    pole.position.y = 1.1;
    g.add(pole);

    this.lamps = {};
    const tiers = [
      { key: 'red', color: C.red, y: 2.25 },
      { key: 'amber', color: C.amber, y: 2.05 },
      { key: 'green', color: C.green, y: 1.85 },
    ];

    tiers.forEach((t) => {
      const mat = new THREE.MeshStandardMaterial({
        color: 0x0a1c28,
        emissive: t.color,
        emissiveIntensity: 0.05,
        roughness: 0.3,
      });
      const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.14, 18, 12), mat);
      lamp.position.y = t.y;
      g.add(lamp);
      this.lamps[t.key] = mat;
    });

    this.scene.add(g);
  }

  // 6. 电控柜 (Cabinet)
  buildCabinet() {
    const g = new THREE.Group();
    g.position.set(-5.6, 0, 1.8);
    const cab = new THREE.Mesh(
      new THREE.BoxGeometry(1.2, 1.85, 0.8),
      this.mat(0x183446, { metalness: 0.7, roughness: 0.45 })
    );
    cab.position.y = 0.92;
    cab.castShadow = true;
    g.add(cab);
    this.scene.add(g);
  }

  // 创建 3D 工件
  createBox() {
    const id = ++this.seq;
    const g = new THREE.Group();
    const isCyan = id % 2 === 0;
    const boxColor = isCyan ? C.cyan : C.amber;

    const body = new THREE.Mesh(
      new THREE.BoxGeometry(0.55, 0.45, 0.55),
      this.mat(0x1a3a4e, {
        metalness: 0.35,
        roughness: 0.6,
        emissive: boxColor,
        emissiveIntensity: 0.05,
      })
    );
    body.castShadow = true;
    g.add(body);

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(body.geometry),
      new THREE.LineBasicMaterial({ color: boxColor, transparent: true, opacity: 0.85 })
    );
    g.add(edges);

    g.position.set(-5.8, 1.25, 0);
    this.scene.add(g);

    return {
      id,
      x: -5.8,
      y: 1.25,
      z: 0,
      vy: 0,
      mode: 'belt', // 'belt' | 'pushed' | 'dropped'
      mesh: g,
    };
  }

  // 物理步进与闭环感知逻辑
  step(dt) {
    const running = !!this.twin.get('line.running');
    const green = !!this.twin.get('stack.green');
    const cylCmd = !!this.twin.get('out.cyl');

    // 输送线皮带纹理流动
    if (running) {
      this.conveyorTextures.forEach((tex) => {
        tex.offset.x -= 0.6 * dt;
      });

      // 生成工件
      this.spawnTimer -= dt;
      if (this.spawnTimer <= 0) {
        this.spawnTimer = 2.4;
        this.boxes.push(this.createBox());
      }
    }

    // 工件位移
    const speed = running ? 1.4 : 0;
    for (const b of this.boxes) {
      if (b.mode === 'belt') {
        b.x += speed * dt;
      } else if (b.mode === 'pushed') {
        b.z -= 2.6 * dt;
        b.vy += 6.5 * dt;
        b.y -= b.vy * dt;
        if (b.y < 0.35) b.mode = 'dropped';
      }
    }

    // 传感器 PE1 碰撞感应检测 (X 位于 -0.5 附近)
    if (this.autoSensor) {
      this.sensor = this.boxes.some(
        (b) => b.mode === 'belt' && Math.abs(b.x - this.sensorPosX) < 0.32
      );
    } else {
      this.sensor = !!this.twin.get('sensor.pe1');
    }

    // 气缸行程模拟 (0 缩回，1 伸出)
    const targetStroke = cylCmd ? 1 : 0;
    this.pusherPos += (targetStroke - this.pusherPos) * Math.min(1, dt * 10);
    if (this.pusherPos < 0.01) this.pusherPos = 0;

    // 气缸活塞与推板 3D 位移更新
    const strokeLen = this.pusherPos * 0.85;
    this.pusherRod.position.z = 0.8 - strokeLen / 2;
    this.pusherRod.scale.y = 1 + strokeLen * 0.9;
    this.pusherPlate.position.z = 0.6 - strokeLen;

    // 气缸推料判定 (工件到达气缸推料口 X 位于 0.6 附近)
    if (this.pusherPos > 0.25) {
      for (const b of this.boxes) {
        if (b.mode === 'belt' && Math.abs(b.x - this.pusherPosX) < 0.45 && b.z > -0.2) {
          b.mode = 'pushed';
          b.vy = 0.1;
        }
      }
    }

    // 清理离开产线的工件
    this.boxes = this.boxes.filter((b) => {
      const keep = b.mode === 'belt' ? b.x < 6.2 : b.y > 0.2;
      if (!keep) this.scene.remove(b.mesh);
      return keep;
    });

    this.boxes.forEach((b) => b.mesh.position.set(b.x, b.y, b.z));

    // 传感器视觉特效（激光束亮红光）
    this.laserMat.color.setHex(this.sensor ? C.red : C.cyan);
    this.laserMat.opacity = this.sensor ? 0.95 : 0.45;
    if (this.sensorEyeMat) {
      this.sensorEyeMat.emissive.setHex(this.sensor ? C.red : C.cyan);
      this.sensorEyeMat.emissiveIntensity = this.sensor ? 2.5 : 1.2;
    }

    // 塔灯视觉联动
    this.lamps.green.emissiveIntensity = (running || green) ? 2.8 : 0.05;
    this.lamps.red.emissiveIntensity = !running ? 1.2 : 0.05;

    // 自动向 PLC 回写 PE1 传感器信号 (10 Hz 节流)
    this.syncCooldown += dt;
    if (this.syncCooldown >= 0.1) {
      this.syncCooldown = 0;
      if (this.autoSensor && (this.twin.status === 'online' || this.twin.status === 'mock')) {
        const curPe = !!this.twin.get('sensor.pe1');
        if (curPe !== this.sensor) {
          this.twin.writeMany({ 'sensor.pe1': this.sensor }).catch(() => {});
        }
      }
    }

    this.updateHUD(running);
  }

  updateHUD(running) {
    const count = this.twin.get('box.count');
    const pe = this.twin.get('sensor.pe1');
    const cyl = this.twin.get('out.cyl');

    $('#hudCount').textContent = count === undefined ? '—' : String(count);
    $('#hudPe').textContent = pe ? '1' : '0';
    $('#hudPe').style.color = pe ? '#ff5d63' : '';
    $('#hudQ').textContent = cyl ? '1' : '0';
    $('#hudQ').style.color = cyl ? '#ffb454' : '';

    const st = $('#hudState');
    st.textContent = running ? 'RUNNING' : 'STOPPED';
    st.style.color = running ? '#54e6a1' : '#7693a8';

    // 侧边栏 Badge 刷新
    const updateBadge = (id, val, onClass = 'on') => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = val === undefined ? '—' : (typeof val === 'boolean' ? (val ? '1' : '0') : val);
      el.classList.toggle(onClass, !!val);
    };

    updateBadge('badge-sensor-pe1', pe, 'on-red');
    updateBadge('badge-cmd-start', this.twin.get('cmd.start'));
    updateBadge('badge-cmd-stop', this.twin.get('cmd.stop'));
    updateBadge('badge-line-running', running, 'on-green');
    updateBadge('badge-out-cyl', cyl, 'on');
    updateBadge('badge-stack-green', this.twin.get('stack.green'), 'on-green');
    updateBadge('badge-box-count', count);
  }

  renderLoop = () => {
    requestAnimationFrame(this.renderLoop);

    // 摄像机轻微自动缓动
    if (!this.dragging) {
      this.yaw += 0.02 * 0.016;
    }

    const cp = Math.cos(this.pitch);
    this.camera.position.set(
      this.target.x + Math.sin(this.yaw) * cp * this.radius,
      this.target.y + Math.sin(this.pitch) * this.radius,
      this.target.z + Math.cos(this.yaw) * cp * this.radius
    );
    this.camera.lookAt(this.target);
    this.renderer.render(this.scene, this.camera);
  }
}

// ==============================================================================
// 3. 页面生命周期与通信调度 (Boot)
// ==============================================================================
let twin = null;
let mock = null;
let line = null;
let manifest = null;
let mode = 'offline';
let gatewayUrl = new URLSearchParams(location.search).get('ws') || 'ws://127.0.0.1:8765/ws';
let gatewayToken = new URLSearchParams(location.search).get('token') || '';
let plcTarget = null;
let lastPlc = { state: 'unknown', message: '' };

function setControls(enabled) {
  QS('[data-cmd]').forEach((b) => { b.disabled = !enabled; });
  const pulseBtn = $('#btnPulsePe1');
  if (pulseBtn) pulseBtn.disabled = !enabled;
}

function showWait(text) {
  $('#waitText').textContent = text;
  $('#waitOverlay').classList.remove('hidden');
}

function hideWait() {
  $('#waitOverlay').classList.add('hidden');
}

function setLinkNote(text, isError = false) {
  const el = $('#linkMsg');
  el.textContent = text;
  el.style.color = isError ? '#ff5d63' : '#54e6a1';
}

function setMode(nextMode, openModal = true) {
  mode = nextMode;
  const isOffline = mode === 'offline';
  $('#modeOffline').classList.toggle('active', isOffline);
  $('#modeOnline').classList.toggle('active', !isOffline);
  $('#panelConnBadge').textContent = isOffline ? '离线 MOCK' : '实时在线';
  $('#panelConnBadge').classList.toggle('on-green', !isOffline && lastPlc.state === 'connected');

  if (!twin) return;

  if (isOffline) {
    $('#dlg').close();
    twin.useMock(mock);
    hideWait();
    setControls(true);
  } else {
    // 切到在线模式：彻底重置 values，避免 Mock 数据污染真实 PLC 监视视图
    twin.useMock(null);
    setControls(false);
    showWait('输入 PLC 地址后开始连接');
    if (openModal) $('#dlg').showModal();
  }
}

function connectToPlc() {
  const ip = $('#plcIp').value.trim();
  if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip)) {
    setLinkNote('请输入合法的 IPv4 地址', true);
    return;
  }
  const model = $('#plcModel')?.value || 's7-1200_1500';
  const rack = parseInt($('#plcRack').value, 10) || 0;
  const slot = parseInt($('#plcSlot').value, 10) || 1;

  plcTarget = { ip, rack, slot };
  localStorage.setItem('tiaTwin.plcIp', ip);
  localStorage.setItem('tiaTwin.plcModel', model);
  localStorage.setItem('tiaTwin.plcRack', rack);
  localStorage.setItem('tiaTwin.plcSlot', slot);

  showWait(`正在连接 S7 PLC (${ip}, Rack ${rack}/Slot ${slot})…`);
  twin.url = gatewayUrl;
  twin.token = gatewayToken;

  if (twin.status === 'online') {
    twin.configurePlc(plcTarget).catch((err) => {
      showWait('PLC 连接异常，请重试');
      setLinkNote(err.message, true);
    });
  } else {
    twin.connect();
  }
}

async function boot() {
  manifest = await TiaTwin.loadManifest('./twin.manifest.json');
  $('#title').textContent = manifest.title || manifest.project;
  mock = new MockPlc3D(manifest);

  const savedIp = localStorage.getItem('tiaTwin.plcIp') || manifest.plc?.ip || '192.168.0.1';
  $('#plcIp').value = savedIp;

  const savedModel = localStorage.getItem('tiaTwin.plcModel') || 's7-1200_1500';
  if ($('#plcModel')) $('#plcModel').value = savedModel;
  if (localStorage.getItem('tiaTwin.plcRack') !== null) {
    $('#plcRack').value = localStorage.getItem('tiaTwin.plcRack');
  }
  if (localStorage.getItem('tiaTwin.plcSlot') !== null) {
    $('#plcSlot').value = localStorage.getItem('tiaTwin.plcSlot');
  }

  twin = await TiaTwin.create({
    manifest,
    url: gatewayUrl,
    token: gatewayToken,
    mock,
  });

  line = new Line3D($('#stage'), twin);

  // 网关通信状态事件
  twin.on('status', ({ state, error }) => {
    if (mode !== 'online') return;
    if (state === 'online' && plcTarget) {
      twin.configurePlc(plcTarget).catch((err) => {
        showWait('PLC 配置失败');
        setLinkNote(err.message, true);
      });
    } else if (state === 'offline') {
      setControls(false);
      showWait('本地 S7 网关未连接');
      setLinkNote('本地网关未启动，请双击【双击启动.bat】', true);
    }
  });

  // PLC 硬件物理连接状态事件
  twin.on('plc', (p) => {
    lastPlc = p || { state: 'unknown', message: '' };
    if (mode !== 'online') return;

    if (lastPlc.state === 'connected') {
      hideWait();
      setControls(true);
      $('#panelConnBadge').textContent = 'PLC 已连通';
      $('#panelConnBadge').classList.add('on-green');
      if ($('#dlg').open) setTimeout(() => $('#dlg').close(), 400);
    } else if (lastPlc.state === 'error') {
      setControls(false);
      showWait('PLC 通信异常');
      setLinkNote('连接失败：' + (p.message || '请检查 PLC IP、PUT/GET 及非优化 DB'), true);
    } else if (lastPlc.state === 'waiting') {
      showWait('正在建立 S7comm 握手…');
    }
  });

  // 按钮交互
  QS('[data-cmd]').forEach((btn) => {
    btn.addEventListener('click', () => {
      twin.pulse(btn.dataset.cmd, 200).catch((e) => console.error(e));
    });
  });

  // 手动模拟光电点动脉冲
  $('#btnPulsePe1').addEventListener('click', () => {
    twin.pulse('sensor.pe1', 300).catch((e) => console.error(e));
  });

  // 模式切换
  $('#modeOffline').addEventListener('click', () => setMode('offline'));
  $('#modeOnline').addEventListener('click', () => setMode('online', true));

  // 对话框操作
  $('#plcModel')?.addEventListener('change', (e) => {
    const model = e.target.value;
    if (model === 's7-1200_1500' || model === 'plcsim_adv') {
      $('#plcRack').value = 0;
      $('#plcSlot').value = 1;
    } else if (model === 's7-300') {
      $('#plcRack').value = 0;
      $('#plcSlot').value = 2;
    }
  });

  $('#btnConnect').addEventListener('click', connectToPlc);
  $('#btnRetry').addEventListener('click', connectToPlc);
  $('#btnClose').addEventListener('click', () => $('#dlg').close());

  // 自动物理碰撞开关
  $('#autoSensor').addEventListener('change', (e) => {
    if (line) line.autoSensor = e.target.checked;
  });

  setMode('offline', false);
}

boot().catch((err) => {
  console.error('Boot error:', err);
  document.body.insertAdjacentHTML(
    'beforeend',
    `<div style="position:fixed;inset:0;display:grid;place-items:center;background:#050d14;color:#ff5d63;font:14px monospace;z-index:99">3D 孪生启动失败：${err.message}</div>`
  );
});
