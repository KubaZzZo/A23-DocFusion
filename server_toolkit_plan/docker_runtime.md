# Docker 运行时设计

## 概述

每个服务器文档任务都在独立 Docker worker 中执行。容器只挂载本次任务目录，执行完成后销毁。L1/L2 默认不联网；L3 Codex CLI worker 只允许访问 OpenAI API 或配置的 LLM API。

## 任务目录

```text
/var/docfusion/tasks/{task_id}/
  input/          # 用户上传文件，只读挂载
  work/           # 中间处理文件
  output/         # 最终结果文件
  logs/
    stdout.log
    stderr.log
    steps.jsonl
  task.json       # 任务描述、执行计划、超时配置
```

后端只从 `output/` 返回结果文件。`input/` 对容器只读，避免原始上传文件被覆盖。

## L1/L2 worker 启动参数

```bash
docker run --rm \
  --name "docfusion-task-${TASK_ID}" \
  --user 1000:1000 \
  --memory 2g \
  --cpus 1.5 \
  --pids-limit 100 \
  --read-only \
  --tmpfs /tmp:size=512m \
  --network none \
  -v "/var/docfusion/tasks/${TASK_ID}/input:/workspace/input:ro" \
  -v "/var/docfusion/tasks/${TASK_ID}/work:/workspace/work" \
  -v "/var/docfusion/tasks/${TASK_ID}/output:/workspace/output" \
  -v "/var/docfusion/tasks/${TASK_ID}/logs:/workspace/logs" \
  -v "/var/docfusion/tasks/${TASK_ID}/task.json:/workspace/task.json:ro" \
  docfusion-worker:latest \
  /entrypoint.sh
```

## L3 Codex worker 启动差异

L3 worker 与普通 worker 的区别：

| 配置项 | L1/L2 worker | L3 Codex worker |
| --- | --- | --- |
| 网络 | `--network none` | 仅允许访问 OpenAI API 或配置的 LLM API |
| 内存 | 2 GB | 4 GB |
| CPU | 1.5 | 2 |
| API Key | 无 | 通过环境变量注入 |
| 可用命令 | `docfusion` + 预装工具 | `docfusion` + 预装工具 + `codex` |
| 默认超时 | 60 秒或 180 秒 | 600 秒 |

示例：

```bash
docker run --rm \
  --name "docfusion-agent-${TASK_ID}" \
  --user 1000:1000 \
  --memory 4g \
  --cpus 2 \
  --pids-limit 150 \
  --network docfusion-llm-only \
  -e OPENAI_API_KEY="${TASK_API_KEY}" \
  -v "/var/docfusion/tasks/${TASK_ID}/input:/workspace/input:ro" \
  -v "/var/docfusion/tasks/${TASK_ID}/work:/workspace/work" \
  -v "/var/docfusion/tasks/${TASK_ID}/output:/workspace/output" \
  -v "/var/docfusion/tasks/${TASK_ID}/logs:/workspace/logs" \
  -v "/var/docfusion/tasks/${TASK_ID}/task.json:/workspace/task.json:ro" \
  docfusion-agent:latest \
  /entrypoint-agent.sh
```

## 超时策略

| 任务级别 | 默认超时 | 最大超时 |
| --- | --- | --- |
| L1 | 60 秒 | 5 分钟 |
| L2 | 3 分钟 | 10 分钟 |
| L3 | 10 分钟 | 30 分钟 |

后端终止流程：

```text
1. 等待容器在 timeout_seconds 内退出。
2. 超时后执行 docker stop，给 10 秒优雅退出时间。
3. 仍未退出则 docker kill。
4. 标记任务为 timeout。
5. 写入 logs/steps.jsonl 和任务错误信息。
```

## entrypoint 行为

普通 worker：

```text
1. 读取 /workspace/task.json。
2. 写入 start 事件到 logs/steps.jsonl。
3. 逐步执行 steps 中的 docfusion 命令。
4. 每步写入 step_started 和 step_completed。
5. stdout 写入 logs/stdout.log，stderr 写入 logs/stderr.log。
6. 退出前写入 complete 或 error。
```

Codex worker：

```text
1. 读取 task.json 中的 agent_prompt。
2. 注入系统约束：只能访问 /workspace，结果必须写入 output/。
3. 启动 codex exec。
4. 要求 Agent 优先调用 docfusion-cli。
5. 收集最终 JSON 输出和 output/ 文件。
```

## 资源和并发

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `MAX_CONCURRENT_TASKS` | 4 | 同时运行的 worker 数 |
| `TASK_QUEUE_SIZE` | 20 | 等待队列长度 |
| `QUEUE_TIMEOUT` | 5 分钟 | 排队超时 |
| `MAX_OUTPUT_SIZE` | 200 MB | 单任务输出上限 |

队列满时，API 返回 `429 QUEUE_FULL`。

## 结果回收

后端只读取：

```text
/var/docfusion/tasks/{task_id}/output/
```

下载规则：

- 0 个输出文件：返回 404。
- 1 个输出文件：直接返回。
- 多个输出文件：打包 zip 返回。

## 清理策略

| 任务结果 | 保留时间 |
| --- | --- |
| 成功 | 24 小时 |
| 失败 | 72 小时 |
| 超时 | 72 小时 |
| 取消 | 24 小时 |

当磁盘使用超过阈值时，优先清理最旧的成功任务。

## 安全清单

- 容器不挂载 Docker socket。
- 容器不挂载宿主机 `/etc`、`/root`、`/home`、服务器源码目录。
- 容器使用非 root 用户运行。
- L1/L2 默认 `--network none`。
- L3 只允许访问 LLM API，不允许任意外网访问。
- API Key 只通过环境变量注入，不写入任务目录。
- 上传文件必须做大小、扩展名和 magic bytes 检查。
- Office 文件可选做宏检查。
- 输出文件必须限制大小。
- 超时任务必须强制终止。
