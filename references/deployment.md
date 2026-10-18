# 部署与“无终端”选项

普通浏览器页面不能直接打开 S7comm 的 TCP 102。因此网页始终需要一个本地或远端的 WebSocket 网关。下面按用户操作复杂度排列。

## A. 双击启动器（默认零命令 · 最推荐）

项目根目录已预置全套免命令行启动器（纯 7-bit ASCII，100% 兼容 Windows 11 24H2）：

- **Windows 用户**：
  - **`start.bat`**：双击即可启动。自动智能寻找真实 Python（避开 WindowsApps 劫持）、启动静态服务与网关，并自动唤起默认浏览器。关闭黑窗口即退出。
  - **`make_shortcut.bat`**：双击一次，使用原生 PowerShell 在 Windows 桌面上创建【TIA Web 3D Twin】桌面快捷方式，后续在桌面双击即可使用。
  - **`start_silent.bat`**：后台静默启动。完全不弹出黑色 cmd 命令行窗口，3 秒后黑窗口自动消失，服务在后台常驻运行，浏览器可直接存为书签访问。
  - **`stop.bat`**：一键干净终止所有后台常驻服务进程。
- **Linux 用户**：双击 `start_twin.desktop`（首次可能需在文件管理器里允许执行）或执行 `./start_twin.sh`。

## B. 目标工控机无 Python 环境的三种交付方案

在实际工业现场或客户电脑上，往往**没有安装 Python**，或者由于权限限制无法运行 `pip` 安装包。系统原生支持三种完全免环境门槛的交付方式：

### 方案 1：绿色便携包（Python Embeddable / Portable Runtime）—— ⭐️ 工业现场最推荐
- **机制**：在项目根目录内置官方免安装的极简 Python 嵌入版（解压后约 20MB 的 `runtime/` 目录，已预置 `python-snap7` 与 `websockets`）。
- **原生自愈检测**：项目中的 `start.bat`、`start_silent.bat` 均已内置便携包自愈检测逻辑：
  ```bat
  if exist "%~dp0runtime\python.exe" (
    set "PY=%~dp0runtime\python.exe"
    goto run
  )
  ```
- **现场体验**：
  - 目标电脑**完全无需安装 Python**；
  - **不需要管理员权限**；
  - **不需要配置任何系统环境变量 (PATH)**；
  - 插上 U 盘或拷贝项目文件夹后，双击 `start.bat` 即可开箱即用。

### 方案 2：独立运行目录（PyInstaller `--onedir` 免安装文件夹）
- **机制**：在有开发环境的机器上，运行 `build_exe.bat`（采用 `--onedir` 模式），打包生成 `dist/TIAWebTwin/` 文件夹。
- **注意**：Windows 11 24H2 严禁分发 `--onefile`（会拦截解压到临时目录导致 `Could not create temporary directory!`），必须分发包含二进制的完整目录。
- **现场体验**：双击 `dist/TIAWebTwin/TIAWebTwin.exe` 即可启动，现场完全看不到 `.py` 文件。

### 方案 3：B/S 纯客户端访问（车间平板 / 手机 / 远程工位）
- **机制**：现场只需要一台连着 PLC 的工控机启动网关服务（无论是便携版还是系统 Python）。
- **现场体验**：
  - 班长、操作工手持的 iPad、安卓平板、触摸屏或办公室电脑，**连批处理脚本都不用跑，电脑上任何东西都不用装**；
  - 只需打开系统自带的 Edge/Chrome 浏览器，输入：
    `http://[工控机IP]:8000/?ws=ws%3A%2F%2F[工控机IP]%3A8765%2Fws`
  - 即可随时随地进行 3D 监控与交互。

## C. 关于 Windows 单文件 exe 的安全限制说明 (Win11 24H2)

> [!WARNING]
> **Windows 11 24H2 安全机制限制（Smart App Control / Temp 目录拦截）**：
> PyInstaller 默认的单文件模式（`--onefile`）在运行时必须向系统 `%TEMP%` 临时目录动态解压二进制文件。在 Windows 11 24H2 下会触发 `Could not create temporary directory!` 的安全拦截。
> 因此：
> 1. **严禁在 Windows 11 上向用户分发 `--onefile` 单文件 exe！**
> 2. 交付首选 **`start.bat`**（支持 `./runtime/` 绿色运行环境）或 **`make_shortcut.bat` 桌面图标**。
> 3. 若必须打包成可执行文件分发给无 Python 的电脑，在 `tia_twin.spec` 中必须使用 `--onedir`（便携文件夹免解压模式），打包出整个目录分发，不得依赖单文件 Temp 释放。

## D. Windows 服务 / 远端网页（浏览器在另一台机器 / 车间平板）

适用于“网页在另一台电脑，网关常驻 PLC 所在工控机”：

1. 在工控机双击 `start_silent.bat`，或把 `run_twin.py --no-browser` 注册为 Windows 服务开机自启。
2. 局域网内的任何电脑或车间平板，直接在浏览器输入：
   `http://[工控机局域网IP]:8000/?ws=ws%3A%2F%2F[工控机局域网IP]%3A8765%2Fws`
3. 页面在线模式选择目标 PLC 即可实时监视。
4. 网关必须设置 Token，限制防火墙来源；不要暴露到公网。

## 不能做的事

- 不能靠网页静默安装/启动 Python 网关；
- 不能从浏览器直连 TCP 102/S7comm；
- 不要把 8765 无 Token 暴露到公网；
- 严禁在非系统盘创建跨盘符 `.venv`（会导致 `_ctypes.pyd` DLL 初始化失败）；
- 严禁使用 `.vbs` 脚本（Win11 24H2 已彻底废除 VBScript 引擎）。
