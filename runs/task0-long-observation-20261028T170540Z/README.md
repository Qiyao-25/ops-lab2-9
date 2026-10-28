# 任务 0：补充云配置及连续 10 秒观测

`console-config.txt` 为已登录华为云控制台读取的非敏感配置字段；`cloud-selected.json` 为实例元数据的白名单字段。不保存账号、资源 ID、完整元数据或地址。

`vmstat.log`、`iostat.log` 和 `bench.txt` 为本次程序输出；`observation.json` 保存命令和执行时序；两个 `*-timing.jsonl` 逐行记录原始文本和接收时间。日志文件未手工修改。

`selected-samples.csv` 为派生取样索引，空载与负载各取连续 10 个一秒区间。完整分析见 `LAB2.md` 第 2 节。原始三次 2000 次 fsync 基线仍在 `runs/task0-baseline/`。

本目录是任务 0 的基准观测记录，不是 `scripts/run.sh` 的分阶段压测输出。
