# 博途 (TIA Portal) 与 S7-PLCSIM Advanced 仿真配置指南

本文档是确保网页数字孪生能够成功连通西门子高级仿真的**核心检查手册**。

---

## 1. S7-PLCSIM Advanced 仿真器启动配置

1. 打开 **S7-PLCSIM Advanced** 控制面板。
2. **Online Access（在线访问接口）**：
   * 必须选择：`Siemens PLCSIM Virtual Ethernet Adapter`（虚拟以太网适配器）。
   * ⚠️ **切勿选择 Softbus**，Softbus 仅限单机西门子内部组件通信，Snap7 无法通过 TCP/IP 连入。
3. **Start Virtual S7-1500 PLC Instance**：
   * **Instance Name**：例如 `PLC_1`
   * **IP Address**：必须输入与上位机处于同网段的独立 IP（例如 `192.168.0.50` 或 `192.168.0.1`）。
   * **Subnet Mask**：`255.255.255.0`
   * 点击 **Start** 启动虚拟 CPU，指示灯变为绿色 RUN。

4. **网关位置**：优先把 `tia_gateway.py` 放在与 PLCSIM Advanced 同一台 Windows 机器上运行；网关绑 `127.0.0.1` 时只有本机浏览器能连。若网关跑在另一台 Linux/Windows 机器，必须能路由并 Ping 通虚拟 PLC 的 IP，同时把网关 `ws.host` 改成 `0.0.0.0` 并设置 Token。

---

## 1.1 页面连接方式（推荐）

```bash
cd <project>
python run_twin.py
```

页面默认是**离线仿真**，可直接改数据。点击右上角“连接 PLC”，只填：

- PLCSIM Advanced 虚拟 PLC 的 IP
- Rack（S7-1500 通常 0）
- Slot（通常 1）

网关由 `run_twin.py` 在后台启动，页面通过 `plc.configure` 热切换 PLC 目标，**不需要改 gateway.config.json，也不需要重启网关**。连接中/失败时操作按钮会禁用；失败时先按本指南检查 PLC 配置，再重试。

---

## 2. 博途 (TIA Portal) 关键工程属性配置

### 步骤 2.1：开启项目仿真支持
1. 在博途左侧项目树最顶端，**右键点击项目名称** -> 选择 **“属性” (Properties)**。
2. 切换至 **“保护” (Protection)** 页签。
3. 勾选 **“块编译时支持仿真” (Support simulation during block compilation)**。
4. 点击“确定”保存。

### 步骤 2.2：开启 CPU 的 PUT/GET 远程访问权限
1. 在“设备和网络”中双击打开你的 S7-1500 / S7-1200 CPU。
2. 在下方属性窗口中，选择 **“常规” (General) -> “防护与安全” (Protection & Security)**。
3. 点击 **“连接机制” (Connection mechanisms)**。
4. 勾选 **“允许来自远程对象的 PUT/GET 通信访问” (Permit access with PUT/GET communication from remote partner)**。

---

## 3. 数据块 (DB) 配置与外部源文件导入

S7comm 协议寻址依赖绝对字节偏移（Offset）。西门子默认启用的“优化的块访问”会打乱变量顺序并隐藏偏移量，因此必须关闭。

### 导入标准 `TwinIO.scl` 步骤：
1. 在博途项目树中展开 CPU -> **“外部源文件” (External source files)**。
2. 双击 **“添加新外部文件”**，选择由 Skill 生成的 `TwinIO.scl`。
3. **右键点击添加进来的 `TwinIO.scl` 文件** -> 选择 **“从源文件生成块” (Generate blocks from source)**。
4. 博途会在“程序块”中自动创建 `TwinIO`，DB 号由项目决定，**不一定是 DB1**。
5. 打开该 DB，确认每个变量右侧都显示了固定的偏移量（如 `0.0`, `2.0`, `4.0`, `8.0`）；如果 DB 号不是 1，必须同步修改 `twin.manifest.json` 的所有地址、`plc.db` 和 `gateway.config.json`。

> `TwinIO.scl` 只生成数据块，不包含控制逻辑。启动/停止自锁、光电触发推料、计数、急停保持等逻辑必须在你自己的 FB/OB 中实现；模板页面的 mock 逻辑可作为行为参考（见 `references/contract.md` 的“模板产线行为”）。

---

## 4. 编译与下载到仿真器

1. 右键点击 CPU -> **“编译” (Compile) -> “硬件和软件 (仅更改)”**。
2. 点击下载按钮，接口类型选择 **PN/IE**，PG/PC 接口选择 **Siemens PLCSIM Virtual Ethernet Adapter**。
3. 搜索并选择刚才启动的虚拟 PLC，点击“下载”。
4. 将 CPU 切换到 RUN 模式。

---

## 5. 常见网络排错 (FAQ)

### Q1: 页面连接 PLC 时提示 `Connection refused` 或 `Timeout`？
* 检查本机网络连接中是否有 `Siemens PLCSIM Virtual Ethernet Adapter`（不是 Softbus）。
* 在网关所在机器运行 `ping <虚拟PLC地址>`，确保能 Ping 通；跨机时检查路由和虚拟网卡桥接。
* 检查 Windows 防火墙是否允许 TCP 102（S7comm）入站；网关默认端口 8765 只需浏览器能访问。
* snap7/PLCSIM 的 rack/slot 通常为 `0/1`，确认 `gateway.config.json` 与虚拟实例一致。

### Q2: 提示 `CLI : function refused by CPU`？
* 说明没有在 CPU 属性中勾选 **“允许来自远程对象的 PUT/GET 通信访问”**。重新勾选后必须**重新编译并下载硬件组态**。

### Q3: 读到的布尔量错位或数值乱跳？
* 说明 DB 块没有关闭“优化的块访问”，或者没有使用 SCL 外部源文件统一生成的 DB 块，导致变量偏移量与 `twin.manifest.json` 不一致。
* 也可能是 TIA 分配的 DB 号不是 1，而 manifest 仍写 `DB1...`；在 TIA 中查看实际 DB 号后统一修改。

### Q4: 页面显示“已连接”，但一按启动就报 `PLC_WRITE_FAILED`？
* 检查写的是不是 `TwinIO` 里的可写 tag；S7comm 不能写 Q 区，也不应写优化 DB。
* 检查 CPU 是否 RUN、PUT/GET 是否已重新编译下载、命令 tag 是否是 `bool` + `pulse`。
* 在 TIA 监视表中手动置位同一地址，确认 DB 偏移和权限正确。
