旧 ARPES 过程库兼容性修复记录
更新：2026-10-19，Asia/Shanghai

历史工作线说明：下文是早前C盘实例的隔离修复记录，不是当前mapping的依赖或运行指令。
用户随后明确要求只用后台已有64位Igor、不改原Igor源程序。当前mapping使用D盘实例和
项目MMMapping独立模块，已取得内存试点回执，详见根目录HANDOFF.txt。
保留这些构建/诊断工具用于溯源；不能据下文旧复现步骤自行启动实例或恢复原库修复。

后续32位对照证据
用户自行打开32位Igor并指出可以运行。智能体只读观察确认窗口标题Igor Pro 9.05 32-bit，
00BXJZHERS_SES2002.ipf已加载，IOP_ARPES/ARPESPanel/3D菜单可见，过程窗无Compile按钮。
进程路径C:\Program Files\WaveMetrics\Igor Pro 9 Folder\IgorBinaries_Win32\Igor.exe。
没有在该32位窗口输入命令、改代码或处理实验；还没捕获其实际加载的源码/函数依赖。
因此不能断定两边加载的版本完全相同，也不能断定必有32位专用XOP。检查到的常用扩展
目录未见XOP文件。下文BCS缺失结论属于被检查的64位会话/磁盘源码搜索范围。
用户按Esc中断界面自动操作后，本轮仅做上述只读观察，保留32位现场作为对照基线。

范围和事实
用户授权“你帮我改吧，运行下这个程序，然后解决所有报错”。截图入口为
00BXJZHERS_SES2002.ipf。本轮恢复旧库编译和启动检查；没有恢复 MMMomentum
科学试跑，没有加载/保存用户实验，没有改写任何安装目录或全局过程文件。

实际程序：C:\Program Files\WaveMetrics\Igor Pro 9 Folder\IgorBinaries_x64\Igor64.exe
版本窗口：Igor Pro 9.05 64-bit。本轮未读取、填写或保存任何授权码。
D:\Applications\Igor Pro 9.0.5.1\Igor Pro 9 Folder 为旧安装/来源对照目录。

项目内已生成的可用修复入口：
local/igor-repair/runtime/MMR001_00BXJZHERS_SES2002.ipf
121个过程副本全部在local/igor-repair/runtime，文件名加MMR序号，引用改为精确
项目绝对路径。原库内同名文件、Jonathan/ Jonathan_old等不再影响修复副本选择。
Igor官方库的尖括号引用仍使用随Igor安装的原库。换位置需重新运行构建脚本。
入口生成副本来自现场实际加载的过程文本，不能说全部来自某个同名磁盘文件。

备份与可复核来源
local/igor-repair/session-before/procedure-list.txt：现场加载的122个过程标题。
同目录names.json和000.ipf至121.ipf：用ProcedureText导出的UTF-8缓冲区；
包括用户未保存的JEG_ReverseLegacy/JEG_ConcatenateLegacy改名；不是原文件字节备份。
Procedure主窗口为空，未作为运行库打包。其余121文件约7.16MB。
local/igor-repair/build-manifest.json：每个输入缓冲区与输出的SHA256对应。
本目录build-manifest.json保留本次验证版本的对应关系。
local/igor-repair/validation-history.txt：从Igor实际History读取的验证回执。
这些第三方库源码与现场备份不在Git；克隆后必须从用户本地库重新导出，或由
用户提供本轮local/igor-repair/session-before备份。缺少它不能重建本次精确版本。
原始PXP、实验数据和数据库均没有参与这次验证。

修复和依据
1. 保留用户将Reverse、Concatenate改名为JEG_*Legacy的修复，避免内置操作冲突。
2. FermiLevelFit_linearBackground的FitFL与EnergyCalibration的FitFL重复。
   仅将前者函数和proc=回调同步改为MMR_LinearBackgroundFitFL。
3. Image_Tool3/OffsetStack中的WAVE w=wn把字符串当作波引用。w没有后续使用，
   移除无效引用，保留其按trace名称构造ModifyGraph命令的行为。
4. 112_JXW_ARToFVisualization调用的wavefromlistbox/wavefromlistbox2是
   CommonFunction2里ModuleName=CmnFunc的static函数。补CmnFunc#限定。
5. LC_ARPESPROCESS_2020调用BCSEDC与BCSEDC_Direct，但当前加载库及检查过的
   C/D安装过程库没有其定义。没有猜测实现或静默返回假数据。
   两个WDS_convFunc_BCSfit函数使用条件编译保留原代码，缺依赖时进入立即Abort
   的明确提示路径，在创建/修改拟合Wave之前退出。两项拟合功能尚未恢复。
   补齐原作者函数/插件后必须重编译并独立验证，不能将这个保护当成拟合已修好。
6. 人工实测旧Reverse在x起点5、步长2时把[1,2,3]反转成[1,1,1]。
   原tmp(np-1-p)是按x坐标插值，改用free wave副本与[np-1-p]点索引；
   保留原波轴缩放，避免创建/覆盖root:tmp。

已执行验证
- 在另外启动的空白Igor实例载入修复入口；整套编译完成，无编译错误对话框，
  IOP ARPES/ARPESPanel等用户菜单实际出现。
- Load_SES2002_Data()创建ARPES_Analysis；FLfit()创建FitFermiLevel。
  两个窗口WinType均为7，已看过实际界面。
- selftest.ipf在真实Igor执行，通过倒序默认轴、非默认轴/轴缩放不变、空数组、
  拼接结果和输入不变、两面板存在、两缺失BCS依赖在改Wave前停止的断言。
- 最终实际History：
  MM_LEGACY_SELFTEST_PASS: reverse/default/scaled/empty; concatenate; two startup panels; missing BCS guards
- BCS保护测试会弹出明确Missing...信息，确认OK后try/catch继续；不是意外失败。
- 再用start_legacy_igor.cmd启动额外新实例时，进程标题出现License Activation Error，
  未出现可控制主窗口，冷启动未通过；未操作授权对话框，不能宣称启动器端到端验收。
  已有修复验证实例仍可运行。不要终止原用户实例。

复现
当前本机：优先使用已打开的修复实例。不要把新旧两套库同时打开在同一实验。
手工恢复时，在一个单独空白Igor实例中执行：
OpenProc "D:SynologyDrive:SJJiang:SynologyDrive:codex:machine mapping:local:igor-repair:runtime:MMR001_00BXJZHERS_SES2002.ipf"
点击Compile，再执行Load_SES2002_Data()和FLfit()。
OpenProc "D:SynologyDrive:SJJiang:SynologyDrive:codex:machine mapping:igor:compatibility:selftest.ipf"
点击Compile，执行MMRepairSelfTest()；确认两条预期Missing BCS提示。

源码重建（Python标准库）：
python tools/build_igor_compatibility.py
从session-before快照重新生成运行库、精确引用、manifest及launch.itx。
仅新目录缺快照时，先在目标Igor现场导出过程清单，再运行：
python tools/capture_igor_procedures.py --directory local/igor-repair/session-before
它仅生成capture.itx，必须在原目标Igor执行LoadWave/T该文件，并确认
MM_CAPTURE_COMPLETE及所有编号源码文件实际存在，再运行构建脚本。
清单导出须先将WinList("*",";","WIN:128")赋给字符串变量，FBinWrite只接受
变量/波，不可直接把WinList表达式放入FBinWrite。Open输出路径使用D:Folder，
不能把Windows路径直接替换成D::Folder。此两项临时导出错误已实际纠正。
本轮/X导出没有取得文件回执，已停止使用；改用Igor原生ITX执行并核对完成标记。

启动器
start_legacy_igor.cmd使用已安装Igor，/I创建单独实例，不使用/N或关闭旧实验。
默认C盘Igor路径，可设置IGOR_LEGACY_EXE。local/igor-repair/launch.itx由构建脚本
生成，安排编译、两个面板启动并打印MM_LEGACY_STARTUP_READY；冷启动的授权问题
需要用户处理。不要因验证入口已准备就说冷启动通过。

剩余边界
尚无BCS两个依赖；未遍历约2600个函数的全部按钮、文件格式、参数及运行分支。
没有做真实数据加载、拟合数值、动量转换、端到端处理、科学精度或保存验证。
面板内原代码带有历史示例名称/零初值，不是本次实验条件。
下一步：用户补BCS来源及处理Igor冷启动授权；针对具体数据和工作流逐项验收。
