# O3：enrolld 三行九格看板查询说明

本看板按 L-08 的“业务 → 服务 RED → 资源 USE”结构，为实验服务 enrolld 展示用户体验、服务排队及资源状态。本文整理了本轮方案对应的查询与面板配置；提交前应与 Grafana 导出的 JSON 核对，保证文档与实际面板一致。

## 1. 数据来源与统一口径

- 数据源：服务器上的 Prometheus，抓取任务为 `enrolld` 和 `node`。
- 读接口的指标标签为 `route="/api/courses/{id}"`，不是具体请求地址中的 `/api/courses/1`。
- 速率、直方图分位数和告警 SLI 默认使用最近 1 分钟的滚动窗口。
- 读路径 SLO：30 天内，99% 的请求在 50 ms 内成功返回。
- 服务端好请求：`code="200"` 且处理耗时不超过 `0.05` 秒；燃烧率为 `(1 - SLI) / 0.01`。
- 本轮服务绑定 CPU 1，数据目录所在块设备为 `vda`；本机压测走回环接口 `lo`，同时展示 `eth0` 的流量。
- 主实验原始数据：`runs/o3-burn-01/`；告警证据：`runs/o3-burn-01-evidence/`；补充写实验：`runs/o3-write-light-01/`。
- 主实验时间为北京时间 2026-10-30 19:51:37—19:57:37。查看历史结果时使用覆盖实验的绝对时间范围，并确认 Grafana 的时区；告警快照文件名中的 `Z` 表示 UTC。
- 本文中的百分比查询已乘以 100，Grafana 应选择 `Percent (0-100)`，避免再次按 0—1 比例转换。
- 没有请求时，比率或分位数可能为 NaN 或无数据，不应统一填成 0 或 100%。查询返回空序列也可能表示指标未采集，应与“真实值为零”区分。
- 各阶段汇总表采用 `scripts/run.sh` 的阶段窗口，排除阶段开头 5 秒；看板采用滚动窗口，两者不要求数值逐点相同。

## 2. 布局与课程示例的对应关系

| 层次 | 第一格 | 第二格 | 第三格 |
|---|---|---|---|
| 业务及活动代理 | 读路径 SLI 与 99% 目标、燃烧率 | 提交成功率 | 在途请求数 |
| 服务 RED | 按接口 QPS 与 5xx 错误率 | 按接口 p50 / p99 延迟 | 连接池占用率与等待 p99 |
| 资源 USE | CPU、内存与运行队列 | 数据盘 vda | 网络收发与 TCP 重传 |

课程图片中的“开放后 10 分钟完成率”和“在线人数”需要业务埋点，enrolld 未提供这些指标。因此第一行使用明确标注的体验及活动代理指标，不把请求达标比例当作实际业务完成率，也不把在途请求数当作在线人数。

本服务的数据库是模拟连接池，没有真实 MySQL、buffer pool 或 Kafka。第三行展示实际主机资源，不能将数据盘指标冒称为 MySQL 指标。

## 3. 第一行：业务及活动代理

### 3.1 读路径 SLI 与 99% 目标

**作用：** 同时观察读请求达标比例、SLO 目标和错误预算燃烧率。

查询 A：读请求达标比例，单位为百分比。

```promql
100 * enrolld:read_sli:ratio1m
```

查询 B：SLO 目标线，单位为百分比。

```promql
vector(99)
```

查询 C：燃烧率，单位为倍。

```promql
enrolld:read_burn_rate:ratio1m
```

这些记录指标由 `deploy/rules.yml` 定义，其计算逻辑为：

```promql
# enrolld:read_rps:rate1m
sum(rate(http_requests_total{
  job="enrolld",route="/api/courses/{id}"
}[1m]))

# enrolld:read_sli:ratio1m
(
  sum(rate(http_request_duration_seconds_bucket{
    job="enrolld",
    route="/api/courses/{id}",
    code="200",
    le="0.05"
  }[1m]))
  or vector(0)
)
/
enrolld:read_rps:rate1m

# enrolld:read_burn_rate:ratio1m
clamp_min(1 - enrolld:read_sli:ratio1m, 0) / 0.01
```

**显示方式：** Time series。A、B 使用左侧百分比轴；C 使用右侧独立轴，标注“倍”。目标线设为虚线。

**解释：** 燃烧率为 10，表示最近窗口内约 10% 的请求不满足 SLO；为 100，表示该窗口中全部请求都不满足“成功且不超过 50 ms”，不等于全部请求返回错误。服务端 SLI 不包含全部客户端等待与网络传输。

### 3.2 提交成功率

**作用：** 观察写接口已完成请求中的成功比例；这不是读路径 SLO。

```promql
100 *
(
  sum(rate(http_requests_total{
    job="enrolld",
    route="/api/enroll",
    code="200"
  }[1m]))
  or vector(0)
)
/
sum(rate(http_requests_total{
  job="enrolld",
  route="/api/enroll",
  code=~"200|5.."
}[1m]))
```

**单位及显示方式：** 百分比，Stat。若计算方式设置为 Last not null，显示的是选定时间范围内最后一个有效的一分钟窗口值，不是整个范围内按请求数加权的成功率。核对实际面板计算方式后保持一致。

**口径：** 分母包括 200 和 5xx，排除 4xx 无效请求。当前示例没有课程已满等真实业务拒绝逻辑，不能将此查询解释为已实现完整的业务拒绝分类。无提交请求时不强行显示 100%。

补充写实验独立保存在 `runs/o3-write-light-01/`，不混入读过载实验的阶段统计。

### 3.3 在途请求数

**作用：** 观察各接口正在处理的请求数量，为并发活动和积压提供线索。

```promql
sum by (route) (
  http_inflight_requests{job="enrolld"}
)
```

**单位及显示方式：** 请求数，Time series，图例为 `{{route}} 在途请求`。

**限制：** 在途请求包含正在执行和等待资源的请求，不等于纯等待队列长度，更不等于独立用户数、在线人数或 TCP 连接数。需结合连接池等待指标判断是否发生排队。

## 4. 第二行：服务 RED

### 4.1 按接口 QPS 与 5xx 错误率

查询 A：服务端每秒完成的请求数，包含全部已记录状态码。

```promql
sum by (route) (
  rate(http_requests_total{job="enrolld"}[1m])
)
```

查询 B：各接口 5xx 请求占比。

```promql
100 *
(
  sum by (route) (
    rate(http_requests_total{
      job="enrolld",code=~"5.."
    }[1m])
  )
  or
  (
    0 * sum by (route) (
      rate(http_requests_total{job="enrolld"}[1m])
    )
  )
)
/
sum by (route) (
  rate(http_requests_total{job="enrolld"}[1m])
)
```

**单位及显示方式：** Time series；A 使用请求/秒轴，B 使用独立百分比轴。图例分别标注接口与 QPS、5xx 错误率。

**口径：** 查询 B 的补零保留接口标签，避免没有 5xx 序列时整条查询为空；无流量时分母仍为零，不代表健康。服务端 QPS 不是 loadgen 的目标到达率，也不是只计算成功请求的 `ok_rps`。服务端 5xx 比例不涵盖客户端所有超时、连接错误及非 2xx 响应。

### 4.2 按接口 p50 / p99 延迟

查询 A：p50，单位为毫秒。

```promql
1000 * histogram_quantile(
  0.50,
  sum by (route, le) (
    rate(http_request_duration_seconds_bucket{
      job="enrolld"
    }[1m])
  )
)
```

查询 B：p99，单位为毫秒。

```promql
1000 * histogram_quantile(
  0.99,
  sum by (route, le) (
    rate(http_request_duration_seconds_bucket{
      job="enrolld"
    }[1m])
  )
)
```

**显示方式：** Time series，同一接口的两条曲线同图展示；图例分别使用 `{{route}} p50`、`{{route}} p99`。Grafana 可将较大的毫秒值自动显示为秒。

**口径：** 先按 `route, le` 聚合不同状态码的桶，再计算分位数；不能直接平均各状态码或各实例的 p99。结果是直方图插值估计值，精度受桶宽影响。这两条查询包含全部已记录状态码，且只测量服务端处理时间，与客户端仅统计成功请求的延迟口径不同。

### 4.3 连接池占用率与等待 p99

查询 A：连接池占用率。

```promql
100 *
db_pool_in_use{job="enrolld"}
/
db_pool_size{job="enrolld"}
```

查询 B：等待连接的 p99，单位为毫秒。

```promql
1000 * histogram_quantile(
  0.99,
  sum by (le) (
    rate(db_pool_wait_seconds_bucket{
      job="enrolld"
    }[1m])
  )
)
```

**显示方式：** Time series，百分比与毫秒使用独立坐标轴。

**解释：** 占用率属于利用率，等待属于饱和度证据。池占满并伴随等待增长、SLI 下降，才支持连接池成为瓶颈的判断。等待直方图包含等连接超时的请求，p99 是插值结果，不应解读为精确测得的单次最长等待。

## 5. 第三行：资源 USE

### 5.1 CPU、内存与运行队列

查询 A：服务所在 CPU 1 的计算忙碌比例，单位为百分比。

```promql
100 * sum(
  rate(node_cpu_seconds_total{
    job="node",
    cpu="1",
    mode!~"idle|iowait|steal"
  }[1m])
)
```

查询 B：CPU 1 的 steal 比例，单位为百分比。

```promql
100 * rate(node_cpu_seconds_total{
  job="node",cpu="1",mode="steal"
}[1m])
```

查询 C：主机可用内存，单位为 MiB。

```promql
node_memory_MemAvailable_bytes{job="node"} / 1048576
```

查询 D：主机可运行任务数。

```promql
node_procs_running{job="node"}
```

**显示方式：** Stat 或 Table，分别给四个字段设置单位。查询 C 已换算为 MiB，不应再配置为原始字节数进行二次换算。若使用 Last not null，应注明该显示值不是阶段平均值。

**限制：**

- CPU 1 忙碌包含该逻辑 CPU 上所有任务，不是 enrolld 进程专属占用。
- 查询 A 排除了 steal；原有 `deploy/queries-use.txt` 中 `svc_cpu_busy` 的过滤条件包含 steal，因此口径略有不同。
- 可运行任务数是主机级瞬时值，不能只凭单次读数判定 CPU 饱和。
- 本机虚拟拓扑中两个 vCPU 呈现相同 CORE；绑定不同逻辑 CPU 仍不能保证完全隔离底层资源，见 `LAB2.md` 的环境说明。

### 5.2 数据盘 vda

查询 A：写请求平均耗时，单位为毫秒。

```promql
1000 *
rate(node_disk_write_time_seconds_total{
  job="node",device="vda"
}[1m])
/
rate(node_disk_writes_completed_total{
  job="node",device="vda"
}[1m])
```

查询 B：磁盘利用率，单位为百分比。

```promql
100 * rate(node_disk_io_time_seconds_total{
  job="node",device="vda"
}[1m])
```

查询 C：平均未完成 I/O 数。

```promql
rate(node_disk_io_time_weighted_seconds_total{
  job="node",device="vda"
}[1m])
```

**显示方式：** Stat 或 Table，各字段保留自己的单位，可显示趋势。若使用 Last not null，不能把截图上的最后值写成过载阶段平均值。

**口径与限制：**

- 写 await 含排队和处理时间，按设备写请求计，不等于应用 fsync 的耗时。
- 平均未完成 I/O 包含正在处理的请求，不能全部当作排队请求。
- util 接近 100% 不能单独证明云盘吞吐已达到上限。
- 这些是整块设备指标，包含其他进程的 I/O。
- enrolld 的读路径通过休眠模拟数据库查询，不产生真实数据库磁盘访问。因此读路径过载时磁盘指标较低是合理现象。
- 没有写请求时 await 可能为 NaN，不用人工补零。

### 5.3 网络收发与 TCP 重传

查询 A：发送速率，单位为 Mbit/s。

```promql
8 * rate(node_network_transmit_bytes_total{
  job="node",device=~"lo|eth0"
}[1m]) / 1000000
```

查询 B：接收速率，单位为 Mbit/s。

```promql
8 * rate(node_network_receive_bytes_total{
  job="node",device=~"lo|eth0"
}[1m]) / 1000000
```

查询 C：TCP 重传速率，单位为段/秒。

```promql
rate(node_netstat_Tcp_RetransSegs{
  job="node"
}[1m])
```

**显示方式：** Time series；A、B 图例分别为 `{{device}} TX`、`{{device}} RX`，使用 Mbit/s 轴；C 使用独立的段/秒轴。A、B 已经换算为 Mbit/s，不应再按原始 bit/s 缩放。

**限制：** 本轮请求走回环 `lo`，其流量不代表公网 EIP 带宽；`eth0` 还包含其他通信。TCP 重传是主机级报文段计数，不能等同于 HTTP 错误率。未采集的指标应标记为无数据，不能伪装成零。本轮不据此测定网络容量上限。

## 6. 看板与告警证据如何结合

- 先看第一行：读请求是否满足 SLO，燃烧率是否升高。
- 再看第二行：请求速率、错误、延迟、在途请求与连接池等待如何变化。
- 最后看第三行：CPU、内存、磁盘和网络是否支持相应瓶颈判断。
- 本轮量化判断引用 `runs/o3-burn-01/` 的原始 CSV 及 `scripts/table.sh` 生成的表，不从截图手抄近似值。
- 图中的燃烧率超过阈值不能单独证明告警已进入 firing，还必须满足持续时间条件。实际触发证据来自 `runs/o3-burn-01-evidence/alerts/` 的 API 原始 JSON。
- 告警时间线和恢复情况见 `LAB2.md` 的 O3 实测部分；看板说明不替代这些原始证据。


