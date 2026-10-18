# 博途 (TIA Portal) 与西门子 S7 真实硬件 PLC / PLCSIM 联调指南

本文档是确保网页数字孪生能够成功连通**西门子实体硬件 PLC (S7-1200 / S7-1500 / S7-300)** 或 **PLCSIM Advanced 仿真器**的核心检查手册。

---

## 1. 目标 PLC 设备类型与连接规范

无论是实体硬件还是虚拟仿真器，底层通信协议完全统一为 **S7comm (ISO-on-TCP，默认端口 102)**。

### 选项 A：连接真实硬件 PLC (S7-1200 / S7-1500 / S7-300)

1. **物理网线连接**：
   - 使用标准以太网网线将电脑网口与 PLC 上的 PROFINET (PN) 网口直接相连，或通过工业交换机连接。
2. **电脑网卡 IP 规划**：
   - 电脑本地网卡必须与真实 PLC 处于**同一局域网网段**。
   - 例如：真实 PLC 的 IP 为 `192.168.0.10`，子网掩码 `255.255.255.0`；
   - 电脑有线网卡设为固定 IP `192.168.0.100`，子网掩码 `255.255.255.0`；
   - 在电脑命令行执行 `ping 192.168.0.10`，确认能稳定收到 ICMP 回复。
3. **机架 (Rack) 与插槽 (Slot) 规范**：
   - **S7-1200 / S7-1500 实体 PLC**：Rack = `0`, Slot = `1`
   - **S7-300 / ET200 实体 PLC**：Rack = `0`, Slot = `2`

### 选项 B：连接 S7-PLCSIM Advanced 虚拟 PLC

1. 打开 **S7-PLCSIM Advanced** 控制面板。
2. **Online Access（在线访问接口）**：
   - 必须选择：`Siemens PLCSIM Virtual Ethernet Adapter`（虚拟以太网适配器）。
   - ⚠️ **切勿选择 Softbus**，Softbus 仅限单机西门子内部组件通信，Snap7 无法通过 TCP/IP 连入。
3. **Start Virtual S7-1500 PLC Instance**：
   - **Instance Name**：例如 `PLC_1`
   - **IP Address**：输入同网段 IP（例如 `192.168.0.1`）
   - **Subnet Mask**：`255.255.255.0`
   - 点击 **Start** 启动虚拟 CPU，指示灯变为绿色 RUN。
4. **机架与插槽**：Rack = `0`, Slot = `1`。

---

## 2. 博途 (TIA Portal) 关键工程属性配置

### 步骤 2.1：开启 CPU 的 PUT/GET 远程访问权限（真实 PLC 必查！）
1. 在博途“设备和网络”中双击打开你的 S7-1200 / S7-1500 CPU 硬件组态。
2. 在下方属性窗口中，选择 **“常规” (General) -> “防护与安全” (Protection & Security)**。
3. 点击 **“连接机制” (Connection mechanisms)**。
4. 勾选 **“允许来自远程对象的 PUT/GET 通信访问” (Permit access with PUT/GET communication from remote partner)**。
   *⚠️ 注：如果不勾选此项，真实 PLC 将在收到上位机握手时直接拒绝，报 `CLI : function refused by CPU`。*

### 步骤 2.2：开启项目仿真支持（仅使用 PLCSIM 时需要）
1. 在博途左侧项目树最顶端，**右键点击项目名称** -> 选择 **“属性” (Properties)**。
2. 切换至 **“保护” (Protection)** 页签。
3. 勾选 **“块编译时支持仿真” (Support simulation during block compilation)**。

---

## 3. 数据块 (DB) 配置与外部源文件导入

S7comm 协议寻址依赖绝对字节偏移（Offset）。西门子默认启用的“优化的块访问”会打乱变量顺序并隐藏偏移量，因此必须关闭。

### 导入标准 `TwinIO.scl` 步骤：
1. 在博途项目树中展开 CPU -> **“外部源文件” (External source files)**。
2. 双击 **“添加新外部文件”**，选择由 Skill 生成的 `TwinIO.scl`。
3. **右键点击添加进来的 `TwinIO.scl` 文件** -> 选择 **“从源文件生成块” (Generate blocks from source)**。
4. 博途会在“程序块”中自动创建 `TwinIO`，生成时已由 SCL 属性 `{ S7_Optimized_Access := 'FALSE' }` 自动关闭了优化访问。
5. 打开该 DB，确认每个变量右侧都显示了固定的偏移量（如 `0.0`, `0.6`, `1.0`）；如果 DB 号不是 1，必须同步修改 `twin.manifest.json` 的所有地址与 `gateway.config.json`。

---

## 4. 编译与下载

1. 右键点击 CPU -> **“编译” (Compile) -> “硬件和软件 (仅更改)”**。
2. 点击下载按钮：
   - 真实 PLC：选择电脑物理网卡，搜索到物理 PLC 并下载；
   - PLCSIM Advanced：选择 `Siemens PLCSIM Virtual Ethernet Adapter` 并下载；
3. 将 CPU 切换到 **RUN** 绿色运行状态。

---

## 5. 常见网络排错 (FAQ)

### Q1: 页面连接 PLC 时提示 `Connection refused` 或 `Timeout`？
* **真实 PLC**：检查网线是否插紧、电脑 IP 与 PLC IP 是否在同一网段，在 CMD 中 `ping <PLC_IP>` 测试网络。
* **PLCSIM**：检查是否误选了 Softbus；检查是否生成了虚拟网卡且 IP 能 ping 通。
* 检查 Windows 防火墙是否放行了 TCP 端口 102。

### Q2: 提示 `CLI : function refused by CPU`？
* 说明没有在 CPU 属性中勾选 **“允许来自远程对象的 PUT/GET 通信访问”**。重新勾选后必须**重新编译并下载硬件组态**。

### Q3: 读到的布尔量错位或数值乱跳？
* 说明 DB 块没有关闭“优化的块访问”，或者没有使用 SCL 外部源文件统一生成的 DB 块，导致变量偏移量与 `twin.manifest.json` 不一致。

### Q4: 提示 `Invalid address (0x05)` 或 `Object does not exist (0x0a)`？
* **0x0a (Object does not exist)**：PLC 内部根本不存在该 DB 块。通常是因为用户在博途中导入了 SCL 源文件但**未执行“从源文件生成块”**，或者**未下载到 CPU**，又或者博途分配的 DB 号是 DB2/DB5 而不是 DB1。
* **0x05 (Invalid address)**：PLC 内部的 DB 块物理长度小于上位机尝试读取的长度！
