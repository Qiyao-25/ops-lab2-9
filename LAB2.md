# 实验 2 记录：第 9 组

评分时依据本文件和 `runs/` 中的原始数据核对。本文件中的每一个数值，都须能在某个 `runs/<名字>/` 的文件中找到：表格用 `scripts/table.sh` 生成后粘贴，其他数值注明出处（例如“`runs/r1-pool4/red.csv` 第 6 阶段”）。不要只贴截图。将 `<填写>` 替换为本组的内容。

第 4.1、4.4、5.1、5.3 节的预测须在对应的测量之前写好，写好后不要修改。预测错误不扣分，与实测不一致之处在分析中讨论。

## 1. 基本信息

| 项 | 内容 |
|---|---|
| 小组 | 第 9 组 |
| 仓库地址 | <https://github.com/Qiyao-25/ops-lab2-9> |
| 主机 | KVM 云主机；2 vCPU，内存 3531 MiB；云厂商与规格名待补充 |
| CPU | x86_64，GenuineIntel，General Purpose Processor；2 vCPU（0、1）；CPU 0、1 的 SOCKET 均为 0，CORE 均为 0 |
| 内存 | `free -m`：total 3531 MiB，available 2894 MiB；Swap 0 MiB |
| 数据目录所在的盘 | `data/` 位于 `/dev/vda1`，ext4，挂载点 `/`；所属块设备 `vda`，容量 40 GB；非 tmpfs，云盘介质与规格待补充 |
| 操作系统与内核 | Ubuntu 24.04.4 LTS；Linux 6.8.0-136-generic |
| Go、Prometheus、node_exporter | Go 1.26.9 linux/amd64；Prometheus 3.13.4；node_exporter 1.12.1 |
| 分核 | enrolld：CPU 1（`taskset -c 1`）；loadgen、Prometheus、node_exporter：CPU 0（`GEN_CPUS=0`，启动时绑定 CPU 0） |

基本信息来源：`runs/task0-baseline/host-info-excerpt.txt`（用户提供的终端输出节选）；仓库地址和工具版本由本次服务器核对，见 `runs/task0-baseline/versions.txt`。

分核限制：虚拟机呈现的 CPU 0、1 具有相同的 SOCKET 和 CORE，`lscpu` 显示每核 2 个线程，因此无法按该拓扑将压测程序与服务分配到不同物理核。仍按指导书的 2 vCPU 方案绑定两个逻辑 CPU，但二者可能争用底层执行资源。虚拟机呈现的拓扑不一定代表宿主机的实际分配，分析结果时需说明这一限制。

## 2. 任务 0：基线

`bin/enrolld -bench-fsync 2000` 连续运行三次的输出：

```text
fsync 次数 2000，总耗时 2.56 s，数据目录 data
fsync 耗时（毫秒）：mean 1.274  p50 1.218  p90 1.401  p99 2.554  max 10.680
按平均值推算，一个写者串行 fsync 每秒最多约 785 次（= 1000 / 1.274）
fsync 次数 2000，总耗时 2.61 s，数据目录 data
fsync 耗时（毫秒）：mean 1.300  p50 1.229  p90 1.452  p99 2.553  max 8.828
按平均值推算，一个写者串行 fsync 每秒最多约 769 次（= 1000 / 1.300）
fsync 次数 2000，总耗时 2.54 s，数据目录 data
fsync 耗时（毫秒）：mean 1.265  p50 1.206  p90 1.412  p99 2.468  max 5.339
按平均值推算，一个写者串行 fsync 每秒最多约 790 次（= 1000 / 1.265）
```

按平均值计算，三次分别约为 785、769、790 次/秒。三次各测试 2000 次，平均耗时的算术平均为 `(1.274 + 1.300 + 1.265) / 3 = 1.279667 ms`，据此单个写者串行 fsync 每秒最多约 **781 次**（`1000 / 1.279667`）。三次平均耗时范围为 1.265～1.300 ms，最大差值为 0.035 ms，相对于最小值约为 2.77%；输出的串行上限范围为 769～790 次/秒，相差 21 次/秒。上述上限只是基于 fsync 基线的推算，实际服务吞吐还包含 HTTP 处理、排队和运行时等开销。

数据来源：`runs/task0-baseline/fsync-bench.txt`，为用户提供的三次终端输出转录，未重新运行测试，也未修改测量数值。

空载和运行 fsync 测试时各工具的读数（各观察 5 秒以上，填写典型值）：

| 工具与列 | 空载 | 运行 `-bench-fsync` 时 | 该列的含义 |
|---|---|---|---|
| `vmstat -w 1`：r、b | r = 0，b = 0 | r = 0，b = 1 | r：运行或等待 CPU 的任务数；b：不可中断睡眠的任务数，常见于等待 I/O |
| `vmstat -w 1`：us、sy、id、wa、st | us = 0～1%，sy = 0～1%，id = 99～100%，wa = 0%，st = 0% | us = 0～1%，sy = 2～4%，id = 49～51%，wa = 47%，st = 0% | us：用户态 CPU 时间；sy：内核态 CPU 时间；id：空闲时间；wa：有未完成磁盘 I/O 时的 CPU 空闲时间；st：虚拟机被宿主机占走的 CPU 时间；均为全机汇总比例 |
| `iostat -dx 1 vda`：w/s、wkB/s | w/s = 0～12，wkB/s = 0～116；多数样本接近 0 | w/s = 2336～2412，wkB/s = 12748～13132 | 每秒完成的设备写请求数、每秒写入的 KiB；包含文件系统与系统后台写入，不等于应用记录数 |
| `iostat -dx 1 vda`：w_await、f/s、f_await | w_await = 0～1.00 ms，f/s = 0～2，f_await = 0～0.50 ms | w_await = 0.40～0.41 ms，f/s = 1556～1602，f_await = 0.04 ms | w_await：写请求平均耗时（含排队）；f/s：每秒 flush 请求数；f_await：flush 请求平均耗时（含排队）；无对应请求时显示 0 不代表一次实际请求耗时为 0 |
| `iostat -dx 1 vda`：aqu-sz、%util | aqu-sz = 0.00～0.01，%util = 0～0.10% | aqu-sz = 1.02～1.04，%util = 95.80～96.80% | aqu-sz：平均未完成 I/O 请求数（包括排队及处理中的请求）；%util：采样期间设备存在未完成 I/O 的时间比例 |

运行 fsync 测试时，CPU **不繁忙**。稳定采样中 `us + sy` 为 2%～5%，`r = 0`，没有明显的 CPU 排队；`wa = 47%` 表示存在 I/O 等待，并不表示 CPU 用了 47% 的时间执行计算。`b` 从空载的 0 变成 1，说明存在不可中断睡眠的任务。结合测试场景，可判断基准程序主要在等待磁盘同步完成。

磁盘侧的证据是：`aqu-sz` 从空载的 0.00～0.01 上升到 1.02～1.04，`%util` 从 0～0.10% 上升到 95.80～96.80%，并持续有 2336～2412 次/秒的写请求与 1556～1602 次/秒的 flush 请求。`w_await = 0.40～0.41 ms`、`f_await = 0.04 ms` 是设备请求的平均耗时，不能直接当作应用每次 fsync 的耗时；一次 fsync 可能涉及多个底层 I/O。空载的少量后台写入也会产生非零 await，因此不能仅凭某个 await 的大小比较两种状态。

这些读数支持“串行同步写过程中，CPU 大部分时间没有执行计算，程序在等待 I/O”的判断。`aqu-sz` 包含正在处理的请求，不能直接解读为约 1 个请求在排队；`%util` 接近 100% 也不能单独证明设备已达到吞吐上限，容量判断留待后续写路径分阶段压测。

采样出处与选择：

- 完整输出保存在 `runs/task0-baseline/vmstat-full.txt` 和 `runs/task0-baseline/iostat-full.txt`，分别含 84 条 vmstat 数据和 67 条 vda 数据。两个工具均排除第 1 条开机以来平均值；重复表头不重新计数，也不代表程序重启。
- 空载基线：两个文件均使用第 2～11 条数据，即排除首组后的连续 10 个一秒采样区间。vmstat 对应文件第 4～13 行；iostat 对应文件第 8～44 行中的 10 条 vda 数据。两者分别从各自的监控启动后取样，不假定它们的起始时刻相同。
- fsync 稳定段：vmstat 使用第 50～54 条数据（文件第 54～58 行），iostat 使用第 39～43 条 vda 数据（文件第 156～172 行中的 5 条 vda 数据），各为连续 5 个一秒采样区间。排除负载开始和结束时只覆盖部分测试时间的过渡样本，以及测试结束后的空载样本。
- 表中为所选区间的取值范围，各列上下界不一定来自同一秒。两个完整文件按附件原始字节保存，未改动数据、空行或表头；旧的四份观测节选也保留，用于追溯此前记录。

记录说明：完整输出已包含足够的空载观测，空载取样满足连续 10 秒，原先仅凭节选无法核验观测时长的问题已消除。两种工具未附逐秒时间戳，不能保证逐行对应；负载稳定段各为 5 秒，不将开始前或结束后的样本算作 fsync 运行时间。基准命令及其最终输出未随这两份观测附件提供，因此不据此反推测试次数或应用 fsync 吞吐。这些文件是用户提供的终端输出附件，不是 `scripts/run.sh` 的分阶段压测输出。

## 3. 任务 1：指标流水线

两个抓取目标的状态（`curl -s 127.0.0.1:9090/api/v1/targets` 中两处 `"health"` 的值）：<填写>

本组编写的四条查询（与 `deploy/queries-red.txt` 一致）：

```text
server_rps          <填写>
server_error_rate   <填写>
server_p99_ms       <填写>
server_slo_good     <填写>
```

`runs/t1-light` 的数据（`scripts/table.sh runs/t1-light ok_rps mean_ms p99_ms server_rps server_mean_ms server_p99_ms cpu_ms_per_req db_query_mean_ms`）：

<粘贴表格>

从这次实验读出：每次查询实际占用连接 <填写> ms（`db_query_mean_ms`）；每个请求消耗的 CPU <填写> ms（`cpu_ms_per_req`，取 100 请求/秒的阶段）。

## 4. 任务 2：读路径

### 4.1 预测（R1 之前写）

| 资源 | 容量 | 每个请求占用（数据来源） | 推算的上限（请求/秒） |
|---|---|---|---|
| 连接池 | <`-pool`> 个连接 | <填写> ms | <填写> |
| CPU | enrolld 的 <填写> 个核 | <填写> ms | <填写> |

先达到上限的是：<填写>。预计从多少请求/秒起，客户端 p99 超过 50 ms：<填写>，理由：<填写>

R1 的到达率（`scripts/rates.sh <较小的上限>` 的输出）：<填写>

### 4.2 R1：`-pool 4`

`scripts/table.sh runs/r1-<…> ok_rps error_rate p99_ms server_p99_ms server_mean_ms inflight_avg cpu_ms_per_req pool_in_use_avg pool_wait_p99_ms sched_wait_p99_ms svc_cpu_busy procs_running_avg`：

<粘贴表格>

最大吞吐量 <填写> 请求/秒，出现在第 <填写> 阶段；客户端 p99 首次超过 50 ms 是在第 <填写> 阶段（<填写> 请求/秒）。

### 4.3 CPU 消耗在何处

在约 0.8 倍上限的负载下采集 20 秒 CPU 剖析，`go tool pprof -top` 的前 10 行（同时保存在 `runs/<填写>/pprof-top.txt`）：

```text
<粘贴>
```

`main.spin` 占 <填写>%；按本次的吞吐量和 enrolld 消耗的 CPU 计算，每个请求 <填写> ms，其中 spin 约 <填写> ms，其余 <填写> ms 消耗在：<填写>

### 4.4 R2：调大连接池（预测在 R2 之前写）

| 项 | 值与算法 |
|---|---|
| 每个请求占用的 CPU（取 R1 哪一阶段的 `cpu_ms_per_req`，选取理由） | <填写> |
| 推算的 CPU 上限 C | <填写> |
| R2 的池大小 P2 = ceil(2 × C × 每次查询的秒数) | <填写> |
| R2 的到达率（`scripts/rates.sh C 0.3 0.6 0.8 0.9 1.0 1.1 1.25 1.5`） | <填写> |
| 预测：R2 中先达到上限的是 | <填写> |

`scripts/table.sh runs/r2-<…> ok_rps error_rate p99_ms server_p99_ms inflight_avg cpu_cores cpu_ms_per_req cpu_wait_threads sched_wait_p99_ms pool_in_use_avg svc_cpu_busy procs_running_avg cpu_psi_some`：

<粘贴表格>

最大吞吐量 <填写> 请求/秒；与预测的 C 相差：<填写>

## 5. 任务 3：写路径

### 5.1 预测：`-sync each`（W1 之前写）

| 项 | 值与算法 |
|---|---|
| fsync 平均耗时（任务 0） | <填写> ms |
| 推算的最大 TPS | <填写> |
| 达到上限时 enrolld 大约使用几个核（写路径没有 spin，按 4.3 节拆分出的“spin 以外的开销”估计每个写请求的 CPU） | <填写> |
| W1 的到达率（`scripts/rates.sh <最大 TPS> 0.2 0.4 0.6 0.8 0.9 1.0 1.1 1.2`） | <填写> |

### 5.2 W1：`-sync each`

`scripts/table.sh runs/w1-<…> ok_rps error_rate p99_ms server_p99_ms cpu_cores fsync_per_s fsync_mean_ms batch_mean svc_cpu_busy cpu_iowait disk_w_per_s disk_w_await_ms disk_f_per_s disk_f_await_ms disk_aqu_sz disk_util`：

<粘贴表格>

### 5.3 预测：`-sync group`（W2 之前写）

在 W1 达到上限时的到达率下，改为组提交后：吞吐量 <填写>；平均每次 fsync 处理 <填写> 条记录；客户端 p99 约 <填写>。理由：<填写>

W2 的到达率：<填写>

### 5.4 W2：`-sync group`

（列与 5.2 相同）

<粘贴表格>

### 5.5 W3：`-sync interval`

（列与 5.2 相同）

<粘贴表格>

## 6. 分析问题

每题先列出所用数据（引用上面的表或 `runs/` 中的文件），再写结论，并说明结论的成立条件。每题 300～600 字。

**问题 1：上限由什么决定。** 按 L-07 第 25 页资源账的格式，为 enrolld 的读路径编制一份资源账：资源、每个请求占用（实测）、容量、推算的上限、实测的最大吞吐量、饱和观测项。预测与实测相差多少，差异来自何处？`cpu_ms_per_req` 随负载如何变化，原因是什么？这对“在低负载下测量每请求开销，再推算上限”的做法意味着什么？`db_query_mean_ms` 为什么大于 `-db-ms`？以“p99 ≤ 50 ms”为目标，R1 能承受的最大阶段相当于上限的多少比例？与 L-07 第 6 页“容量 = 上限 × 0.7”比较，为什么尚未达到上限延迟就已上升？R2 调大连接池后，瓶颈转移到了哪个资源？

<填写>

**问题 2：利用率不等于饱和。** R1 达到上限时，enrolld 所在核的 CPU 利用率是多少？哪个数值最先表明资源已经饱和？R2 中 CPU 利用率接近 100% 时，内核层的 `procs_running_avg`、`cpu_psi_some`、`cpu_wait_threads` 和 Go 运行时层的 `sched_wait_p99_ms` 分别如何变化？为什么内核层几乎观察不到排队，排队发生在哪里？这与 L-06 第 16、17 页 Tomcat 的线程池有何相同之处？最后用 Little's Law 核对：从 R1 选取三个阶段，用 `server_rps × server_mean_ms` 计算在途请求数，并与 `inflight_avg` 比较；W 为什么必须用平均值而不能用 p99？哪个阶段不一致，原因是什么？

<填写>

**问题 3：持久性以延迟为代价。** W1 实测的最大 TPS 与 1000 ÷ fsync 平均耗时相比如何？W1 达到上限时 CPU、内存、磁盘的指标各是多少，哪几列表明磁盘饱和？应用测得的 `fsync_mean_ms` 与 `disk_w_await_ms`、`disk_f_await_ms` 为什么不同？一次 fsync 大约对应几次写和几次 flush？W1 与 W2 在 `disk_util` 相近时吞吐量相差多少，`%util` 接近 100% 能否说明磁盘已经饱和？组提交的 `batch_mean` 如何随负载变化，低负载时是否有收益，本组的预测是否正确？W3 快了多少，代价是什么？选课记录应采用哪一种方式，在什么条件下 interval 可以接受？

<填写>

**问题 4：延迟数值的测量位置与方法。** 同一阶段中，客户端与服务端的平均值、p99 各相差多少？列出只计入客户端的时间组成。找出一个服务端 p99 大于客户端 p99 的阶段，并解释原因（L-08 第 10 页）。比较服务端的 `server_slo_good` 与客户端的 `slo_good`；若存在过载阶段，二者为何相差很大？SLI 应在何处测量（L-08 第 19 页）？用 R1 的 `steps.csv`，将各阶段的 p99 求平均，与 `all` 行的 p99 比较，说明百分位数为什么不能平均，以及正确的合并方法。最后计算错误预算：SLO 为“30 天内 99% 的读请求在 50 ms 内成功返回”，若 R1 中第一个不达标阶段的负载持续下去，燃烧率是多少，30 天的预算多久耗尽（L-08 第 21 页）？

<填写>

## 7. 选做记录

| 选做 | 完成情况与证据 |
|---|---|
| O1 内存与 GC | <未做 / 预测、`runs/` 目录、结论> |
| O2 网络 | <未做 / 两台主机的规格与拓扑、`runs/` 或日志、结论> |
| O3 告警与看板 | <未做 / 规则文件、触发记录、看板说明> |
| O4 迁移到小组项目 | <未做 / 仓库链接、测了哪个资源、结论> |

## 8. 成员分工

每位成员一行，只填写 GitHub 用户名，无需填写姓名；行数应与小组人数一致。

| GitHub 用户名 | 负责的部分 |
|---|---|
| <用户名> | <填写> |
