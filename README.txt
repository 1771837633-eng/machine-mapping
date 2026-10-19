Machine Mapping：独立实验记录面板与Igor机械mapping试点

无需GitHub的共享目录接手：先读“首先阅读_接手说明.txt”。
python tools/prepare_local_handoff.py可生成固定版本源码/文档、SQLite在线备份、JSON和哈希清单，
最新检查点见local/handoff/LATEST.txt；数据依赖留在项目原位，不保存Igor内存科学结果。
新电脑用独立的--db及--bridge-dir，桥生成脚本的--directory必须与--bridge-dir一致。
不要让两台电脑同时写同一SQLite或共用连接文件。第二台电脑端到端运行尚未验收。

先读HANDOFF.txt；当前精确验收与输入/源码SHA256见pilot/mapping_validation.json。
已跑通：记录面板 -> 已有64位Igor -> PXP内六条处理CUT -> 费米面及I(E,kx,ky) ->
真实完成/失败回执。FeSe实际输出201×121×81，源CUT的CRC不变。
当前只覆盖已有处理后CUT，不包含新采集原始文件的自动加载/预处理。
物理定标与人工科学结果对照尚未完成，不能把插值网格当成实验分辨率。

启动（项目根，Python3.9+，运行只需标准库）：
python -m app.server --port 8766
http://127.0.0.1:8766/
默认local/notebook.sqlite3。Windows可双击start_notebook.cmd，PATH需有Python。
仅监听127.0.0.1，未知端口占用先查来源，不自动结束服务。

试点数据（不在Git）：
由用户从D:/SynologyDrive/SJJiang/SynologyDrive/DATA_FeSe_Jiajunjie/FeSe20211118_JJJ.pxp
复制到pilot/input/FeSe20211118_JJJ_current.pxp，核对SHA256：
81dd8282998b672c9c4d5aaf24e19098f3e9826eaefdad60d87184fa1b61d5da
python tools/seed_trial.py --pxp "pilot/input/FeSe20211118_JJJ_current.pxp"
python -m app.server --port 8766 --db local/trial-notebook.sqlite3
seed不覆盖已有记录，只填六条已确认身份/theta/hv，未知条件留空。
试点库另有一条明确“非实验数据”的界面QA记录，不属于FeSe实验条件。
无用户数据时仍可运行Python测试和Igor模型自检，不能复现实验图。

连接用户选定、已经打开的64位Igor（不启动另一个，不修改原源程序）：
python tools/prepare_notebook_bridge.py
把打印的LoadWave/T命令在该Igor命令区执行一次，面板应显示“已连接”。
若已经连接，无需重做。它加载项目中的MMMomentum.ipf和MMNotebookBridge.ipf，
在独立模块MMMapping中编译，未编辑原ARPES库include或安装目录。
每个新实验/新会话需按实际状态重新连接；当前试验不保存Igor实验。
启动脚本只准备连接命令，不自动操纵Igor。
旧--igor参数保留兼容配置，不用于启动程序；实际目标由在哪个会话加载模块决定。
tools/igor_command.py的历史/X接口没有可靠路由验收，不再作为面板执行路径。

操作：
任意实验类型均可记录、编辑、沿用条件、筛选和导出Excel。
面板仅在提交mapping时校验CUT、扫描组、顺序、theta、角度来源、固定hv及PXP路径。
phi可填0或留空，omega留空；Polar/Tilt/Azimuth保留原记录，不默认转换到Igor角度。
在机械mapping页确认本组采集结束、选择积分窗口/插值网格后提交。
±5meV仅技术初值；超过源能量范围会拒绝处理。插值网格不提高实验采样分辨率。
完成显示实际回执及内存结果位置。未测动量留NaN，三维轴为E/eV、kx/pi/a、ky/pi/a，无kz。
失败不妨碍普通记录/导出；180秒未回执显示未确认，不能当完成，也不盲目重复运行。
结果只在Igor内存，关闭/重开实验会丢失；历史回执不等于当前仍有Wave。
当前没有科学结果保存、原模板导入或原版式往返。

Excel导出保存全部记录（含34字段+ID/Created/Updated，共37列）及公共实验条件两张表。
空白不补零，文本不当公式。保留原模板22字段；能量步长与马达步长分开。
HTTP导出已用openpyxl独立检查；未做原生Excel版面验收，原模板未修改。

验证：
python -m unittest discover -s tests -v
node --check app/static/app.js
Igor人工模型：加载项目igor/MMMappingSelfTest.ipf并编译，
MMMapping#MM_SelfTest("一个未用过的标准名称")
应见MM_SELFTEST_PASS；不需要FeSe数据，不会改原库。
实际科学试点数值/失败实例/边界见pilot/review.txt与mapping_validation.json。

local/、pilot/input/、pilot/exports/、pilot/results/均忽略，不提交原始实验、数据库、截图或回执。
克隆缺用户PXP和历史导出时，不能重放对应实验验收。
旧ARPES库兼容性工作独立保留于igor/compatibility/README.txt，不是本轮mapping依赖，
缺失BCS依赖/额外实例冷启动未验收；用户最新要求不改原库，后续不得自动恢复该工作线。
