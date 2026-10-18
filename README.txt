Machine Mapping：机械扫描批量处理试点

完整讨论进度、自动化方案、验收标准和待办见 PROGRESS.txt。
首次接手先读 HANDOFF.txt；仓库后续每次提交须遵循 AGENTS.md 的交接要求。
当前版本只实现预检；Igor 一键加载、标注、处理、拼图和保存入口尚待开发。

当前实现：Igor 原生导出的参数表和 IBW -> 明确指定 CUT 顺序 ->
按起始 theta 与步长生成预览 -> 核对已有角度、备注、数据网格和积分范围。
当前工具只预检，不覆盖 Igor 中的角度，不执行动量转换或科学拟合。

运行目录：C:\Users\Administrator\Documents\pROCESS\Machine Mapping
依赖：requirements.txt，已验证 Python 3.9 / igor2 0.5.12 / numpy 1.26.4。
新环境安装：python -m pip install -r requirements.txt（先核对所用 Python 环境）。
有本地试点导出后，可运行 python tools\verify_pilot.py，检查当前预检及确认保护。
Igor 导出步骤和原生命令见 pilot/export_commands.igor.txt。

本次复现命令（PowerShell 单行）：
python src\prepare_mapping.py --table pilot\exports\original_parameters.tsv --exports pilot\exports --cuts A20211118121854 A20211118123854 A20211118130449 A20211118133047 A20211118135051 A20211118141230 --start 0 --step -3 --energy-window -0.01 0.01 --resolutions pilot\angle_confirmation.json --output pilot\results

输入来自正在运行的 FeSe20211118_JJJ 实验的 Igor 原生 Save/J/W 和 Save/C。
完整磁盘 PXP 的备份位于 pilot/input；原始参数表和 12 个 IBW 位于 pilot/exports。
上述本地实验数据与派生结果已通过 .gitignore 排除，不应作为代码推送。

输出：
  pilot/results/angle_preview.tsv：逐 CUT 角度对照表，保留原行号、原备注。
  pilot/results/audit.json：Wave 的哈希、维度、坐标、数值统计、完整 Note 和异常。
  pilot/review.txt：本次已核验结果及下一步边界。
  pilot/angle_confirmation.json：用户确认的角度与依据，绑定当前参数表 SHA256。
  指定 --resolutions 后，已确认的备注冲突进入 resolved_issues，原备注仍保留。
  参数表改变或确认值不匹配时拒绝复用确认；其他错误仍正常报告。

使用边界：
1. --cuts 明确表示采集顺序，程序不会偷偷按文件名、表行或 theta 排序。
2. --start/--step 是显式给定的扫描规则，不能证明实际采集角度。
3. FineMapping 备注最后一项仅作为本次试点的角度候选；其他格式不能照搬。
4. 非等步长扫描应使用明确角度清单，当前版本尚未实现。
5. ProcessFlag 只能辅助分组，不能单独证明一组 CUT 属于同一扫描。
6. 预检完成不等于物理标定完成；ready_for_scientific_mapping 始终保持 false。

后续接入路线：
按文件标识匹配加载数据 -> 预览并解决角度冲突 -> 备份角度表 -> 批量赋值 ->
复用已核验的 Process/GetFS 路径 -> 验证输出网格、覆盖范围和数值 -> 保存新实验。
开始处理新实验前，还需核实机械 theta 的记录来源、几何、能量零点和积分窗口。
