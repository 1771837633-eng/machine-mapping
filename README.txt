Machine Mapping：独立实验记录面板与 Igor 处理试点

接手先读HANDOFF.txt，项目规则见AGENTS.md，阶段状态见PROGRESS.txt。
当前已有独立记录面板、SQLite持久化、Excel导出、扫描分组和Igor任务发送原型。
Igor/MMMomentum.ipf尚未验证编译/科学结果，完整自动化没有交付。
用户正在自行处理Igor Demo/授权，明确恢复后才继续Igor操作。

普通记录面板（项目根，Python3.9+，只用标准库）：
python -m app.server --port 8766
打开http://127.0.0.1:8766/，默认local/notebook.sqlite3。
Windows也可用start_notebook.cmd，PATH中需有Python。
不需要安装requirements.txt；可用--db和--igor配置实际数据库/Igor64.exe路径。
仅绑定127.0.0.1；端口占用时另选--port，不终止未知服务。

所有实验类型可正常记录、编辑、沿用条件、筛选；仅提交mapping时校验扫描条件。
Excel导出已保存的逐条记录和公共实验条件，分为“实验记录”“实验条件”两表。
保留模板22个原字段，扩展扫描组/顺序/明确Igor角度等，总34字段。
空白不补零；位置/真空单位在公共条件填写；Polar/Tilt/Azimuth不默认映射Igor角度。
当前没有原Excel模板导入/原版式往返。

重建本次试点（需用户本地数据，数据不进Git）：
python tools/seed_trial.py --pxp "pilot/input/FeSe20211118_JJJ_current.pxp"
python -m app.server --port 8766 --db local/trial-notebook.sqlite3
seed只生成六条已核对身份/角度/hv，未知温度等留空；已有记录时拒绝重复填充。
本机界面验证另有一条“非实验数据”记录，不是FeSe实验条件。
默认--igor适用于本轮电脑；换机应显式指定Igor64.exe完整路径。

Igor内存原型：
igor/MMMomentum.ipf计划从已有处理后CUT生成I(E,kx,ky)、Coverage和积分图。
固定hv/零偏压/共同phi，k单位pi/a，不考虑kz；未测区域保留NaN。
±5meV仅为技术试跑初值，不是科学窗口确认。
只读加载隔离副本和参数查询已实际成功，带引号/X加载程序曾出错；
修改后的桥和IPF编译都未成功核验，没有新的科学输出。
当前任务状态“已发送”不表示计算通过；无自动结果回读、重复运行保护等。
原始新采集文件加载/预处理、角度回写和保存尚未实现。
本轮用户要求仅尝试内存计算，代码没有Igor保存操作。

测试：
python -m unittest discover -s tests -v
node --check app/static/app.js
五组Python行为测试通过（Igor连接失败隔离用mock，不验证科学转换）。
Excel导出已用独立读取器检查字段、数值类型和中文，未做原生Excel版面验证。

历史只读预检（与面板依赖分开）：
requirements.txt固定igor2==0.5.12、numpy==1.26.4，原验证Python3.9。
src/prepare_mapping.py读取Igor原生导出的TSV/IBW，检查角度、网格和积分范围，
不修改Igor或执行动量转换。导出步骤见pilot/export_commands.igor.txt。
本轮电脑缺少历史导出，不能重放python tools/verify_pilot.py。

历史命令：
python src/prepare_mapping.py --table pilot/exports/original_parameters.tsv --exports pilot/exports --cuts A20211118121854 A20211118123854 A20211118130449 A20211118133047 A20211118135051 A20211118141230 --start 0 --step -3 --energy-window -0.01 0.01 --resolutions pilot/angle_confirmation.json --output pilot/results

历史确认绑定精确表哈希，新PXP与旧副本不同；禁止为消除错误直接改确认哈希。
完整新旧路径、哈希、事实和接续步骤见HANDOFF.txt。
local/、pilot/input/、pilot/exports/、pilot/results/被忽略，不提交实验数据、数据库、
截图、测试导出、凭据或授权信息；代码、测试和交接记录进Git。
