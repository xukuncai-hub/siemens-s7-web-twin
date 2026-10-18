---
name: siemens-s7-web-twin
description: 生成可直接连接西门子真实实体 S7 PLC (S7-1200 / S7-1500 / S7-300) 以及博途 PLCSIM Advanced 的网页产线数字孪生。用于制作 2D/3D 产线仿真、教学 HMI、虚拟调试页面，通过固定 twin.manifest.json 契约、浏览器 WebSocket SDK 和 Python snap7 网关，把网页传感器回写给实体 PLC / 仿真 PLC。触发词：数字孪生、产线仿真、真实PLC、实体PLC、S7-1200、S7-1500、PLCSIM Advanced、博途仿真、S7comm、虚拟调试、Three.js/Canvas 连 PLC。
---

# Siemens S7 Web Twin (S7comm: 实体 PLC + PLCSIM)

## 1. 这个 skill 解决什么

让 AI 生成的网页不是“孤立的动画”，而是一个**遵循固定 I/O 契约的被控对象模型**：

```text
浏览器数字孪生  ⇄  WebSocket JSON  ⇄  tia_gateway.py (snap7/S7comm)  ⇄  真实 S7 PLC (S7-1200/1500/300) / PLCSIM Advanced
```

浏览器不直接说 S7comm；PLC 逻辑留在 PLC；网页只负责机构动画、传感器计算和操作台。默认 S7comm + snap7，不使用 OPC UA。

## 核心设计哲学：为调用者（Agent 与最终工程师）着想

本 Skill 为**两层调用者**提供极致流畅体验：
1. **执行层（AI Agent）**：承担 100% 的繁琐技术劳动（分析、编写、校验、生成 SCL、创建双击脚本与快捷方式）。**严禁向用户抛出任何终端命令行！**
2. **用户层（最终工程师 / 客户 / 产线人员）**：享受“纯图形化、零环境门槛、开箱即用”的体验。

```text
AI Agent（后台全自动执行）:
  产线机电分析 ➔ 生成 manifest ➔ 自动校验 ➔ 自动生成 TwinIO.scl ➔ 准备中文双击脚本/单文件 exe
                                       │
                                       ▼ 交付给人类用户
最终用户（零命令行使用）:
  ① 双击启动脚本 / exe ➔ ② 博途导入 SCL 鼠标生成块 ➔ ③ 浏览器右上角输入 PLC IP 点击连接
```

## 快速开始

以下工程脚手架与 SCL 生成由 **AI Agent 在后台自动执行**；交付给用户的工程**默认即具备双击即用能力**：

```bash
# 由 AI 在后台执行，切勿让用户在终端敲：
python scripts/make_project.py --out ./my-line          # 2D 操作台
python scripts/make_project.py --out ./my-line --scene 3d  # 3D 产线展示
```

项目生成后直接交付用户，**全程无需敲任何命令**：

- **Windows 用户（双击即用，0 终端输入，0 环境依赖）**：
  - 双击 `start.bat`（或运行 `make_shortcut.bat` 一键在桌面生成专属图标）。
  - **内置免安装运行时**：脚手架自动内置 ~20MB 极简 Python 运行环境（内置 `snap7` 与 `websockets`），**现场目标工控机完全无需安装 Python、无需联网、无需管理员权限**，开箱即用。
  - **Win11 24H2 兼容**：全面采用原生 PowerShell 隐藏模式与 7-bit ASCII 批处理，告别 `.vbs` 废弃与单文件 exe `%TEMP%` 解压拦截。
- **Linux 用户**：双击 `start_twin.desktop`。

## 2. 硬性规则（不得绕过）

1. **只通过网关访问 PLC**。网页里禁止出现 `snap7`、S7 socket 或 PLC 原始地址直连。
2. **单一契约**：`twin.manifest.json` 是 tag、地址、访问方向、写模式和对象绑定的唯一定义。网页禁止硬编码 DB 地址。
3. **PLC 边界**：所有 I/O 都通过 `TwinIO` DB 交换。命令用 `pulse` 写。
4. **严格区分信号流向与产线机电职责（核心原则）**：
   - **现场输入 ➔ PLC (DI / AI，外部向 PLC 发信号)**：
     - 包括：操作按钮（`cmd.start`, `cmd.stop`）、现场光电/接近传感器（`sensor.pe1`）、气缸原位/到位磁簧反馈（`cyl.retracted`, `cyl.extended`）、安全光栅等。
     - **严禁**将传感器设计为由 PLC 控制的输出！传感器是客观世界的状态，**必须由网页虚拟现场在工件到位时自动写入 PLC**，并在界面上提供单步人工点动测试通道。
   - **PLC 输出 ➔ 现场执行器 (DO / AO，由 PLC 逻辑控制外部)**：
     - 包括：输送带电机接触器（`line.running`）、推料/阻挡气缸电磁阀（`out.cyl`）、运行/报警指示灯（`stack.green`, `stack.red`）、分拣计数与状态字（`box.count`）。
     - **网页在真实模式下严禁自行虚构控制逻辑**，网页动画（皮带转动、气缸推拉、灯亮灭）**必须且只能读取 PLC 输出状态来驱动**。PLC 输出 1 则动，输出 0 则停。
5. **DB 必须非优化访问**，CPU 必须允许 PUT/GET；16 位量偶数字节对齐，32 位量 4 字节对齐。
6. **页面只有两种模式**：`离线仿真`（本地 mock，可直接改数据）和 `连接 PLC`（用户只填 PLC IP/rack/slot）。默认离线；真实连接由用户点击触发。不要把网关 URL/Token、MOCK/Tag 工程面板暴露给操作者。未连接时禁用按钮并显示等待状态。
7. **安全边界**：这是仿真/教学工具，不是安全回路。页面不得写 Q 输出区，只写 `TwinIO`；不得用于真实设备安全控制。
8. **通信扫描周期可调（50ms / 100ms）**：页面与网关必须提供动态切换扫描周期选择器。默认提供 `50 ms (20 Hz · 高速响应)` 与 `100 ms (10 Hz · 工业标准推荐)`。页面顶部状态栏、连接弹窗必须提供选择下拉框，左下角 HUD 必须实时展示当前扫描周期节拍。禁止逐帧无节制刷写，网关必须具备时间差精确补偿。
9. **严禁向物理输入区（%I）直写信号（PLC 硬件输入过程映像区 PII 循环刷新机制）**：
   - **底层机制**：西门子 S7-1200/1500 PLC 的工作机制是周期循环扫描：每轮扫描周期的起始阶段，CPU 固件以微秒级硬件中断刷新“过程映像输入区 (PII)”，直接采样外部物理接线端子的电压。若物理端子悬空未接线，PII 刷新会立刻把该位强制重置为 0。
   - **致命陷阱**：上位机若通过 S7comm 强行写入 `%I0.0`，在微秒内就会被硬件扫描覆盖清零，PLC 用户逻辑（梯形图/SCL）在后续执行时读取到的依旧是 0，永远无法触发逻辑。
   - **铁律规范**：虚拟传感器与按钮等外部回写信号，**严禁直写物理 %I 区**！必须写入非优化数据块（如 `TwinIO` DB）或 M 寄存器；PLC 控制程序在仿真/调试时必须读取该 DB 变量代替物理 `%I`。
10. **读写字节严格隔离（Byte Isolation，防位覆盖竞争）**：
   - **底层机制**：S7comm（Snap7 `db_write`）在底层对布尔位（Bool）进行写入时，执行的是字节级“读-改-写 (Read-Modify-Write)”操作（先读入整个 Byte，修改目标 bit，再写回整个 Byte）。
   - **竞争隐患**：若同一个字节（如 `DB1.DBB0`）内混排了 PLC 负责刷新的输出信号（如 `DB1.DBX0.0`，权限 `r`）与上位机回写的数据（如 `DB1.DBX0.1`，权限 `w`），当上位机回写该字节时，极大概率把 PLC 在这几毫秒内刚刚置位的输出信号给覆盖冲掉！
   - **铁律规范**：**不同读写方向（r 与 w/rw）的变量严禁共享同一个 Byte 偏移量**。规范做法是划分清晰的字节边界（如 `DBB0` 集中放输出位 `r`，`DBB1` 集中放输入位 `w`）。`validate_manifest.py` 会对此进行自动检查与预警。
11. **博途 DB 编号防冲突与核对机制**：
   - **原理解析**：`twin.manifest.json` 默认基于 `DB1` 分配绝对地址。若用户博途项目中原本已存在占用 `DB1` 的老程序，在导入 `TwinIO.scl` 执行“从源生成块”时，博途会自动将数据块编号递增（如变成 `DB2`），导致上位机因找不到 `DB1` 报错。
   - **规程**：导入后需在博途项目树中核对数据块编号是否为 `DB1`；若已被占用，可在 DB 块属性中手动改回 1，或在 `twin.manifest.json` 中统一修改为实际 DB 编号。


## 3. 标准交付结构

生成项目时，把下列内容落到项目根目录（推荐用 `assets/template` + `scripts/make_project.py` 自动生成，而不是从零重写）：

```text
project/
├── runtime/                    # 官方绿色免安装 Python 运行时（内置 snap7 与 websockets，开箱即用）
├── index.html                 # 孪生主页面（2D/3D 画布 + 双模式操作台）
├── app.js                     # 孪生场景机构动画、物理碰撞感应、状态同步
├── styles.css                 # 工业深色风格样式
├── tia-twin-client.js         # 固定浏览器 SDK，不要改动协议
├── twin.manifest.json         # 信号字典、多 DB 地址、bindings 契约
├── TwinIO.scl                 # 由 AI 自动生成好的 SCL 数据块外部源文件（含非优化声明与中文注释）
├── TwinDemoLogic.scl          # 自动生成的博途配套示例控制逻辑（可在 OB1 中直接一键调用测试）
├── start.bat                  # Windows 极简启动器（优先使用 ./runtime/ 绿色环境，双击即用）
├── start_silent.bat           # Windows 后台静默启动（PowerShell Hidden 模式，完全无黑框）
├── make_shortcut.bat          # 一键在用户 Windows 桌面上创建图标
├── stop.bat                   # 一键干净终止所有后台常驻服务进程
├── start_twin.bat             # Windows 兼容启动器
├── start_twin.sh              # Linux 启动脚本
├── start_twin.desktop         # Linux 桌面图标双击启动
├── tia_gateway.py             # 本地 S7comm / WebSocket 网关
├── run_twin.py                # 网关 + HTTP 协同启动调度器
├── validate_manifest.py       # 契约规则自动校验器
├── generate_scl.py            # 多 DB SCL 自动生成器
├── requirements.txt           # Python 依赖清单
├── gateway.config.json        # 网关本地端口与默认配置
└── vendor/                    # 3D 模板本地 Three.js 依赖（无 CDN 纯离线）
```

2D 和 3D 二选一；`--scene` 决定生成哪套。3D 需要浏览器 WebGL，2D 无此依赖。

参考实现都在本 skill 的 `assets/` 与 `scripts/` 中；先复用，再改场景。

## 4. 产线分析与推荐工作流（AI 必经步骤）

任何数字孪生生成前，**AI 必须先执行意图分类与机电拓扑分析**，不得跳过：

### 步骤 0：双用途模式识别与意图澄清（必选判定）

AI 接收到用户需求时，必须第一时间识别并确定用户属于以下哪一种工业用途模式：

- **模式 A：工业现场纯监控看板 / 轻量 SCADA / HMI (Industrial Monitoring)**
  - **应用场景**：现场已有真实运转的实体自动化产线、电气接线已固定、PLC 内已有现成的成熟梯形图/SCL 程序在运行。
  - **核心定位**：上位机仅作为“数据观察者”与“监控大屏”。
  - **信号与权限铁律**：
    - 以**只读（`r`）为主**：读取 PLC 的输出状态（`Q` 区或 `TwinIO` 中的 DO 镜像）、现场真实传感器状态（`I` 区只读或 DB 状态）、设备运行参数（Real 速度、Int 计数、DInt 伺服位置、Word 故障字）。
    - **绝对严禁向 PLC 回写任何虚拟传感器信号**（因为现场物理传感器已真实接入，回写会产生严重逻辑冲突甚至设备安全事故）！
    - 允许的写入（`w`）仅限于人工干预的启停确认、模式切换或工艺配方参数下发。
    - **交付重点**：高可靠性数据刷新、异常报警弹窗、产能走势图表、局域网多终端看板（车间平板直接浏览器查看）。

- **模式 B：虚拟产线闭环教学实训 / 数字化虚拟调试 (Virtual Commissioning & Training)**
  - **应用场景**：工程师/学生手头仅有一台裸机 PLC（S7-1200/1500 等）或 PLCSIM Advanced 仿真器，现场没有物理机电机构和物理传感器。
  - **核心定位**：网页扮演**“被控对象机电模型”**（包含 3D/2D 输送带、推料气缸、光电管、工件物理碰撞）。
  - **信号与权限铁律**：
    - 必须具备完整的**双向闭环通讯**：PLC 输出信号驱动 3D 网页机械机构运动；网页物理引擎计算出工件遮挡光电管后，**必须通过 WebSocket + 网关向非优化 `TwinIO` DB 回写虚拟传感器信号（`w`）**，形成闭环。
    - **冷启动防呆破局（配套 TwinDemoLogic.scl）**：
      - 新手工程师导入 DB 连上真实 PLC 后，常困惑“为什么网页连上了但画面一动不动？”——根本原因在于其 PLC 内尚未编写梯形图控制逻辑，DB 输出全为 0。
      - `generate_scl.py` 在生成 `TwinIO.scl` 数据块的同时，自动配套生成一份 `TwinDemoLogic.scl` 示例控制功能块（含启停自锁、PE1 触发气缸推料、计数与复位）。用户只需在博途 OB1 中插入一行 `"TwinDemoLogic"();` 下载，即可在 1 分钟内完成首轮活体闭环联调！

### 步骤 1：产线机电对象与信号流向分析
AI 在动手写代码或 manifest 前，必须在思考与回答中显式完成以下三张清单梳理：
1. **执行机构清单（Actuators，归入 PLC 输出 ➔ 现场）**：
   - 输送系统：主输送带电机（`line.running`）、分拣输送带、转台
   - 气动与执行：推料气缸电磁阀（`out.cyl`）、阻挡气缸、升降气缸、真空吸盘
   - 声光报警：三色灯（`stack.green`, `stack.yellow`, `stack.red`）、蜂鸣器
2. **传感器与人机输入清单（Sensors & Inputs，归入 现场输入 ➔ PLC）**：
   - 操作指令：启动（`cmd.start`）、停止（`cmd.stop`）、复位（`cmd.reset`）、急停（`cmd.estop`）
   - 物料检测：入口检测光电（`sensor.in`）、分拣到位光电（`sensor.pe1`）、满料检测光电
   - 机构状态反馈：气缸原位磁簧（`cyl.retracted`）、气缸伸出到位磁簧（`cyl.extended`）
3. **闭环交互链推演（确保闭环成立）**：
   - 例子：`网页按启动 [cmd.start]` ➔ `PLC 输出驱动输送带 [line.running=1]` ➔ `网页工件到达 PE1 自动回写 [sensor.pe1=1]` ➔ `PLC 收到后输出气缸电磁阀 [out.cyl=1]` ➔ `网页气缸伸出推料` ➔ `工件入箱/气缸到位 [cyl.extended=1]` ➔ `PLC 计数器 [box.count+1] 并收回气缸 [out.cyl=0]`。

### 步骤 2：编写 manifest
按 `references/contract.md` 的地址/类型规则分配 tag；语义 ID 用 `cmd.*` / `line.*` / `sensor.*` / `out.*` / `cyl.*`。没有现成 DB 时，以紧凑 `TwinIO` 为起点，按前述分析严格标明读写权限与说明。必须确保读写字节严格隔离（输入独立字节，输出独立字节）。

### 步骤 3：校验 + 生成 SCL（AI 在后台自动完成）

> [!IMPORTANT]
> **AI 职责红线**：此步骤由 AI Agent 在后台静默执行，**绝对不要**将此命令作为步骤抛给人类用户在终端敲！
> AI 必须确保 `TwinIO.scl`（数据块）与配套控制块 `TwinDemoLogic.scl` 在交付给用户前已自动生成完毕，包含正确的变量名、多 DB 分区和偶数字节对齐。

```bash
# AI 后台自主执行，无需用户参与：
python validate_manifest.py twin.manifest.json
python generate_scl.py twin.manifest.json TwinIO.scl
# 此命令将自动生成 TwinIO.scl（非优化数据块）与 TwinDemoLogic.scl（配套示例控制逻辑）
```

### 步骤 4：生成项目与一键启动工具（AI 自动装配）

```bash
# AI 后台自主执行：
python scripts/make_project.py --out ./my-line [--manifest ./my-line.manifest.json] [--scene 3d]
```
脚手架会自动装配好 `start.bat`（极简双击启动）、`start_silent.bat`（PowerShell 后台静默无黑框）、`make_shortcut.bat`（一键生成桌面图标）与 `stop.bat`，并内置 ~20MB 极简 Python 运行环境（`runtime/`，内含 `snap7` 与 `websockets`）。
现场工控机零依赖，无需安装任何环境，杜绝 Windows 11 24H2 对 `.vbs` 的废弃与对 `--onefile` 单文件临时目录的拦截。

### 步骤 5：定制场景与物理感知
保留 `tia-twin-client.js`、manifest 契约与两种模式。
- **物理感知**：在场景动画循环中检测工件位置，当工件遮挡传感器时，**自动调用 SDK 回写 PLC**；工件离开时写 `false`。
- **操作面板**：将监控列表明确区分为 **【现场输入 ➔ PLC (DI)】**（提供点动发信号按钮）与 **【PLC 输出 ➔ 现场 (DO)】**（纯读取展示）。

### 步骤 6：离线与在线闭环验收
- 离线模式：启动/停止/复位/急停、修改布尔/数值数据、自动检测开关、推料、计数。
- 在线模式：输入 PLCSIM Advanced 地址连接，验证 S7 读写完全正常、无地址越界报错、网页与 PLC 闭环顺畅。

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

## 8. 实战经验总结与设计红线 (Lessons Learned & Anti-Patterns)

根据多轮真实 PLC 联调反馈，AI 开发或修改数字孪生时必须坚守以下七大准则：

1. **双服务协同原则（禁止单独启动静态服务）**：
   - 数字孪生依赖「静态 Web 服务 (8000)」与「S7 WebSocket 网关 (8765)」成对协同工作。
   - 严禁教唆用户仅使用 `python -m http.server` 启动，否则缺少 8765 网关监听，页面必定报错“连接断开/无法连接”。统一使用 `run_twin.py` 或 `start_twin.bat`。

2. **传输链路层与数据块层解耦（连接只管连接，不要因 DB 读失败中断网络）**：
   - 核心认知：即使 PLC 内部尚未建立 DB1、或 DB 块尚未下载到 CPU（报 0x05/0x0a），S7 物理连接（TCP 102 握手）依然是成功的！
   - 严禁在网关 `read_all()` 抛出 DB 异常时执行 `self.connected = False` 强行切断连接。网关应做物理层保活（如探测 M 区），页面状态必须如实显示「PLC 已连通（绿色）」，并将具体 DB 不存在的友好提示作为字段警告展示，不能直接判定链路死亡。

3. **紧凑初始契约与容错读取（严防 0x05 Invalid address 越界崩塌）**：
   - 真实 PLC 中新建的测试 DB 往往极小（例如仅有 2 个字节）。如果上位机 manifest 规划了 8~10 字节，S7comm 读越界就会直接报 `0x05` 彻底失败。
   - 最小闭环应当采用紧凑 2 字节布局（如 DBB0 装所有开关量，DBB1 装计数值）；网关必须包含数组切片防越界检查。

4. **离线/在线数据彻底隔离（严禁残留 Mock 数据污染在线视图）**：
   - 痛点：“这些数据我 PLC 根本没有给，哪里来的？”
   - 必须杜绝 Mock 数据缓存残留。切到在线模式时，必须强制无条件重置 `values = {}`，未收到 PLC 真实广播前，所有数据必须显示为 `— (未提供)`。

5. **纯信号驱动机制（前端严禁自行跑仿真业务逻辑）**：
   - 痛点：“产线不需要逻辑，只是读取信号，PLC 那边发什么就动什么”。
   - 真实模式下的数字孪生是标准的 I/O 镜像与物理受控对象。输送带滚不滚、气缸伸不伸、指示灯亮不亮，**100% 仅响应从 PLC 读回的真实输出（DO）**。PLC 给 1 动画才动，PLC 给 0 动画停止，严禁前端内置虚假定时器。

6. **传感器（DI）本质与双通道触发（客观世界向 PLC 发信号，绝非 PLC 修改）**：
   - 痛点：“光电检测 PE1 这种传感器是外面向 PLC 发信号，就应该有信号给 PLC，而不是 PLC 那边修改！”
   - 现场传感器（光电、接近、限位）是**输入设备（DI）**，是客观物理世界向 PLC 反馈信号。
   - 数字孪生必须提供：
     ① **自动物理感应**：工件在输送带上移动遮挡探头时，前端自动向 PLC 写入 `sensor.pe1 = 1`；离开后自动写 `0`。
     ② **单步测试点动通道**：操作台提供一键「触发感应脉冲 (发给 PLC)」按钮，监控面板提供每项输入的「发脉冲 ⚡」按钮，且支持鼠标直点画布上的探头。

7. **强制产线机电与信号流向三清单分析**：
   - 任何生成任务前，AI 必须先将信号严谨划分为【现场输入 ➔ PLC (DI)】与【PLC 输出 ➔ 现场 (DO)】，并推演完整闭环时序链，不得盲目生成混乱的 tag。

8. **零终端交付与调用者共情原则（严禁向用户抛命令行）**：
   - 痛点：“还要敲命令行啥的，对于其他人好麻烦！”
   - 工控与自动化领域工程师、现场调试员或客户普遍排斥黑色命令行窗口。
   - **AI 的职责是技术全包**：`twin.manifest.json` 编写、`validate_manifest.py` 校验、`TwinIO.scl` 生成、启动工具配置全部在后台由 AI 自主静默执行完毕，**严禁**让用户去跑这些构建命令！
   - **交付物必须干净可靠**：工程根目录必须包含 `start.bat`（标准双击启动）、`make_shortcut.bat`（桌面图标生成）、`start_silent.bat`（后台完全静默启动）与 `stop.bat`（干净关闭服务）。

9. **Windows 11 24H2 兼容性避坑红线（系统级核心经验）**：
   - **红线 A：严禁向用户交付 PyInstaller `--onefile` 单文件 exe！**
     - 现象：用户双击 `dist\TIAWebTwin.exe` 弹出报错 `Could not create temporary directory!`。
     - 原理：Windows 11 24H2（启用了 Smart App Control 或组策略安全限制）严禁未签名的第三方单文件 exe 动态解压二进制到 `%TEMP%` 临时目录执行。
     - 规则：交付首选原生批处理与桌面快捷方式。如确需打包，只能采用 `--onedir`（便携文件夹免解压模式），严禁单文件动态释放。
   - **红线 B：严禁生成任何 `.vbs` 脚本！**
     - 现象：双击报错 `没有文件扩展“.vbs”的脚本引擎`。
     - 原理：微软在 Windows 11 24H2 中已彻底废弃并默认移除了 VBScript 引擎。
     - 规则：严禁生成 `.vbs`。后台隐藏运行统一使用纯 7-bit ASCII `.bat` 内部调用 PowerShell（`-WindowStyle Hidden`）。
   - **红线 C：所有批处理脚本必须严格保持 7-bit 纯 ASCII 编码！**
     - 现象：`.bat` 脚本若存为 UTF-8 编码，中文 Windows `cmd.exe`（默认 CP936）在解析非英文字符时会发生字节断裂，报语法错误或路径截断。
     - 规则：批处理中的命令与提示必须使用纯 7-bit ASCII 字符，中文信息放到 Python、HTML 或由 PowerShell 统一输出。
   - **红线 D：批处理参数截断与逗号 `,` 陷阱！**
     - 现象：`python -c "import snap7, websockets"` 在批处理中执行时，cmd 会把逗号解析为参数分隔符，传入 Python 变成 `import snap7 websockets` 产生 SyntaxError，导致批处理误判依赖缺失。
     - 规则：批处理中检测依赖必须单行单模块执行，如 `python -c "import snap7"` 与 `python -c "import websockets"` 分开检测。
   - **红线 E：WindowsApps 微软应用商店空壳别名劫持！**
     - 现象：`where python` 找到的第一条往往是 `AppData\Local\Microsoft\WindowsApps\python.exe`，调用时会弹窗“打开应用商店”。
     - 规则：批处理查找 Python 时，必须循环遍历 `where python` 并过滤含有 `WindowsApps` 的虚拟别名，精准锁定宿主机物理 Python 路径。

10. **跨盘符虚拟环境 DLL 初始化避坑（Python 在 C 盘，项目在 D 盘）**：
    - 现象：在非系统盘（如 D: 盘）工程目录下执行 `python -m venv .venv` 创建虚拟环境后，调用 `import snap7` 会报：
      `ImportError: DLL load failed while importing _ctypes: 动态链接库(DLL)初始化失败`，导致网页弹出“缺少 python-snap7”。而在宿主机 C 盘全局 Python 直接运行却 100% 正常。
    - 原理：Windows Loader 跨盘符加载 C 运行时动态库和 `libffi-8.dll` 时入口点（DllMain）返回失败。
    - 规则：启动器优先检测本地绿色便携包（`runtime\python.exe`），若无则直接复用宿主机真实的 Python 3.10+。切勿在非系统盘强行创建隔离 `.venv`，避免底层跨盘符 DLL 冲突。

11. **双目标支持：真实西门子硬件 PLC 与 PLCSIM Advanced 仿真器并重**：
    - **网络层等价性**：西门子实体 PLC（S7-1200 / S7-1500 / S7-300）与虚拟仿真器（PLCSIM Advanced）在网络底层都是西门子工业以太网原生协议 **S7comm（ISO-on-TCP，默认端口 102）**。网关基于 `snap7`，本就是工业级真实硬件直连库。
    - **机型预设差异**：
      - 西门子 S7-1200 / S7-1500 实体 PLC：Rack = 0, Slot = 1
      - 西门子 S7-300 / ET200 实体 PLC：Rack = 0, Slot = 2
      - PLCSIM Advanced 虚拟 PLC：Rack = 0, Slot = 1
    - **真实硬件直连四大必查清单（AI 必须在界面或交付指引中给出）**：
      1. **物理网络互通**：电脑网卡与 PLC IP 处于同一局域网网段，终端可互相 ping 通；
      2. **PUT/GET 权限放行**：博途 CPU 属性【保护与安全】➔【连接机制】勾选 **“允许来自远程对象的 PUT/GET 通信访问”**；
      3. **非优化 DB 访问**：将生成的 `TwinIO.scl` 导入博途生成 DB1，右键属性确认未勾选【优化的块访问】（SCL 默认 `{ S7_Optimized_Access := 'FALSE' }`）；
      4. **程序下载运行**：将包含 DB1 的项目完整编译并下载到真实 PLC，且 CPU 处于 **RUN** 绿灯状态。
    - **界面交互规范**：系统标题与连接弹窗**严禁局限于“PLCSIM”**，必须展示为“西门子 S7 真实 PLC / PLCSIM 3D 数字孪生”，提供机型预设下拉框（自动填写对应 Rack/Slot）以及硬件检查提示。

12. **3D 工业真实产线建模与动静分离规范**：
    - **零外部 CDN 依赖**：本地提供 Three.js（`vendor/three.module.min.js` 与 `OrbitControls.js`），保证无网环境下也能 100% 渲染。
    - **机械与传感器三要素**：分段动力皮带、气动推杆/阻挡气缸、对射光电 PE 动态激光束（被工件遮挡时光束截断并变红）。
    - **动静分离与信号闭环**：输送带滚筒与气缸推拉**100% 响应 PLC 真实回传的 DO 输出**，PLC 输出 1 则运动，0 则停止，严禁前端伪造常转动画；工件到位时自动向 PLC 写入 DI。

13. **现场工控机零 Python 环境交付准则（绿色便携 Runtime 与多终端方案）**：
    - **痛点认知**：“跑脚本不用 Python 吗？客户电脑/现场工控机完全没有 Python 怎么办？”
    - **架构事实**：
      - 前端 3D 渲染与控制台运行在浏览器中，**100% 不需要 Python**。
      - 但西门子 S7comm 是底层的 TCP 102 端口，现代浏览器出于安全沙箱限制**禁止直接建立原生 TCP Socket**，必须由本地网关将 S7comm 转换为 WebSocket 喂给前端。
      - 因此负责与 PLC 握手的网关服务机确实需要一个执行引擎。
    - **工业级零环境门槛交付三大规范**：
      1. **绿色便携包（Python Embeddable / Portable Runtime）—— ⭐️ 工业现场最推荐**：
         - 项目根目录可自带官方绿色免安装 Python（放入 `runtime/` 文件夹，解压后仅约 20MB，内置 `python-snap7` 与 `websockets`）。
         - 所有启动脚本（`start.bat`、`start_silent.bat`）已内置自愈检测逻辑，**第一优先级寻找 `./runtime/python.exe`**：
           ```bat
           if exist "%~dp0runtime\python.exe" (
             set "PY=%~dp0runtime\python.exe"
             goto run
           )
           ```
         - **客户体验**：拷到现场纯净工控机上，插上 U 盘直接双击，**目标电脑无 Python、无网络、无管理员权限均可一秒起飞**。
      2. **PyInstaller `--onedir` 独立文件夹**：
         - 打包成独立可执行文件夹 `dist/TIAWebTwin/`（严禁 Win11 24H2 拦截的 `--onefile`），双击 exe 启动，对客户完全隐藏脚本。
      3. **B/S 纯客户端访问（车间平板 / 手机 / 远程工位）**：
         - 网关只需在连接 PLC 的一台工控机上运行，其他工位电脑、车间平板**无需运行任何脚本、无需安装任何环境**，直接浏览器输入 `http://工控机IP:8000` 即可实时监控与交互。

## 9. AI Agent 交付规范与最终回复模板 (Agent Delivery Response Standard)

当 AI 完成数字孪生任务后，向人类用户交付的回复**必须严格遵循以下结构**，保持极致的人类友好：

```markdown
### 1. 产线机电拓扑与信号流向
- **现场输入 ➔ PLC (DI)**：按钮、光电检测 PE1、气缸到位反馈（工件到位时由网页自动回写 PLC，操作台提供单步点动测试通道）
- **PLC 输出 ➔ 现场 (DO)**：输送带运转、推料气缸电磁阀、三色运行灯（由 PLC 逻辑真实控制，网页纯读取驱动机构动画）

### 2. 三种无门槛启动方式（完全无需敲任何命令行）
- **方式 1：桌面图标一键直达（日常最推荐）**：
  - 首次双击运行项目目录下的 `make_shortcut.bat`，会在 Windows 桌面上生成【TIA Web 3D Twin】快捷方式；
  - 以后在桌面上直接双击该图标，浏览器便会自动弹开展开 3D 产线。
- **方式 2：目录双击启动**：
  - 打开工程文件夹，直接鼠标双击 `start.bat`，服务自动就绪并自动唤起浏览器。
- **方式 3：后台静默常驻（完全无黑窗口）**：
  - 双击 `start_silent.bat`，黑窗口 3 秒后自动消失，服务在后台静默运行；
  - 浏览器访问 `http://127.0.0.1:8000/?ws=ws%3A%2F%2F127.0.0.1%3A8765%2Fws`（可存为书签，车间平板同网段也可访问）；
  - 需要停止时双击 `stop.bat` 即可干净关闭。

### 3. 连接真实硬件 PLC 或 PLCSIM Advanced（两步完成）
1. **博途 PLC 侧导入数据块与示例控制程序**：
   - **导入数据块**：博途项目树展开 `外部源文件` ➔ 双击 `添加新的外部源文件` ➔ 选择项目中的 `TwinIO.scl` ➔ 右键 **“从源生成块”**，生成非优化 DB1（注意核对编号是否为 DB1）；
   - **导入示例逻辑（可选，1 分钟活体闭环联调）**：同样将 `TwinDemoLogic.scl` 添加到外部源文件并生成块，在 OB1 ("Main") 中插入一行 `"TwinDemoLogic"();` 即可自动实现启停自锁、光电感应推料与计数清零；
   - 检查 CPU 属性【保护与安全】➔【连接机制】已勾选 **“允许来自远程对象的 PUT/GET 通信访问”**；
   - 下载程序到 PLC 并将 CPU 置于 RUN 绿灯模式。
2. **网页一键连接**：
   - 浏览器右上角点击 **“连接 PLC”**；
   - **设备目标类型**：选择实体机型（S7-1200 / S7-1500 / S7-300）或 PLCSIM Advanced；
   - **通信扫描周期**：选择 `50ms (20 Hz · 高速响应)` 或 `100ms (10 Hz · 工业标准推荐)`；
   - **PLC IP 地址**：输入真实 PLC 的物理 IP（如 `192.168.0.10`）或仿真器 IP（如 `192.168.0.1`）；
   - 点击 **“连接 PLC”**，即可实时完成双向闭环通讯！
```

## 10. 验收清单

- [ ] `validate_manifest.py` 返回 OK，且无读写字节混排严重告警（读写字节严格隔离）。
- [ ] 生成的 `TwinIO.scl` 偏移与 manifest 完全一致，非优化访问声明正确。
- [ ] 配套生成的 `TwinDemoLogic.scl` 包含启停闭环与传感器联动逻辑，可在博途 OB1 中无缝调用。
- [ ] 离线模式：启动/停止/复位/急停、修改布尔/数值数据、自动检测开关、推料、计数、刷新。
- [ ] 在线模式：只输入 PLC 地址与选择扫描周期即可；连接中/失败时禁用操作；成功后实时驱动。
- [ ] 网关：`pending` 初始状态、`plc.configure` ack、`snapshot`/`delta`、`pulse`、`writeMany`、重连。
- [ ] 真实 PLCSIM / 实体 PLC：PLC 状态、TIA 监视表、传感器回写、PLC 输出驱动网页、计数/故障。
- [ ] 页面没有硬编码地址；没有在真实模式重复 PLC 逻辑；没有逐帧写 PLC；未暴露网关 URL/Token。
- [ ] 严格遵守禁止向物理 `%I` 区直写规范；严格遵守 Windows 11 24H2 零命令行绿色交付规范。
- [ ] 明确标注仿真用途，未宣称未经实测的 PLC 联调结果。

## 11. 边界

- 通信支持 **S7comm/snap7 + 多 DB / 跨 DB 原生支持 + 标量 tag**（支持任意 DB1..DB65535 独立分区）；不支持 OPC UA、动态数组、字符串。
- 不支持安全功能；急停按钮只是教学仿真信号。
- 不能保证所有 PLCSIM Advanced 版本/固件都允许 S7comm；先用 TIA 监视表验证，再联调网页。
- 遇到优化 DB、PUT/GET 关闭、虚拟网卡选择错误时，网关会报通信错误；先修 PLC 配置，不要改代码绕过。

## 12. 资源

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
- `assets/tia/TwinDemoLogic.scl`：参考配套控制逻辑外部源文件（可在 OB1 直接调用）。
