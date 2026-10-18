---
name: plcsim-web-twin
description: 生成可直接连接西门子博途 PLCSIM Advanced 的网页产线数字孪生。用于制作 2D/3D 产线仿真、教学 HMI、虚拟调试页面，通过固定 twin.manifest.json 契约、浏览器 WebSocket SDK 和 Python snap7 网关，把网页传感器回写给 S7-1500 仿真 PLC。触发词：数字孪生、产线仿真、PLCSIM Advanced、博途仿真、S7comm、虚拟调试、Three.js/Canvas 连 PLC。
---

# PLCSIM Web Twin (S7comm)

## 1. 这个 skill 解决什么

让 AI 生成的网页不是“孤立的动画”，而是一个**遵循固定 I/O 契约的被控对象模型**：

```text
浏览器数字孪生  ⇄  WebSocket JSON  ⇄  tia_gateway.py (snap7/S7comm)  ⇄  PLCSIM Advanced (虚拟 S7-1500)
```

浏览器不直接说 S7comm；PLC 逻辑留在 PLC；网页只负责机构动画、传感器计算和操作台。默认 S7comm + snap7，不使用 OPC UA。

## 快速开始

以下生成命令由 **AI/开发者** 执行；最终用户只双击，不敲命令。

```bash
python scripts/make_project.py --out ./my-line          # 2D 操作台
python scripts/make_project.py --out ./my-line --scene 3d  # 3D 产线展示
```

生成后把项目文件夹交给用户，**无需敲任何命令**：

- Windows：双击 `start_twin.bat`
- Linux：双击 `start_twin.desktop`（首次可能需在文件管理器里允许执行）

首次启动会自动创建 `.venv` 并安装依赖，随后自动打开页面。页面默认是**离线仿真**，可直接改数据；点“连接 PLC”，输入 PLCSIM Advanced 的 IP/rack/slot 即可切到实时模式。`run_twin.py` 只用于自动化或开发调试。3D 场景需要 WebGL；不支持时用默认 2D。

如果要**完全无 Python、无终端**：在 Windows 构建机双击 `build_exe.bat` 生成 `dist/TIAWebTwin.exe`，把 exe 交给用户双击即可。详见 `references/deployment.md`。

## 2. 硬性规则（不得绕过）

1. **只通过网关访问 PLC**。网页里禁止出现 `snap7`、S7 socket 或 PLC 原始地址直连。
2. **单一契约**：`twin.manifest.json` 是 tag、地址、访问方向、写模式和对象绑定的唯一定义。网页禁止硬编码 DB 地址。
3. **PLC 边界**：所有 I/O 都通过 `TwinIO` DB 交换。网页写传感器/到位信号，读取 PLC 输出和状态；命令用 `pulse` 写。
4. **真实模式下网页不重复实现 PLC 逻辑**。网页的物理模型只响应 PLC 输出、计算传感器并回写；梯形图/SCL 控制逻辑在 PLC 中。
5. **DB 必须非优化访问**，CPU 必须允许 PUT/GET；16 位量偶数字节对齐，32 位量 4 字节对齐。
6. **页面只有两种模式**：`离线仿真`（本地 mock，可直接改数据）和 `连接 PLC`（用户只填 PLC IP/rack/slot）。默认离线；真实连接由用户点击触发。不要把网关 URL/Token、MOCK/Tag 工程面板暴露给操作者。未连接时禁用按钮并显示等待状态。
7. **安全边界**：这是仿真/教学工具，不是安全回路。页面不得写 Q 输出区，只写 `TwinIO`；不得用于真实设备安全控制。
8. **10–30 Hz 同步**。不要逐帧刷写 PLC；按变化批量写，视觉插值即可。网页不是 1 ms 实时 HMI。

## 3. 标准交付结构

生成项目时，把下列内容落到项目根目录（推荐用 `assets/template` + `scripts/make_project.py` 复制，而不是从零重写）：

```text
project/
├── index.html
├── tia-twin-client.js         # 固定浏览器 SDK，不要改协议
├── twin.manifest.json         # 信号字典 + bindings
├── TwinIO.scl                 # 由 generate_scl.py 生成
├── gateway.config.json
├── run_twin.py                # 自动化/开发启动（用户不直接运行）
├── start_twin.bat             # Windows 双击启动
├── start_twin.sh              # Linux 启动脚本
├── start_twin.desktop         # Linux 双击启动
├── desktop_app.py             # 无终端 exe 的入口（开发者打包用）
├── tia_twin.spec              # PyInstaller 配置
├── build_exe.bat              # Windows 单文件 exe 构建
├── tia_gateway.py
├── validate_manifest.py
├── generate_scl.py
├── requirements.txt
├── styles.css                 # 2D 模板（与 app.js 一起）
├── app.js                     # 2D 场景/物理模型/两模式操作台
└── vendor/                    # 3D 模板：本地 Three.js（无 CDN，与 index.html 一起）
```

2D 和 3D 二选一；`--scene` 决定生成哪套。3D 需要浏览器 WebGL，2D 无此依赖。

参考实现都在本 skill 的 `assets/` 与 `scripts/` 中；先复用，再改场景。

## 4. 推荐工作流

1. **采集对象**：列出执行器（电机、气缸、阀）、传感器（光电、限位、到位）和按钮；确认 PLC IP、rack/slot、DB 号。
2. **写 manifest**：按 `references/contract.md` 的地址/类型规则分配 tag；语义 ID 用 `cmd.*` / `line.*` / `sensor.*` / `out.*` / `cyl.*`。没有现成 DB 时，以模板 `TwinIO` 为起点并明确说明假设。
3. **校验 + 生成 SCL**：
   ```bash
   python validate_manifest.py twin.manifest.json
   python generate_scl.py twin.manifest.json TwinIO.scl
   ```
4. **生成项目**：
   ```bash
   python scripts/make_project.py --out ./my-line [--manifest ./my-line.manifest.json] [--scene 3d]
   ```
   或手工复制 `assets/template` + `tia-twin-client.js` + 网关脚本。
5. **改场景**：保留 `tia-twin-client.js`、manifest 契约、两种模式和 HUD；替换 Canvas 或 Three.js 场景与物理逻辑。离线数据面板从 manifest 生成；在线表单只收 PLC IP/rack/slot。
6. **离线验收**：启动/停止/复位/急停、修改布尔/数值数据、自动检测开关、推料、计数、刷新页面。
7. **在线验收**：用 `run_twin.py` 启动页面 + 网关，点“连接 PLC”输入 PLCSIM Advanced 地址；网关通过 `plc.configure` 热切换目标，不要求用户改 JSON 或重启网关。
8. **闭环验收**：网页启动 → PLC 运行 → 光电触发（网页写 `sensor.pe1`） → PLC 输出 `out.cyl` → 推料气缸动作 → 网页写 `cyl.extended` → PLC 计数/联锁。

## 5. 浏览器 SDK（固定 API）

`tia-twin-client.js` 零依赖，暴露 `TiaTwin`：

```js
const manifest = await TiaTwin.loadManifest('./twin.manifest.json');

const twin = await TiaTwin.create({
  manifest,                                  // 或 manifestUrl: './twin.manifest.json'
  url: 'ws://127.0.0.1:8765/ws',
  token: '',
  mock: new MockPlc(manifest),               // 可选；模板里已有 MockPlc
  autoConnect: false,
});

twin.on('status', ({ state, error }) => {});        // idle/connecting/online/offline/mock
twin.on('plc', ({ state, message }) => {});         // connected/error/unknown
twin.on('values', ({ values, changed }) => {});     // 全量状态 + 本次变化
twin.on('tag:out.cyl', (v) => {});                  // 单 tag 变化
twin.on('latency', (ms) => {});
twin.on('error', (e) => {});
// MockPlc 是模板 app.js 内的类；新项目复用模板或实现同接口的本地 PLC。

twin.bind('pusher', 'extended');                    // 通过 manifest.bindings 取 tag 值
twin.get('line.running');                           // 原始 tag
twin.tagOf('pusher', 'command');                    // tag id
await twin.pulse('cmd.start', 150);                 // 按钮脉冲
await twin.writeMany({ 'sensor.pe1': true });       // 传感器回写（按变化发送）
await twin.configurePlc({ ip: '192.168.0.50', rack: 0, slot: 1 }); // 在线模式：热配置 PLC
```

切换真实 PLC：

```js
twin.useMock(null);
twin.url = 'ws://127.0.0.1:8765/ws';
twin.token = '';
twin.connect();
```

切换本地模拟：`twin.useMock(mockPlc)`。

**必须遵守的页面行为**：
- 顶部只有 `离线仿真 / 连接 PLC` 两个模式，不显示网关 URL、Token、MOCK、PLC 调试信息。
- 离线模式：本地 mock 可运行；显示可编辑的仿真数据（bool 勾选框、数值输入），可直接改传感器/反馈/计数等；提供“自动检测传感器/到位”开关，关掉后由用户数据驱动。
- 在线模式：只要求输入 PLC IP/rack/slot；连接中/失败时禁用操作并显示状态；成功后启用启动/停止/复位/急停。
- 启动/停止/复位/急停全部通过 `pulse`；传感器/到位信号按变化 10 Hz 回写，不能每帧写。
- 页面标注 `SIMULATION ONLY — NOT A SAFETY DEVICE`。
- 连接失败要显示原因和重试入口，不假装成功，也不自动静默切回 mock。

## 6. 网关

一键启动（推荐）：

```bash
cd <project>
pip install -r requirements.txt
python run_twin.py            # 页面 + 本地网关；页面默认离线，可输入 PLC 地址
python run_twin.py --mock     # 只启动页面，本地离线仿真，不启动网关
```

直接调试网关：

```bash
python tia_gateway.py --config gateway.config.json --wait-plc
```

网关启动后处于 `pending` 状态；页面在线模式会发送：

```json
{ "type": "plc.configure", "ip": "192.168.0.50", "rack": 0, "slot": 1 }
```

网关热切换 S7 后端，无需改 JSON 或重启。`--mock` 网关只用于协议测试；网页的离线数据编辑不使用网关。

`gateway.config.json`（网关地址、轮询、Token 等；其中 `plc` 只是直连模式的默认值，页面在线表单会覆盖）：

```json
{
  "manifest": "twin.manifest.json",
  "backend": "s7",
  "plc": { "ip": "192.168.0.1", "rack": 0, "slot": 1 },
  "ws": { "host": "127.0.0.1", "port": 8765, "token": "" },
  "pollHz": 10,
  "logLevel": "info"
}
```

- 网关把可读 tag 合并成按 DB 的连续块读取，变化才广播 `delta`。
- `pulse` 在网关侧自动复位；`writeMany` 用于传感器批量回写。
- `plc.configure` 在运行中切换 PLC 目标；界面不暴露网关地址。
- 局域网使用时设置 Token 并限制防火墙来源；不要把 8765 暴露到公网。
- 网关推荐与 PLCSIM Advanced 同机（尤其 Windows）；跨机需能路由到 PLCSIM 虚拟网卡。

## 7. PLC 侧关键配置

详见 `references/tia-setup-guide.md`。最少四条：

1. PLCSIM Advanced 使用 **Siemens PLCSIM Virtual Ethernet Adapter**（不要 Softbus），虚拟 PLC 有与网关同网段 IP。
2. 项目属性勾选 **块编译时支持仿真**。
3. CPU 防护与安全 → 连接机制 → 勾选 **允许来自远程对象的 PUT/GET 通信访问**。
4. 导入 `TwinIO.scl` 生成 DB，确认 **“优化的块访问”未勾选**，地址与 manifest 一致；注意 TIA 分配的 DB 号可能不一定是 1，必须核对。

### 示例 tag 映射

| Tag | 地址 | 方向 | 用途 |
| --- | --- | --- | --- |
| `cmd.start` | DB1.DBX0.0 | 网页→PLC pulse | 启动 |
| `box.count` | DB1.DBW2 | PLC→网页 | 计数 |
| `line.speed` | DB1.DBD4 | PLC→网页 | 速度 |
| `line.running` | DB1.DBX8.0 | PLC→网页 | 运行 |
| `sensor.pe1` | DB1.DBX8.2 | 网页→PLC level | 光电 |
| `cyl.extended` | DB1.DBX8.3 | 网页→PLC level | 到位 |
| `out.cyl` | DB1.DBX8.4 | PLC→网页 | 推料输出 |

## 8. 验收清单

- [ ] `validate_manifest.py` 返回 OK。
- [ ] 生成的 `TwinIO.scl` 偏移与 manifest 完全一致。
- [ ] 离线模式：启动/停止/复位/急停、修改布尔/数值数据、自动检测开关、推料、计数、刷新。
- [ ] 在线模式：只输入 PLC 地址即可；连接中/失败时禁用操作；成功后实时驱动。
- [ ] 网关：`pending` 初始状态、`plc.configure` ack、`snapshot`/`delta`、`pulse`、`writeMany`、重连。
- [ ] 真实 PLCSIM：PLC 状态、TIA 监视表、传感器回写、PLC 输出驱动网页、计数/故障。
- [ ] 页面没有硬编码地址；没有在真实模式重复 PLC 逻辑；没有逐帧写 PLC；未暴露网关 URL/Token。
- [ ] 明确标注仿真用途，未宣称未经实测的 PLC 联调结果。

## 9. 边界

- v1 只支持 **S7comm/snap7 + 单 DB + 标量 tag**；不支持 OPC UA、数组、字符串、跨 DB。
- 不支持安全功能；急停按钮只是教学仿真信号。
- 不能保证所有 PLCSIM Advanced 版本/固件都允许 S7comm；先用 TIA 监视表验证，再联调网页。
- 遇到优化 DB、PUT/GET 关闭、虚拟网卡选择错误时，网关会报通信错误；先修 PLC 配置，不要改代码绕过。

## 10. 资源

- `references/contract.md`：manifest 与 WebSocket 协议完整定义。
- `references/tia-setup-guide.md`：PLCSIM Advanced / TIA / DB / 排错。
- `references/deployment.md`：双击启动、Windows 单文件 exe、Windows 服务三种部署方式。
- `assets/template/`：2D 操作台示例（离线数据编辑 + PLC 连接）。
- `assets/three-demo/`：3D 产线示例，使用同一 manifest/SDK/网关。
- `scripts/run_twin.py`：一条命令启动页面 + 网关。
- `assets/runtime/tia-twin-client.js`：固定浏览器 SDK。
- `scripts/tia_gateway.py`：S7comm WebSocket 网关。
- `scripts/validate_manifest.py`：地址、类型、对齐、重叠校验。
- `scripts/generate_scl.py`：由 manifest 生成 `TwinIO.scl`。
- `scripts/make_project.py`：一键复制模板、网关和 SCL；`--scene 3d` 选 3D。
- `assets/tia/TwinIO.scl`：参考 DB 外部源文件。
