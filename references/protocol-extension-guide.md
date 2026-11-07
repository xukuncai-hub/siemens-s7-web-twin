# 多工业协议接入与 AI 自主开发扩展规范指南 (Multi-Protocol Guide)

> **核心哲学**：前端 Web 数字孪生（无论是 HTML 原生建模还是 Blender 工业级 3D 资产）**与底层工业硬件协议完全解耦**。  
> 网页层只与本地网关进行标准化 WebSocket JSON（`tia-web-twin/1`）通信；底层硬件无论是 **西门子 S7comm、Modbus TCP、Modbus RTU (RS-485)、原始 TCP/IP Socket**，还是**三菱 MC、欧姆龙 FINS、MQTT**，均由网关层的“协议适配驱动（Protocol Backend）”统一适配。

---

## 1. 架构与数据流图

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Web 孪生前端 (HTML 原生建模 / Blender 3D)              │
│       tia-twin-client.js  ⇄  WebSocket JSON (tag:value 差量广播)       │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  ws://127.0.0.1:8765/ws
┌────────────────────────────────────▼───────────────────────────────────┐
│               本地通信网关 (tia_gateway.py 统一差量调度引擎)               │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │           统一协议驱动接口规范 (BaseProtocolBackend)            │   │
│   └──────┬──────────────┬──────────────┬──────────────┬────────────┘   │
│          │              │              │              │                │
│          ▼              ▼              ▼              ▼                │
│     S7comm驱动     Modbus TCP     Modbus RTU      Raw TCP/IP           │
│     (西门子S7)     (以太网502)    (RS-485串口)    (自定义Socket)         │
│          │              │              │              │                │
│          ▼              ▼              ▼              ▼                │
│     [新扩展协议：AI 按照本规范 10 分钟自主编写派生类 (如三菱MC/欧姆龙FINS/MQTT)] │
└──────────┬──────────────┬──────────────┬──────────────┬────────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
       西门子 PLC    Modbus仪表/PLC    RS-485模块     工业相机/扫码枪/自研板卡
```

---

## 2. 统一地址寻址语法规范 (Manifest Address Contract)

在 `twin.manifest.json` 中，通过顶层 `"protocol"` 声明使用的底层协议，各协议的 `tags.address` 遵循以下统一语法：

| 协议类型 (`protocol`) | 变量类型 (`type`) | 推荐地址写法 (`address`) | 对应硬件/底层含义 |
| :--- | :--- | :--- | :--- |
| **`s7` (西门子)** | `bool` | `DB1.DBX0.0` / `I0.0` / `Q0.0` / `M0.0` | 数据块位、物理输入(%I)、物理输出(%Q)、位存储器(%M) |
| | `byte` | `DB1.DBB1` / `IB0` / `QB0` / `MB10` | 8位无符号字节 |
| | `int16` / `uint16` (模拟量) | `DB1.DBW2` / `IW64` / `QW64` / `MW10` | 16位整数/模拟量通道 (如标准 0~27648 传感器或给定值) |
| | `int32` / `uint32` | `DB1.DBD4` / `ID100` / `QD100` / `MD20` | 32位双字/长整型 |
| | `real` (工程浮点量) | `DB1.DBD8` / `MD30` | 32位单精度 IEEE 754 浮点数 (如温度、压力、流量实际值) |
| **`modbus-tcp`** | `bool` | `0x0001` 或 `coil:1` | 线圈 (Coil 0x)，读写 |
| | `bool` | `1x0001` 或 `di:1` | 离散输入 (Discrete Input 1x)，只读 |
| | `int16` / `uint16`| `3x0001` 或 `ir:1` | 输入寄存器 (Input Register 3x)，只读 |
| | `int16` / `real` | `4x0001` 或 `hr:1` | 保持寄存器 (Holding Register 4x)，读写 |
| **`modbus-rtu` (RS-485)**| `bool` / `int16` | `1#4x0001` 或 `slave:1:hr:1` | 站号 1 从机的保持寄存器 1 |
| **`tcp-raw` (原始 Socket)**| `bool` / `int16` | `offset:0.0` / `offset:2` | 报文固定字节/位偏移量 |
| **`custom` (AI 自定义)** | 任意 | 由 AI 在扩展驱动中自由映射 | 例如 MQTT Topic、JSON Key 或命令码 |

### 西门子 S7 原生存储区与模拟量采集工程详解

网关底层基于 Snap7 标准工业接口，将地址自动映射至西门子固件原生存储区代码：
* **DB 块 (`0x84`, S7AreaDB)**：非优化数据块，支持跨 DB 访问（如 `DB1.DBX0.0`, `DB2.DBD4`）。
* **过程输入 I 区 (`0x81`, S7AreaPE)**：PLC 物理接线输入端子与数字/模拟量采集模块（如 `I0.0` 为急停开关，`IW64` 为温度传感器模拟量原始值）。**注意：物理 I 区由 PLC 硬件中断周期性刷新，上位机应仅设为只读 (`access: "r"`)。**
* **过程输出 Q 区 (`0x82`, S7AreaPA)**：PLC 物理继电器/晶体管输出端子与模拟量输出模块（如 `Q0.0` 为电机接触器，`QW64` 为变频器频率给定）。
* **位存储器 M 区 (`0x83`, S7AreaMK)**：PLC 内部通用中间寄存器，可自由读写布尔位（`M0.0`）、整型字（`MW10`）与浮点双字（`MD20`）。

#### 模拟量量程与工程量标定（0~27648 vs Real）
西门子 S7-1200 / S7-1500 / S7-300 的标准模拟量采集机制如下：
1. **原始采集通道 (`IW...` / `QW...`)**：
   - 信号类型：标准电压（`0~10V`）或电流（`4~20mA`）；
   - 在 PLC 中以 `int16` 格式存储，标准工程满量程固定为 `0 ~ 27648`（单极性）或 `-27648 ~ 27648`（双极性）；
   - 配置示例：
     ```json
     { "id": "sensor.pressure_raw", "address": "IW64", "type": "int16", "access": "r", "mockInit": 13824, "desc": "压力传感器 0~27648 (对应 0~10bar)" }
     ```
2. **标定后的浮点工程量 (`Real`, `MD...` 或 `DB...`)**：
   - 经过 PLC 内部 `SCALE_X` 或自定义算式转换后，输出为具备实际工程物理单位的浮点数；
   - 配置示例：
     ```json
     { "id": "sensor.pressure_bar", "address": "MD20", "type": "real", "access": "r", "mockInit": 5.0, "desc": "实时管网压力 (单位: bar)" }
     ```
3. **网关性能优化（自动合并连续块）**：
   网关在初始化时会自动将所有标签按 `(area_code, db)` 分组，并计算连续地址区间的最小包络 `[min_offset, max_offset]`。每个轮询周期仅执行一次块读取（Block Read），杜绝因散落地址导致的高频小包通信堵塞。

---

## 3. 驱动统一抽象基类规范 (`BaseProtocolBackend`)

所有协议驱动必须继承或实现以下标准接口（位于 `scripts/tia_gateway.py`）：

```python
class BaseProtocolBackend:
    name: str = "custom"

    def status(self) -> dict:
        """返回当前连接状态与诊断信息，供前端 HUD 实时展示。
        返回值标准格式:
        {
            "connected": bool,           # 是否已连通
            "target": str,               # 通信目标 (如 '192.168.0.10:502' 或 'COM3@9600')
            "protocol": str,             # 协议标识 (如 'modbus-tcp', 's7')
            "detail": str,               # 补充说明 (如 'PLC 运行正常' 或错误提示)
            "ts": float                  # 时间戳
        }
        """
        raise NotImplementedError

    async def ensure_connected(self) -> bool:
        """建立或维持与下位机的物理通信连接。
        必须内置指数退避或自动重连保护，连接失败返回 False，成功返回 True。
        """
        raise NotImplementedError

    async def read_all(self) -> dict[str, Any]:
        """批量读取 manifest 中所有 access 含有 'r' 的变量。
        返回字典映射: { tag_id: value, ... }
        """
        raise NotImplementedError

    async def write(self, tag: Tag, value: Any) -> None:
        """向硬件下发单点写入请求。
        tag: 包含 address, type, write_mode 等信息的 Tag 对象
        value: 经校验转换后的目标值 (bool, int, float)
        """
        raise NotImplementedError

    async def close(self) -> None:
        """安全释放底层网络套接字或串口句柄。"""
        raise NotImplementedError
```

---

## 4. 内置原生支持的三大通用协议

### 4.1 Modbus TCP 原生支持
* **适用设备**：汇川、信捷、欧姆龙、台达、施耐德及绝大多数支持以太网的工业传感器与温控表。
* **特性**：
  * 内置**纯 Python 异步实现**，零第三方库依赖；
  * 支持功能码：`01` (读线圈)、`02` (读离散输入)、`03` (读保持寄存器)、`04` (读输入寄存器)、`05/15` (写线圈)、`06/16` (写寄存器)；
  * 默认端口 `502`，支持 `slaveId` (单元标识符) 配置。

### 4.2 Modbus RTU (RS-485 串口)
* **适用设备**：通过 USB 转 RS-485 模块接入工控机/PC 的工业变频器、步进电机驱动器、电表、称重传感器。
* **配置参数**：
  ```json
  "plc": {
    "protocol": "modbus-rtu",
    "port": "/dev/ttyUSB0",    // Windows 下为 "COM3"
    "baudrate": 9600,
    "bytesize": 8,
    "parity": "N",
    "stopbits": 1,
    "slaveId": 1
  }
  ```

### 4.3 Raw TCP/IP (原始流式 Socket)
* **适用设备**：工业扫码枪、基恩士/海康工业相机、激光测距传感器、单片机/树莓派自研板卡。
* **工作模式**：
  * **客户端模式**：网关主动连接设备的 TCP Server 端口（如 `:8080`）；
  * **定界符/定长切包**：支持换行符 `\r\n` 分包、固定字节长或十六进制帧头帧尾。

---

## 5. 遇到其他新协议时，AI Agent 如何依规自主开发扩展？(SOP)

当用户提出连接未内置的专有协议时（例如：**三菱 MC 协议、欧姆龙 FINS、Beckhoff ADS、MQTT、CANopen** 等），**AI Agent 必须严格按照以下 SOP 自主编写扩展**：

### 步骤 1：确认通信参数与变量映射
在 `twin.manifest.json` 中声明协议名与目标参数：
```json
{
  "schema": "tia-web-twin/manifest@1",
  "project": "mitsubishi-line",
  "protocol": "mitsubishi-mc",
  "plc": {
    "ip": "192.168.1.250",
    "port": 5000,
    "networkNo": 1,
    "pcNo": 255
  },
  "tags": [
    { "id": "line.running", "address": "M100", "type": "bool", "access": "r" },
    { "id": "out.cyl",      "address": "Y0",   "type": "bool", "access": "r" },
    { "id": "sensor.pe1",   "address": "X0",   "type": "bool", "access": "w" }
  ]
}
```

### 步骤 2：在网关中实现派生类 (以三菱 MC 协议为例)
AI Agent 直接在工程的 `tia_gateway.py` 或新建驱动文件 `driver_mitsubishi.py` 中继承 `BaseProtocolBackend`：

```python
import asyncio
import struct
from tia_gateway import BaseProtocolBackend, Tag

class MitsubishiMcBackend(BaseProtocolBackend):
    name = "mitsubishi-mc"

    def __init__(self, manifest, cfg):
        self.manifest = manifest
        self.ip = cfg.get("ip", "192.168.1.250")
        self.port = int(cfg.get("port", 5000))
        self.reader = None
        self.writer = None
        self._connected = False

    async def ensure_connected(self) -> bool:
        if self._connected and self.writer:
            return True
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=3.0
            )
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def read_all(self) -> dict:
        if not await self.ensure_connected():
            return {}
        # 按照三菱 3E 帧格式组装二进制报文并发送:
        # subheader(2B) + network(1B) + pc(1B) + io(2B) + station(1B) + len(2B) + timer(2B) + cmd(0401) ...
        # 解析返回的数据并映射至 manifest.tags
        return {"line.running": True, "out.cyl": False}

    async def write(self, tag: Tag, value: any):
        if not await self.ensure_connected():
            return
        # 组装 3E 帧 1401 (批写入) 报文发送给三菱 PLC
        pass

    def status(self) -> dict:
        return {"connected": self._connected, "target": f"{self.ip}:{self.port}", "protocol": "MC-3E"}

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
```

### 步骤 3：在网关工厂函数中注册新协议
在 `tia_gateway.py` 的 `create_backend` 中增加一条分支：
```python
elif protocol in ("mitsubishi-mc", "mc"):
    return MitsubishiMcBackend(manifest, plc_cfg)
```

**立竿见影**：只要完成上述步骤，前端所有的 3D/HTML 产线画面、数字孪生传感器与点动控制台立刻能与三菱/其他硬件双向互通，无需做任何前端改动！
