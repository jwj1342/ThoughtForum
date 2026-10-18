# 可行性 memo：在 Nibi 上用开源权重模型做"多 agent coding 中的 latent/KV 隐式通信"实验

> 日期：2026-10-17
>
> **工作方式**：只做网页检索，读本地 Alliance 文档，在登录节点 `l1.nibi` 上跑 `module spider`、`avail_wheels`、`curl` 小 JSON、`gh` 只读查询这类轻量命令。没有跑模型，没有下载权重，也没有安装任何东西。
>
> **证据标记**
> - `[本地]`：`/cvmfs/soft.computecanada.ca/custom/docs/en/` 下的文件。
> - `[实测]`：登录节点上的轻量查询结果。
> - `[估算]`：我自己的算术，例如参数量×2 字节。
> - `[推断]`：没有直接证据的判断。
> - `[复核]`：我亲自打开原页面核对过的数字。
> - 其余数字由检索子任务给出，出处 URL 都附在旁边。
>
> 查不到的一律写"未查到"。

---

## 0. 结论速览

1. **MVP 的 benchmark**：首选不需要 Docker、自带信息不对称的两个：
   - **CrossCodeEval（Python 子集）**：把跨文件上下文只交给 sender，用来检验"内容是否被传递"。
   - **ClassEval**：把类里的方法拆给不同 agent，有可执行测试，用来检验内容传递和分工协调。

   另外两个只作辅助：**LiveCodeBench** 按时间切分，做等预算对照；**HumanEval+/MBPP+** 只作为复现 LatentMAS 的锚点。
2. **MVP 的模型**：
   - **Qwen3-8B 加 Qwen3-14B**：同族异构。所有 dense 尺寸都是 8 个 KV 头、head_dim 128，只有层数和 hidden 不同。LatentMAS、C2C 和 Cheng 等人的因果审计都已经在 Qwen3 上跑过。
   - **Devstral-Small-2507（24B，Mistral 族）**：跨族对照。它的 KV 张量形状和 Qwen3-14B **完全相同**：40 层、8 个 KV 头、head_dim 128、hidden 5120 `[复核 config.json]`。只有 Q 头数和 tokenizer 不同，可以把"形状不匹配"和"表征不匹配"分开研究。
   - 三个模型 bf16 单卡都放得下。
3. **SWE-bench 级实验**：技术上可行，但**不适合作为 MVP**。
   - 跑 agent 有官方路径：mini-swe-agent 原生支持 singularity/apptainer。
   - 评分有路径：OpenHands benchmarks 已合并 `--apptainer` 评分（PR #743、#745 `[复核]`），也可以用 sb-cli 云评分。
   - 主要障碍：
     - 白盒推理吞吐低：HF 进程内推理没有 continuous batching，而轨迹长、轮数多。
     - 每个实例的镜像都要转成 SIF 或 sandbox，体积和 fakeroot 可用性都要先实测。
     - Apptainer 下没有 cgroup 隔离。
     - Verified 污染严重。
     - 臂数×种子数会把成本成倍放大。
   - 建议第二阶段先做 **Agentless 式固定流水线**：定位 agent 把 KV 传给修复 agent，轮数少。用 SWE-bench Lite 或 Verified 的子集，加上 SWE-bench-Live 做去记忆对照。
4. **Nibi 的关键事实** `[本地]`：
   - **所有节点都有外网。**
   - **没有 Docker**；有 Apptainer 1.2.4 到 1.5.4。
   - 每个 GPU 节点有 8 张 H100 SXM 80GB（NVLink），推荐每卡 14 核、250 GB 内存。
   - 约一半 GPU 节点开了 MIG。
   - `$SLURM_TMPDIR` 约 3T。
   - scratch 的软配额是 1 TB，宽限期 60 天。
   - 作业最长 7 天。

---

## 1. Benchmark 表

**列说明**
- **Docker**：官方评测是否需要 Docker。
- **替代**：有没有 Apptainer 或无容器的方案。
- **~30B 分数 / 饱和**：当前开源 ~30B 级模型的大致分数和出处。
- **多 agent**：有没有天然可拆分的信息不对称。
- **检验**：(a) 内容是否被传递，(b) 等预算对比，(c) 协调。

### 1.1 函数级与竞赛级

| Benchmark | 题目数 | Docker | 替代（证据） | ~30B 分数 / 饱和 | 污染风险 | 多 agent | 检验 |
|---|---|---|---|---|---|---|---|
| **HumanEval+**（EvalPlus） | 164 题，测试数是原版的 80 倍 [hf](https://huggingface.co/datasets/evalplus/humanevalplus) | 否，Docker 只是可选 | 本地进程执行，有内存和超时限制，但"不是安全沙箱" [execution.md](https://raw.githubusercontent.com/evalplus/evalplus/master/docs/execution.md)。Apptainer 官方文档未查到 | Qwen2.5-Coder-32B-Inst 87.2 [2409.12186](https://arxiv.org/html/2409.12186v3)；Qwen3-Coder-30B-A3B 87.2（第三方 [2603.16790](https://arxiv.org/html/2603.16790)）。**接近饱和** | 高：与 Pile、Stack 大量重叠 [2403.04811](https://arxiv.org/html/2403.04811)；LCB 论文指出不少模型对 HumanEval 过拟合 [2403.07974](https://arxiv.org/html/2403.07974) | 弱，单函数 | (b)，作 LatentMAS 复现锚点 |
| **MBPP+** | v0.2.0 共 378 题，由 399 题剔除而来 [evalplus](https://github.com/evalplus/evalplus) | 否 | 同上 | Qwen2.5-Coder-32B 75.1；Qwen3-Coder-30B-A3B 77.2（出处同上） | 高 | 弱 | (b) |
| **LiveCodeBench** | 累积版本 [GitHub README](https://github.com/LiveCodeBench/LiveCodeBench) `[复核]`，见表下 | 否 | 纯本地 Python，同进程 `exec`，源码注明 "NOT a security sandbox" [testing_util.py](https://raw.githubusercontent.com/LiveCodeBench/LiveCodeBench/main/lcb_runner/evaluation/testing_util.py) | 见表下 | **低且可控**：模型 cutoff 之后的题目"stark drop" [2403.07974](https://arxiv.org/html/2403.07974)。但 v6 只到 2025-04，2026 年的新模型已没有干净窗口 `[推断]` | 弱，要人工拆角色 | **(b) 最合适** |
| **BigCodeBench** | Full 1140 / Hard 148；complete 和 instruct 是同一批题的两种提示 [GitHub](https://github.com/bigcode-project/bigcodebench)；涉及 139 个库 [2406.15877](https://arxiv.org/abs/2406.15877) | 默认远程评测（HF gradio 或 e2b）；本地运行官方"strongly recommend" Docker | `--execution local`，风险自担 [ADVANCED_USAGE](https://raw.githubusercontent.com/bigcode-project/bigcodebench/main/ADVANCED_USAGE.md)；仓库已 archived | Qwen2.5-Coder-32B：Full-Inst 49.6 / Hard-Inst 27.0 [2409.12186](https://arxiv.org/html/2409.12186v3)；Qwen3-Coder-30B：Full 46.9 / Hard 27.7（[2603.16790](https://arxiv.org/html/2603.16790)，未说明是 complete 还是 instruct）。未饱和 | 专门研究未查到 | 中：库的 API 文档可以只给一方 | (a)(b) |
| **APPS** | 10,000 题（train / test 各 5k），三档难度 [2105.09938](https://arxiv.org/abs/2105.09938)；1235 道 test 题没有参考解 [hf](https://huggingface.co/datasets/codeparrot/apps) | 否，本地脚本，官方甚至带 Slurm 脚本 [eval README](https://raw.githubusercontent.com/hendrycks/apps/main/eval/README.md) | 本地 | 未查到 | 测试弱：AlphaCode 测得 60% 的假阳性 [2203.07814](https://ar5iv.labs.arxiv.org/html/2203.07814) | 弱 | (b)，噪声大 |
| **CodeContests** | train 13,328 / valid 117 / test 165 [hf](https://huggingface.co/datasets/deepmind/code_contests) | 否：Bazel 加 clang 沙箱，仅限 Linux [GitHub](https://github.com/deepmind/code_contests) | 原生 Linux，Nibi 上能否构建未验证 | 未查到 | test 按时间切分（2021-09 之后），对现今模型已过旧 [2203.07814](https://ar5iv.labs.arxiv.org/html/2203.07814) | 弱 | (b) |

**LiveCodeBench 各版本**（时间都从 2023-05 起算，可用 `--start_date`/`--end_date` 或 `v4_v5` 这类增量切片）：

| 版本 | 题目截至 | 题目数 |
|---|---|---|
| release_v1 | 2024-03 | 400 |
| release_v2 | 2024-05 | 511 |
| release_v3 | 2024-07 | 612 |
| release_v4 | 2024-09 | 713 |
| release_v5 | 2025-01 | 880 |
| release_v6 | 2025-04 | 1055 |

v6 之后的版本：未查到。HF 数据集卡片只列到 v5。

**LiveCodeBench 上的 ~30B 分数**（未饱和）：
- Qwen3 技术报告 [2505.09388](https://arxiv.org/html/2505.09388) `[复核]`，口径 "v5, 2024.10–2025.02"：

| 模型 | thinking | non-thinking |
|---|---|---|
| Qwen3-32B | 65.7 | 31.3 |
| Qwen3-30B-A3B | 62.6 | 29.8 |

- Qwen3-Coder-30B-A3B：v5 43.1 / v6 36.0（第三方 [2603.16790](https://arxiv.org/html/2603.16790)）。
- Multi-LCB（Python 列，题目时间 2025-02 至 05）[2606.20517](https://arxiv.org/html/2606.20517)：
  - gpt-oss-20B：medium 63.6、low 46.2
  - Qwen3-Coder-30B：36.6
  - Devstral-Small-2505：23.2

### 1.2 类级与仓库级

| Benchmark | 题目数 | Docker | 替代 | ~30B 分数 / 饱和 | 污染风险 | 多 agent | 检验 |
|---|---|---|---|---|---|---|---|
| **ClassEval** | 100 个类；方法数论文写 412 [2308.01861](https://arxiv.org/html/2308.01861)，README 写 410 [GitHub](https://github.com/FudanSELab/ClassEval) | 否：进程内 unittest，每个 5 秒 [test_pipeline.py](https://raw.githubusercontent.com/FudanSELab/ClassEval/master/classeval_evaluation/test_pipeline.py) | 本地，放在作业里跑 | 类级 pass 率：~30B 未查到。一篇 2025 年论文（含 Qwen2.5-Coder-32B、gpt-oss）的 test 级通过率为 83.6–88.3%，而真实类只有 24.6–33.6% [2510.26130](https://arxiv.org/html/2510.26130)。**test 级接近饱和** | 中：人工构造，但 2023 年就已公开；ClassEval-Pro 称人工 benchmark "increasingly susceptible" [2604.26923](https://arxiv.org/abs/2604.26923) | **强**：76.2% 的方法依赖字段或其他方法（论文），按方法拆给不同 agent 就自然形成信息差 | **(a)(c)**，(b) 也便宜 |
| **RepoBench** v1.1 | 只有补全任务，每种语言分 cross_file_first / cross_file_random / in_file 三个设置，题数见表下 | 否：EM/ES 文本匹配，不执行代码 | 本地 | DS-Coder-33B EM：Python 39.1 / Java 44.8（12 月子集）[2406.11931](https://arxiv.org/html/2406.11931)；Qwen 系未查到 | 中：数据取自 2023-10 至 12，已与 Stack v2 去重 [hf](https://huggingface.co/datasets/tianyang/repobench_python_v1.1) | **强**："检索后补全"天然对应上下游两个 agent，gold 跨文件片段有标注 | (a)(b) |
| **CrossCodeEval** | Python 2,665 / Java 2,139 / TS 3,356 / C# 1,768 [2310.11248](https://arxiv.org/html/2310.11248) | 否：EM/ES 加标识符匹配，不执行 [cceval](https://github.com/amazon-science/cceval) | 本地 | Qwen2.5-Coder-32B（base）平均 EM 57.1 / ES 86.8 [2409.12186](https://arxiv.org/html/2409.12186) | 中到高：仓库建于 2023-03 至 06，已与 Stack 过滤 `[推断]` | **强**：跨文件上下文只给 A，补全交给 B | **(a) 最佳**：标识符匹配直接度量跨文件名字有没有被下游用上 |

RepoBench v1.1 各设置的题数（cross_file_first / cross_file_random / in_file）：
- Python：8,033 / 7,618 / 7,910 [hf size](https://datasets-server.huggingface.co/size?dataset=tianyang/repobench_python_v1.1)
- Java：8,722 / 8,705 / 8,696 [hf size](https://datasets-server.huggingface.co/size?dataset=tianyang/repobench_java_v1.1)

注：RepoBench 和 CrossCodeEval 原本是为 base 或 FIM 模型设计的下一行补全任务，用 instruct 模型要改写 prompt。Qwen2.5-Coder 和 Qwen3 都有 base 版，这一点反而方便。

### 1.3 SWE 家族

**整个 SWE-bench 系列的共同情况**
- 官方评测需要 Docker [FAQ](https://www.swebench.com/SWE-bench/faq/)。harness 要求 120GB 磁盘、16GB 内存、8 核以上 [harness](https://www.swebench.com/SWE-bench/reference/harness/)。
- 评分的替代方案：
  - `--modal true` 在 Modal 云端评分（同上页）。
  - sb-cli 云评分，只支持 Lite 和 Verified [sb-cli](https://github.com/SWE-bench/sb-cli)。
  - **OpenHands benchmarks 的 `--apptainer` 评分**：PR [#743](https://github.com/OpenHands/benchmarks/pull/743) "Add Apptainer SWE-bench evaluation"，2026-06-16 合并；PR [#745](https://github.com/OpenHands/benchmarks/pull/745)，2026-06-22 合并 `[复核]`。
- 官方对 Apptainer 的态度：
  - issue [#242](https://github.com/SWE-bench/SWE-bench/issues/242) 里维护者说 "we don't plan on actively supporting extensions to different containerization software"，该 issue 已 closed `[复核]`。
  - 社区的 `--use_apptainer` PR [#432](https://github.com/SWE-bench/SWE-bench/pull/432) 关闭了，没有合并。
- 已有的 Apptainer 实践：
  - NVIDIA Nemotron 在 Slurm 上把 Verified、SWE-Gym、R2E-Gym 的镜像转成 `.sif` 来跑，并说明 Apptainer 没有 cgroup 隔离，所以自己加了内存 watchdog [nemotron swe](https://docs.nvidia.com/nemotron/latest/nemotron/super3/rl/swe.html)。
  - Epoch AI 的瘦身镜像：Verified 500 个约 30 GiB（原版 189 GiB），全集 2,290 个约 67 GiB [epoch](https://epoch.ai/blog/swebench-docker)。

| Benchmark | 题目数 | Docker | 替代 | ~30B 分数 / 饱和 | 污染风险 | 多 agent | 检验 |
|---|---|---|---|---|---|---|---|
| **SWE-bench Lite** | test 300 / dev 23，每个只改单个文件 [lite](https://www.swebench.com/lite.html) | 是 | 见上方共同情况 | Qwen2.5-Coder-32B（OpenHands）零样本 3.0%，经 SWE-Gym 微调后 15.3% [2412.21139](https://arxiv.org/html/2412.21139)；SWE-agent-LM-32B 30.7% [2504.21798](https://arxiv.org/html/2504.21798) | 高，同 Verified | 中：可以按 Agentless 拆成"定位、修复、验证" [2407.01489](https://arxiv.org/abs/2407.01489) | (a)：定位者把文件和行号传给修复者；(b) |
| **SWE-bench Verified** | 500（SWE-bench 全集 2,294）[FAQ](https://www.swebench.com/SWE-bench/faq/) | 是 | 同上，另有 NVIDIA `.sif` 和 Epoch 镜像 | 分数见表下。**24B 级已接近 70%，正在逐渐饱和** | **高**，见表下 | 中：定位和修复可拆，一方只看 issue、一方只看代码 | (a)(b)；(c) 一般，因为最终只交一个 patch |
| **SWE-bench Pro**（Scale） | 1,865 题、41 个仓库：public 731 / held-out 858 / commercial 276 [2509.16941](https://arxiv.org/html/2509.16941)；V2 把 public 精修为 642 题，另有 HARD-51 [GitHub](https://github.com/scaleapi/SWE-bench_Pro-os) | 是：推荐 Modal，本地 Docker 标为 Beta | 没有官方 Apptainer；镜像在 ghcr 上，理论上可转换 `[推断]` | 论文 Table 5（public）：gpt-oss-20B 16.2、SWE-Smith-32B 6.8、Qwen3-32B 3.4。榜单上 qwen3-coder-480b 38.70，第一名 61.50 [leaderboard](https://labs.scale.com/leaderboard/swe_bench_pro_public)。**远未饱和，但 ~30B 分数太低，噪声大** | 较低：GPL 或 copyleft 仓库，另有 held-out 集 | 中，多数是多文件改动 `[推断]` | 三类都能测，但信噪比差 |
| **SWE-bench-Live**（Microsoft） | 论文 1,319 题、93 个仓库 [2505.23419](https://arxiv.org/abs/2505.23419)；HF 上 lite 300 / verified 500 / full 约 1.89k [hf](https://huggingface.co/datasets/SWE-bench-Live/SWE-bench-Live)；2025-09 之后停止月更 [GitHub](https://github.com/microsoft/SWE-bench-Live) | 是，每题一个镜像 | 未查到 | ~30B 未查到。Claude 3.7 在这里 19.25%，在 Verified 上 43.20%（论文） | **低**，按时间切分 | 同 Verified | 去记忆对照 |
| **SWE-Gym** | 2,438 题、11 个仓库；Lite 子集论文写 230，README 写 234 [2412.21139](https://arxiv.org/html/2412.21139) | 是，镜像合计约 6 TB（论文） | NVIDIA `.sif` 方案 | 训练环境：Qwen2.5-Coder-32B 在 Verified 上 7.0 → 20.6，加 verifier 后 32.0 | 已避开 SWE-bench 的仓库 | 同 Verified | 训练用 |
| **SWE-smith** | 约 50k 题、128 个仓库 [2504.21798](https://arxiv.org/html/2504.21798)，README 现写 52k | 是，README 原话 "requires Docker" [GitHub](https://github.com/SWE-bench/SWE-smith) | 自身没有；mini-swe-agent 的 singularity 环境可能可用（未验证） | SWE-agent-LM-32B 在 Verified 上 40.2 | 已排除 SWE-bench 的 12 个仓库 | 合成 bug 的注入位置已知，**正好可作 (a) 探针的 ground truth** | (a) |
| **R2E-Gym** | 8,135 题，另有 4,578 题子集 [2504.07164](https://arxiv.org/html/2504.07164)；摘要写 ">8.7K"，两者不一致 | 是，每题 300–500MB | 只有 docker 或 kubernetes 后端 [docker.py](https://raw.githubusercontent.com/R2E-Gym/R2E-Gym/master/src/r2egym/agenthub/runtime/docker.py) | R2EGym-32B 34.4（Verified） | 已去重 | 同上 | 训练用 |
| **Multi-SWE-bench** | arXiv 版 1,632 题、7 种语言 [2504.02605](https://arxiv.org/abs/2504.02605)；NeurIPS 版 2,132 题、8 种语言 [NeurIPS](https://papers.neurips.cc/paper_files/paper/2025/hash/5afa9cb1e917b898ad418216dc726fbd-Abstract-Datasets_and_Benchmarks_Track.html)；mini 400 [hf](https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini)，flash 300 [GitHub](https://github.com/multi-swe-bench/multi-swe-bench) | 是 | 未查到 | 未查到 | 未查到 | 同 Verified | — |

**SWE-bench Verified 上的 ~30B 分数**

| 模型 | Verified | 出处 |
|---|---|---|
| Devstral Small 2（24B） | 68.0 | [mistral](https://mistral.ai/news/devstral-2-vibe-cli) |
| Devstral Small 1.1 | 53.6 | [mistral](https://mistral.ai/news/devstral-2507) |
| gpt-oss-20b（low / medium / high） | 37.4 / 53.2 / 60.7 | [2508.10925](https://arxiv.org/html/2508.10925) |
| Qwen3-Coder-30B-A3B（Nebius 用 OpenHands 实测） | 50.0 | [hf](https://huggingface.co/nebius/SWE-rebench-openhands-Qwen3-30B-A3B) |
| SWE-agent-LM-32B | 40.2 | [2504.21798](https://arxiv.org/abs/2504.21798) |

**SWE-bench Verified 的污染证据**
- 只给 issue 文本，模型说出出错文件路径的准确率可达 76%，而在 SWE-bench 以外的仓库上是 53% [2506.12286](https://arxiv.org/abs/2506.12286)。
- SWE-bench+：被判成功的 patch 中，32.67% 的答案已经写在 issue 里，31.08% 是因为测试太弱才通过 [2410.06992](https://arxiv.org/abs/2410.06992)。

### 1.4 协作类

五个都查到了 arXiv abs 页和官方仓库。

| Benchmark | 题目数 | Docker | 替代 | ~30B 分数 | 污染风险 | 多 agent | 检验 |
|---|---|---|---|---|---|---|---|
| **CooperBench** [2601.13295](https://arxiv.org/abs/2601.13295) / [repo](https://github.com/cooperbench/CooperBench) | 652 个 feature 对，12 个仓库，4 种语言 [v2](https://arxiv.org/html/2601.13295v2) | 是：每个 agent 有自己的容器，最后用 git merge 合并两份 patch | Modal（默认）、GCP、本地 Docker；没有 Apptainer | Qwen3-Coder-30B（OpenHands）：solo 21.6% / coop 13.3%；Qwen3-30B 6.3 / 4.6；GPT-5 48.31 / 27.95 [leaderboard](https://cooperbench.com/leaderboard) `[复核]` | 已排除 SWE-bench 和 Multi-SWE-bench 的仓库 | **原生协作**：每人负责一个 feature，有消息信道 | **(c) 最佳**；(a) 可借用论文的通信失败分类；(b) 用 solo 对 coop |
| **MultiAgentBench / MARBLE** [2503.01935](https://arxiv.org/abs/2503.01935) | coding 场景 100 题 [repo](https://github.com/ulab-uiuc/MARBLE/tree/main/multiagentbench/coding) | 未提到 Docker，推断不需要 | — | ~30B 未查到；Llama-3.1-70B 62.10（论文） | 任务由 LLM 从 SRDD 生成 | 比较星形、链式、树形、图拓扑，**没有私有信息拆分** | (b)(c)；rubric 评分，所以 (a) 弱 |
| **DevBench（现名 DevEval）** [2403.08604](https://arxiv.org/abs/2403.08604) / [repo](https://github.com/open-compass/DevEval) | 22 个仓库、4 种语言、5 个阶段；各阶段题数未查到 | 是 | 未查到 | DeepSeek-Coder-33B 实现阶段：acceptance 4.4% / unit 5.5%（README） | 未查到 | 阶段之间交接，例如设计到实现 | (a)：检验设计文档有没有被用上；(c) |
| **ProjectEval** [2503.07010](https://arxiv.org/abs/2503.07010) / [repo](https://github.com/RyanLoil/ProjectEval) | 20 个项目、284 个测试用例 | 可选 | `run_judge.py` 可无容器运行，但需要 Selenium | ~30B 未查到；最好的是 GPT-4o，Pass@5 12.49 | 论文未讨论 | 三级输入（prompt、checklist、skeleton）可拆给不同 agent | (a) |
| **Commit0** [2412.01769](https://arxiv.org/abs/2412.01769) / [repo](https://github.com/commit-0/commit0) | 54 个库（README 写 57），lite 16 个 | 是 | 本地 Docker、Modal、E2B [execution_context.py](https://github.com/commit-0/commit0/blob/main/commit0/harness/execution_context.py) | ~30B 未查到；DeepSeek-V2.5 lite 16.55%（论文） | 都是热门 PyPI 库；论文的 10-gram 分析认为记忆不是主因 | 多文件，规格说明可只给部分 agent | (a)(b)(c) |

**Benchmark 小结**
- **不需要 Docker 的**：EvalPlus、LCB、ClassEval、RepoBench、CCE、APPS、CodeContests。可以直接在 `salloc` 或 `sbatch` 作业里本地跑。
- **需要容器的**：整个 SWE 家族、CooperBench、DevBench、Commit0。
- **信息不对称最天然的**：CrossCodeEval、RepoBench（跨文件上下文）、ClassEval（方法依赖）、CooperBench（feature 分工）。

---

## 2. 开源权重 coding 模型表（2025–2026）

**表的约定**
- **KV 形状**一列来自 config.json，写作 层数 / Q 头 / KV 头 / head_dim / hidden / vocab。
- **bf16 权重** `[估算]` = 参数量 × 2 字节；**KV/token** `[估算]` = 2 × 层数 × KV 头 × head_dim × 2 字节。
- SWE-V 指 SWE-bench Verified，括号里注明 scaffold，没写就是"未注明"。

| 模型 | 参数 / 架构 | 上下文 | SWE-V | LCB | 单张 H100 80GB | 同族多尺寸 | KV 形状 |
|---|---|---|---|---|---|---|---|
| **Qwen2.5-Coder** 0.5B–32B | dense；32B 为 32.5B [hf](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) | 0.5B–3B 为 32K；7B 及以上的卡片写 131,072，需要 YaRN（config 为 32,768） | 官方未报。第三方：32B Agentless 30.2、14B 19.4、7B 4.2 [2506.03524](https://arxiv.org/html/2506.03524)；32B OpenHands 零样本 7.0 [2412.21139](https://arxiv.org/html/2412.21139) | 技术报告 T16：0.5B 2.0 / 1.5B 6.1 / 3B 10.8 / 7B 18.2 / 14B 23.4 / 32B 31.4 [2409.12186](https://arxiv.org/html/2409.12186)；时间窗前后写法不一致，见存疑 | 14B 及以下 bf16 宽裕（14B 约 29GB）；32B bf16 约 65GB 加 KV 256KiB/token，**很紧**；官方有 AWQ、GPTQ-Int4 [AWQ](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ) | **是，6 个尺寸**；有 base 和 FIM | 7B：28/28/4/128/3584/152064；14B：48/40/8/128/5120；32B：64/40/8/128/5120 [config](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct/raw/main/config.json) |
| **Qwen3** dense 0.6B–32B（2504 版） | dense；32B 为 32.8B [hf](https://huggingface.co/Qwen/Qwen3-32B) | 原生 32,768，YaRN 到 131,072 | 官方未报。第三方：8B Agentless 14.6 / OpenHands 3.4 [2506.03524](https://arxiv.org/html/2506.03524) | 见表下 | 0.6B–14B bf16 都宽裕（8B 约 16GB，14B 约 30GB）；32B 约 66GB 偏紧，有官方 FP8 [FP8](https://huggingface.co/Qwen/Qwen3-32B-FP8) | **是，6 个尺寸，KV 头和 head_dim 全部一致** | 8B：36/32/**8/128**/4096/151936；14B：40/40/**8/128**/5120 `[复核]`；32B：64/64/8/128/5120 |
| **Qwen3-30B-A3B**（含 2507 版） | MoE，128 专家激活 8 | 2504 版 32K；2507 版原生 262,144 [hf](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507) | NVIDIA 实测 Thinking-2507 SWE-Bench（OpenHands）22.0 [hf](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) | 2504 版 v5：62.6 / 29.8（thinking / non）；2507 版 v6：Instruct 43.2、Thinking 66.0 | bf16 约 61GB 可行，KV 96KiB/token；有 FP8 | 同属 Qwen3 族 | 48/32/4/128/2048 [config](https://huggingface.co/Qwen/Qwen3-30B-A3B/raw/main/config.json) |
| **Qwen3-Coder-30B-A3B** | MoE，30.5B，激活 3.3B [hf](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | 原生 262,144，YaRN 到 1M | 官方数字只在图片里，未核实到文字；Nebius 用 OpenHands 实测 50.0 [hf](https://huggingface.co/nebius/SWE-rebench-openhands-Qwen3-30B-A3B)；CooperBench solo 21.6 | v5 43.1 / v6 36.0（第三方 [2603.16790](https://arxiv.org/html/2603.16790)） | bf16 约 61GB 可行；有 FP8 | 480B-A35B 单卡跑不了 | 48/32/4/128/2048/151936 `[复核]` |
| **Qwen3-Coder-Next**（2026-02） | 80B，激活 3B；混合结构：每 4 层只有 1 层 full attention，其余是 Gated DeltaNet [hf](https://huggingface.co/Qwen/Qwen3-Coder-Next) | 262,144 | SWE-Agent 70.6 / MiniSWE-Agent 71.1 / OpenHands 71.3 [2603.00729](https://arxiv.org/html/2603.00729v1) | v6 58.93（同上） | bf16 约 160GB、FP8 约 80GB，都放不下，只有 4-bit 现实 | — | **大部分层是递归状态，不是标准 KV** |
| **Qwen3.5 / 3.6**（2026） | VLM；混合 DeltaNet；27B dense、35B-A3B MoE 等 | 原生 262,144 | 3.5-27B 72.4；3.5-35B-A3B 69.2 [hf](https://huggingface.co/Qwen/Qwen3.5-27B)；3.6-27B 77.2（内部 scaffold）[hf](https://huggingface.co/Qwen/Qwen3.6-27B) | v6：3.5-27B 80.7；3.6-27B 83.9 | 27B bf16 约 56GB 可行；35B-A3B 建议 FP8 | 是（0.8B–397B） | 3.6-27B：64 层，24Q/4KV/256；**vocab 248,320，与 Qwen3 不同**；混合层 |
| **Devstral Small 1.0 / 1.1**（2505 / 2507） | 24B dense，基于 Mistral-Small-3.1 [hf](https://huggingface.co/mistralai/Devstral-Small-2507) | 128K | 1.0：46.8（OpenHands）；1.1：53.6（OpenHands）[mistral](https://mistral.ai/news/devstral-2507) | 官方未报；Multi-LCB 上 2505 为 23.2 [2606.20517](https://arxiv.org/html/2606.20517) | bf16 约 47GB 可行，KV 160KiB/token | **没有其他开源尺寸**（Medium 只开放 API） | 40/32/**8/128**/5120/131072 `[复核]`，**与 Qwen3-14B 的 KV 形状相同** |
| **Devstral Small 2**（2512） | 24B，带视觉，**发布即为 FP8**，Apache 2.0 [hf](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512) | YaRN（factor 48） | 68.0（未注明 scaffold） | 未查到 | FP8 可行 | Devstral 2 是 123B，单卡跑不了 | 文本部分同 Small 1.x |
| **gpt-oss-20b / 120b** | MoE，MXFP4：20b 为 21B / 激活 3.6B，120b 为 117B / 激活 5.1B [hf](https://huggingface.co/openai/gpt-oss-120b) | 131,072（YaRN×32） | 20b：37.4 / 53.2 / 60.7；120b：47.9 / 52.6 / 62.4（low / med / high，未注明 scaffold）[2508.10925](https://arxiv.org/html/2508.10925) | 官方未报；NVIDIA 实测 20b v6 61.0 [hf](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) | 都能放下；120b 留给 KV 的余量有限 | 是（2 个尺寸） | 20b：24/64/8/64/2880/201088；**sliding window 与 full 交替，带 attention sink**，KV 通信要改造 |
| **SWE-agent-LM-32B** | 基于 Qwen2.5-Coder-32B-Instruct [hf](https://huggingface.co/SWE-bench/SWE-agent-LM-32B) | 同基座 | 40.2（SWE-agent，单次，无 TTS）；7B 版 15.2 [2504.21798](https://arxiv.org/html/2504.21798) | 未查到 | 同 32B，偏紧 | 7B / 32B | 推定同基座（未逐个核对） |
| **DeepSWE-Preview** | 基于 Qwen3-32B [hf](https://huggingface.co/agentica-org/DeepSWE-Preview) | 64K | Pass@1 42.2（R2E-Gym scaffold，16 次平均）；hybrid TTS Best@16 59.0 | 未查到 | bf16 加 64K KV 超过 80GB，需要 FP8 `[估算]` | — | 推定同 Qwen3-32B |
| **Kimi-Dev-72B** | 基于 Qwen2.5-72B | 131,072 | Agentless 加 TTS 60.4（1×1 为 48.0）；SWE-Agent 模式 48.6 [2509.23045](https://arxiv.org/html/2509.23045) | 未查到 | bf16 约 145GB、FP8 约 73GB，**都不现实** | — | 80/64/8/128/8192 |
| **OpenHands-LM-32B / SWE-Gym / R2E-Gym / Skywork-SWE** | 都基于 Qwen2.5-Coder（-32B） | 32K–128K | 分数见表下 | 未查到 | 32B 都偏紧；R2E-Gym 的权重是 F32，下载体积翻倍 | 7B / 14B / 32B | 推定同基座 |
| **KAT-Dev-32B** | 基于 Qwen3-32B [hf](https://huggingface.co/Kwaipilot/KAT-Dev) | — | 62.4（未注明 scaffold） | 未查到 | 偏紧 | — | 推定同 Qwen3-32B |
| **CWM 32B**（Meta） | dense 64 层，local / global 3:1 [hf](https://huggingface.co/facebook/cwm) | — | 53.9，TTS 后 65.8 | v5 68.6 / v6 63.5 | 偏紧；**非商用、需申请（gated）** | — | 有 local 层 |
| **Seed-Coder-8B / Seed-OSS-36B**（字节） | dense | 8B 为 32K；36B 为 512K | 8B：Agentless 19.2 / OpenHands 11.2 [2506.03524](https://arxiv.org/html/2506.03524)；36B：56（OpenHands）[hf](https://huggingface.co/ByteDance-Seed/Seed-OSS-36B-Instruct) | 8B 24.7（2410–2502）；36B v6 67.4 | 8B 宽裕；36B bf16 约 72GB，需要量化 | 是（跨尺寸） | 8B：32/32/8/128/4096/155136 |
| **GLM-4.7-Flash**（30B-A3B） | MoE，**MLA 压缩 KV** [hf](https://huggingface.co/zai-org/GLM-4.7-Flash) | 202,752 | 59.2（未注明 scaffold） | v6 64.0 | bf16 约 62GB 可行 | GLM-4.5 / 4.5-Air 单卡跑不了 | MLA，不是标准 KV |
| **Nemotron-3-Nano-30B-A3B** | Mamba2 加 Transformer 混合 MoE，52 层里只有 6 层 attention [hf](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) | — | SWE-Bench（OpenHands）38.8，未写明是否 Verified | v6 68.3 | 可行，有 FP8 | — | 大部分层是 SSM 状态 |

**Qwen3 dense 的 LCB v5**（2024.10–2025.02，thinking / non-thinking）[2505.09388](https://arxiv.org/html/2505.09388) `[复核]`：

| 模型 | thinking | non-thinking |
|---|---|---|
| 4B | 54.2 | 21.3 |
| 8B | 57.5 | 22.8 |
| 14B | 63.5 | 29.0 |
| 32B | 65.7 | 31.3 |

**基于 Qwen2.5-Coder 的 SWE 微调模型的 SWE-V**

| 模型 | SWE-V | 出处 |
|---|---|---|
| OpenHands-LM-32B | 37.2 | [hf](https://huggingface.co/all-hands/openhands-lm-32b-v0.1) |
| SWE-Gym 32B（OpenHands） | 20.6 | [2412.21139](https://arxiv.org/html/2412.21139) |
| R2EGym-32B | 34.4 | [2504.07164](https://arxiv.org/html/2504.07164) |
| Skywork-SWE-32B | 38.0 | [hf](https://huggingface.co/Skywork/Skywork-SWE-32B) |

**对实验设计最有用的几点**
- **同族异构**：Qwen3 dense 0.6B–32B 的 KV 头都是 8 个、head_dim 都是 128，只有层数和 hidden 不同。跨尺寸做 KV 或 hidden 对齐，只需要处理层数映射和 hidden 投影。LatentMAS 用的就是 Qwen3-4B / 8B / 14B。
- **同架构、不同权重**：Qwen2.5-Coder-32B 衍生出的 SWE 微调系（SWE-agent-LM、Skywork、OpenHands-LM、R2E-Gym）可以拿来研究"同骨架、不同后训练"的 KV 兼容性。
- **跨族但形状对齐**：Devstral-Small-2507 和 Qwen3-14B 都是 40 层 × 8 KV 头 × 128 head_dim，hidden 都是 5120 `[复核]`。不同的只有 tokenizer（131,072 vs 151,936）和 Q 头数（32 vs 40，GQA 分组不同）。
- **要避开或单独处理的缓存结构**：Qwen3.5 / 3.6 和 Qwen3-Coder-Next（DeltaNet）、Nemotron-3-Nano（Mamba2）、GLM-4.7-Flash（MLA）、gpt-oss（sliding window 加 sink）都不是标准 KV，现有 KV 通信方法不能直接套用。

---

## 3. Agent 框架与执行环境

### 3.1 没有 Docker、只有 Apptainer 时能不能跑

| 框架 | 能否用 Apptainer | 证据 | 在 Nibi 上要注意的 |
|---|---|---|---|
| **mini-SWE-agent** | **能，原生支持** | `environments/singularity.py`："Execute code in a singularity or apptainer container" [src](https://github.com/SWE-agent/mini-swe-agent/tree/main/src/minisweagent/environments)。SWE-bench 用法页 FAQ："Docker isn't available on my HPC cluster" → "set `environment.environment_class` to `singularity`" [usage/swebench](https://mini-swe-agent.com/latest/usage/swebench/) `[复核]`。实现是先 `singularity build --sandbox <tmpdir> docker://...`，再 `exec --contain --cleanenv --fakeroot --writable` [doc](https://mini-swe-agent.com/latest/reference/environments/singularity/) | 设 `MSWEA_SINGULARITY_EXECUTABLE=apptainer`。sandbox 建在 `tempfile.gettempdir()` 下，**必须把 `TMPDIR` 指到 `$SLURM_TMPDIR`**：Alliance 文档说 `/tmp` 占用 RAM，而且不要在网络盘上用 fakeroot 建 sandbox。计算节点上 fakeroot 能不能用要实测。bubblewrap 环境是 "experimental"，它绑定的是宿主机 /usr，不加载 SWE-bench 镜像，不适用 |
| **SWE-agent / SWE-ReX** | **不能** | SWE-ReX 的 deployment 只有 `local`、`docker`（docker 或 podman）、`modal`、`fargate`、`remote`、`dummy`、`daytona` [config.py](https://github.com/SWE-agent/SWE-ReX/blob/main/src/swerex/deployment/config.py)；用 `gh search` 搜 singularity 和 apptainer，结果都是 0 | 变通办法：在 Apptainer 里起一个 swerex server，再用 `remote` 连过去 `[推断，无官方文档]` |
| **OpenHands** | 旧版不能；**2025 年之后的 SDK 和 benchmarks 能** | 旧 issue [#5294](https://github.com/OpenHands/OpenHands/issues/5294) "Apptainer Support" 因 stale 被关。SDK 有 `ApptainerWorkspace`："Running on HPC clusters"、"Docker daemon cannot be installed"，可选 `use_fakeroot`、`--nv` [doc](https://docs.openhands.dev/sdk/guides/agent-server/apptainer-sandbox)。benchmarks 仓库 PR #743 和 #745 已合并 `[复核]` | 用 host networking；fakeroot 不可用时可设 `use_fakeroot=False` |
| **SWE-bench 官方 harness** | 不能（只有 Docker 和 Modal） | issue #242 已 closed，维护者不打算支持其他容器 `[复核]`；PR #432 未合并 | 评分走 OpenHands `--apptainer`、sb-cli 或 Modal |
| **其他** | 见下 | 见下 | — |

**其他框架与已有实践**
- R2E-Gym 只支持 docker 和 kubernetes，源码里是 `assert backend in ["docker","kubernetes"]`。
- rLLM / DeepSWE 建议用 Kubernetes，要求 "200 CPUs and over 6 TB+ of disk"，并行 512 个容器 [rllm](https://github.com/agentica-project/rllm)。
- SkyRL 的 `examples/train/mini_swe_agent` 里有 singularity 分支 [SkyRL](https://github.com/NovaSky-AI/SkyRL/tree/main/examples/train/mini_swe_agent)。
- NVIDIA Nemotron 在 Slurm 上用 Apptainer `.sif` 加 writable tmpfs overlay，并自己加了内存 watchdog 和命令黑名单（`killall`、`pkill`）[nemotron](https://docs.nvidia.com/nemotron/latest/nemotron/super3/rl/swe.html)。
- 论文证据：ProRL Agent [2603.18815](https://arxiv.org/html/2603.18815v1) 在 rootless HPC 上用 `.sif` 加 `--fakeroot` 跑 SWE-Gym 和 Verified。

### 3.2 和白盒 hook 的兼容性

**框架那一侧只看得到文本**
- mini-swe-agent 默认通过 litellm 连接模型（`hosted_vllm/...` 加 `api_base`）[local_models](https://mini-swe-agent.com/latest/models/local_models/)。
- SWE-agent 原话 "all models that serve to an endpoint with an OpenAI-compatible API" [keys](https://swe-agent.com/latest/installation/keys/)。
- OpenHands 用 vLLM 或 SGLang 起 OpenAI-compatible endpoint [local-llms](https://docs.openhands.dev/openhands/usage/llms/local-llms)。
- 所以只要走 API，**latent/KV 通信就必须在推理侧实现**。
- **关键例外**：mini-swe-agent 的 `get_model_class` 接受完整 import 路径，并且 "takes precedence"。可以自己写一个 Model 类，在同一进程里直接调 HF 模型，完全不经过 API，KV 和 hidden state 都拿得到。

**推理后端**

| 后端 | hidden state 输出 | embeds / latent 输入 | KV 读写 | Nibi wheelhouse `[实测 avail_wheels]` |
|---|---|---|---|---|
| **HF transformers** | `output_hidden_states=True`；注意 `hidden_states[-1]` 不一定等于 `last_hidden_state` [doc](https://huggingface.co/docs/transformers/main/en/main_classes/output) | `inputs_embeds` | `DynamicCache` 和 `past_key_values` 完全可读写，前缀 cache 可以 deepcopy 后复用 [kv_cache](https://huggingface.co/docs/transformers/main/en/kv_cache) | 最新 5.18.0；**旧版本也在**，包括 4.50.0/4.50.3、4.52.4、4.53.3、4.57.6，正好覆盖 C2C、KVComm、Cheng 审计固定的版本 |
| **SGLang** | `return_hidden_states`；服务端开 `--enable-return-hidden-states`，模式为 `last` 或 `full`；会因为 cuda graph 重建降低吞吐 [sampling_params](https://docs.sglang.io/basic_usage/sampling_params.html) | `input_embeds` | 外部 KV 注入没有官方接口 | 0.5.15.post1 |
| **vLLM** | v0.18.0 起可以用 `--speculative_config '{"method":"extract_hidden_states"}'` 加 connector，**结果写成磁盘上的 `.safetensors`**，响应里只返回路径；与 chunked prefill 不兼容 [blog](https://vllm.ai/blog/2026-03-30-extract-hidden-states)。把 hidden states 直接放进响应的 RFC #48743 仍然 open。CVE-2026-44223 影响 0.18.0 到 0.19.1 | `--enable-prompt-embeds`，以 base64 编码的 tensor 传入；与 prefix caching 的冲突现状不明 [prompt_embeds](https://docs.vllm.ai/en/latest/features/prompt_embeds.html) | KV connector（LMCache、Nixl 等）是 "experimental"；**不能修改 KV**。LatentMAS README 原话："vLLM does not officially support modifying KV-cache … We modify the partial inner package inside vLLM" | 0.18.1 到 0.25.0；从 0.22.0 起用 cuda/13.2 编译 `[本地 VLLM.md]` |
| **LMCache** | — | — | 可以跨引擎复用 KV，CacheBlend 支持非前缀位置 [docs](https://docs.lmcache.ai/) | **wheelhouse 里没有** |

**已有 latent/KV 多 agent 工作用的后端**

| 工作 | 会议 | 后端 | 能否直接迁到 coding |
|---|---|---|---|
| LatentMAS [2511.20639](https://github.com/Gen-Verse/LatentMAS) | ICML 2026 | 以 HF 为主；HF 加 vLLM 的混合模式只让 vLLM 做最终文本生成；README 说复现论文结果要用 HF 后端 | 已经测过 HumanEval+ 和 MBPP+ |
| C2C [2510.03215](https://github.com/thu-nics/C2C) | ICLR 2026 | `transformers==4.52.4` | 需另做 |
| KVComm（Shi 等）[2510.03346](https://github.com/Zephyroam/KVComm) | ICLR 2026 | `transformers==4.53.3` | 需另做 |
| KVCOMM（Ye 等）[2510.12872](https://github.com/FastMAS/KVCOMM) | NeurIPS 2025 | `transformers==4.50.2`，DynamicCache | **已含 HumanEval 协作编程** |
| DroidSpeak | NSDI 2026 | vLLM 加 LMCache | 官方代码未查到 |

**常见做法和取舍**
1. **纯 HF，自写 agent loop**：最灵活，上表的工作都走这条路，但吞吐低。适合 MVP，比如 CCE、ClassEval、LCB 这类单轮或少轮任务。
2. **SGLang：注入 embeds，返回 hidden state**：两样都在 API 里，适合把 soft-token 或 latent-embedding 类方法放大规模。但 KV 级方法（KVComm、C2C）仍然要改引擎。
3. **LMCache 或 KV connector 共享 KV**：适合同模型或同架构变体之间复用 KV，DroidSpeak 就是这样。Nibi 的 wheelhouse 没有 LMCache，需要提工单申请 wheel。
4. **自建 OpenAI-compatible 薄服务，把 latent 通信藏在服务端**：现成开源实现未查到。mini-swe-agent 的自定义 `model_class` 更轻，可以替代这一层。
5. **公平性提醒**：LatentMAS 的速度对比，一边是 vLLM 加速的 TextMAS，一边是 HF 实现的 latent，实现不一致（见本仓库 `deep_read/zou2025latent.md`）。**所有臂应在同一后端上跑**，或者只报告 token 数和 FLOPs，不报墙钟时间。

**推荐的组合**
- **MVP**：HF transformers（固定 4.5x 版本）加自写的 2 到 3 个 agent 流水线。在 `salloc` 申请的 1 张 H100 上，两个模型同进程加载。
- **SWE 阶段**：mini-swe-agent 的 singularity 环境，加自定义 HF Model 类；评分用 OpenHands benchmarks 的 `--apptainer`。

---

## 4. Nibi 集群约束

所有引用均来自本地只读文档 `/cvmfs/soft.computecanada.ca/custom/docs/en/`。

| 主题 | 原文要点 | 文件 |
|---|---|---|
| 规模与 GPU | "134,400 CPU cores and 288 H100 NVIDIA GPUs"；GPU 节点 36 台，每台 112 核、2000G 内存、11T 本地盘，"8 x Nvidia H100 SXM (80 GB), connected via NVLink"；另有 6 台 AMD MI300A 节点，**目前没有 ROCm 模块** | `Nibi.md` |
| GPU 申请语法 | `--gpus=h100:1`，或 `--gpus-per-node=h100:2`、`:3`、`:4` | `Nibi.md` |
| MIG | "Approximately half of the GPU nodes are configured with MIG"，规格有 `h100_1g.10gb`、`h100_2g.20gb`、`h100_3g.40gb` | `Nibi.md` |
| 每卡 CPU 和内存 | 每张 H100-80gb 的 bundle 是 **14 cores, 250 GB**（推荐值相同），RGU 12.2；3g.40gb 推荐 6 核、124 GB；2g.20gb 推荐 4 核、62 GB；1g.10gb 推荐 2 核、31 GB | `Allocations and compute scheduling.md`（Ratios in bundles 一节） |
| **外网** | "**All nodes on Nibi have internet access, no special firewall permission or proxying is necessary.**" | `Nibi.md`（Site specifics → Internet access） |
| 模型下载 | "models must be downloaded on a login node to avoid idle compute while waiting for resources to download"；默认缓存在 `$HOME/.cache/huggingface/hub` | `VLLM.md` |
| 模型下载（草稿页） | `HF_HUB_DISABLE_XET=1 hf download --max-workers=1 ...`："hf_xet … leads to failures on our systems" | `Large Language Models (LLMs).md`（标注为 draft） |
| 离线运行 | 无网环境要设 `HF_DATASETS_OFFLINE=1` 等变量（Nibi 有网，但这样做可以避免作业被网络卡住） | `Huggingface.md` |
| **Docker** | "Using Docker on a multiuser cluster creates security risks, therefore **we do not make Docker available** on our HPC clusters." 不能用 `sudo` | `Apptainer.md` |
| Apptainer 用法 | `module load apptainer`；用 GPU 要加 `--nv`；作业中用 `-W ${SLURM_TMPDIR}`，因为 "`/tmp` and similar filesystems use RAM"；"One should not be running programs (including Apptainer) on a login node"；`apptainer build x.sif docker://...` 通常不需要额外权限；1.1 版之后 `--fakeroot` 不用申请；"Avoid building a sandbox image using `--fakeroot` on networked filesystem(s)"；`APPTAINER_CACHEDIR` 要设到非网络盘；SIF 只占 1 个文件配额，sandbox 会占成千上万个 | `Apptainer.md` |
| Apptainer 版本 | `module spider apptainer` 列出 1.2.4、1.3.4、1.3.5、1.4.5、1.5.4（1.5.4 依赖 StdEnv/2026）。登录节点 `max_user_namespaces=1030638`，计算节点**未查** | `[实测]` |
| `$SLURM_TMPDIR` | 作业专用的本地盘，作业结束即清空，输出必须拷回；Nibi 可用约 **3T**（盘有 3T 和 11T 两种）；"if the job requests less than a whole node, then other jobs may also write to the same filesystem" | `Using node-local storage.md` |
| 存储 | /home、/project、/scratch 都在 VAST 全闪存上，按文件表观大小计费；scratch 软配额 1 TB，可超出 60 天，之后禁止写入 | `Nibi.md` |
| 作业时长与数量 | 最长 7 天；分区按 3h、12h、24h、72h、7d 划分，"Shorter jobs have access to more resources"；处于 pending 或 running 的作业最多 1000 个，"Each task of a job array counts as one job" | `Job scheduling policies.md` |
| Python 包 | 有 wheel 时用 `--no-index`；没有的可以预下载，或提工单申请 | `Python.md` |
| Brine（SHARCNET AIaaS） | 基于 LiteLLM 的 OpenAI-compatible 托管模型服务。**它是黑盒，不能用于 latent 臂**，最多做文本基线或 judge，而且模型和本地臂不同。不要提交敏感数据 | `Nibi.md` |

**wheelhouse 里有什么** `[实测 avail_wheels，2026-10-17]`
- 有：vllm 0.25.0（另有 0.18.1–0.24.0）、sglang 0.5.15.post1、transformers 5.18.0（另有 4.50–4.57）、torch 2.14.1、flash_attn 2.8.3、litellm 1.72.4、accelerate 1.14.0、autoawq 0.2.5、bitsandbytes 0.50.1、datasets 5.0.0。
- 没查到：lmcache、swebench、mini-swe-agent、swe-rex、evalplus、openhands-ai、llmcompressor。这些多是纯 Python 包，可以预下载，或提工单申请 wheel。

---

## 5. 建议

### 5.1 最小可行实验（MVP）

**Benchmark**
1. **CrossCodeEval（Python 2,665 题）**：sender 只看跨文件上下文，receiver 只看当前文件。
   - 实验臂：true KV / 别题 KV（deranged）/ 无 / 文本中继 / skyline（receiver 直接看原文）。
   - 这正好对应 KVComm 的"上下文给 sender、问题给 receiver"设定，也对应 Cheng 等人"receiver 必须依赖私有信息"的审计原则。
   - EM/ES 和标识符匹配是**不执行代码的确定性指标**，便宜、可重复。
   - RepoBench v1.1 的 cross_file_first 可以作复测集。
2. **ClassEval（100 类，410–412 个方法）**：按方法拆给 2 到 3 个 agent，每个 agent 只看到自己负责的方法签名和部分字段说明，用 latent 或 KV 交换"其他方法的实现意图"。
   - 指标：方法级测试通过率，以及跨方法调用是否正确。
   - 不需要 Docker，在作业里直接跑 unittest。
3. **辅助**：
   - LiveCodeBench：取模型 cutoff 之后的切片，例如 Qwen2.5-Coder 用 v5 或 v6 的增量，做等 token / 等 FLOPs 的预算对照。
   - HumanEval+/MBPP+：只用来复现 LatentMAS 的基线。

**模型**
1. **Qwen3-8B 与 Qwen3-14B**：同族异构，bf16 合计约 46GB `[估算]`，可以同进程放在 1 张 H100 上。单模型调试可以只申请 MIG 的 `h100_3g.40gb`，节省 RGU。
2. **Devstral-Small-2507（24B）**：跨族，和 Qwen3-14B 的 KV 形状相同。和 14B 同时加载约 77GB `[估算]`，单卡几乎没有 KV 余量。可以申请 2 张卡（`--gpus-per-node=h100:2`，最多 28 核），或者用 FP8。
3. 可选的 coder 专精对照：Qwen2.5-Coder-7B 或 14B。它有 base 和 FIM 版，CCE 的原生用法是给 base 模型的。C2C 已经发布了 Qwen2.5 到 Qwen3 的 fuser。

### 5.2 SWE-bench 级实验是否现实

**结论**：可行，但应作为第二阶段，先用小子集。

**主要障碍**
1. **白盒推理的吞吐**：latent 臂必须在进程内用 HF（或改过的 SGLang）跑，没有 continuous batching 和 paged attention。SWE 轨迹几十轮、上下文 32K 到 128K，成本会被实验臂数和种子数成倍放大。例如 Verified 500 题 × 4 个臂 × 3 个种子 = 6,000 条轨迹 `[算术]`。单条轨迹的 GPU 时间未实测。
2. **容器化**：需要逐个实例把镜像转成 SIF，或在运行时建 sandbox。
   - Epoch 的瘦身镜像 Verified 合计约 30 GiB（Docker 分层），但 SIF 不共享层，**总体积未查到**，需要抽 5 到 10 个实例实测。
   - sandbox 必须放在 `$SLURM_TMPDIR`。
   - 计算节点上 fakeroot 和 user namespace 能不能用未验证。
   - scratch 的 1 TB 软配额要事先算好。
3. **隔离与礼仪**：Apptainer 没有 cgroup 隔离，agent 执行的命令可能占满节点内存或误杀进程。要像 NVIDIA 那样加 watchdog 和命令黑名单，并且只在自己申请到的资源里跑。
4. **CPU 配比**：每张 GPU 只配 14 核，但并行跑测试很吃 CPU。评分是纯 CPU 任务，建议**拆成 CPU 节点上的作业**（Nibi 有 700 台 192 核的 CPU 节点），并把多个短任务打包成一个作业，同时注意 1000 个作业的上限。
5. **评测有效性**：Verified 污染严重，24B 级模型已接近 70% 分数。结论应该用 SWE-bench-Live 或 SWE-smith 的新任务交叉验证。Pro 上 ~30B 只有 3–16%，信噪比太低。CooperBench 最贴近协作研究，但只支持 Docker、Modal 或 GCP，要移植。

**降低成本的路径**
- 用 Agentless 式**固定 2 到 3 个阶段的流水线**：定位 agent 读 issue 和仓库，把 KV 或 latent 传给修复 agent。轮数少、上下文可控，HF 白盒能承受。
- 文本基线在同一个 HF 后端上跑，保证可比。
- 先在 SWE-bench Lite 或 Verified 里抽 50 到 100 题跑通；评分用 OpenHands `--apptainer`，或者 sb-cli（Nibi 有外网，只上传 patch）。

---

## 6. 存疑与未查到

- **Qwen3-Coder-30B-A3B 和 480B 的官方 SWE-V** 只在图片里，常被引用的 51.6 和 69.6 未核实到文字出处。本 memo 改用第三方数字（Nebius 50.0；Mistral 表引用的 69.6）。
- **Qwen2.5-Coder 的 LCB**：报告正文和表格不一致，正文写 7B 为 37.6，表中是 18.2；时间窗一处写 2407–2409，另一处写 2407–2411。
- **gpt-oss 的 SWE-V** 未说明 scaffold，也不确定是否用了 477 题子集。
- **未注明 scaffold 的分数**：Devstral Small 2、Qwen3.5 / 3.6、KAT-Dev、GLM-4.7-Flash。
- **SWE-bench Pro**：gpt-oss-20B 和 120B 在论文里都是 16.2，可能是笔误。
- **各处计数冲突**

| Benchmark | 冲突 |
|---|---|
| ClassEval 方法数 | 410 vs 412 |
| SWE-Gym Lite | 230 vs 234 |
| SWE-smith | 50k vs 52k |
| R2E-Gym | 8.1K vs 8.7K |
| Multi-SWE-bench | 1,632 vs 2,132 |
| Commit0 | 54 vs 57 |

- **计算节点上的情况**：外网（文档说全部节点都有，但没在计算节点实测）、fakeroot、user namespace，都需要在 `salloc` 里实测。
- **SWE 微调模型的 config**：SWE-agent-LM、Skywork、DeepSWE 等是按基座推定的，没有逐个核对。
- **同族 tokenizer 是否逐 token 一致**：未核实。Qwen2.5-Coder 小尺寸和大尺寸的 vocab 行数分别是 151,936 和 152,064，应该只是 padding 差异。
- **未查到的 ~30B 分数**：APPS、CodeContests、Multi-SWE-bench、SWE-bench-Live、MARBLE、ProjectEval、Commit0。
- **其他未查到**：LCB v6 之后的版本；DevBench 各阶段的题数；SIF 化之后 SWE-bench 镜像的总体积。
