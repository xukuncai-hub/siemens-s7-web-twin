# 工业 CAD (SolidWorks / Inventor) 模型导入与数字孪生绑定指南

在严肃的工业数字孪生项目中，真实产线往往在机械设计阶段就已经在 **SolidWorks、Autodesk Inventor、Siemens NX、Creo 或 Fusion 360** 中完成了 1:1 的三维装配体设计。

为了保证工业级渲染质感、真实尺寸与零件精度，同时**彻底杜绝 AI 在网页端手写复杂几何体带来的空间算错、悬浮与穿模问题**，本项目原生支持工业标准 `.glb` / `.gltf` 模型的开箱即用导入与 PLC 信号自动驱动。

---

## 1. 工业 CAD 导出推荐规范

### 1.1 导出格式首选
* **首选：单个二进制 `.glb`（Binary glTF）**
  * 优点：将网格（Mesh）、层级结构（Hierarchy）、材质贴图（PBR Materials）完整封装在单个文件内，杜绝散落 `.bin` 或贴图丢失报错。
* **次选：带外部贴图的 `.gltf`**
  * 放入项目 `assets/models/` 目录中。

### 1.2 单位与坐标系规范
1. **尺寸单位**：
   * Three.js 默认世界单位为 **米 (Meter)**。
   * 若从 SolidWorks 导出时为 **毫米 (mm)**，前端加载时执行全局缩放：`model.scale.set(0.001, 0.001, 0.001)` 即可完全 1:1 吻合。
2. **坐标系对齐**：
   * **Y 轴向上 (Y-Up)**：Three.js 遵循右手坐标系 Y 轴垂直朝上；
   * **地面原点**：装配体底面请与坐标系原点 $Y=0$（实验台面或车间地面）贴平，便于全线标高基准链闭环。

---

## 2. 机械动件与传感器命名契约 (Naming Convention)

在 SolidWorks / Inventor 装配体中，将需要被 PLC 驱动运动或用于感应检测的特征/子装配体重命名，推荐遵循如下工业语义前缀：

| 构件类别 | 命名规范示例 | 对应工业机电功能 | 绑定驱动动作 |
| :--- | :--- | :--- | :--- |
| **直线执行器** | `Actuator_Pusher_1` / `Cylinder_Reject` | 气缸伸缩推头、升降顶缸 | 沿 X/Y/Z 轴平移 (`translate`) |
| **旋转执行器** | `Actuator_Turntable` / `Motor_Disk` | 回转分度盘、旋转机械臂 | 绕 X/Y/Z 轴旋转 (`rotate`) |
| **输送动力面** | `Conveyor_Belt_Main` | 连续滚动皮带面 | UV 纹理连续流动 (`texture_scroll`) |
| **光电传感器** | `Sensor_PE1` / `Sensor_Infeed` | 入口光电、分拣到位对射管 | 空间 Raycast 探头原点 (`raycast`) |
| **状态指示灯** | `Light_Green` / `Light_Red` | 设备运行灯、警报三色灯 | 材质自发光变色 (`emissive`) |

---

## 3. 在 `twin.manifest.json` 中建立绑定契约

用户只需在 `twin.manifest.json` 顶层指定模型路径，并在 `bindings` 中将模型节点与 PLC tag 建立物理映射，**无需手写一行底层 3D 矩阵代码**：

```json
{
  "project": "sorting-line-cad",
  "cadModel": "./assets/models/sorting_line.glb",
  "plc": { "ip": "192.168.0.1", "rack": 0, "slot": 1 },
  "tags": [
    { "id": "line.running", "address": "DB1.DBX0.4", "type": "bool", "access": "r", "desc": "主线运行" },
    { "id": "out.cyl",      "address": "DB1.DBX0.5", "type": "bool", "access": "r", "desc": "推料气缸输出" },
    { "id": "sensor.pe1",   "address": "DB1.DBX0.6", "type": "bool", "access": "w", "desc": "分拣光电回写" },
    { "id": "stack.green",  "address": "DB1.DBX0.7", "type": "bool", "access": "r", "desc": "绿灯运行指示" }
  ],
  "bindings": [
    {
      "node": "Actuator_Pusher_1",
      "tag": "out.cyl",
      "type": "translate",
      "axis": "x",
      "from": 0.0,
      "to": 0.15,
      "durationMs": 200,
      "desc": "气缸输出为 1 时，推头沿 X 轴伸出 150mm"
    },
    {
      "node": "Conveyor_Belt_Main",
      "tag": "line.running",
      "type": "texture_scroll",
      "axis": "y",
      "speed": 0.3,
      "desc": "输送带运行时，皮带材质以 0.3m/s 滚动"
    },
    {
      "node": "Light_Green",
      "tag": "stack.green",
      "type": "emissive",
      "onColor": "#00ff33",
      "offColor": "#112211",
      "desc": "PLC 绿灯输出时，材质发出高亮绿色荧光"
    },
    {
      "node": "Sensor_PE1",
      "tag": "sensor.pe1",
      "type": "raycast",
      "direction": [0, -1, 0],
      "length": 0.25,
      "desc": "从探头节点向下方发射 250mm 激光检测工件"
    }
  ]
}
```

---

## 4. 前端通用模型加载与驱动标准实现

在 3D 页面中（`app.js`），直接利用已内置的本地 `GLTFLoader` 加载模型并由 `TiaTwin` 驱动：

```javascript
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export async function loadIndustrialCadModel(scene, client, manifest) {
  if (!manifest.cadModel) return null;

  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync(manifest.cadModel);
  const root = gltf.scene;

  // 1. 毫米转米自适应（若模型包络大于 50 米，自动判断为毫米单位）
  const bbox = new THREE.Box3().setFromObject(root);
  const size = bbox.getSize(new THREE.Vector3());
  if (size.x > 50 || size.z > 50) {
    root.scale.set(0.001, 0.001, 0.001);
  }
  scene.add(root);

  // 2. 建立节点索引表
  const nodeMap = new Map();
  root.traverse((obj) => {
    if (obj.name) nodeMap.set(obj.name, obj);
  });

  // 3. 自动绑定 PLC 信号驱动器
  const bindings = manifest.bindings || [];
  bindings.forEach((binding) => {
    const node = nodeMap.get(binding.node);
    if (!node) return;

    if (binding.type === 'translate') {
      const orig = node.position[binding.axis];
      client.on(`tag:${binding.tag}`, (val) => {
        const target = val ? (orig + binding.to) : orig;
        // 可配合 GSAP 或线性插值丝滑位移
        node.position[binding.axis] = target;
      });
    } else if (binding.type === 'emissive' && node.material) {
      const onColor = new THREE.Color(binding.onColor || '#00ff00');
      const offColor = new THREE.Color(binding.offColor || '#111111');
      client.on(`tag:${binding.tag}`, (val) => {
        node.material.emissive = val ? onColor : offColor;
      });
    }
  });

  return root;
}
```

---

## 5. 核心工程收益

1. **工业级视觉保真**：完全还原倒角、型材槽深、钣金折弯与五金螺栓，彻底告别“手写积木块”的粗糙感；
2. **AI 零幻觉**：AI 不再需要编写任何脆弱的顶点几何体与三维矩阵，只需生成清晰严谨的 `manifest.bindings` 映射；
3. **极速交付**：机械工程师导出模型 $\to$ AI 提取节点绑定 PLC $\to$ 双击启动，10 分钟即可交付一套工业级真实产线数字孪生。
