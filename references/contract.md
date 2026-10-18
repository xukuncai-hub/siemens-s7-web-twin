# TIA Web Twin 通信契约 (tia-web-twin/1)

本文件是网页、`tia-twin-client.js` 和 `tia_gateway.py` 之间的唯一协议来源。改动协议必须同时改三处。

## 1. 连接

- WebSocket 端点：`ws://<host>:<port>/ws`
- 可选 Token：`ws://<host>:<port>/ws?token=<shared_secret>`
- 默认：`127.0.0.1:8765`，10 Hz 轮询；生产或在局域网使用时必须加 Token，且不要直接暴露到公网。
- 浏览器不允许直接说 S7comm；必须经过本网关。
- 操作界面不展示网关 URL/Token；`run_twin.py` 通过 `?ws=` 把地址传给页面，网关由启动器负责。

## 2. 服务端消息

### 2.1 hello（连接后立即发送）

```json
{
  "type": "hello",
  "protocol": "tia-web-twin/1",
  "project": "sorting-line",
  "title": "输送带分拣线 · 数字孪生",
  "manifestHash": "c9d5fc5f27a5",
  "pollHz": 10,
  "backend": "s7",
  "db": 1,
  "ts": 1713438000.123
}
```

`backend` 为 `s7` 或 `mock`。`manifestHash` 是清单文件的 SHA-256 前 12 位，用于确认网关和网页加载的是同一份契约。

### 2.2 snapshot（新连接的全量状态）

```json
{
  "type": "snapshot",
  "seq": 1,
  "ts": 1713438000.125,
  "values": {
    "box.count": 0,
    "line.speed": 1.2,
    "line.running": true,
    "sensor.pe1": false,
    "out.cyl": false
  }
}
```

只包含 `access` 为 `r` 或 `rw` 的 tag。`w` 命令 tag 不会出现在快照里。

### 2.3 delta（变化量广播）

```json
{
  "type": "delta",
  "seq": 42,
  "ts": 1713438001.050,
  "values": { "box.count": 5, "sensor.pe1": true }
}
```

`diff` 是历史别名，客户端应同时接受；网关只发送 `delta`。没有变化时不发消息。

### 2.4 status（PLC / 网关状态）

```json
{ "type": "status", "plc": "error", "message": "PLC connect failed | ...", "ts": 1713438001.100 }
```

`plc` 取值：`waiting`（等待页面输入 PLC 地址）、`connected`、`error`。网关连接本身正常但 PLC 不通时，客户端仍是 `online`，但应显示 PLC 错误并禁用写命令。

### 2.5 ack / error

```json
{ "type": "ack", "id": "w12", "tag": "cmd.start", "ok": true, "pulseMs": 150 }
{ "type": "error", "id": "w13", "code": "READ_ONLY", "message": "line.running 不可写" }
```

错误码：`BAD_JSON`、`BAD_MESSAGE`、`BAD_TAG`、`READ_ONLY`、`BAD_VALUE`、`PLC_WRITE_FAILED`。

### 2.6 pong

```json
{ "type": "pong", "ts": 1713438002.512, "echo": 1713438002.500 }
```

客户端用 `Date.now() - echo` 计算 RTT。浏览器每 5 s 发送一次 app-level ping。

## 3. 客户端消息

### 3.1 hello

```json
{ "type": "hello", "client": "tia-web-twin-js/1.0.0", "protocol": "tia-web-twin/1", "project": "sorting-line" }
```

服务端在收到后再发一次 snapshot，便于重连后重新同步。

### 3.2 write（电平写）

```json
{ "type": "write", "id": "w1", "tag": "sensor.pe1", "value": true }
```

### 3.3 pulse（按钮点动）

```json
{ "type": "pulse", "id": "w2", "tag": "cmd.start", "ms": 150 }
```

仅允许可写 `bool`。网关先置 `true`，`ms` 后自动置 `false`；用于启动/停止/复位/急停按钮。不要把 `sensor` 之类的电平量用 pulse 写。

### 3.4 writeMany（批量写，传感器回写常用）

```json
{ "type": "writeMany", "id": "w3", "values": { "sensor.pe1": false, "cyl.extended": true } }
```

一次最多 64 项。任一项非法则整批拒绝。网页应按变化发送，建议 10 Hz 同步，不要逐帧刷写。

### 3.5 plc.configure（在线模式输入 PLC 地址）

页面只向用户要 PLC IP/rack/slot；网关在运行中热切换 S7 后端，不需要改 JSON 或重启。

```json
{ "type": "plc.configure", "id": "w4", "ip": "192.168.0.50", "rack": 0, "slot": 1 }
```

成功应答：

```json
{ "type": "ack", "id": "w4", "ok": true, "plc": { "ip": "192.168.0.50", "rack": 0, "slot": 1 } }
```

随后网关广播 `status: waiting`，再根据连接结果广播 `connected` 或 `error`。网关启动时可为 `pending` 后端（`--wait-plc`），在收到本消息前不尝试连接 PLC。`mock` 后端拒绝本消息。

### 3.6 ping

```json
{ "type": "ping", "ts": 1713438002.500 }
```

## 4. Tag 语义

| 字段 | 说明 |
| --- | --- |
| `id` | 语义化点分小写名，如 `line.running`、`out.cyl` |
| `address` | `DBn.DBX<byte>.<bit>` / `DBB` / `DBW` / `DBD` |
| `type` | `bool`、`byte`、`int16`、`uint16`、`int32`、`uint32`、`real` |
| `access` | `r` PLC→网页；`w` 网页→PLC；`rw` 双向 |
| `writeMode` | `level` 或 `pulse`（pulse 仅 bool） |
| `pulseMs` | 50..2000，默认 150 |
| `mockInit` | 浏览器 Mock 与网关 Mock 的初始值 |

**地址必须与 TwinIO DB 的实际偏移一致。** DB 必须关闭“优化的块访问”；CPU 必须允许 PUT/GET。16 位量按偶数字节、32 位量按 4 字节对齐。

### 数字孪生方向

- **PLC → 网页（执行器/状态）**：`out.cyl`、`line.running`、`line.fault`、`stack.*`、`box.count`，用 `r`。
- **网页 → PLC（被控对象传感器）**：`sensor.pe1`、`cyl.extended`，用 `rw` 或 `w` + `level`。
- **网页 → PLC（命令）**：`cmd.start`、`cmd.stop`、`cmd.reset`、`cmd.estop`，用 `w` + `pulse`。

网页端必须实现被控对象模型（输送带、气缸、传感器），但**不要在真实 PLC 模式下再实现一遍 PLC 逻辑**。PLC 的输出去驱动网页动画；网页算出的传感器再写回 PLC。mock 模式可以用 `MockPlc` 同时模拟 PLC 逻辑和对象，便于离线演示。

## 5. 连接与错误处理

- 网关断开：客户端按 0.6 s 起指数退避重连，最多 10 s；重连后重新发送 hello，并在在线模式重新发送 `plc.configure`。
- PLC 写入失败：保留网页物理模型，显示 PLC 错误，不假装成功。
- 在线模式下，PLC 未 `connected` 前不要回写传感器/命令；等待状态应禁用操作。
- 写入命令必须有 ack；不要 fire-and-forget 启动/停止命令。
- **原生支持跨 DB 通信**：manifest 支持定义任意多个合法 DB 块（如 `DB1.DBX0.0` 输入、`DB2.DBX0.0` 输出、`DB3.DBD0` 数据）。网关自动按目标 DB 分块并行轮询，SCL 自动生成器亦会同步生成各 DB 的非优化数据块源文件。v1 暂不支持动态数组和字符串。

## 6. 模板产线行为（mock / 推荐 PLC 逻辑）

模板 `sorting-line` 的语义如下，PLC 侧按此实现即可得到与 mock 一致的闭环：

1. `cmd.start` 脉冲：`line.running = 1`、`line.fault = 0`、`line.speed = 0.15`、`stack.green = 1`、`stack.red = 0`。
2. `cmd.stop` 脉冲：`line.running = 0`、`line.speed = 0`、`out.cyl = 0`、`stack.green = 0`。
3. `cmd.estop` 脉冲：锁存 `line.fault = 1`、`line.running = 0`、`out.cyl = 0`、`stack.red = 1`；`cmd.reset` 清故障。
4. `sensor.pe1` 上升沿（且运行、无故障）：`box.count + 1`，`out.cyl` 置 1 并在约 700 ms 后复位（实际项目可用 TON）。
5. 网页把推料气缸的 `cyl.extended` 真实/模型状态回写；PLC 可把它作为下一次动作的互锁条件。
6. `out.cyl` 驱动网页推料动画；被推下的箱体不再触发 `sensor.pe1`。计数以 PLC 的 `box.count` 为准，网页不自行计数。

PLC 的控制逻辑不在 `TwinIO.scl` 里；该文件只是数据块。不要把这段逻辑塞回网页真实模式，否则同一动作会被计算两次。
