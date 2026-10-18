# 代码导览

这份文档讲代码怎么组织、每块负责什么、实验怎么跑、输出里有什么。研究本身见 `method.md`、`benchmark.md` 和 `research_notes.md`。

## 四个代码文件夹

**`model/`：方法本身，即潜在帖子怎么写、怎么读。**
- `backends/hf.py` 包了一层 HuggingFace 模型：普通的文字生成，以及把 soft token 插进提示（`chat`）。帖子有两种写法：`encode` 是旧的池化版，`gist` 是本方法，即从上下文读出。
- `backends/mock.py` 是一个不加载模型的假后端，只用来测管线。
- `train_writer.py` 里的 `WriteHead` 就是"k 个查询向量加一个可选的映射"。`random_head` 生成未训练的版本，也就是我们的方法。
- 三个训练脚本 `train_reader.py`、`train_writer.py`、`train_secret.py` 分别训练读取侧 adapter 和 writer。在现在的故事里，它们只作消融。

**`benchmark/`：任务和评测。**
- `secretbench.py` 生成 SecretBench 项目。
- `secret_tasks.py` 把它变成离线测量用的样本：合成的生产者上下文、读者的问题、消费者代码的判分。
- `tasks.py` 读 ClassEval 并定义"项目 / 子任务"。
- `workspace.py` 是共享代码区：每个方法有版本号，只能由认领它的 agent 写。
- `sandbox.py` 在子进程里跑测试，有超时和资源限制。
- `validate.py` 挑出 ClassEval 里参考实现自己能通过测试的类，结果写在 `data/classeval_valid.json`。

**`forum/`：多 agent 论坛，端到端地跑一个项目。**
- `run.py` 是入口，`config.py` 是全部实验开关。
- `orchestrator.py` 按轮次调度 agent。
- `agent.py` 是单个 agent 的一次工作：认领方法、读帖、写代码、跑可见测试、发帖。
- `posts.py` 是论坛本身：帖子、出处、谁能读到哪些帖子。
- `prompts.py` 收着所有提示模板。
- `probe.py` 事后对帖子"打断提问"。
- `metrics.py` 汇总指标。

**`analysis/`：结果分析。**
- `tables.py` 出带置信区间的条件对比表。
- `paired.py` 在同一批方法上做配对符号检验。
- `linprobe.py` 对保存下来的潜在帖子跑线性探针。
- `neutral_probe.py` 把同一段文字去掉上下文重新编码，作为对照。
- `secret_cross.py` 只统计"生产者是别的 agent"的消费者通过率。
- `secret_mislead.py` 检查每条生产者帖子把格式说对还是说错，以及读到它的消费者表现如何。

## 论坛的实验开关

开关都在 `forum/config.py`，命令行用 `--名字 值` 设置，`--grid 名字=a,b` 一次跑多个取值。常用的有：

| 开关 | 含义 |
|---|---|
| `--channel none / text / latent` | 不交流、发文字、发潜在帖子 |
| `--writer-head random:16` | 潜在帖子用本方法（16 个未训练的查询向量）；不给就是旧的池化版；给 `.pt` 路径就加载训练过的 head |
| `--control none / shuffle` | 读者收到的潜在帖子是否换成别人的（内容对照） |
| `--source report / artifact` | 帖子来自作者的汇报，还是由系统直接编码代码和测试日志；文字信道下 `artifact` 就是直接贴代码 |
| `--tasks toy / classeval:0-29 / secret:40` | 玩具任务、ClassEval 的前 30 个类、40 个 SecretBench 项目 |
| `--spec full / private` | 每个 agent 是看到全部方法的文档，还是只看到自己那个方法的 |
| `--memory true` | agent 写依赖方法时能看到自己先前写过的代码（否则它会忘了自己定的格式） |
| `--overclaim-frac 0.34 --overclaim-mode ...` | 让一部分 agent 说谎：`always` 直接把状态改成"做完了"，`deceive` 让模型自己写连贯的谎言，`mislead` 把接口格式说错，`pressure` 只施加"尽快完成"的压力 |
| `--trust blind / attested / crosscheck` | 是否只有 CI 通过才算做完；`crosscheck` 还要另一个 agent 写的测试也通过 |
| `--save-latents true` | 把每条潜在帖子连同真值保存成 `latents.pt`，供离线分析和训练 |

## 输出

每次运行在 `runs/<名字>/<条件>/` 下写这些文件：
- `config.json`：本条件的全部开关。
- `events.jsonl`：每一次认领、工作和发帖，包括作者说了什么、真实测试结果、读了哪些帖子。
- `projects.jsonl`：每个项目、每个方法的最终结果。
- `summary.json`：汇总指标。
- `latents.pt`：只在开了 `--save-latents` 时生成。

汇总指标里最常看的有三类：
- **方法和类的通过率**：`method_pass`、`class_pass`。其中 `method_pass_iso` 把其他方法都换成参考实现，只测这个方法自己，排除"被别人写坏的依赖拖累"。`dep_pass_iso` 只看需要调用别的方法的那些方法。
- **团队有没有谎报完成**：`false_declaration` 是团队宣布完成、但隐藏测试不过的比例。
- **成本**：`prompt_tokens`、`gen_tokens`、`latent_bytes`。

## 作业脚本

`jobs/` 下每个脚本对应一个实验，文件开头的注释写了它做什么、怎么提交。结果分别记在 `research_notes.md` 的 R1–R13 里：

| 脚本 | 实验 |
|---|---|
| `smoke.sbatch` | 3 个项目的冒烟测试 |
| `e0.sbatch`、`run.sbatch` | ClassEval 上的第一轮测量（R1–R3、R5） |
| `e0p.sbatch` | 私有规格（R6） |
| `e0d.sbatch`、`neutral.sbatch` | 连贯谎言与中性上下文对照（R3、R7、R8） |
| `e0ck.sbatch` | 同伴交叉验证；不分块的潜在帖子（R4、R9） |
| `e1a.sbatch`、`e1b.sbatch` | 训练读取侧 adapter，并接回论坛（R4） |
| `e1w.sbatch`、`e1w_forum.sbatch` | 训练 writer，并接回论坛（R12） |
| `e0s.sbatch`、`e0s2.sbatch` | SecretBench 论坛（R10、R11） |
| `e1s.sbatch`、`e1s2.sbatch` | 在 SecretBench 上训练 writer，以及诊断（R13） |
| `e0s3.sbatch`、`e0s4.sbatch` | 本方法放进 SecretBench 论坛：作者诚实 / 作者把格式说错 |
| `probe_cpu.sbatch` | 只用 CPU 跑线性探针 |

## 集群上的注意事项

- 我们在 Alliance 的 Nibi 集群上跑：一张 MIG 切片（`h100_3g.40gb`），4 个 CPU，48 GB 内存。
- `setup_env.sh` 在作业里用 Alliance 的 wheelhouse 现场建虚拟环境，并把模型权重复制到节点本地盘。几个作业同时从共享盘按需读权重会慢到每秒几 MB。
- 两个容易踩的坑：`sbatch --export` 会在逗号处把值切开，所以带逗号的 `--grid` 参数要写在脚本里，不能经环境变量传；`set -u` 会和 Lmod 冲突，脚本里只用 `set -eo pipefail`。
