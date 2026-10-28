# 任务 0 基线证据

- `host-info-excerpt.txt`：用户提供的主机终端输出节选。
- `fsync-bench.txt`：用户提供的连续三次 fsync 基准输出，数值原样保留。
- `versions.txt`：本次连接服务器核对的仓库地址和工具版本。

本目录为任务 0 的手工记录，不是 `scripts/run.sh` 生成的分阶段压测目录，不包含 `steps.csv`、`red.csv` 或 `use.csv`。已补充空载及 fsync 负载期间的 vmstat、iostat 终端转录，来源和采样限制见下文。

## 资源工具观测

- `vmstat-idle.txt`、`vmstat-fsync.txt`：用户提供的两种状态下的输出，数据行原样保留；负载片段复用空载片段的列头。
- `iostat-idle.txt`、`iostat-fsync.txt`：用户提供的两种状态下的输出，数据行原样保留，仅合并重复表头与空行。
- 具体取样行、单位和局限见 `LAB2.md` 第 2 节。文件中不含时间戳，不虚构观测时长或测试命令。

## 完整观测附件（本次更新）

- `vmstat-full.txt`、`iostat-full.txt`：用户提供的完整附件，按原始字节保存，保留表头、重复表头和空行。
- `LAB2.md` 第 2 节现以完整附件为主要依据：空载均取第 2～11 条数据；fsync 稳定段分别取 vmstat 第 50～54 条、iostat 第 39～43 条 vda 数据。
- 旧的四份节选文件保留以便追溯，空载片段不足的旧说明已由完整记录补足。
