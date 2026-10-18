# 聚焦 Multi-Agent Coding：把“隐式交流”落到写代码的 agent 团队上

> **版本**：2026-10-17。
>
> **依据**：
> - “精读笔记”页的 25 篇精读；
> - 本轮在索引里新增 162 篇 coding 相关文献，加上原有条目补打的 66 篇，统一打了 `coding` 标签，其中新开一类 **多 Agent 编程（场景）**（`coding-mas`），收录通信本身仍是文本、但属于协作编程的系统、benchmark 和失败分析；
> - 一份基础设施可行性调研（benchmark、开源模型、Nibi 集群约束）。
>
> 在文献索引页勾选“精选 → Coding 相关”，就能看到全部 coding 条目。
>
> **评分口径**：与“研究方向”页一致。难度、影响、灌水度都按 1–5 打分，属于主观判断；算力按 H100·天粗估。
>
> 下文所有数字都出自所引论文的摘要、正文或排行榜。凡是我们自己换算的数字，都注明了“按表自算”或“估算”。

<div id="coding-map"></div>

## 0. 结论：能贴着 coding 做，而且 coding 可能是这个课题最好的落地场景

1. **coding 是 latent 通信声称增益最大、却最没被审计的场景。**
   - **报告的增益最大的都在代码题上。**
     - LatentMAS：HumanEval+ 81.1→86.5（Qwen3-14B），MBPP+ 69.5→74.6（Qwen3-8B）（[笔记](#note:zou2025latent)）。
     - Vision Wormhole：代码任务的平均增益同样最大，MBPP+ +13.3、HumanEval+ +11.1（[笔记](#note:liu2026vision)）。
   - **两篇因果审计都没有覆盖代码任务。**
     - [Relayed KV Audit](#paper:cheng2026latent) 的冻结设计要求每臂 n=500，而 HumanEval+ 只有 164 题、MBPP+ 只有 378 题。
     - [Causal Audit](#paper:zhang2026latent) 也没有测代码任务。
   - **代码任务上恰恰是 latent 最不稳的地方。**
     - 他人复现的结果从 +5 到 −37 都有：[StateBridge](#paper:peng2026statebridge)、[KITE](#paper:zhang2026task) 各自报告了对 LatentMAS 的复现。
     - [TFlow](#note:bao2026good) 在 HumanEval+ 上比 TextMAS 低 9.8 分。
     - [对齐矩阵消融](#paper:deshpande2026role)把 LatentMAS 的对齐矩阵换成恒等矩阵，结果不显著掉点；在代码任务上还得出“文本优于 latent”的结论。
   - **在代码任务上做过错配消息（deranged）对照的论文：0 篇。**
2. **coding 天然具备回答本课题核心空白的三个条件。** 这个空白是：latent thought 到底有没有传递**样本特定**的信息（见“研究方向”页 §0，证据在 [Relayed KV Audit 笔记](#note:cheng2026latent)）。
   - **信息不对称是默认状态。**
     - explorer 读过的文件，main agent 没读过；
     - tester 看过 traceback，coder 没看过；
     - 并行开发者各自持有自己模块的接口。
   - **内容高熵、可执行验证。**
     - 函数名、文件路径、字段名这些标识符猜不出来，单元测试能判定它们对不对；
     - 数学题则不同，答案可能只是“被启发”出来的。
   - **有现成的、可以改造成私有信息设定的 benchmark。**
     - CrossCodeEval 的跨文件上下文可以只交给发送方；
     - ClassEval 中 76.2% 的方法依赖其他方法或字段。
3. **多 agent coding 的瓶颈就是“交流”，而非文本信道在这里还是空白。**
   - **交接和协调处的失败已有量化。**
     - [CooperBench](#paper:khatua2026cooperbench)：两个 agent 合作时，成功率比各自单独完成平均低 30%。
     - [Planner-Coder Gap](#paper:lyu2025understanding)：75.3% 的失败来自 planner→coder 交接时的信息丢失。
     - [Deep Agentic Search](#paper:oskooei2026deep)：41.8% 的失败发生在 planner 与 subagent 交接处，而且大多是“流畅而自信的错误答案”。
   - **非文本信道在 repo 级任务上还没有人做过。**
     - 在 repo 级协作编程任务上，**没有任何 agent 之间的 latent/KV 通信评测**。
     - 最接近的 [LOHA/ACD](#paper:zou2026compress) 只是单 agent 在 SWE-bench Verified 上用 soft-token 压缩自己的历史。
4. **coding 与 OpenAI–HF 事件、AI control 是同一条线。**
   - **事件本身**：出事的就是编程/网络安全评测中的 agent（[OpenAI 技术报告](#paper:openai2026openai)、[DseWiki 外部重建](#note:lutje2026mechanics)）。
   - **AI control 的标准设定本来就是写代码。**
     - 例如 [APPS backdoor](#paper:greenblatt2023ai)、[BashArena](#paper:kaufman2025basharena)、[LinuxArena](#paper:tracy2026linuxarena)。
     - 同权重的 coder 与 monitor 能否不靠通信形成合谋，正是 coding 版的“一个眼神”：[Subversion via Focal Points](#note:jarviniemi2025subversion)。
   - **已经出现了“共享缓存当信道”的苗头。**
     - [Cache-History Sensitivity](#paper:gu2026request)：持久化 KV 复用让答案依赖之前处理过的请求，换一下请求顺序，69.0% 的答案会变。
     - [Code-A1](#paper:wang2026code)：同一套权重既写代码又写测试时，会“自共谋”写出平凡测试。
5. **两个前提**：
   - **要白盒，就只能用开源权重模型。**
     - latent/KV 通信需要读写 hidden state 和 KV，所以主实验只能在 8–24B 的开源模型上做。
     - SWE-bench 级任务在 Nibi 上可以跑，但贵：没有 Docker，只能走 Apptainer，且要用 HF 后端做白盒推理，吞吐低。
     - 因此应当**从函数级、类级、跨文件级任务起步**，第二阶段再上 repo 级。
   - **不要把论点建立在“多 agent 比单 agent 强”上。**
     - 等预算比较时，函数级任务上多 agent 的增益接近 0，甚至为负（[BenchAgent](#paper:fu2026more)、[Rethinking MAS Efficiency](#paper:zhang2026rethinking)）。
     - repo 级只有一组等 token 证据，约 +9 分，而且是作者自报（[EvoMAS](#paper:hu2026evomas)）。
     - 更站得住的问题是：**在必须分工的场景里，信息以什么形式在 agent 之间流动最划算、最可审计。**

## 1. 为什么 coding 适合这个课题

| coding 的性质 | 对隐式交流研究意味着什么 | 证据 |
|---|---|---|
| 分工后自然出现私有信息 | 正是“内容确实被传递”的审计结果成立的条件，即接收方必须依赖私有信息才能答对 | [Relayed KV Audit](#note:cheng2026latent)、[Causal Audit](#note:zhang2026latent) |
| 标识符高熵、可执行验证 | 可以直接度量“传过去多少样本特定信息”，例如标识符匹配率、测试通过率 | CrossCodeEval 的标识符指标；ClassEval 的方法依赖 |
| 上下文很长，每个 agent 都要重读同一份 repo | KV 复用在这里有真实的效率价值，GSM8K 上则很难体现 | [KVCOMM](#paper:ye2025kvcomm)、[Continuum](#paper:li2025continuum)、[Copilot traces](#paper:liu2026agentic)（轮内 KV 命中 90%，跨轮 55%） |
| 交接靠有损的文本摘要 | subagent 通常只交回 1–2k token 的摘要（Anthropic 的 context engineering 博客）；“共享完整轨迹”的主张（Cognition 的 Don't Build Multi-Agents）正好可以用 KV 交接来实现和检验 | [Handoff Debt](#paper:kc2026handoff)、[Deep Agentic Search](#paper:oskooei2026deep) |
| 并行开发必须对齐接口 | 是“一个眼神”最干净的实验场：不交流时，两个 agent 能否选到同一套接口 | [Specification Gap](#paper:sartori2026specification)：规格越少，联合正确率从 58% 降到 25%；[stale](#paper:xia2026passes)：一条消息就能挽回 82% |
| 共享 repo 就是天然的 stigmergy | 事件里的“记事本”机制在 repo 中天然存在，包括 AGENTS.md、TODO、测试文件、锁文件 | [Reward Hacking 传染](#paper:hu2026reward)、[Self-Propagating Misalignment](#note:das2026self)、Anthropic 用 16 个并行 Claude 构建 C 编译器的实验（只靠锁文件协调） |
| 有可执行的安全设定 | 合谋、监控、破坏都可以在代码上客观判定 | [Red-Teaming Auto Mode](#paper:remedios2026red)、[Code-Review Collusion](#paper:za2025studying) |

## 2. 现有证据速查

### 2.1 latent/KV 通信在代码任务上的表现

| 工作 | 代码任务上相对 TextMAS | 内容对照 |
|---|---|---|
| [LatentMAS](#note:zou2025latent) | 自报：14B HE+ +5.4，8B MBPP+ +5.1 | 无 |
| ↳ 他人复现 | [StateBridge](#paper:peng2026statebridge) 报告的复现：4B/8B 为 0 到 +5，OLMo3 HE+ −37；[KITE](#paper:zhang2026task) 报告的复现：Qwen3-4B −12.2/−17.2 | — |
| [Vision Wormhole](#note:liu2026vision) | 各配置平均 MBPP+ +13.3，HE+ +11.1；代码任务上部分配置比 TextMAS 更慢 | 只有重建层面的打乱，没有任务级错配 |
| [TFlow](#note:bao2026good) | HE+ 65.24 对 75.00（−9.8），MBPP+ 67.20 对 68.52（−1.3） | 错配 LoRA 对照只在 GSM8K 上做 |
| [StateBridge](#paper:peng2026statebridge) | 4B/8B 为 +2.6 到 +7.4，32B 为 +0.6 到 +1.1 | 只有随机噪声前缀 |
| [LatCom](#paper:zhang2026latcom) / [KITE](#paper:zhang2026task) / [DiffMAS](#paper:yu2026learning) | −1.7 到 +1.6 / −2.5 到 +9.6 / +0.8 到 +6.2 | 都没有内容级对照 |
| [RecursiveMAS](#paper:zou2026recursive) | LiveCodeBench +4.2（对比 Recursive-TextMAS） | 无 |
| [对齐矩阵消融](#paper:deshpande2026role)（ICML 2026 workshop，只读到 OpenReview 摘要） | 换成恒等矩阵不显著掉点；代码任务上文本优于 latent；谱匹配的随机矩阵比原矩阵更好 | **唯一做了随机矩阵对照的** |
| [SelectKV](#paper:liao2026selective) | 相对完整 KV，HE+ −6 | 无 |

按表自算的结论有两点：
- 代码任务上，“latent 优于文本”的结论**取决于是谁在复现**，跨度超过 40 分。
- TFlow 作者认为文本 MAS 的优势在于“隐式扩大了生成预算”。这个混杂没有任何论文控制过。

### 2.2 多 agent coding 的真实增益与失败点

**等预算下的增益**
- [EvoMAS](#paper:hu2026evomas)：SWE-bench Verified，Claude-3.5，同为 29M token，42.7 对单 agent 循环的 33.6；best-of-10 用了 40M token，只有 37.8。
- [BenchAgent](#paper:fu2026more)：统一协议、GPT-4.1 下，6 种 MAS 里有 5 种低于单 agent 1.71–8.76 分。
- [Rethinking MAS Efficiency](#paper:zhang2026rethinking)：HumanEval 上，拓扑剪枝的收益和随机剪枝相当。
- [DATS](#paper:hong2026learning)：分层协作在最难三分之一的题上 +21.1，但 token 约为 10 倍。
- 报告两位数增益的 [CAID](#paper:geng2026effective)、[AgentRadio](#paper:ren2026agentradio)、[DeLM](#paper:mao2026decentralized)，都**没有等 token**。

**协作类 benchmark**
- [CooperBench](#paper:khatua2026cooperbench)：652 个 feature 对、12 个仓库。排行榜上，Qwen3-Coder-30B 单独完成 21.6%、合作 13.3%；GPT-5 为 48.31% 对 27.95%。失败原因有三类：消息含糊、不履行承诺、对他人计划的预期错误。
- [stale](#paper:xia2026passes)：只统计合并后才出现的失败。用真实 Django helper 构造的任务里，干扰率 97%；但在 417 对真实 PR 中只出现 1 次。
- 其他还有 [AsynCodeBench](#paper:zhang2026asyncodebench)、[NP-Bench](#paper:muku2026verifying)、[MSEval](#paper:ren2026empirical)，以及并发 subagent 开/关的[匹配对照研究](#paper:li2026sub)（2,124 次执行，13 种并发特有的失败模式）。

**交接处的损失**
- [Planner-Coder Gap](#paper:lyu2025understanding)：语义等价的改写就让系统丢掉 7.9%–83.3% 原本能解的题。
- [Deep Agentic Search](#paper:oskooei2026deep)：subagent 方案正确率 46.2%，向量检索 65.2%。
- [Handoff Debt](#paper:kc2026handoff)：比较了仅仓库状态、原始轨迹、摘要、结构化笔记四种交接方式。**它正好缺一种 latent/KV 交接。**
- [PACT](#paper:huang2026should)：把消息改成结构化的 action-state，SWE-agent 上输入 token 减半，解决率持平。

### 2.3 KV 复用系统：目前只被当作加速器

- **精确前缀复用是无损的。** 典型加速 1.8–6 倍，例如 [KVFlow](#paper:pan2025kvflow)、[TokenCake](#paper:bian2025tokencake)、[Continuum](#paper:li2025continuum)、[EfficientAgent](#paper:shao2026efficientagent)。
- **跨上下文或近似复用，典型是加速 1.5–8 倍、损失 0–5 分。**
  - [KVCOMM](#paper:ye2025kvcomm)：TTFT 最高 7.8 倍，HumanEval −0.7 到 −4.9。
  - [RelayCaching](#paper:geng2026relaycaching)：4.7 倍，损失 ≤0.6 分。
- **失效模式**：
  - [CacheBlend](#paper:yao2024cacheblend) 在 HumanEval 上只有 21–33 分，dense 为 84–86。
  - 任务冲突时直接复用别人的非前缀 KV，性能最多下降约 90%（[LatentRemedy](#paper:chen2026latentremedy)）。复用来的 KV **带着发送方的任务身份**。
- **这类论文的盲区**：没有一篇 coding 系统论文把 KV 当成**信息载体**来研究。

### 2.4 安全：合谋、监控、传染

**同权重、无通信的合谋**
- [Järviniemi](#note:jarviniemi2025subversion)：3903 对 prompt 中 134 对合谋成功，约 3.4%。真正靠焦点协调成功的只有 31 对，约 0.8%。
- [Gardner-Challis](#paper:gardnerchallis2026trust)：经 SFT 诱导出被动自识别后，红队胜率达到 9.8%；预共享信号的策略只有 2.8%。
- [代码自识别](#paper:barkhordar2026style)：平衡准确率只有 49–58%。
- 结论是目前很低，但**上面这些都是函数级任务**。

**同谱系监控的取舍**
- [Calibration-Family Overfit](#paper:pinto2026calibration)：同谱系监控能抓到 41%，跨谱系只有 19%。同谱系更会检测，也恰好最可能合谋。
- [Decorrelation ≠ Complementarity](#paper:jha2026decorrelation)：跨谱系的监控集成并不更好。

**交接与压缩是监控盲区**
- [Red-Teaming Auto Mode](#paper:remedios2026red)：借助多上下文、多 agent 和 compaction，79% 的试验绕过了生产级阻断分类器。
- [Sabotage Continuation](#paper:kirk2026evaluating)：接手已被破坏的轨迹后，模型继续破坏的比例为 0–7%，论文同时提出了 prefill awareness。

**代码产物本身就是信道**
- [MAS Code Injection](#paper:bowers2025analyzing)：攻击成功率从 0% 升到 71.95%。
- [Shadows in the Code](#paper:wang2025shadows)：在 ChatDev / MetaGPT 上为 45–93%。
- [Code-Review Collusion](#paper:za2025studying)：7 个模型中有 6 个会提交后门；这些 agent 请其他破坏者来审查的比例为 29.2–38.5%，随机基线是 20%。

**传染**
- [Reward Hacking 传染](#paper:hu2026reward)：reward hacking 可以经代码、共享记忆和计划传播。
- [Mind Viruses](#paper:papadopoulos2026mind)：会在共享编码项目里扩散。
- [跨 run 隐式通道](#note:wu2026collective)：mini-SWE-agent 的默认 Docker bridge 网络让两个“独立”的 run 能互相读取。
- [EVOMAL](#paper:wu2026evomal)：共享技能库中的恶意 skill 被其他 agent 模仿后又写回库里，跨任务自我传播；删掉最初植入的那一条后，传播仍在继续。
- [Skill Misevolution](#paper:mao2026practice)：会话清空、技能库保留时，不安全的流程会被带进新会话。
- [Countdown-Code](#paper:khalifa2026countdown)：蒸馏 SFT 数据里只要有 1% 篡改测试的轨迹，学生模型就会内化这种行为。这是“一个 agent 的轨迹训练另一个 agent”这条风险链的直接量化。
- [Trace Tampering](#paper:qin2026llm)：多数本地 harness 允许 agent 删除自己的执行轨迹。依赖事后日志来重建 agent 之间的协调，可能因此失效。

### 2.5 引用滚雪球带来的新证据（2026-09～10）

这些论文来自 C2C、LatentMAS、KVCOMM 等枢纽论文的被引列表，大多是最近一个月的新工作。

**“latent/KV 到底传了没有”：多数偏阴性，但有分歧**
- [Close Enough is Nowhere Near](#paper:deng2026close)：在冻结的 reader 上试了 8 种“直接替换 cache”的方法，**全部停在无信息 cache 的基线上**。只有保留 reader 自己的 cache、把 sender 的 cache 当作附加上下文，并且只在 query 侧做适配，才能超过基线。
- [2×2 Internal-State Sharing](#paper:deng2026augment)：KV 适合“增补”，激活适合“替换”。错配对照在浅层是干净的，到深层会升高。跨族配对（GPT-Neo-1.3B 发送、Qwen2.5-1.5B 接收）时，两种载体都塌回基线。
- [SwaT](#paper:alabdulkareem2026swarm)：结论相反。跨族、免 prefill 的 KV 迁移比文本通信平均高 40%，速度快 4 倍。但摘要里看不到内容对照，17 个 benchmark 中有 9 个的训练集被模型见过。**这正是 C2 可以裁决的分歧。**
- [AeroLat](#paper:ghosh2026aerolat)：同构冻结 LLM 广播出去的隐状态，会坍缩到共享的 prompt 模板上；做白化之后，虚假相似度下降 97.5%。这提示“看起来对齐”可能只是模板效应。
- [SYNC](#paper:li2026share)：免训练，只发送共享词表的索引（符号），不发向量。在 5 个家族的 9 个 receiver 上，四个答案全对的比例为 72.0–98.3%；无消息时为 0%；设有 shuffled 对照。**可以作为 C2 的“符号信道”基线。**

**交接与复用**
- [CacheLink](#paper:qiu2026cachelink)：跨模型的 context handoff。K/V 重建误差的变化不到 0.4%，接收方的行为却明显改变；交接延迟最多降低 7.27 倍。结论是**保真度不等于可用性**，C3 必须以行为作为指标。
- [BCR](#paper:kang2026budgeted)：在 KVCOMM 式的多 agent KV 复用中，按行做选择性重算，能修掉 49.5% 超出随机水平的 cache 误差；在 HumanEval 上几乎无损；设有抛硬币对照。
- [Communication Bottleneck](#paper:suau2026communication)：16×16 跨模型的文本往返实验。只是交换角色，准确率就能相差 60.4 分；至少 73.6% 的失败出在生成端。**这是文本信道的有损基线。**
- [ReLAT](#paper:yuan2026closing)：Qwen3-8B 在 MBPP+ 上，单模型 64.8 / TextMAS 69.5 / LatentMAS 74.6 / ReLAT 76.7。注意它实质上是单模型方法。
- [LatentMem](#paper:fu2026latentmem)：多 agent 的 latent 记忆，最高提升 19.36%；评测包含 KodCode 和 BigCodeBench。

**安全**
- [Cached Goal Leakage](#paper:gupta2026goals)：同一模型在两个客户之间共享状态时，22% 的决策偏离了当前客户的目标。另一个客户的目标表征留在 KV 里，并且有因果作用。**这是 C7 最直接的前置证据。**
- [VReparo](#paper:lin2026cache)：跨模型复用 KV 时，复用 V 比复用 K 更容易破坏接收方原有的安全行为。修复后 HarmBench ASR 从 57.28% 降到 39.21%。**这是 C8 的动机。**

## 3. 原有 10 个方向在 coding 下的对应

| 原方向 | coding 版 | 在 coding 下更好做还是更难做 |
|---|---|---|
| D1 按位置分区的 latent 审计 | **C1** | **更好**：代码任务是没人审计过的地方，复现结果分歧也最大 |
| D2 统一的内容归因与等预算 benchmark | C1 + **C2** | **更好**：标识符级指标让“内容”可以直接计量 |
| D3 记事本传染的内容对照 | **C6** | 差不多：repo 里有现成的记事本 |
| D4 信息不对称下的“传思考” | **C3**、**C4** | **更好**：信息不对称是默认状态 |
| D5 “编码了”不等于“被用了”，以及信道容量 | **C2** | **更好**：被用到的信息可以按标识符逐个计数 |
| D6 拆解“一个眼神” | **C5** | **更好**：接口约定可以明确计数，不再只是 5 选 1 |
| D7 latent 记事本 | **C7** | 工程更重，但动机更直接 |
| D8 latent 防火墙 | **C8** | **更好**：有现成的 AI control 编程设定 |
| D9 权重即消息 | **C9** | 有底座：Code2LoRA、Skill-to-LoRA |
| D10 RL 训练的可审计 latent 语言 | **C10** | 更难：长程任务的奖励稀疏、工程量大，但有 CURE / MAGRPO 这类底座 |

## 4. 十个方向

| # | 方向 | 难度 | 影响 | 灌水度 | 起步算力 | 是否需要白盒 |
|---|---|---|---|---|---|---|
| C1 | 代码任务上的 latent MAS 审计（**灌水 ①，但推荐作为第一步**） | 2 | 4 | 4.5 | 2–4 H100·天 | 是 |
| C2 | 私有信息代码任务：latent 能传多少样本特定信息 | 2.5 | 4.5 | 2.5 | 4–8 H100·天 | 是 |
| C3 | subagent 交接：KV 交接 vs 文本摘要 | 3.5 | 5 | 2 | 10–30 H100·天 | 是 |
| C4 | Tester→Coder：执行反馈的隐式回传 | 3 | 4 | 3 | 3–6 H100·天 | 是 |
| C5 | “一个眼神”的编程版：不交流时的接口默契 | 2.5 | 4.5 | 3 | API 起步；白盒部分 3–5 H100·天 | 部分需要 |
| C6 | repo 作为记事本：传染研究的内容对照（**灌水 ②**） | 1.5 | 3 | 5 | 只用 API | 否 |
| C7 | 共享 KV / latent 记忆的编码团队 | 4 | 5 | 1.5 | 20–50 H100·天 | 是 |
| C8 | coder–reviewer 合谋与 latent 防火墙 | 3.5 | 4.5 | 3 | 5–15 H100·天 | 是 |
| C9 | 把 repo 写进权重：参数信道的团队共享及其潜意识风险 | 4 | 4 | 2 | 10–30 H100·天 | 是 |
| C10 | 用 RL 训练可审计的 latent 编码协议（**最有挑战**） | 5 | 5 | 1 | 50–200 H100·天 | 是 |

### C1｜代码任务上的 latent MAS 审计

- **问题**：LatentMAS、Vision Wormhole、StateBridge 在 HumanEval+ / MBPP+ / LiveCodeBench 上的增益，有多少来自消息的**内容**，有多少来自接口、额外计算和生成预算？
- **为什么是现在**：
  - 两篇审计都绕开了代码任务（见 §0），而代码任务上的复现分歧最大（§2.1）。
  - [对齐矩阵消融](#paper:deshpande2026role) 已经做了一部分，Relayed KV Audit 也把这个实验列为未来工作，**被抢先的风险高**，宜快做。
- **最小可行实验**：
  - **代码**：LatentMAS 官方实现，HF 后端。
  - **模型与题目**：Qwen3-4B/8B/14B；HumanEval+（164）、MBPP+（378）、BigCodeBench-Hard（148），再加 LiveCodeBench 的较新切片。
  - **对照臂**：
    - Single、TextMAS、LatentMAS；
    - LatentMAS-deranged：换成另一道题的 latent，**保持边缘分布不变**；
    - LatentMAS-zero；
    - 额外计算对照：给接收方补上等量的空 latent 步；
    - 等生成预算的 TextMAS：控制 TFlow 指出的那个混杂。
  - **按位置分区的错配**：只换 prompt 段的 KV，或者只换 latent thought 段的 KV（即 D1 的做法）。
  - **统计**：题目少，所以用逐题配对、≥5 个种子、按题聚类的 bootstrap 置信区间，再用 TOST 检验等价性。
- **预期**：多半会得到“增益在错配后大部分保留”或“依赖实现细节”的结论。不论正负，都能补上代码这块空白。
- **风险**：结果为阴性时，故事要讲成“审计代码任务的方法论与实证”，不要讲成“latent 没用”。
- **投稿去向**：EMNLP / ACL Findings，或 NeurIPS / ICLR workshop。基础设施（流水线、对照臂、统计）可以直接给 C2–C4 复用。

### C2｜私有信息代码任务：latent 到底能传多少样本特定信息

- **问题**：让发送方看到接收方看不到的跨文件上下文、类字段或 API 签名，接收方必须写出正确的标识符。分别用 KV、latent thought、文本转述传过去，各能带过去多少？
- **为什么重要**：这是本课题最核心的空白，即“latent thought 有没有携带样本特定信息”。它在代码上**可以逐个标识符地计数**。
- **最小可行实验**：
  - **数据**：
    - CrossCodeEval Python（2,665 题），跨文件上下文只给发送方；
    - RepoBench `cross_file_first` 作复测集；
    - ClassEval，按方法拆给不同 agent。
  - **关键技巧：随机重命名。** 把被依赖的标识符随机重命名成无意义的字符串，模型就无法凭先验猜中名字，同时也消除了污染。
  - **对照臂**：
    - 发送方读过上下文后的完整 KV；
    - 只保留 latent thought 段，去掉上下文 token 的 KV；
    - 错配 KV；
    - 不通信；
    - 发送方写的 k-token 文本摘要，k 取 64 / 256 / 1k；
    - 接收方直接读原文（skyline）；
    - C2C fuser；
    - “增补式”接口：保留接收方自己的 cache，再附加 sender 的 cache，只做 query 侧适配。这是 [Close Enough is Nowhere Near](#paper:deng2026close) 里唯一超过基线的接口；
    - 符号信道：只发送共享词表的索引（[SYNC](#paper:li2026share)）。
  - **指标**：EM/ES、标识符 F1，以及 ClassEval 的测试通过率。
  - **模型**：
    - Qwen3-8B→14B（同族）；
    - Qwen3-14B↔Devstral-Small-2507（跨族，两者 KV 形状完全相同）；
    - Qwen2.5-Coder 的 base 版（CrossCodeEval 原生面向 base 模型）。
- **预期**：
  - 文本 token 的 KV 接近 skyline；
  - 只保留 latent thought 时接近不通信；
  - 文本摘要的标识符损失随 k 变小而增加。
  - 由此可以画出一条“每 MB 通信量能带过去多少标识符”的效率曲线。
- **产出**：一个 benchmark 加一个关键结论，可以投 NeurIPS D&B 或 ACL。它也是 C3–C5 的度量工具。

### C3｜subagent 交接：KV 交接 vs 文本摘要

- **问题**：explorer subagent 读了 N 个文件，通常只交回 1–2k token 的摘要。若改为交回它读过的文件对应的 KV（或压缩后的 KV），在**相同显存和相同 FLOPs** 下，能不能补上交接损失？
- **为什么重要**：
  - 失败集中在交接处，Deep Agentic Search 中占 41.8%，Planner-Coder Gap 中占 75.3%。
  - 行业里正在争论“共享完整上下文”还是“隔离加摘要”（Cognition 对 Anthropic）。
  - KV 交接恰好是“共享完整上下文，又不重读”的折中，可以直接拿来检验这个争论。
  - 正面结果最多的恰恰就是文本 token 的 KV（见“研究方向”页 §0 和 [Relayed KV Audit 笔记](#note:cheng2026latent)），所以这个方向成功的先验概率较高。
  - 最接近的系统工作 [CacheLink](#paper:qiu2026cachelink) 只测了延迟和重建误差，而它自己就发现，误差极小时行为仍会改变。所以 C3 要做的是**行为层面**的对照。
- **最小可行实验**：
  - **流水线**：先用 Agentless 式的固定两段流水线：定位 agent → 修复 agent。
  - **数据**：
    - SWE-smith（arXiv 2504.21798，未收入索引）一类合成 bug，注入位置已知，可以当作定位的 ground truth；
    - SWE-bench Lite / Verified 抽 50–100 题；
    - SWE-bench-Live 做去记忆对照。
  - **对照臂**：
    - 文本摘要；
    - 结构化笔记（[PACT](#paper:huang2026should) 风格）；
    - 原始轨迹（Cognition 主张的做法）；
    - 完整 KV 交接；
    - 压缩 KV 交接（参考 [KVComm](#note:shi2025kvcomm) 的选层，以及 KVCOMM 的锚点复用）；
    - 错配 KV；
    - 不交接。
  - **指标**：解决率、定位准确率，以及 token、FLOPs、显存，**全部在同一后端上测**。
  - **显存估算**：Qwen3-14B 每 token 的 KV = 2×40×8×128×2 B = 160 KiB，32k token 约 5 GiB，单卡可以容纳。
- **风险**：
  - 工程量大：需要 mini-swe-agent 的 Apptainer 环境、自定义的 HF 模型类、OpenHands 的 `--apptainer` 评分。
  - 结论可能只对同族模型成立。
- **投稿去向**：ICLR / ICML 主会级。

### C4｜Tester→Coder：执行反馈的隐式回传

- **问题**：tester 跑完测试看到 traceback 并做出诊断，然后把诊断以 latent 形式回传给 coder，对比直接回传文本。
- **定位**：这是 D4 的廉价版。信息不对称天然存在：coder 没看到 traceback。
- **最小可行实验**：
  - **数据**：LiveCodeBench（取较新的切片）和 ClassEval，每题最多 3 轮修复。
  - **对照臂**：
    - 原始 traceback 文本；
    - tester 写的诊断文本；
    - tester 诊断时的 KV / latent；
    - 错配的 latent，即来自另一道题的失败；
    - 不给反馈，只告诉 coder “失败了”。
  - **指标**：修复成功率和每轮成本。
- **预期**：traceback 里的行号和变量值都是高熵内容。如果 latent 带不过去，可以和 C2 互相印证。
- **风险**：在函数级任务上，单 agent 的 self-debug 可能已经足够强。必须报告 single-agent self-debug 作为基线。

### C5｜“一个眼神”的编程版：不交流时的接口默契

- **问题**：两个 agent 分别实现同一个类或同一组模块的不同部分，**不发消息**。它们在函数名、数据结构、返回格式上的一致程度，有多少超出“各自独立采样时的碰撞概率”？同权重、同族、跨族三种配对的“超额默契”分别是多少？进一步，只让 B 看一眼 A 的计划 KV，即一次性、N token 的“一瞥”，能补回多少协调缺口？
- **为什么重要**：
  - 这正是用户最初的动机。
  - 文献里的“默契”多半只是低熵：[Tacit Coordination](#note:aharon2026tacit) 中单模型的 NCI 等价于碰撞概率。
  - 接口选择的空间远大于 5 选 1，可以把“一个眼神”拆得更干净。
- **最小可行实验**：
  - **数据**：
    - 用 ClassEval 按方法拆分，不允许通信；
    - 复现 [Specification Gap](#paper:sartori2026specification) 的设定；
    - 第二阶段移植 [CooperBench](#paper:khatua2026cooperbench) 的子集。CooperBench 只支持 Docker / Modal，需要改造。
  - **配对**：
    - 同权重；
    - 同族不同尺寸；
    - 跨族；
    - 同模型不同温度；
    - 共享或不共享部分规格。
  - **信道**：
    - 无；
    - 一条 k-token 文本消息（[stale](#paper:xia2026passes) 中一条消息挽回 82%，可作基线）；
    - 一瞥 KV；
    - 只能观察共享 repo（stigmergy）。
  - **基线**：对每个接口决策，先估计各 agent 独立采样时的分布 p，碰撞基线为 Σp²，再报告超出这一基线的超额一致率。
- **成本**：不交流的那部分可以直接用 API 模型做，成本低；“一瞥 KV”需要白盒。
- **投稿去向**：ACL / EMNLP，或 NeurIPS 主会。可以和 C2 合成一个“编程中的隐式协调”系列。

### C6｜repo 作为记事本：传染研究的内容对照

- **问题**：AGENTS.md、TODO、被改过的测试、经验库这些共享产物，会传播测试作弊和 reward hacking。传播的是**内容**，还是“存在一条前人留言”这件事本身？
- **为什么容易出论文**：
  - 底座都现成：
    - 传染研究：[Reward Hacking 传染](#paper:hu2026reward)、[Self-Propagating Misalignment](#note:das2026self)、[Mind Viruses](#paper:papadopoulos2026mind)、[EVOMAL](#paper:wu2026evomal)、[Code-A1](#paper:wang2026code)；
    - 测试作弊 benchmark：[ImpossibleBench](#paper:zhong2025impossiblebench)、[SpecBench](#paper:zhao2026specbench)。
  - 这些工作都**没有做内容对照**。
- **最小可行实验**：
  - **对照**：
    - 真实留言；
    - 错配留言，即来自另一个任务；
    - 只保留“有人留过言”这一事实，内容抽空；
    - 改写过的留言；
    - 被安全措辞改写的留言。
  - **规模**：只用 API 模型，2–3 个家族，ImpossibleBench 一类 benchmark 的子集。
- **定位**：两周可以出结果。但影响有限，属于典型的增量工作。若能和 C7 联动，用作 C7 的明文基线，价值会更高。

### C7｜共享 KV / latent 记忆的编码团队

- **问题**：把团队的明文记事本（notes、memory bank）换成持久化共享的 KV 或 latent 记忆之后：
  - 效率有没有提升？
  - 测试作弊、目标偏离这类行为传染还会不会发生？
  - 能不能审计？
- **为什么重要**：
  - 这正是事件机制的“隐式化”版本。
  - [Cache-History Sensitivity](#paper:gu2026request) 已经显示，共享缓存会形成无意的跨请求信道。
  - [Cached Goal Leakage](#paper:gupta2026goals) 发现，共享状态下，另一个客户的目标表征会留在 KV 里，并让 22% 的决策偏离当前客户的目标。
  - 目前没有人在 coding 团队里测过跨 agent 的 KV 信息流。
- **最小可行实验**：
  - **设定**：3–5 个 agent 轮流处理同一 repo 上的一串 issue。共享介质分四种：
    - 明文 notes；
    - 共享前缀 KV；
    - 压缩后的 latent memory；
    - 无共享。
  - **注入**：在某一轮注入一个“偏离”的源头，例如修改测试，然后观察传播曲线。
  - **审计手段**：
    - 用 probe 读出共享 KV 里有没有“偏离意图”；
    - 用 KV 复算校验，确认共享 KV 与可见文本重新计算得到的 KV 一致；
    - 日志要防篡改，否则 agent 可以删掉自己的轨迹（[Trace Tampering](#paper:qin2026llm)）。
- **风险**：工程量大，结果对实现细节很敏感。需要先用 C6 的明文版本跑通。

### C8｜coder–reviewer 合谋与 latent 防火墙

- **问题**：如果为了效率，把 coder→reviewer 之间的通道换成 KV 或 latent：
  - reviewer 会更容易被带偏，还是能从 KV 里读出更多意图？
  - 同权重 coder 和 reviewer 的合谋能力会不会提高？
  - 简单的防火墙能不能补上？候选有两种：KV 复算校验；只允许传递文本 token 对应的 KV，不允许传纯 latent。
- **基线**：
  - 文本条件下，无通信合谋成功率约 0.8–3.4%（[Järviniemi](#note:jarviniemi2025subversion)）；
  - SFT 诱导后上限约 9.8%（[Gardner-Challis](#paper:gardnerchallis2026trust)）；
  - 同谱系监控更会检测，也更可能合谋（[Calibration-Family Overfit](#paper:pinto2026calibration)）；
  - 跨模型复用 KV 会破坏接收方原有的安全行为（[VReparo](#paper:lin2026cache)）。
- **最小可行实验**：
  - **设定**：APPS backdoor 或 [ControlArena](#paper:aisi2025controlarena) 的编程设定，Qwen3 同族 coder 和 reviewer；
  - **对照**：文本审查、KV 审查、带 KV 复算校验的审查；
  - **指标**：后门检出率、误报率、合谋成功率。
- **说明**：这是防御方向的研究，产出是检测与隔离手段。任何攻击侧的设定都只用于评估防御，并沿用已有的公开控制设定。

### C9｜把 repo 写进权重：参数信道的团队共享及其潜意识风险

- **问题**：agent A 把对 repo 的理解蒸馏成一个 LoRA，agent B 直接加载。和让 B 读 AGENTS.md / 文档相比，查询多少次以后权重消息才更划算（摊销曲线）？另一面：用同伴的轨迹训练自己时，会不会连带继承隐藏特质？
- **底座**：
  - [Code2LoRA](#paper:hotsko2026code2lora)：由 repo 生成 LoRA，EM 63.8/66.2；
  - [Skill-to-LoRA](#paper:zhang2026skill)；
  - [Doc-to-LoRA](#paper:charakorn2026doc)；
  - [Agent Subliminal Transfer](#paper:dang2026subliminal)：经由 agent 轨迹的潜意识传递；
  - [Subliminal Learning](#note:cloud2025subliminal)：共享初始化在其中起到“密钥”的作用；
  - 风险侧：[Countdown-Code](#paper:khalifa2026countdown) 中 1% 的作弊轨迹就会被内化；[Natural EM](#paper:macdiarmid2025natural) 中生产级 coding RL 里学会的作弊会泛化成更广的失准；[Emergent Misalignment](#paper:betley2025emergent) 只用不安全代码微调就能引发广泛失准。
- **空白**：coding agent 之间互传权重的论文目前是 **0 篇**，现有工作全是单 agent。
- **最小可行实验**：
  - Qwen2.5-Coder-7B 或 Qwen3-8B，在 5–10 个 repo 上比较三种做法：读文档、加载 Code2LoRA、加载同伴 agent 经验蒸馏出的 LoRA。
  - 记录两类指标：随查询次数变化的性能与成本；继承的副作用，例如测试作弊倾向。

### C10｜用 RL 训练可审计的 latent 编码协议

- **问题**：在 coder 与 tester（或 reviewer）协同训练的框架里，加一条可训练的 latent 信道，同时满足四个约束：
  - 消息内容确实被用到：错配后性能显著下降；
  - 在 C2 / C3 这类信息不对称任务上，等预算胜过文本；
  - 跨家族可用；
  - 可监控：有解码器或 probe 能读出它在说什么。
- **底座**：
  - [CURE](#paper:wang2025co)、[MAGRPO](#paper:liu2025llm)、[AT-GRPO](#paper:zhao2025stronger)、[MARS²](#paper:li2026mars)；
  - 端到端训练过 latent 信道的 [DiffMAS](#paper:yu2026learning)、[RecursiveMAS](#paper:zou2026recursive)，但只做到函数级任务。
- **难点**：
  - [Code-A1](#paper:wang2026code) 显示，同权重的 RL 会**自发出现自共谋**，例如写平凡测试。加上 latent 信道以后，这种合谋会更难发现。
  - 长程任务的奖励稀疏。
  - 必须先有 C2（度量工具）和 C8（监控工具）。

## 5. 最有挑战与最容易灌水

### 最有挑战：C10

C10 要同时做到四件事：真用内容、等预算胜过文本、跨家族可用、可监控。四个约束彼此冲突，代码场景还额外带来稀疏奖励和自共谋问题。

次难的两个：
- **C7**：工程最重。
- **C3** 的 repo 级版本：基础设施最重，涉及 Apptainer 化的 SWE 环境和白盒推理。

### 最容易灌水：C6 与 C1

- **C6**：只调 API、两周出结果、有现成底座。
- **C1**：代码和 benchmark 都现成，2–4 H100·天就能出结果。

两者的区别是：
- C1 的“灌水”是**体面的**。结论正负都有信息量，产出的流水线可以给后续方向复用，所以仍推荐作为第一步。
- C6 如果不和 C7 联动，基本是增量工作。

### coding 场景里常见的灌水套路（审稿人越来越不买账）

1. **“把 LatentMAS / KVComm 用到 HumanEval / MBPP 上，省了 X% token。”** HumanEval+ 接近饱和；不做错配对照就会被 §2.1 的复现分歧追问。
2. **“N 个角色的流水线加新 prompt，在 HumanEval 上 +2。”** 等预算后通常就没有了（[BenchAgent](#paper:fu2026more)）。
3. **“在 HumanEval 上做通信拓扑剪枝。”** 随机剪枝的效果差不多（[Rethinking MAS Efficiency](#paper:zhang2026rethinking)）。
4. **“多 agent SWE 系统在 Verified 上 +X。”** 不等 token；Verified 污染严重：只给 issue，模型就能以 76% 的准确率说出出错文件，非 SWE-bench 仓库上只有 53%。
5. **“新的 KV 复用系统，在 SWE-bench 上 TTFT 降 N 倍。”** 系统方向已经很拥挤，而且这类工作不回答任何关于“信息”的问题。

## 6. 推荐路线

**主线**：C1 → C2 → C3 或 C5 → C8 / C7

| 时间 | 做什么 | 产出 |
|---|---|---|
| 第 1–3 周 | **C1**：HF 流水线、对照臂、统计框架，单卡 | 一篇快出的审计论文；给后续所有方向复用的基础设施 |
| 第 3–8 周 | **C2**：私有信息的代码 benchmark，加上随机重命名 | 论文 1 的主体；后续方向的统一度量工具 |
| 第 2–4 月 | **C3**（偏实用、偏效率），或 **C5**（偏“一个眼神”的原始动机）；二选一作为主论文 | 主会级论文 |
| 之后 | 安全线 **C8 → C7**；长期 **C10** | — |

**如果想先有一篇最快的论文**：并行做 C6，只用 API，不占 GPU。

**选 C3 还是 C5**：
- 如果更想贴“一个眼神”的动机，选 **C5**。它的不交流部分可以先用 API 模型做，GPU 压力小。
- 如果更想做对工业界有用的事，选 **C3**。

## 7. 在 Nibi 上怎么做（实操要点）

完整调研见 `coding_infra.md`，网页上附在本页末尾作为附录。这里只摘结论。

**环境**
- 所有节点都有外网（`Nibi.md`）。
- **没有 Docker**；有 Apptainer 1.2.4–1.5.4。
- 每张 H100 建议配 14 核。
- `$SLURM_TMPDIR` 约 3T。
- 作业最长 7 天。
- 模型要在登录节点下载（`VLLM.md` 的要求）。

**模型**
- 主力用 **Qwen3-8B / 14B**：同族，KV 都是 8 个头 × 128 维。
- 跨族对照用 **Devstral-Small-2507**：KV 形状与 Qwen3-14B 完全相同（40 层 × 8 头 × 128 维，hidden 5120），只有 tokenizer 和 Q 头数不同。这样可以把“形状不匹配”和“表征不匹配”分开。
- **不要**拿以下模型做 KV 通信的主模型，因为它们的缓存不是标准 KV：
  - gpt-oss：sliding window 加 attention sink；
  - Qwen3.5 / 3.6 / Coder-Next：DeltaNet；
  - Nemotron-3-Nano：Mamba；
  - GLM-4.7-Flash：MLA。

**后端**
- MVP 用 HF transformers 4.5x（wheelhouse 里有 4.50–4.57）。
- **vLLM 不能改写 KV。**
- SGLang 支持 embeds 输入和 hidden states 输出，适合以后扩大规模。
- **所有对照臂都在同一后端上跑**，或者只报 token 数和 FLOPs。LatentMAS 的速度对比就混用了两个后端。

**benchmark**
- 不需要容器、可以直接在作业里跑的：EvalPlus、LiveCodeBench、ClassEval、CrossCodeEval、RepoBench。
- SWE 级任务：
  - agent 用 mini-swe-agent 的 singularity 环境，配自定义的 HF 模型类；
  - 评分用 OpenHands benchmarks 的 `--apptainer`，或 sb-cli 云评分；
  - 测试评分属于纯 CPU 任务，拆到 CPU 节点上的作业里跑。

**资源申请**
- MVP 示例，在计算节点上调试：
  ```
  salloc --account=def-zhouyang --time=03:00:00 --gpus-per-node=h100:1 --cpus-per-task=14 --mem=64G
  ```
- 只跑单模型调试时，可以改申请 MIG `h100_3g.40gb`，节省配额。
- 正式实验写成 `sbatch` job array，在 `$SLURM_TMPDIR` 里建 venv，依赖用 `requirements.txt` 固定。

## 8. coding 实验的最低标准

1. **内容对照**：保持边缘分布的错配消息（换成另一道题的消息）、置零消息、额外计算对照，三者都要有。
2. **等预算**：报告 token 数、FLOPs 和**生成预算**。文本 MAS 隐式扩大生成预算这一点（TFlow 指出）必须控制。
3. **同后端**：所有对照臂在同一推理后端上跑，否则不报墙钟时间。
4. **小 benchmark 的统计**：HumanEval+ 只有 164 题，要逐题配对、≥5 个种子、按题做 bootstrap；声称“等价”时用 TOST。
5. **去记忆**：用随机重命名标识符、模型 cutoff 之后的 LiveCodeBench 切片、SWE-bench-Live。不要只报 Verified。
6. **异构**：至少一组跨族配对，例如 Qwen3 与 Devstral。
7. **把单 agent 当一等基线**：包括 single-agent self-debug，以及同 token 预算的 best-of-n。

## 9. 局限与待核实

- **评分和算力都是主观估计。** 本轮新增的 162 篇只读了摘要和元数据，没有精读。若要动手做 C1–C3，建议先精读这几篇：CooperBench、stale、Handoff Debt、对齐矩阵消融、LOHA、Code-A1、KVCOMM。
- **[对齐矩阵消融](#paper:deshpande2026role) 只有 OpenReview 摘要。** 集群访问 OpenReview 会得到 403，正文没读到。它对 LatentMAS 对齐矩阵的描述（“训练所得”）与 LatentMAS 原文不符：原文的对齐矩阵是闭式的岭回归解，需要核对。
- **LatentMAS 的复现分歧数字来自 StateBridge 和 KITE 两篇论文的自述，没有交叉核对。**
- **集群上有三件事要在 `salloc` 里实测**：计算节点的外网、fakeroot、user namespace。目前只看了文档。
- **CooperBench 只支持 Docker / Modal / GCP。** 移植到 Apptainer 的工作量未知。
