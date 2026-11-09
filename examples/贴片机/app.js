/**
 * =========================================================================
 * SMT 高速贴片机生产线 · 数字孪生 Web 引擎 (Three.js + TIA Twin Client)
 * 工业级双模式：离线真运动学自主仿真 + 西门子 S7/Modbus 实时网关驱动
 * 支持中英文双语即时无缝切换 (Bilingual i18n: English / 简体中文)
 * =========================================================================
 */

// 0. 中英文国际化语言字典 (i18n Translation Dictionary)
const I18N = {
  zh: {
    brandTitle: "SMT-PRO 5000 · 高速贴片机生产线数字孪生系统",
    brandSubtitle: "SIEMENS S7 & MODBUS MULTI-PROTOCOL TWIN · VER 4.8",
    statusRunning: "产线运行中 (NORMAL)",
    statusPaused: "生产已暂停 (PAUSED)",
    statusEStop: "产线紧急停机 (E-STOP)",
    gwOffline: "模式: 离线自主仿真",
    gwConnected: "网关已连通 (S7/MODBUS)",
    batchLabel: "生产批次:",
    tactLabel: "节拍:",
    btnXRay: "🔍 外壳透视",
    btnTags: "🏷️ 工位标注",
    btnPause: "⏸️ 暂停生产",
    btnResume: "▶️ 恢复生产",
    btnEStop: "🛑 产线急停",
    btnResetEStop: "🔄 复位急停",
    panelMetricsTitle: "📊 综合生产效能",
    panelMetricsBadge: "LIVE METRICS",
    kpiCphLabel: "实时贴片速度 (CPH)",
    kpiCphSub: "额定 45,000 CPH",
    kpiYieldLabel: "综合良品率 (Yield)",
    kpiYieldSub: "缺陷 3 / 误报 1",
    kpiCountLabel: "今日生产总数",
    kpiCountSub: "目标: 3,000 PCS",
    kpiOeeLabel: "设备综合效率 (OEE)",
    kpiOeeSub: "开动率 97.8%",
    waveTitle: "实时贴装速度动态波形 (CPH)",
    axisTitle: "🎯 贴片机核心运动轴坐标 (mm)",
    axisXLabel: "X 轴贴装小车",
    axisYLabel: "Y 轴双驱龙门梁",
    visionTitle: "飞行视觉相机补偿 (Vision Alignment)",
    feederTitle: "📦 飞达料站剩余元件监控 (Reels)",
    feederBadge: "12 FEEDERS",
    nozzleTitle: "💨 8 联装真空吸嘴矩阵 (kPa)",
    ovenTitle: "🔥 8 温区热风回流焊实时温控",
    viewLabel: "视角预设:",
    viewOverview: "产线全景",
    viewSmt: "贴片机特写",
    viewFeeder: "飞达料站",
    viewOven: "回流焊透视",
    viewAoi: "AOI 光学检测",
    viewPcb: "跟随当前 PCB",
    btnDefect: "⚠️ 模拟缺陷报警",
    btnSpeed: "⏩ 速度: ",
    logReady: "SYSTEM READY · 贴片机龙门双驱同步对准完成，激光视觉就绪",
    tagStations: ["01 上板机", "02 锡膏印刷机", "03 接驳台", "04 高速贴片机", "05 回流焊接炉", "06 AOI 光学检测", "07 自动下板机"],
    zoneNames: ['预热1', '预热2', '恒温1', '恒温2', '回流1', '峰值2', '降温1', '冷却2'],
    langBtn: "🌐 English"
  },
  en: {
    brandTitle: "SMT-PRO 5000 · High-Speed Pick & Place Digital Twin",
    brandSubtitle: "SIEMENS S7 & MODBUS MULTI-PROTOCOL TWIN · VER 4.8",
    statusRunning: "Line Running (NORMAL)",
    statusPaused: "Production Paused (PAUSED)",
    statusEStop: "Emergency Stop (E-STOP)",
    gwOffline: "Mode: Offline Simulation",
    gwConnected: "Gateway Linked (S7/MODBUS)",
    batchLabel: "Batch ID:",
    tactLabel: "Tact:",
    btnXRay: "🔍 X-Ray Shell",
    btnTags: "🏷️ 3D Tags",
    btnPause: "⏸️ Pause",
    btnResume: "▶️ Resume",
    btnEStop: "🛑 E-Stop",
    btnResetEStop: "🔄 Reset E-Stop",
    panelMetricsTitle: "📊 Production Performance",
    panelMetricsBadge: "LIVE METRICS",
    kpiCphLabel: "Placement Speed (CPH)",
    kpiCphSub: "Rated: 45,000 CPH",
    kpiYieldLabel: "Overall Yield Rate",
    kpiYieldSub: "Defects 3 / False 1",
    kpiCountLabel: "Today's Output",
    kpiCountSub: "Target: 3,000 PCS",
    kpiOeeLabel: "Overall Efficiency (OEE)",
    kpiOeeSub: "Availability: 97.8%",
    waveTitle: "Real-time CPH Waveform",
    axisTitle: "🎯 Core Axis Coordinates (mm)",
    axisXLabel: "X Placement Head",
    axisYLabel: "Y Dual-Drive Gantry",
    visionTitle: "Flying Vision Alignment Compensation",
    feederTitle: "📦 Feeder Bay Component Stock (Reels)",
    feederBadge: "12 FEEDERS",
    nozzleTitle: "💨 8-Nozzle Vacuum Array (kPa)",
    ovenTitle: "🔥 8-Zone Reflow Oven Temperatures",
    viewLabel: "Camera View:",
    viewOverview: "Overview",
    viewSmt: "SMT Mounter",
    viewFeeder: "Feeder Bay",
    viewOven: "Reflow X-Ray",
    viewAoi: "AOI Camera",
    viewPcb: "Follow PCB",
    btnDefect: "⚠️ Sim Defect",
    btnSpeed: "⏩ Speed: ",
    logReady: "SYSTEM READY · Dual-drive gantry aligned, laser vision ready",
    tagStations: ["01 Loader", "02 Stencil Printer", "03 Buffer", "04 SMT Mounter", "05 Reflow Oven", "06 AOI Camera", "07 Unloader"],
    zoneNames: ['Preheat 1', 'Preheat 2', 'Soak 1', 'Soak 2', 'Reflow 1', 'Peak 2', 'Cool 1', 'Cool 2'],
    langBtn: "🌐 简体中文"
  }
};

let currentLang = 'zh';

// 1. 初始化 WebGL 视口与管线
const container = document.getElementById('webgl-container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0f18);
scene.fog = new THREE.FogExp2(0x0a0f18, 0.015);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 150);
camera.position.set(2, 10, 18);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.maxPolarAngle = Math.PI / 2 - 0.03;
controls.minDistance = 3;
controls.maxDistance = 55;
controls.target.set(1.0, 2.5, 0);

// 2. 工业光照环境
const ambientLight = new THREE.AmbientLight(0x94a3b8, 0.75);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 1.3);
dirLight.position.set(15, 25, 12);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 2048;
dirLight.shadow.mapSize.height = 2048;
dirLight.shadow.camera.near = 0.5;
dirLight.shadow.camera.far = 60;
const d = 25;
dirLight.shadow.camera.left = -d;
dirLight.shadow.camera.right = d;
dirLight.shadow.camera.top = d;
dirLight.shadow.camera.bottom = -d;
dirLight.shadow.bias = -0.0005;
scene.add(dirLight);

const blueFillLight = new THREE.DirectionalLight(0x38bdf8, 0.5);
blueFillLight.position.set(-15, 12, -10);
scene.add(blueFillLight);

// 3. 材质库配置 (工业级 PBR)
const MATS = {
  floor: new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.65, metalness: 0.2 }),
  machineBodyDark: new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.45, metalness: 0.35 }),
  machineBodyBlue: new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.35, metalness: 0.25 }),
  machineWhite: new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.3, metalness: 0.2 }),
  steel: new THREE.MeshStandardMaterial({ color: 0xcbd5e1, roughness: 0.2, metalness: 0.9 }),
  darkMetal: new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.3, metalness: 0.85 }),
  brass: new THREE.MeshStandardMaterial({ color: 0xd97706, roughness: 0.25, metalness: 0.9 }),
  esdBelt: new THREE.MeshStandardMaterial({ color: 0x090d16, roughness: 0.85, metalness: 0.05 }),
  acrylic: new THREE.MeshPhysicalMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.32, roughness: 0.05, transmission: 0.7, thickness: 0.4 }),
  safetyYellow: new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.4, metalness: 0.1 }),
  pcbBoard: new THREE.MeshStandardMaterial({ color: 0x047857, roughness: 0.35, metalness: 0.2 }),
  icChip: new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.4, metalness: 0.4 }),
  ledGreen: new THREE.MeshBasicMaterial({ color: 0x10b981 }),
  ledYellow: new THREE.MeshBasicMaterial({ color: 0xfbbf24 }),
  ledRed: new THREE.MeshBasicMaterial({ color: 0xef4444 }),
  ovenGlowPre: new THREE.MeshBasicMaterial({ color: 0xf59e0b }),
  ovenGlowPeak: new THREE.MeshBasicMaterial({ color: 0xef4444 }),
  aoiStrobe: new THREE.MeshBasicMaterial({ color: 0x38bdf8 })
};

// 4. 地面与网格
const floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 40), MATS.floor);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

const gridHelper = new THREE.GridHelper(70, 70, 0x38bdf8, 0x1e293b);
gridHelper.position.y = 0.01;
scene.add(gridHelper);

/**
 * =========================================================================
 * 生产线物理基准参数（绝不穿模核心规范）
 * =========================================================================
 */
const TRACK_Y = 2.40;       // 传送带轨顶基准高
const TRACK_Z = 0.0;        // 导轨中心 Z 轴基准
const PCB_WIDTH = 1.6;
const PCB_LENGTH = 2.2;
const PCB_THICKNESS = 0.06;

function buildConveyorTracks() {
  const group = new THREE.Group();
  const railLength = 34;
  const railGeo = new THREE.BoxGeometry(railLength, 0.14, 0.08);
  
  const railLeft = new THREE.Mesh(railGeo, MATS.darkMetal);
  railLeft.position.set(1.0, TRACK_Y - 0.07, -PCB_WIDTH / 2 - 0.05);
  railLeft.castShadow = true;
  group.add(railLeft);

  const railRight = new THREE.Mesh(railGeo, MATS.darkMetal);
  railRight.position.set(1.0, TRACK_Y - 0.07, PCB_WIDTH / 2 + 0.05);
  railRight.castShadow = true;
  group.add(railRight);

  const beltGeo = new THREE.BoxGeometry(railLength, 0.02, 0.06);
  const beltL = new THREE.Mesh(beltGeo, MATS.esdBelt);
  beltL.position.set(1.0, TRACK_Y - 0.01, -PCB_WIDTH / 2);
  group.add(beltL);

  const beltR = new THREE.Mesh(beltGeo, MATS.esdBelt);
  beltR.position.set(1.0, TRACK_Y - 0.01, PCB_WIDTH / 2);
  group.add(beltR);

  for (let x = -15; x <= 17; x += 3.5) {
    const legGeo = new THREE.CylinderGeometry(0.06, 0.08, TRACK_Y - 0.14, 16);
    const legL = new THREE.Mesh(legGeo, MATS.darkMetal);
    legL.position.set(x, (TRACK_Y - 0.14)/2, -PCB_WIDTH/2 - 0.05);
    group.add(legL);

    const legR = new THREE.Mesh(legGeo, MATS.darkMetal);
    legR.position.set(x, (TRACK_Y - 0.14)/2, PCB_WIDTH/2 + 0.05);
    group.add(legR);
  }
  return group;
}
scene.add(buildConveyorTracks());

const shellMeshes = [];

// 工位 1: 上板机
function buildLoader(x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);
  const base = new THREE.Mesh(new THREE.BoxGeometry(1.8, TRACK_Y - 0.2, 2.2), MATS.machineBodyDark);
  base.position.set(0, (TRACK_Y - 0.2) / 2, 0);
  base.castShadow = true;
  group.add(base);

  const tower = new THREE.Mesh(new THREE.BoxGeometry(0.6, 2.2, 1.8), MATS.machineBodyBlue);
  tower.position.set(-0.5, TRACK_Y + 1.0, 0);
  group.add(tower);
  shellMeshes.push(tower);

  for (let i = 0; i < 6; i++) {
    const slot = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.04, 1.4), MATS.pcbBoard);
    slot.position.set(0.1, TRACK_Y + 0.3 + i * 0.25, 0);
    group.add(slot);
  }
  return group;
}
scene.add(buildLoader(-12.5));

// 工位 2: 锡膏印刷机
let printerSqueegee;
function buildPrinter(x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);
  const body = new THREE.Mesh(new THREE.BoxGeometry(2.6, 3.4, 2.8), MATS.machineBodyDark);
  body.position.set(0, 1.7, 0);
  group.add(body);
  shellMeshes.push(body);

  const win = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.2, 0.05), MATS.acrylic);
  win.position.set(0, 2.2, 1.41);
  group.add(win);

  printerSqueegee = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.25, 1.5), MATS.brass);
  printerSqueegee.position.set(0, TRACK_Y + 0.3, 0);
  group.add(printerSqueegee);
  return group;
}
scene.add(buildPrinter(-8.5));

// 工位 3: 缓冲接驳台
function buildBuffer(x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);
  const baseL = new THREE.Mesh(new THREE.BoxGeometry(0.2, TRACK_Y - 0.2, 1.8), MATS.machineBodyDark);
  baseL.position.set(-0.8, (TRACK_Y - 0.2)/2, 0);
  group.add(baseL);
  const baseR = new THREE.Mesh(new THREE.BoxGeometry(0.2, TRACK_Y - 0.2, 1.8), MATS.machineBodyDark);
  baseR.position.set(0.8, (TRACK_Y - 0.2)/2, 0);
  group.add(baseR);
  return group;
}
scene.add(buildBuffer(-5.0));

// 工位 4: 高速多功能贴片机
let gantryY;
let carriageX;
let nozzleArray = [];
let feederReels = [];
let statusTowerLights = {};

function buildPickAndPlace(x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);

  const base = new THREE.Mesh(new THREE.BoxGeometry(4.2, TRACK_Y - 0.1, 3.4), MATS.darkMetal);
  base.position.set(0, (TRACK_Y - 0.1)/2, 0);
  base.castShadow = true;
  group.add(base);

  const shell = new THREE.Mesh(new THREE.BoxGeometry(4.2, 2.0, 3.4), MATS.machineWhite);
  shell.position.set(0, TRACK_Y + 1.0, 0);
  group.add(shell);
  shellMeshes.push(shell);

  const frontGlass = new THREE.Mesh(new THREE.BoxGeometry(3.6, 1.3, 0.06), MATS.acrylic);
  frontGlass.position.set(0, TRACK_Y + 1.0, 1.72);
  group.add(frontGlass);

  // 12 站位飞达料站
  const feederBase = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.3, 0.8), MATS.darkMetal);
  feederBase.position.set(0, TRACK_Y - 0.1, 1.35);
  group.add(feederBase);

  for (let f = 0; f < 12; f++) {
    const fx = -1.45 + f * 0.26;
    const fz = 1.45;
    const reel = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.04, 24), MATS.machineWhite);
    reel.rotation.x = Math.PI / 2;
    reel.position.set(fx, TRACK_Y + 0.35, fz + 0.2);
    group.add(reel);
    feederReels.push(reel);
  }

  // Y 轴双驱龙门横梁
  gantryY = new THREE.Group();
  gantryY.position.set(0, TRACK_Y + 1.6, 0);
  const beam = new THREE.Mesh(new THREE.BoxGeometry(3.7, 0.22, 0.35), MATS.darkMetal);
  beam.castShadow = true;
  gantryY.add(beam);

  // X 轴高速小车
  carriageX = new THREE.Group();
  carriageX.position.set(0, 0, 0);
  const carriageBody = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.38, 0.45), MATS.steel);
  carriageBody.position.y = -0.15;
  carriageBody.castShadow = true;
  carriageX.add(carriageBody);

  // 8 联装真空吸嘴矩阵
  for (let n = 0; n < 8; n++) {
    const nx = -0.30 + n * 0.085;
    const nzGroup = new THREE.Group();
    nzGroup.position.set(nx, -0.28, 0);

    const collet = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.18, 16), MATS.brass);
    collet.position.y = -0.05;
    nzGroup.add(collet);

    const tip = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.12, 16), MATS.steel);
    tip.position.y = -0.18;
    nzGroup.add(tip);

    carriageX.add(nzGroup);
    nozzleArray.push(nzGroup);
  }

  gantryY.add(carriageX);
  group.add(gantryY);

  // 顶部三色声光报警塔
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.6), MATS.steel);
  pole.position.set(-1.8, TRACK_Y + 2.3, -1.3);
  group.add(pole);

  statusTowerLights.red = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.09, 16), MATS.darkMetal);
  statusTowerLights.red.position.set(-1.8, TRACK_Y + 2.65, -1.3);
  group.add(statusTowerLights.red);

  statusTowerLights.yellow = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.09, 16), MATS.darkMetal);
  statusTowerLights.yellow.position.set(-1.8, TRACK_Y + 2.75, -1.3);
  group.add(statusTowerLights.yellow);

  statusTowerLights.green = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.09, 16), MATS.ledGreen);
  statusTowerLights.green.position.set(-1.8, TRACK_Y + 2.85, -1.3);
  group.add(statusTowerLights.green);

  return group;
}
scene.add(buildPickAndPlace(0.0));

// 工位 5: 8温区回流焊炉
const ovenZoneMeshes = [];
function buildReflowOven(x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);
  const ovenLength = 9.2;

  const lowerBody = new THREE.Mesh(new THREE.BoxGeometry(ovenLength, TRACK_Y - 0.1, 2.6), MATS.machineBodyDark);
  lowerBody.position.set(0, (TRACK_Y - 0.1)/2, 0);
  group.add(lowerBody);

  const upperHood = new THREE.Mesh(new THREE.BoxGeometry(ovenLength, 1.4, 2.6), MATS.machineBodyBlue);
  upperHood.position.set(0, TRACK_Y + 0.9, 0);
  group.add(upperHood);
  shellMeshes.push(upperHood);

  for (let z = 0; z < 8; z++) {
    const zx = -3.8 + z * 1.08;
    const isPeak = (z >= 4 && z <= 6);
    const zMat = isPeak ? MATS.ovenGlowPeak : MATS.ovenGlowPre;

    const heatBox = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.12, 1.8), zMat);
    heatBox.position.set(zx, TRACK_Y + 0.45, 0);
    group.add(heatBox);
    ovenZoneMeshes.push(heatBox);

    const win = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.3, 0.04), MATS.acrylic);
    win.position.set(zx, TRACK_Y + 0.9, 1.32);
    group.add(win);
  }
  return group;
}
scene.add(buildReflowOven(7.0));

// 工位 6: AOI 检测
let aoiLightDome;
function buildAOI(x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);
  const body = new THREE.Mesh(new THREE.BoxGeometry(2.4, 3.2, 2.6), MATS.machineBodyDark);
  body.position.set(0, 1.6, 0);
  group.add(body);
  shellMeshes.push(body);

  aoiLightDome = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.35, 0.25, 24), MATS.aoiStrobe);
  aoiLightDome.position.set(0, TRACK_Y + 0.45, 0);
  group.add(aoiLightDome);
  return group;
}
scene.add(buildAOI(13.5));

// 工位 7: 下板收料
function buildUnloader(x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);
  const base = new THREE.Mesh(new THREE.BoxGeometry(1.8, TRACK_Y - 0.2, 2.2), MATS.machineBodyDark);
  base.position.set(0, (TRACK_Y - 0.2)/2, 0);
  group.add(base);

  const passBox = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.8, 1.4), MATS.machineBodyBlue);
  passBox.position.set(0, TRACK_Y + 0.9, 0);
  group.add(passBox);
  return group;
}
scene.add(buildUnloader(16.8));

// 动态 PCB 板流转
class ActivePCB {
  constructor(initialX) {
    this.mesh = new THREE.Group();
    const board = new THREE.Mesh(new THREE.BoxGeometry(PCB_LENGTH, PCB_THICKNESS, PCB_WIDTH), MATS.pcbBoard);
    board.position.y = PCB_THICKNESS / 2;
    board.castShadow = true;
    this.mesh.add(board);

    // 芯片组
    const bga = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.04, 0.45), MATS.icChip);
    bga.position.set(-0.25, PCB_THICKNESS + 0.02, 0);
    this.mesh.add(bga);

    const qfp = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.03, 0.35), MATS.icChip);
    qfp.position.set(0.45, PCB_THICKNESS + 0.015, -0.3);
    this.mesh.add(qfp);

    this.mesh.position.set(initialX, TRACK_Y, TRACK_Z);
    scene.add(this.mesh);
  }
}

const pcbQueue = [
  new ActivePCB(-12.5),
  new ActivePCB(-8.5),
  new ActivePCB(0.0),
  new ActivePCB(5.2),
  new ActivePCB(8.8),
  new ActivePCB(13.5)
];

/**
 * =========================================================================
 * 贴片机高精运动学与物理运动循环 (Kinematics & Animation FSM)
 * =========================================================================
 */
let isRunning = true;
let isEStop = false;
let simSpeed = 1.0;
let animationTime = 0;
let isGatewayMode = false;

const SMT_STATES = {
  MOVE_TO_FEEDER: 0,
  PICK_COMPONENT: 1,
  MOVE_TO_VISION: 2,
  MOVE_TO_PCB: 3,
  PLACE_COMPONENT: 4
};
let smtState = SMT_STATES.MOVE_TO_FEEDER;
let smtTimer = 0;
let currentFeederIndex = 0;
let targetPCBPos = { x: 0, z: 0 };

function updateSMTKinematics(delta) {
  if (!isRunning || isEStop) return;

  const dt = delta * simSpeed;
  animationTime += dt;
  smtTimer += dt;

  // 1. 锡膏印刷机刮刀往返
  if (printerSqueegee) {
    printerSqueegee.position.z = Math.sin(animationTime * 1.5) * 0.55;
  }

  // 2. 飞达卷料微动
  if (feederReels[currentFeederIndex]) {
    feederReels[currentFeederIndex].rotation.z += 0.01 * simSpeed;
  }

  // 3. 贴装头运动
  if (!isGatewayMode) {
    const PICK_Z_DEPTH = -0.16;
    const PLACE_Z_DEPTH = -0.14;

    switch (smtState) {
      case SMT_STATES.MOVE_TO_FEEDER:
        gantryY.position.z += (1.1 - gantryY.position.z) * 0.12 * simSpeed;
        const targetFeederX = -1.45 + currentFeederIndex * 0.26;
        carriageX.position.x += (targetFeederX - carriageX.position.x) * 0.15 * simSpeed;
        if (Math.abs(gantryY.position.z - 1.1) < 0.05) {
          smtState = SMT_STATES.PICK_COMPONENT;
          smtTimer = 0;
        }
        break;

      case SMT_STATES.PICK_COMPONENT:
        const activeNozzle = nozzleArray[currentFeederIndex % 8];
        if (smtTimer < 0.25) {
          activeNozzle.position.y = -0.28 + PICK_Z_DEPTH * (smtTimer / 0.25);
        } else if (smtTimer < 0.4) {
          activeNozzle.position.y = -0.28 + PICK_Z_DEPTH;
        } else if (smtTimer < 0.65) {
          activeNozzle.position.y = -0.28 + PICK_Z_DEPTH * (1 - (smtTimer - 0.4) / 0.25);
        } else {
          activeNozzle.position.y = -0.28;
          targetPCBPos.x = (Math.random() - 0.5) * 1.2;
          targetPCBPos.z = (Math.random() - 0.5) * 0.8;
          smtState = SMT_STATES.MOVE_TO_VISION;
          smtTimer = 0;
        }
        break;

      case SMT_STATES.MOVE_TO_VISION:
        gantryY.position.z += (0.5 - gantryY.position.z) * 0.18 * simSpeed;
        carriageX.position.x += (0.0 - carriageX.position.x) * 0.18 * simSpeed;
        if (Math.abs(gantryY.position.z - 0.5) < 0.08) {
          smtState = SMT_STATES.MOVE_TO_PCB;
          smtTimer = 0;
          triggerLog(currentLang === 'zh' 
            ? `贴装头相机视觉识别完成 [元件 #${currentFeederIndex + 1} 对准合格]` 
            : `Vision alignment complete [Component #${currentFeederIndex + 1} aligned]`);
        }
        break;

      case SMT_STATES.MOVE_TO_PCB:
        gantryY.position.z += (targetPCBPos.z - gantryY.position.z) * 0.16 * simSpeed;
        carriageX.position.x += (targetPCBPos.x - carriageX.position.x) * 0.16 * simSpeed;
        if (Math.abs(gantryY.position.z - targetPCBPos.z) < 0.04 && Math.abs(carriageX.position.x - targetPCBPos.x) < 0.04) {
          smtState = SMT_STATES.PLACE_COMPONENT;
          smtTimer = 0;
        }
        break;

      case SMT_STATES.PLACE_COMPONENT:
        const placingNozzle = nozzleArray[currentFeederIndex % 8];
        if (smtTimer < 0.2) {
          placingNozzle.position.y = -0.28 + PLACE_Z_DEPTH * (smtTimer / 0.2);
        } else if (smtTimer < 0.35) {
          placingNozzle.position.y = -0.28 + PLACE_Z_DEPTH;
        } else if (smtTimer < 0.55) {
          placingNozzle.position.y = -0.28 + PLACE_Z_DEPTH * (1 - (smtTimer - 0.35) / 0.2);
        } else {
          placingNozzle.position.y = -0.28;
          currentFeederIndex = (currentFeederIndex + 1) % 12;
          smtState = SMT_STATES.MOVE_TO_FEEDER;
          smtTimer = 0;
          incrementProductionMetrics();
        }
        break;
    }
  }

  // 坐标更新
  document.getElementById('axis-x').innerText = (carriageX.position.x * 100).toFixed(2);
  document.getElementById('axis-y').innerText = (gantryY.position.z * 100).toFixed(2);

  // AOI 频闪
  if (aoiLightDome) {
    const flash = Math.sin(animationTime * 4.0);
    aoiLightDome.material.color.setHex(flash > 0.8 ? 0xffffff : (flash > 0 ? 0x38bdf8 : 0x0284c7));
  }

  // 回流焊脉动
  ovenZoneMeshes.forEach((mesh, idx) => {
    const pulse = 1.0 + Math.sin(animationTime * 3.0 + idx) * 0.15;
    mesh.scale.set(1.0, pulse, 1.0);
  });
}

/**
 * =========================================================================
 * 上位机 SCADA 数据渲染
 * =========================================================================
 */
let totalProduced = 2864;
let cphBase = 43200;
const waveHistory = new Array(40).fill(43200);

function incrementProductionMetrics() {
  totalProduced++;
  document.getElementById('kpi-count').innerText = totalProduced.toLocaleString();

  cphBase += (Math.random() - 0.5) * 350;
  cphBase = Math.max(41000, Math.min(44800, cphBase));
  document.getElementById('kpi-cph').innerText = Math.round(cphBase).toLocaleString();
  document.getElementById('wave-val').innerText = (cphBase / 1000).toFixed(1) + 'k';

  waveHistory.shift();
  waveHistory.push(cphBase);
  drawWaveChart();
}

const cphCanvas = document.getElementById('cph-canvas');
const ctx = cphCanvas.getContext('2d');
function drawWaveChart() {
  const w = cphCanvas.width = cphCanvas.offsetWidth * window.devicePixelRatio;
  const h = cphCanvas.height = cphCanvas.offsetHeight * window.devicePixelRatio;
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = '#38bdf8';
  ctx.lineWidth = 2 * window.devicePixelRatio;
  ctx.beginPath();
  const min = 40000;
  const max = 46000;
  for (let i = 0; i < waveHistory.length; i++) {
    const x = (i / (waveHistory.length - 1)) * w;
    const y = h - ((waveHistory[i] - min) / (max - min)) * (h - 10) - 5;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.fillStyle = 'rgba(56, 189, 248, 0.15)';
  ctx.fill();
}
window.addEventListener('resize', drawWaveChart);
setTimeout(drawWaveChart, 100);

// 生成 12 飞达卡片
const feederContainer = document.getElementById('feeder-container');
const feederNames = ['0402 C', '0603 R', '0805 C', 'QFP-48', 'BGA-144', 'SOT-23', '0402 R', '0603 C', 'LED-0805', 'Inductor', 'SOP-8', 'Diode'];
const feederCounts = [3400, 2900, 1800, 420, 210, 890, 4100, 2700, 3100, 680, 520, 1400];
feederNames.forEach((name, idx) => {
  const row = document.createElement('div');
  row.className = 'feeder-row';
  const pct = Math.min(100, Math.round((feederCounts[idx] / 5000) * 100));
  row.innerHTML = `
    <span style="color:var(--text-muted);font-family:var(--font-mono);">#${(idx+1).toString().padStart(2,'0')}</span>
    <span style="font-weight:600;">${name}</span>
    <div class="feeder-bar-bg"><div class="feeder-bar-fill ${pct < 20 ? 'warn' : ''}" style="width:${pct}%"></div></div>
    <span style="text-align:right;font-family:var(--font-mono);color:#fff">${feederCounts[idx]}</span>
  `;
  feederContainer.appendChild(row);
});

// 生成 8 联装吸嘴
const nozzleContainer = document.getElementById('nozzle-container');
for (let n = 1; n <= 8; n++) {
  const cell = document.createElement('div');
  cell.className = 'nozzle-cell';
  cell.innerHTML = `
    <div class="nozzle-title">${currentLang === 'zh' ? '吸嘴 #' : 'Nozzle #'}${n}</div>
    <div class="nozzle-kpa" id="nz-kpa-${n}">-84.2</div>
    <div class="nozzle-status">OK</div>
  `;
  nozzleContainer.appendChild(cell);
}

// 生成 8 温区
const ovenContainer = document.getElementById('oven-container');
const zoneTemps = [148, 162, 175, 188, 222, 246, 215, 78];
zoneTemps.forEach((temp, idx) => {
  const row = document.createElement('div');
  row.className = 'oven-zone-row';
  const pct = Math.min(100, Math.round((temp / 260) * 100));
  row.innerHTML = `
    <span class="oven-zone-name" style="color:var(--text-muted);">${I18N[currentLang].zoneNames[idx]}</span>
    <div class="temp-bar-bg"><div class="temp-bar-fill" style="width:${pct}%"></div></div>
    <span style="font-family:var(--font-mono);font-weight:700;color:#fff;">${temp}°C</span>
  `;
  ovenContainer.appendChild(row);
});

function triggerLog(msg) {
  document.getElementById('log-text').innerText = msg;
}

/**
 * =========================================================================
 * 语言即时动态切换函数 (Language Switcher)
 * =========================================================================
 */
function applyLanguage(lang) {
  currentLang = lang;
  const t = I18N[lang];

  // 顶栏
  document.getElementById('ui-brand-title').innerText = t.brandTitle;
  document.getElementById('ui-brand-sub').innerText = t.brandSubtitle;
  document.getElementById('sys-status-text').innerText = isRunning ? t.statusRunning : (isEStop ? t.statusEStop : t.statusPaused);
  document.getElementById('gw-link-text').innerText = isGatewayMode ? t.gwConnected : t.gwOffline;
  document.getElementById('ui-batch-label').innerText = t.batchLabel;
  document.getElementById('ui-tact-label').innerText = t.tactLabel;
  document.getElementById('btn-toggle-lang').innerText = t.langBtn;
  document.getElementById('btn-toggle-xray').innerText = t.btnXRay;
  document.getElementById('btn-toggle-tags').innerText = t.btnTags;
  document.getElementById('btn-play-pause').innerText = isRunning ? t.btnPause : t.btnResume;
  document.getElementById('btn-estop').innerText = isEStop ? t.btnResetEStop : t.btnEStop;

  // 左侧 KPI 面板
  document.getElementById('ui-panel-metrics').innerText = t.panelMetricsTitle;
  document.getElementById('ui-kpi-cph').innerText = t.kpiCphLabel;
  document.getElementById('ui-kpi-cph-sub').innerText = t.kpiCphSub;
  document.getElementById('ui-kpi-yield').innerText = t.kpiYieldLabel;
  document.getElementById('ui-kpi-yield-sub').innerText = t.kpiYieldSub;
  document.getElementById('ui-kpi-count').innerText = t.kpiCountLabel;
  document.getElementById('ui-kpi-count-sub').innerText = t.kpiCountSub;
  document.getElementById('ui-kpi-oee').innerText = t.kpiOeeLabel;
  document.getElementById('ui-kpi-oee-sub').innerText = t.kpiOeeSub;
  document.getElementById('ui-wave-title').innerText = t.waveTitle;
  document.getElementById('ui-axis-title').innerText = t.axisTitle;
  document.getElementById('ui-axis-x').innerText = t.axisXLabel;
  document.getElementById('ui-axis-y').innerText = t.axisYLabel;
  document.getElementById('ui-vision-title').innerText = t.visionTitle;

  // 右侧遥测面板
  document.getElementById('ui-feeder-title').innerText = t.feederTitle;
  document.getElementById('ui-nozzle-title').innerText = t.nozzleTitle;
  document.getElementById('ui-oven-title').innerText = t.ovenTitle;

  // 吸嘴格文字
  document.querySelectorAll('.nozzle-title').forEach((el, idx) => {
    el.innerText = (lang === 'zh' ? '吸嘴 #' : 'Nozzle #') + (idx + 1);
  });

  // 温区文字
  document.querySelectorAll('.oven-zone-name').forEach((el, idx) => {
    el.innerText = t.zoneNames[idx];
  });

  // 底栏
  document.getElementById('ui-view-label').innerText = t.viewLabel;
  const viewBtns = document.querySelectorAll('.camera-views .view-btn');
  const viewKeys = [t.viewOverview, t.viewSmt, t.viewFeeder, t.viewOven, t.viewAoi, t.viewPcb];
  viewBtns.forEach((btn, idx) => {
    btn.innerText = viewKeys[idx];
  });

  document.getElementById('btn-sim-defect').innerText = t.btnDefect;
  document.getElementById('btn-speed-toggle').innerText = `${t.btnSpeed}${simSpeed.toFixed(1)}x`;

  // 3D 浮动标签
  tagElements.forEach(({ el }, idx) => {
    el.innerText = t.tagStations[idx];
  });

  triggerLog(t.logReady);
}

document.getElementById('btn-toggle-lang').addEventListener('click', () => {
  const nextLang = currentLang === 'zh' ? 'en' : 'zh';
  applyLanguage(nextLang);
});

/**
 * =========================================================================
 * tia-twin-client 工业网关无缝接入
 * =========================================================================
 */
let twinClient = null;
if (typeof TiaTwinClient !== 'undefined') {
  try {
    twinClient = new TiaTwinClient({ url: 'ws://127.0.0.1:8765', autoReconnect: true });
    
    twinClient.on('connect', () => {
      isGatewayMode = true;
      document.getElementById('gw-link-dot').className = 'indicator green';
      document.getElementById('gw-link-text').innerText = I18N[currentLang].gwConnected;
      triggerLog(currentLang === 'zh' 
        ? '🟢 成功连接本地工业网关 ws://127.0.0.1:8765，进入真机闭环驱动模式' 
        : '🟢 Connected to local gateway ws://127.0.0.1:8765, entered live PLC drive mode');
    });

    twinClient.on('disconnect', () => {
      isGatewayMode = false;
      document.getElementById('gw-link-dot').className = 'indicator blue';
      document.getElementById('gw-link-text').innerText = I18N[currentLang].gwOffline;
      triggerLog(currentLang === 'zh'
        ? '⚪ 网关断开，自动平滑切回离线自主运动学仿真模式'
        : '⚪ Gateway disconnected, seamlessly fell back to offline simulation mode');
    });

    twinClient.on('tag', (id, val) => {
      if (id === 'smt.axis_x') carriageX.position.x = val / 100.0;
      if (id === 'smt.axis_y') gantryY.position.z = val / 100.0;
      if (id === 'smt.vacuum_kpa') document.getElementById('nz-kpa-1').innerText = Number(val).toFixed(1);
      if (id === 'smt.cph') document.getElementById('kpi-cph').innerText = Math.round(val).toLocaleString();
      if (id === 'smt.total_count') document.getElementById('kpi-count').innerText = val;
      if (id === 'smt.running') {
        isRunning = Boolean(val);
        document.getElementById('sys-status-text').innerText = isRunning ? I18N[currentLang].statusRunning : (isEStop ? I18N[currentLang].statusEStop : I18N[currentLang].statusPaused);
        document.getElementById('sys-status-dot').className = `indicator ${isRunning ? 'green' : 'red'}`;
      }
    });

    twinClient.connect();
  } catch (e) {
    console.warn('TiaTwinClient info:', e);
  }
}

/**
 * =========================================================================
 * 视口与交互
 * =========================================================================
 */
const VIEW_PRESETS = {
  overview: { pos: new THREE.Vector3(2, 12, 20), target: new THREE.Vector3(1, 2.5, 0) },
  smt:      { pos: new THREE.Vector3(0, 5.5, 4.8), target: new THREE.Vector3(0, TRACK_Y + 0.5, 0) },
  feeder:   { pos: new THREE.Vector3(-0.5, 4.2, 3.2), target: new THREE.Vector3(-0.5, TRACK_Y, 1.4) },
  oven:     { pos: new THREE.Vector3(7.0, 5.8, 5.5), target: new THREE.Vector3(7.0, TRACK_Y + 0.4, 0) },
  aoi:      { pos: new THREE.Vector3(13.5, 5.2, 4.2), target: new THREE.Vector3(13.5, TRACK_Y + 0.5, 0) },
  pcb:      { pos: new THREE.Vector3(0, 4.5, 2.8), target: new THREE.Vector3(0, TRACK_Y, 0) }
};

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const preset = VIEW_PRESETS[btn.getAttribute('data-view')];
    if (preset) animateCameraTo(preset.pos, preset.target);
  });
});

function animateCameraTo(destPos, destTarget) {
  const startPos = camera.position.clone();
  const startTarget = controls.target.clone();
  let progress = 0;
  function step() {
    progress += 0.04;
    const ease = 0.5 - Math.cos(progress * Math.PI) / 2;
    camera.position.lerpVectors(startPos, destPos, ease);
    controls.target.lerpVectors(startTarget, destTarget, ease);
    if (progress < 1.0) requestAnimationFrame(step);
  }
  step();
}

// 外壳透视
let isXRay = false;
document.getElementById('btn-toggle-xray').addEventListener('click', (e) => {
  isXRay = !isXRay;
  e.target.classList.toggle('active', isXRay);
  shellMeshes.forEach(mesh => {
    mesh.material = isXRay ? MATS.acrylic : ((mesh === shellMeshes[0] || mesh === shellMeshes[3]) ? MATS.machineWhite : MATS.machineBodyDark);
  });
  if (twinClient && isGatewayMode) twinClient.write('smt.xray_mode', isXRay);
  triggerLog(isXRay 
    ? (currentLang === 'zh' ? "🔍 已开启设备机箱半透视 X-Ray 视图" : "🔍 Enabled translucent X-Ray enclosure view") 
    : (currentLang === 'zh' ? "🔒 已恢复设备实体钣金外壳" : "🔒 Restored solid sheet metal enclosures"));
});

// 启停
const playPauseBtn = document.getElementById('btn-play-pause');
playPauseBtn.addEventListener('click', () => {
  isRunning = !isRunning;
  playPauseBtn.innerText = isRunning ? I18N[currentLang].btnPause : I18N[currentLang].btnResume;
  playPauseBtn.classList.toggle('active', isRunning);
  document.getElementById('sys-status-text').innerText = isRunning ? I18N[currentLang].statusRunning : I18N[currentLang].statusPaused;
  document.getElementById('sys-status-dot').className = `indicator ${isRunning ? 'green' : 'red'}`;
  if (twinClient && isGatewayMode) {
    twinClient.write(isRunning ? 'cmd.start' : 'cmd.stop', true);
  }
  triggerLog(isRunning 
    ? (currentLang === 'zh' ? "生产线恢复自动循环运转" : "Production line resumed auto cycle") 
    : (currentLang === 'zh' ? "产线已安全暂停，维持真空保持状态" : "Production paused, vacuum hold engaged"));
});

// 急停
const estopBtn = document.getElementById('btn-estop');
estopBtn.addEventListener('click', () => {
  isEStop = !isEStop;
  if (isEStop) {
    isRunning = false;
    estopBtn.innerText = I18N[currentLang].btnResetEStop;
    statusTowerLights.red.material = MATS.ledRed;
    statusTowerLights.green.material = MATS.darkMetal;
    document.getElementById('sys-status-text').innerText = I18N[currentLang].statusEStop;
    document.getElementById('sys-status-dot').className = "indicator red";
    if (twinClient && isGatewayMode) twinClient.write('cmd.estop', true);
    triggerLog(currentLang === 'zh' 
      ? "🛑 收到工业安全急停信号！全线伺服制动，所有吸嘴真空安全泄压" 
      : "🛑 Emergency Stop triggered! All servos braked, vacuum depressurized");
  } else {
    isRunning = true;
    estopBtn.innerText = I18N[currentLang].btnEStop;
    statusTowerLights.red.material = MATS.darkMetal;
    statusTowerLights.green.material = MATS.ledGreen;
    document.getElementById('sys-status-text').innerText = I18N[currentLang].statusRunning;
    document.getElementById('sys-status-dot').className = "indicator green";
    if (twinClient && isGatewayMode) twinClient.write('cmd.reset', true);
    triggerLog(currentLang === 'zh' 
      ? "产线急停已复位，伺服回原点完成，继续生产" 
      : "Emergency Stop reset, servos homed, production continuing");
  }
});

// 仿真倍速
const speedBtn = document.getElementById('btn-speed-toggle');
speedBtn.addEventListener('click', () => {
  if (simSpeed === 1.0) simSpeed = 2.0;
  else if (simSpeed === 2.0) simSpeed = 5.0;
  else simSpeed = 1.0;
  speedBtn.innerText = `${I18N[currentLang].btnSpeed}${simSpeed.toFixed(1)}x`;
  triggerLog(currentLang === 'zh' 
    ? `仿真速度已切换为 ${simSpeed.toFixed(1)} 倍速` 
    : `Simulation speed set to ${simSpeed.toFixed(1)}x`);
});

// 模拟缺陷
document.getElementById('btn-sim-defect').addEventListener('click', () => {
  statusTowerLights.yellow.material = MATS.ledYellow;
  document.getElementById('kpi-yield').innerText = "99.82%";
  triggerLog(currentLang === 'zh' 
    ? "⚠️ [AOI 视觉告警] 焊盘 C14 锡膏量不足，判定轻微偏位 (0.012mm)" 
    : "⚠️ [AOI Vision Alert] Pad C14 insufficient solder paste, slight offset (0.012mm)");
  setTimeout(() => { statusTowerLights.yellow.material = MATS.darkMetal; }, 4000);
});

// 3D 浮动标签
let showTags = true;
const TAG_STATIONS = [
  { name: "01 上板机", pos: new THREE.Vector3(-12.5, TRACK_Y + 1.8, 0) },
  { name: "02 锡膏印刷机", pos: new THREE.Vector3(-8.5, TRACK_Y + 2.2, 0) },
  { name: "03 接驳台", pos: new THREE.Vector3(-5.0, TRACK_Y + 1.0, 0) },
  { name: "04 高速贴片机", pos: new THREE.Vector3(0.0, TRACK_Y + 2.6, 0) },
  { name: "05 回流焊接炉", pos: new THREE.Vector3(7.0, TRACK_Y + 2.4, 0) },
  { name: "06 AOI 光学检测", pos: new THREE.Vector3(13.5, TRACK_Y + 2.2, 0) },
  { name: "07 自动下板机", pos: new THREE.Vector3(16.8, TRACK_Y + 1.8, 0) },
];

const tagElements = TAG_STATIONS.map((st, idx) => {
  const el = document.createElement('div');
  el.className = 'annotation-tag';
  el.innerText = I18N[currentLang].tagStations[idx];
  container.appendChild(el);
  return { el, pos: st.pos };
});

document.getElementById('btn-toggle-tags').addEventListener('click', (e) => {
  showTags = !showTags;
  e.target.classList.toggle('active', showTags);
  tagElements.forEach(t => t.el.style.display = showTags ? 'block' : 'none');
});

function updateTagsPosition() {
  if (!showTags) return;
  const tempV = new THREE.Vector3();
  tagElements.forEach(({ el, pos }) => {
    tempV.copy(pos).project(camera);
    if (tempV.z > 1.0) { el.style.opacity = '0'; return; }
    const x = (tempV.x * 0.5 + 0.5) * window.innerWidth;
    const y = (-(tempV.y * 0.5) + 0.5) * window.innerHeight;
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    el.style.opacity = '1';
  });
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// 动画主循环
const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  updateSMTKinematics(delta);
  controls.update();
  updateTagsPosition();
  renderer.render(scene, camera);
}
animate();
