# O2 两机网络实验

`prediction.md` 是在本轮测量前提交的预测，保持原样。`results.md` 为测后表格与分析；完整正文也写入根目录 `LAB2.md`。

原始文件：A 的 `enrolld.log`、`meta-A.txt`、`sar-net-A.log`、`mpstat-A.log`、`ss-A.log`；B 的 `steps.csv`、`loadgen.log`、`meta-B.txt`、`sar-net-B.log`、`mpstat-B.log`。来源和字节哈希见 `source-manifest.json`。

派生文件：`network-summary.csv` 为各阶段汇总；`sample-index.csv` 标明选中的原始行；`ss-snapshots.csv` 是仅包含 B→A:8080 连接的快照汇总；`o2-results.png/svg` 是结果图。

`cloud-topology.json` 为收尾时核对的非敏感元数据，VPC ID 仅保留哈希；`cleanup.json` 为进程和规则清理状态。临时 8080 规则按用户决定暂保留，不能把服务停止等同于规则已删除。

重算：在本目录执行 `python3 analyze_o2.py`，需要 Python 3 标准库，无第三方分析依赖。脚本在派生 CSV 中保留原始文件行号，检查客户端各项计数相加与总数一致，并断言每阶段每个主机都有 20 个完整的一秒网卡及全机 CPU 样本。也支持把原始文件放在脚本旁的 `raw/` 子目录中。

所有原始日志按字节保留。本目录是选做 O2 的双机记录，不是 `scripts/run.sh` 的单机分阶段采集目录。
