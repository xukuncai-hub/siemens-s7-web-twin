# Blender 工业级产线建模与数字孪生全流程指南 (替代 Siemens NX / SolidWorks)

> 本指南专为工业自动化、数字孪生与虚拟调试工程师编写，阐述如何使用 **Blender 彻底替代 Siemens NX / SolidWorks 等重型 CAD**，构建具备工业级几何精度、原生 PBR 质感、极低面数（Draw Call 优化）并能与西门子 PLC (S7-1200/1500/PLCSIM) 双向联动的 Web 3D 产线数字孪生模型。

---

## 1. 为什么用 Blender 替代 Siemens NX / 重型 CAD？

在工业控制与 Web 3D 数字孪生（Three.js / WebGL）场景下，传统重型 CAD（Siemens NX、SolidWorks、Creo）存在难以逾越的工程痛点：

| 对比维度 | Siemens NX / 重型 CAD | Blender 现代化方案 |
| :--- | :--- | :--- |
| **文件输出与 Web 兼容** | 仅导出 STEP/IGES/JT，无法在浏览器渲染；转 STL 丢失层次与法线，极易破面、黑斑 | **原生 glTF 2.0 / `.glb` 支持**，单文件打包网格、节点层次、PBR 材质与变换，100% 契合 Three.js |
| **面数与 Draw Call** | 实体制模，倒角和螺栓动辄百万级面；上百个零件导致上百个 Draw Call，网页严重掉帧卡死 | **多边形（Polygon）精准控制**，可自由将静态零件合并（Draw Call 降至 10~20 个），全线轻松维持在 120 FPS |
| **动件轴心点 (Origin / Pivot)** | 必须在装配体建立复杂机械配合约束，难以直接定义 Three.js 的局部平移/旋转轴心 | **3D 游标一键定位旋转轴心**，气缸推程基准点精确可控，归零操作极其直观 |
| **材质渲染与自发光** | 工业灰质感单调，无法表达运行状态指示灯高亮发光、皮带滚动 UV 动画 | 原生 Principled BSDF（PBR 材质），支持 Emissive 自发光动态调色、UV 滚动动画 |
| **轻量化与部署成本** | 商业授权动辄数万至十余万元，安装包数十 GB，工控机无法运行 | **完全免费、开源、无授权风险**，绿色免安装仅几百 MB，现场便携修改即刻生效 |

---

## 2. 打造 Blender 工业级 CAD 建模环境

### 2.1 必备工程环境配置
1. **公制工程单位设置**：
   * 打开右侧属性面板 -> **场景属性 (Scene Properties)** -> **单位 (Units)**：
     - **单位系统**：`公制 (Metric)`
     - **长度**：`毫米 (Millimeters)` 或 `米 (Meters)`（建议使用米，与 Three.js 1:1 吻合；若习惯毫米，导出时缩放 0.001 即可）
     - **单位缩放 (Unit Scale)**：设为 `1.0`（米）或 `0.001`（毫米）。
2. **高精度捕捉 (Snapping) 设置**：
   * 顶部磁铁图标开启捕捉，捕捉目标选 **`增量 (Increment)` + `顶点 (Vertex)`**；
   * 勾选 `绝对网格对齐 (Absolute Grid Snap)`，确保型材框架与滑槽移动时按整数尺寸严密贴合。

### 2.2 推荐利器插件：`CAD Sketcher` (SolveSpace 内核)
* **核心价值**：为 Blender 提供类似 NX / SolidWorks 草图模块的**参数化几何约束与尺寸标注引擎**。
* **工作流**：
  1. 在平面上按 `Add Sketch` 创建草图；
  2. 绘制线段、圆弧、矩形；
  3. 添加几何约束（水平、垂直、平行、同心、共线、相切）；
  4. 添加尺寸约束（给定精确长度，如 `40.0mm`、半径 `25.0mm`）；
  5. 退出草图后添加 `Solidify`（加厚）或直接拉伸（Extrude）生成精准实体。

---

## 3. 六大工业机电建模铁律 (Hard Rules)

为了确保导出的 `.glb` 模型能被 `siemens-s7-web-twin` 前端框架与 PLC 信号无缝驱动，必须在 Blender 中遵守以下六大铁律：

### 铁律 1：严格执行动静分离 (Static vs Dynamic Hierarchy)
* **静态构件必须合并 (Merge)**：
  - 包括：铝型材机架、支撑底座、地脚螺栓、配电箱、安全护栏、不动的气缸缸体。
  - **操作**：全选所有静态零件，按 `Ctrl + J` 合并为单个网格，命名为 **`Static_Base`** 或 **`Static_Frame`**。
  - **收益**：避免浏览器为每个螺丝螺栓发起独立的 Draw Call，瞬间降低 90% 的渲染开销。
* **动态构件绝对独立 (Keep Isolated)**：
  - 每一个由 PLC 独立控制的动作部件必须保持为独立的 Object（对象），严禁与基座合并！

### 铁律 2：动件轴心点 (Origin / Pivot) 精准对齐
这是数字孪生中最容易翻车的环节！Three.js 的旋转和位移完全基于 Blender 对象的 **Origin (黄色原点)**：
1. **回转分度盘 / 电机转子 (Rotation)**：
   * 旋转构件的原点**必须位于其旋转轴心的正中心**！
   * **校准方法**：进入编辑模式（Tab），Alt + 点击选中转盘中心圆孔或轴承外圈的一圈顶点；按 `Shift + S` 选择 **`游标 -> 选中项 (Cursor to Selected)`**；退出编辑模式，右键物体选择 **`设置原点 -> 原点 -> 3D 游标 (Set Origin to 3D Cursor)`**。
2. **气缸伸缩推头 / 升降顶头 (Translation)**：
   * 推头的原点必须位于其**收回原位（缩回状态）的安装接触面**；
   * 确保其位移方向刚好沿局部坐标系或世界坐标系的单一轴向（推荐对齐 X 轴或 Z 轴）。

### 铁律 3：必须应用变换 (Apply Transform: Ctrl + A)
在 Blender 中缩放或旋转物体后，物体的 `Scale` 往往不是 `1.0, 1.0, 1.0`，`Rotation` 也不是 `0, 0, 0`。
* **致命后果**：导入 Three.js 后，位移动画幅度会因为非等比缩放失真，甚至方向反向！
* **必做操作**：在导出前，全选所有物体，按快捷键 **`Ctrl + A` -> 选择 `所有变换 (All Transforms)`**（或单独选择 `旋转和缩放 (Rotation & Scale)`）。

### 铁律 4：全线标高基准链统一 ($Y_0$)
* 无论是输送带皮带面、滚筒线滚子切面、回转台物料槽底，还是工站之间的滑槽入口，**所有承托工件下表面的绝对高度必须在 Z 轴（Blender）或 Y 轴（Three.js）上绝对齐平**。
* 严禁出现阶梯台阶，杜绝物理引擎中工件滑移时发生卡料与跳变。

### 铁律 5：零悬浮立柱生根 (Zero-Floating Grounding)
* 所有滑道、料仓、气缸悬臂支架，必须向下建出 4040/4020 铝型材立柱并延伸至工作台面或车间地面，底部配置三角加强筋（角码）或法兰底座。

### 铁律 6：光电/接近传感器采用“空物体 (Empty)”挂载
* 在装配体中安装光电探头（如检测工件是否到位的传感器）时：
  * 在探头激光出射孔位置创建一个 **`Empty -> 纯轴 (Plain Axes)`**，命名为 `Sensor_PE1`；
  * 该 Empty 会作为三维射线检测（Raycast）的发光原点和方向向量，极大简化前端代码逻辑。

---

## 4. 机构命名契约 (Naming Convention)

在 Blender 大纲视图（Outliner）中，请为每个需要与 PLC 产生数据交互的对象设置规范前缀名称：

| 机构功能 | 命名推荐 | 对应机电行为 | PLC 绑定示例 |
| :--- | :--- | :--- | :--- |
| **气缸推头 / 直线电缸** | `Actuator_Pusher_1` | 沿 X/Y/Z 轴推拉平移 | 绑定 DO `out.cyl` |
| **回转分度盘 / 旋转轴** | `Actuator_Turntable` | 绕局部轴定速或分度旋转 | 绑定 DO `motor.turn` |
| **输送带表面** | `Conveyor_Belt_Main` | 材质 UV 沿前进方向持续滚动 | 绑定 DO `line.running` |
| **光电对射/接近开关** | `Sensor_PE1` / `Sensor_Infeed` | 挂载 3D 射线检测工件到位 | 绑定 DI `sensor.pe1` (回写) |
| **气缸磁簧原位/到位** | `Sensor_Cyl_Retracted` | 气缸机构到达极限行程 | 绑定 DI `cyl.retracted` (回写) |
| **设备三色报警灯** | `Light_Green` / `Light_Red` | PBR 材质 `emissive` 自发光色彩切换 | 绑定 DO `stack.green` |
| **静态机架与地盘** | `Static_Frame` | 静态无动作物理碰撞网格 | 无绑定 (纯渲染) |

---

## 5. 工业 PBR 材质配方速查 (Principled BSDF)

在 Blender 中赋予真实金属与工程塑料质感：

1. **工业阳极氧化铝型材 (Silver Anodized Aluminum)**：
   * Base Color (基础色): `#D4D8DD` (冷浅灰)
   * Metallic (金属度): `0.9`
   * Roughness (粗糙度): `0.3`
2. **安全围栏 / 醒目警示黄 (Industrial Safety Yellow)**：
   * Base Color: `#FDB813`
   * Metallic: `0.05`
   * Roughness: `0.4`
3. **气缸镀铬活塞杆 (Chrome Plated Rod)**：
   * Base Color: `#FFFFFF`
   * Metallic: `1.0`
   * Roughness: `0.05` (镜面光滑)
4. **状态指示灯三色灯罩 (Indicator Lens)**：
   * Base Color: `#00FF44` (绿灯) / `#FF2222` (红灯)
   * Transmission (透射): `0.8` (半透明亚克力质感)
   * Emission (发光颜色): 匹配基础色，Emission Strength 默认设为 `0.0`（熄灭），由 PLC 输出置 1 时前端动态提亮至 `2.0`。

---

## 6. glTF 2.0 (`.glb`) 导出标准设置

在 Blender 中完成建模与命名后，点击菜单 **文件 (File) -> 导出 (Export) -> glTF 2.0 (.glb/.gltf)**：

* **格式 (Format)**：必须选 **`glTF 二进制 (.glb)`**（单一文件，内嵌所有网格、层级与材质）；
* **包含 (Include)**：
  - 勾选 `限制到: 可见物体 (Visible Objects)`；
  - 勾选 `自定义属性 (Custom Properties)`；
* **变换 (Transform)**：
  - 勾选 **`+Y 向上 (+Y Up)`**（自动由 Blender Z 向上转为 Three.js Y 向上）；
* **几何体 (Geometry)**：
  - 勾选 **`应用修改器 (Apply Modifiers)`**；
  - 勾选 **`UV (UVs)`**、**`法线 (Normals)`**、**`切线 (Tangents)`**；
* **压缩 (Compression，可选)**：
  - 若模型文件较大，可勾选 `Draco 压缩`；但在不需要极致加载速度时建议默认关闭，以保证本地离线零依赖加载。

---

## 7. 接入数字孪生配置 (twin.manifest.json)

将导出的 `.glb` 文件（如 `my_line.glb`）复制到项目目录 `assets/models/my_line.glb`。

在项目根目录的 `twin.manifest.json` 中，配置 `cadModel` 与 `bindings`：

```json
{
  "project": "sorting-line-blender",
  "cadModel": "./assets/models/my_line.glb",
  "plc": {
    "ip": "192.168.0.10",
    "rack": 0,
    "slot": 1
  },
  "tags": [
    { "id": "line.running", "address": "DB1.DBX0.0", "type": "bool", "access": "r", "desc": "输送线主电机" },
    { "id": "out.cyl",      "address": "DB1.DBX0.1", "type": "bool", "access": "r", "desc": "分拣推料气缸" },
    { "id": "sensor.pe1",   "address": "DB1.DBX1.0", "type": "bool", "access": "w", "desc": "到位光电传感器" },
    { "id": "stack.green",  "address": "DB1.DBX0.2", "type": "bool", "access": "r", "desc": "运行绿灯" }
  ],
  "bindings": [
    {
      "node": "Actuator_Pusher_1",
      "tag": "out.cyl",
      "type": "translate",
      "axis": "x",
      "from": 0.0,
      "to": 0.12,
      "durationMs": 180,
      "desc": "PLC 输出置 1 时，推头沿 X 轴快速伸出 120mm"
    },
    {
      "node": "Conveyor_Belt_Main",
      "tag": "line.running",
      "type": "texture_scroll",
      "axis": "y",
      "speed": 0.4,
      "desc": "PLC 运行时，输送带表面材质以 0.4m/s 滚动"
    },
    {
      "node": "Light_Green",
      "tag": "stack.green",
      "type": "emissive",
      "onColor": "#00ff33",
      "offColor": "#112211",
      "intensity": 2.5,
      "desc": "PLC 运行输出为 1 时，指示灯高亮亮起"
    },
    {
      "node": "Sensor_PE1",
      "tag": "sensor.pe1",
      "type": "raycast",
      "direction": [0, -1, 0],
      "length": 0.15,
      "desc": "光电探头空物体向下发射 150mm 射线，工件遮挡时向 PLC 回写 1"
    }
  ]
}
```

---

## 8. 一键自检工具：`inspect_glb.py`

为了防止在 Blender 中命名不慎遗漏、大小写拼错或未正确导出 Empty 节点，可以使用配套的纯 Python 检查脚本：

```bash
# 自动分析 GLB 节点树，列出动件并自动生成 bindings 模板：
python scripts/inspect_glb.py assets/models/my_line.glb
```

该工具会直接输出每个节点的层级关系、网格类型，并自动提取带 `Actuator_` / `Sensor_` / `Light_` 前缀的节点，直接生成符合契约的 JSON 代码片段供复制使用。
