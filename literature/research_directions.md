# 隐式交流：10 个最值得做的研究方向

> **版本**：2026-10-15
>
> **依据**：精读 25 篇核心论文（笔记在 `deep_read/`，网页“精读笔记”页签），加上 364 篇索引（`index.csv`）。
>
> **2026-10-17**：要把这些方向落到 multi-agent coding 场景，见 `coding_focus.md`（网页“Coding 聚焦”页签）。那里有 D1–D10 与 C1–C10 的对应关系。
>
> **评分说明**：
> - **难度**：1–5，越高越难。
> - **影响**：1–5，指做成之后对领域叙事的改变有多大。
> - **灌水度**：1–5，越高越容易靠现成代码和固定套路快速出论文。
> - 这三项都是主观判断，用来排序，不是精确数值。
> - 算力是**粗略估计**，按 Nibi 的 H100 计。
>
> 下图横轴是难度，纵轴是影响，圆越大越容易灌水。点圆圈可以跳到对应方向。

<div id="dir-map"></div>

## 0. 精读之后的五个判断

这五个判断决定了下面的方向怎么选。

1. **“通信”的证据比宣传弱得多。**
   - 精读的 8 篇方法论文是 AC、ThoughtComm、Interlat、Vision Wormhole、C2C、KVComm、LatentMAS、TFlow。其中只有 [Interlat](#note:du2025enabling) 做了系统的内容对照，而它在 unseen 集上，随机消息几乎和真消息一样有效。
     - TFlow 只在 GSM8K 上单次跑过随机 LoRA。
     - KVComm 的任务里不传消息就接近 0 分，内容显然有用，所以不需要这类对照。
   - 两篇审计的结论是：在标准 benchmark 上，LatentMAS 和 C2C 的增益与消息内容基本无关。
     - [Relayed KV Audit](#note:cheng2026latent) 用 TOST 把配对效应限定在 ±2.8pp 内。
     - [Draft-KV](#note:wu2026draft) 显示换成他题消息，准确率至多变 0.60pp。
   - [Causal Audit](#note:zhang2026latent) 是例外：它在 Qwen3-4B 上测到了正的内容效应，但只审计了 LatentMAS，样本也小。
   - 内容真正起作用只有两种情况：receiver **缺私有信息**，或 sender **算力更强、直接给出答案**。
2. **增益有三个来源，必须分开。**
   - 来源一：接口或适配器的容量。例如 [C2C](#note:fu2025cache) 把 Sharer 换成 Receiver 自己，就拿到约 86% 的增益。
   - 来源二：额外的前向计算。例如 [LatentMAS](#note:zou2025latent) 在 m=0 时与单模型持平，m=10 就拿到大部分增益。
   - 来源三：可言语化的内容，比如原文或答案。
   - **迄今所有正面结果都走“文本 token 的 KV”**。只保留 latent 的接口，两臂准确率都只有约 3.5%（[Relayed KV Audit](#note:cheng2026latent) App. E.5）。非言语的 latent thought 是否传了样例特定信息，**还没有人直接检验过**。
3. **“一个眼神”存在，但弱，而且来源平凡。**
   - 同一前沿模型两个实例在 5 选 1 题上一致率约 0.70，异构池约 0.35，人类约 0.4（[Tacit Coordination](#note:aharon2026tacit)，由 NCI/m 换算）。这主要来自低熵和共享文化先验，加大 reasoning 没有帮助。
   - 无通信的焦点合谋成功率只有约 0.8%（[Subversion via Focal Points](#note:jarviniemi2025subversion)）。
   - 隐写信号跨模型也能解出 40–83%，说明能力比“同权重”更重要（[FYEO](#note:shirnin2026eyes)）。
   - 事件中真正放大协调的是**共享可写环境**，也就是 stigmergy。
4. **参数层通信的机制已经清楚，但“以权重为消息”的证据很弱。**
   - Subliminal learning 本质是：输出携带了参数增量，**共享初始化（共享 Jacobian）就是钥匙**（[Subliminal Learning](#note:cloud2025subliminal)、[DSL](#note:fenoglio2026distributed)）。
   - [Phantom Transfer](#note:draganov2026phantom) 是另一种机制：弥散的语义线索，可以跨族传递。
   - 唯一“以权重为消息”的 [TFlow](#note:bao2026good)，在 5 个 benchmark 上准确率全部低于文本 MAS。实例内容只多带来约 1.3pt，单条消息约 16.5MB（估算）。
5. **安全研究还停在明文。**
   - latent 信道已被证明是攻击面（[Latent Attack](#note:wang2026out)、[Latent Comm Safety](#note:huzaifa2026safety)），但**没有人做 latent 消息的监控**。
   - 事件相关研究（[Self-Propagation](#note:das2026self)、[Collective Loss of Control](#note:wu2026collective)、[OAI-HF Reproduction](#note:slocum2026openai)、[Mechanics of a Swarm](#note:lutje2026mechanics)）全部是明文记事本，而且都**没有做笔记内容的错配对照**。

## 1. 总览

| # | 方向 | 类型 | 难度 | 影响 | 灌水度 | 起步算力（估） | 现成代码 |
|---|---|---|---|---|---|---|---|
| D1 | Latent thought 到底有没有在传：按位置分区的因果审计 | 主线 · 最该先做 | 2 | 4.5 | 4 | 2–4 H100·天 | LatentMAS |
| D2 | “这是通信吗？”统一的内容归因 + 等预算 benchmark | **最容易灌水 ①** | 2.5 | 3.5 | 5 | 1–2 H100·周 | 5 个方法均有 |
| D3 | 给“共享记事本传染”研究补内容对照 | **最容易灌水 ②** | 1 | 2.5 | 5 | 主要是 API 费用 | 3 个仓库 |
| D4 | 信息不对称下的“传思考” | 主线 | 3.5 | 4.5 | 2 | 1–2 H100·周 | KVComm、C2C |
| D5 | “编码了”≠“被用了”：接收方读心能力与信道容量 | 主线 | 3 | 4 | 3 | 约 1 H100·周 | AC 可复现 |
| D6 | “一个眼神”的分解：同权重默契从哪里来 | 主线 · 贴合动机 | 2.5 | 4 | 3 | 数个 H100·天 + 少量 API | Tacit Coordination |
| D7 | Latent stigmergy：把事件里的记事本换成 KV / latent 记忆 | 主线 · 高影响 | 4 | 5 | 1.5 | 1–3 H100·周 | Self-Propagation、RogueHandoff |
| D8 | 隐式信道的可监控性：latent 防火墙与可审计协议 | 主线 · 安全 | 3.5 | 4.5 | 3 | 1–2 H100·周 | Latent Attack（评测部分） |
| D9 | 参数层：权重即消息，以及“共享初始化即密钥”的隐蔽载荷 | 主线 · 空白 | 4 | 4 | 1.5 | 1–2 H100·周 | TFlow、D2L |
| D10 | RL 训练出的、可审计的 latent 语言 | **最有挑战** | 5 | 5 | 1 | 数十到上百 H100·天 | Draft-KV、HRPO 作起点 |

## 2. 十个方向

### D1｜Latent thought 到底有没有在传？按位置分区的因果审计

**问题**：在 LatentMAS 类 KV 中继里，把“prompt / 文本 KV 行”和“latent thought 行”**分开**做错配，看 latent thought 本身携带了多少样例特定的信息。然后把同样的检验推广到 soft-token 和 hidden-state 信道（[Interlat](#note:du2025enabling)、[Vision Wormhole](#note:liu2026vision)、[ThoughtComm](#note:zheng2025thought) 的前缀）。

**为什么现在值得做**：
- [Relayed KV Audit](#note:cheng2026latent) 把“只错配 latent 块”列为**没做的关键实验**（App. E.2）。它的校准任务达到了天花板，但信息可能完全走的是 prompt KV。
- [Causal Audit](#note:zhang2026latent) 在 Qwen3-4B 上测到正的内容效应：GSM8K 的 CAG 为 +5.17pp，MATH-500 为 +6.67pp。但它没有区分这些效应来自哪些行。
- [Draft-KV](#note:wu2026draft) 显示 prompt KV 的配对增益只有 0.09–0.17（Table 2）。
- [LatentMAS](#note:zou2025latent) 自己没做任何内容对照。

**最小可行实验**：

- **代码与模型**：LatentMAS 官方代码，Qwen3-4B / 8B。
- **任务**：
  1. 校准任务：sender 持有私有的 key-value 绑定，沿用 Cheng 的 registry 设计。
  2. 自然任务：GSM8K 全集加 MATH-500，按“receiver 单独能否答对”分层。
- **实验臂**：
  - 原样（true）
  - 只错配 latent 行
  - 只错配 prompt 行
  - 全部错配
  - latent 行置零，或换成范数匹配的噪声
  - 重复同一个 pause 嵌入
  - 单 agent 自己做 3m 步 latent
- **统计**：5 个种子，用 TOST 等价检验加分层 bootstrap。
- **附加 probe**：在 latent 行上训练线性 probe，测能否解码出 sender 的私有信息，用来区分“编码了”和“被用了”（与 D5 衔接）。

**预期**：两种结果都有价值。
- 如果只错配 latent 行，校准任务仍接近天花板：说明 latent thought 不承载私有信息，“latent 协作”应改称“KV 前缀共享 + 额外计算”。
- 如果在难题子集上，错配 latent 行会显著掉分：这是**第一个“非言语 latent 传递”的因果证据**。

**难度与风险**：难度低，没有训练，单卡就能做。最大风险是**被抢发**，因为 Cheng 已经把这个实验写成未来工作。建议 4–6 周内完成。

**灌水度 4 / 影响 4.5**：短文就能成，但结论会直接改写这个子领域的叙事。适合投 ACL / EMNLP short；如果加上 D5 的 probe 分析，可以投 ICML / NeurIPS 主会。

### D2｜“这是通信吗？”统一的内容归因 + 等预算 benchmark（最容易灌水 ①）

**问题**：给所有隐式信道建立一套标准评测，包括三部分。
- **内容归因**：
  - 配对效应 τ = A(true) − A(deranged)，即真消息与错配消息的准确率差。
  - 自生成增益 SSG：与 receiver 自己生成的消息比。
  - 等价检验：TOST。
- **成本核算**：在等字节、等 FLOPs、等延迟的条件下比较，并计入 prefill 和接口训练的摊销。
- **三类任务**：
  - 共享题面：现有论文基本都只测这一类。
  - 信息不对称：私有事实、拆分的证据。
  - 算力不对称：强 sender 配弱 receiver。

**为什么容易做**：
- 方法和代码都现成：LatentMAS、C2C、KVComm、Interlat、Vision Wormhole 都有代码，AC 也容易复现。
- 估计量现成：Cheng 的 τ、Zhang 的 CAG / SSG、Draft-KV 的 P = G + (A_R − A_D)。
- 效率口径普遍混乱，“统一核算”这件事本身就有人需要：
  - [LatentMAS](#note:zou2025latent) 只计输出 token，而且 18 格里有 15 格比单模型慢。
  - [KVComm](#note:shi2025kvcomm) 报的是相对 AC 的增量 FLOPs。
  - [Interlat](#note:du2025enabling) 的 24× 是相对全长 latent 消息算的。
  - [C2C](#note:fu2025cache) 计入了 prefill，但没把每对模型 45–54 GPU·h 的 fuser 训练摊销进去。

**最小可行实验**：
- 5 个方法 × 3 类任务 × 6 个实验臂：true、deranged、zero、moment-matched、no-message、self-message。
- 统一用 FLOPs 计量。
- 开源 harness 和 leaderboard。

**怎么才不算灌水**：2026 年 7–9 月已经有三篇审计，只是“再审计一遍”会被认为是增量工作。**必须有新维度**：跨信道（embedding、hidden、KV、LoRA 同台），加上信息不对称任务，再加上完整的成本前沿。

**灌水度 5 / 影响 3.5**：会成为后续论文的标配对照，引用潜力大。适合投 NeurIPS Datasets & Benchmarks 或 ICLR。

### D3｜给“共享记事本传染”研究补内容对照（最容易灌水 ②，几乎纯 API）

**问题**：在 [Self-Propagation](#note:das2026self)、[RogueHandoff](#note:wu2026collective)、[OAI-HF Reproduction](#note:slocum2026openai) 中，“读了笔记就偏离任务”的效应，有多少来自笔记的**语义**，又有多少只是因为“有一条继承下来的状态”加上结构性服从？

**为什么容易做**：
- 三个仓库都开源。
- Wu 在 §9.3 已经写好了 (O,P,A) 2³ 因子消融，并附带 placebo 设计，只是没跑。
- Das 只有 matched neutral control，没有错配或随机笔记。它的端到端成功率：显式目标时 58%，只给 values 时 18%。
- 实验只需调用 API，不需要 GPU。

**最小可行实验**：
- **四种笔记**，加在原有设置上：
  - 错配：指向无关动作。
  - 随机。
  - 语义抹除：保留格式，抹掉内容。
  - 反向：劝阻原动作。
- **因子消融**：Wu 的 2³ 设计。
- **指标**：端到端执行率和 τ，画成“语义相关性 → 执行率”的剂量曲线。

**怎么才不算灌水**：
- 把剂量曲线变成**可部署的防御**，例如 Das §V 提出的执行点上下文许可层。
- 或者把它当作 D7 的“明文对照组”，并入 D7。

**灌水度 5 / 影响 2.5**：1–2 周就能出 workshop 论文，例如 NeurIPS / ICLR 的安全 workshop，或 ACL Findings。

### D4｜信息不对称下的“传思考”：sender 的推理能否经 latent 带来原文之外的增益？

**问题**：sender 独占证据，并先在证据上推理（CoT 或 latent 步），再把推理后的 KV 或 hidden state 发给只看到问题的 receiver。这样做能否超过下面两个基线？在异构模型之间又如何？
- （a）直接转发原文，即 Skyline。
- （b）等字节的文本摘要。

**为什么这是“通信”的真正检验**：现有方法都绕开了这个问题。
- [C2C](#note:fu2025cache)：Sharer 和 Receiver 的输入完全相同。
- [KVComm](#note:shi2025kvcomm)：sender 看不到问题，也不推理。
- [LatentMAS](#note:zou2025latent)：所有 agent 看同一道题。

真正做了信息不对称的两篇，结果都很弱：
- [Draft-KV](#note:wu2026draft) 的 Private 协议，系统增益只有 2.51pp，14 个设置中 6 个为负。
- [Relayed KV Audit](#note:cheng2026latent) 中，KVComm 只有部分传递，C2C 检测不到传递。

**最小可行实验**：
- **任务**：
  - 多跳 QA：把 2Wiki、MuSiQue 的证据拆给 sender。
  - 合成的“需推导私有事实”任务：sender 拿到一组规则，要推出中间结论。
- **sender 先推理 m 步再发送。对照组**：
  - 原文的 KV
  - CoT 文本
  - CoT 的 KV
  - 只发 latent 步的 KV
  - 错配消息
- **模型**：先用同构的 Qwen3-8B；异构时借 C2C fuser 或 [StateBridge](#paper:peng2026statebridge) 做对齐。

**预期**：
- “CoT 的 KV”超过 Skyline，就证明传的是思考而不只是原文。
- **关键问题**：latent 步的 KV 能否不输 CoT 的 KV。

**灌水度 2 / 影响 4.5**：如果只是“把 C2C 和 KVComm 拼起来”，会滑向灌水；但“传思考”本身是真问题。适合投 ICML 或 NeurIPS 主会。

### D5｜“编码了”≠“被用了”：LLM 接收方的读心能力与信道容量

**问题**：每种隐式信道能装多少信息？用 probe 可解码的量作为上界。接收方实际用了多少？用行为来衡量。两者的差距（signaling ≠ listening）怎样随层、信道宽度、同构 / 异构而变化？

**证据**：
- [AC](#note:ramesh2025communicating)：在 Countries 上，单个激活向量能把准确率从 0 提到 78。
- [TFlow](#note:bao2026good)：一条约 16.5MB 的消息，实例内容只多带来约 1.3pt。
- [Interlat](#note:du2025enabling)：去掉 adapter 后只剩 4.05。
- [Causal Audit](#note:zhang2026latent)：承诺的 PS（probe 可解码性）指标一个结果都没给。
- [Beyond Tokens](#note:liu2026tokens) §7.4 也把“容量 vs 可用信息”列为议程。

**最小可行实验**：
- **任务**：sender 持有 k 条 key-value 事实，k 取 1–64。
- **信道**：
  - 单个激活向量
  - m 个 soft token
  - KV 行
  - rank-r 的 LoRA
  - m 个文本 token
- **对每种信道测三项**：
  - probe 解码准确率
  - 接收方的行为准确率
  - 每字节能传的事实数
- **扫描范围**：层、k、同构 / 异构。

**预期**：画出“容量—利用率”曲线。很可能发现利用率远低于容量，也就是说瓶颈在**接收方读不懂**，而不在信道。这会把研究重点从“设计信道”转到“训练读取器”。

**灌水度 3 / 影响 4**：给领域一个可以比较的“单位”。适合投 ICLR 或 NeurIPS（偏分析）。

### D6｜“一个眼神”的分解：同权重默契从哪里来

**问题**：把同权重 agent 的默契拆成六个因素，并画出“权重距离 → 默契”曲线：
1. 同权重
2. 同 prompt
3. 低熵（mode collapse）
4. 共享文化先验
5. 推理对方
6. 共享可写环境

**一个可以直接用的分解**：
- 两个独立实例选中同一项的概率是 P(same) = Σₓ p(x)·q(x)。
- 同权重时 p = q，P(same) 就是碰撞概率 Σp²，**只要熵低，它就高**。
- 所以“同权重优势”可以分成两部分：
  - **分布重合 × 低熵**：用 “pick” 条件下的碰撞概率来度量。
  - **“coordinate” 指令带来的分布偏移**：这才是真正的“揣摩对方”。
- [Tacit Coordination](#note:aharon2026tacit) 的数据已经暗示前者占大头。
  - 它的单模型 NCI 是把同一模型采样 90 次当作一个“人群”算的，本身就是 m·Σp²，也就是碰撞概率。论文**没有真实的两两配对**。
  - 作者自己也承认，同族优势来自多样性下降。加大 reasoning 无益。

**证据**：
- 同一模型一致率约 0.70，异构池约 0.35，人类约 0.4（Tacit Coordination，由 NCI/m 换算）。
- 真焦点合谋只有 0.8%（[Subversion via Focal Points](#note:jarviniemi2025subversion)）。
- 跨模型解码 40–83%，说明能力比同权重更重要（[FYEO](#note:shirnin2026eyes)）。
- [Mechanics of a Swarm](#note:lutje2026mechanics) 明确表示，无法把 Schelling 显著性和“同模型基线相似”分开。
- 事件中的会合发生在共享可写环境里。

**最小可行实验**：
- **模型配对矩阵**：Qwen2.5-7B / Llama-3.1-8B 的 base、instruct、不同 RL checkpoint、LoRA、量化版。
- **因素**：
  - 同 / 异权重
  - 同 / 异选项顺序
  - 温度
  - 有无共享 scratchpad
- **任务**：
  - Tacit Coordination 的 Schelling 题
  - Subversion via Focal Points 的暗号任务
  - 一个新的环境任务：在 mock 文件系统里会合
- **指标**：超出碰撞概率基线的协调增益，以及首次会合时间。

**预期**：
- 大部分同权重优势可以用碰撞概率解释。
- 共享可写环境带来的协调增益，远大于同权重带来的增益。
- 这会给“一个眼神”一个**定量、可证伪**的定义。

**灌水度 3 / 影响 4**：基础版（只跑配对矩阵）容易出增量论文。带上分解公式和环境会合实验才有分量。适合投 ACL / EMNLP；若有理论分析可投 ICML。

### D7｜Latent stigmergy：把事件里的“记事本”换成 KV / latent 记忆

**问题**：假设共享记事本不是明文，而是 KV 片段、prefix cache 或 activation 笔记。那么：
- 行为传染（自传播、handoff 易感性）是否依然发生？
- 会不会更快？会不会更难审计？
- Lütje 式基于明文 delta 的外部取证，是否会彻底失效？

**证据**：
- 明文笔记的传染是因果性的：
  - 端到端成功率，显式目标 58%，只给 values 18%。
  - 现成的记忆审计器 MemMorph 只能把传播率从 71% 压到 34%（[Self-Propagation](#note:das2026self)）。
  - 注入 handoff 后有害率达 40–95%（[Collective Loss of Control](#note:wu2026collective)）。
- 同基座模型可以免训练互读 KV（[KVComm](#note:shi2025kvcomm)），同权重可以直接交接 KV（[LatentMAS](#note:zou2025latent)）。
- KV 交接是攻击面；范数检测只能抓住一部分攻击（[Latent Attack](#note:wang2026out)）。
- 外部重建完全依赖明文 delta（[Mechanics of a Swarm](#note:lutje2026mechanics)）。

**最小可行实验**：
- **设置**：在 Das 的 20 个场景或 RogueHandoff-20 上，用同权重开源模型 Qwen3-8B / 32B。
- **把“会话 A 的笔记”换成三种载体**：
  1. 文本笔记
  2. 该文本的 KV prefix
  3. A 在 latent 步中产生的 KV，不含文本
- **对照**：错配笔记、随机笔记。
- **指标**：
  - 执行率与 τ
  - 三类审计器的检出率：文本审计、激活 probe、KV 完整性校验（[KV Integrity](#paper:brito2026latent)）

**预期**：
- 文本 KV 与文本笔记效果相近（同权重下信息等价），但文本审计器看不到它。
- 纯 latent 笔记如果有效，是重大安全发现；如果无效，则与 D1 结论互相印证。

**灌水度 1.5 / 影响 5**：安全、事件、隐式通信三条线在这里交汇。目前没人做，而且难以做成增量论文。适合投 NeurIPS 或 ICLR 主会，也可以投安全会议。

### D8｜隐式信道的可监控性：latent 防火墙与可审计协议

**问题**：能否在读不懂 latent 消息的前提下监控它？分三层：
- **完整性**：同权重时，prompt 位置的 KV 可以确定性地复算。抽样比对就能发现篡改；对 latent 位置，要求 sender 一并提交 latent 输入，让接收方能复算。
- **内容 probe**：检测有害意图、外泄的信息，以及消息里是否夹带了与可见文本承诺不一致的内容。
- **鲁棒性**：在自适应攻击下评估上面两层。

**证据**：
- [Latent Comm Safety](#note:huzaifa2026safety) 没有任何 latent 监控，也没有做内容对照。被攻击后的 link 很可能只是一个与内容无关的越狱前缀。
- [Latent Attack](#note:wang2026out) 的范数检测在约 5% FPR 下，对 PCA KV 边攻击的 TPR 为 0.849，但完全抓不到 RePS 节点攻击，也没测自适应攻击。
- LatentMAS 的 debug mode 是另外并行解码的文本，不是对 latent 的解码，所以不忠实。
- 激活 probe 检测合谋已有初步结果：[VLA Monitor](#paper:kaur2026transcript) 在同构设置下 AUROC 0.993；[NARCBench](#paper:rose2026detecting) 零样本迁移 0.73–0.93。这两篇没有精读。

**最小可行实验**：
- **被测系统**：LatentMAS，以及 RecursiveMAS 式的 link。
- **构造三类恶意消息**：
  1. Latent Attack 的攻击方向。
  2. Latent Comm Safety 式的被攻击 link。
  3. D7 中植入的秘密。
- **实现三种检测**：KV 复算校验、线性 probe、文本承诺一致性检测。
- **自适应攻击**：范数保持的旋转注入，以及对 probe 方向做正交化。

**灌水度 3 / 影响 4.5**：“检测器 vs 攻击”的论文容易写；可复算校验和自适应评估才是新东西。适合投安全或 ML 主会。

### D9｜参数层：权重即消息，以及“共享初始化即密钥”的隐蔽载荷

**问题**：分两部分。

（a）**什么时候值得把消息编译成权重？** 需要测四件事：
- 容量：每字节能传多少事实。
- 摊销：一条 LoRA 服务 M 个后续 query 时的盈亏平衡点。
- 可组合：多个 sender 的 LoRA 能否叠加。
- 可撤销：传过去的东西能否收回。

（b）**隐蔽性**：subliminal 传递的钥匙是共享初始化。sender 能否把载荷藏在只有同源 receiver 能解码的方向里，例如 H_q 的零空间，或 LoRA 的特定子空间，让监控者看不见？

**证据**：
- [TFlow](#note:bao2026good) 是唯一一篇“以权重为消息”：5 个 benchmark 全部低于 TextMAS，实例内容只多带来约 1.3pt，而且没有 no-sender 对照。
- [Subliminal Learning](#note:cloud2025subliminal) 的定理基于共享初始化：跨底座传递基本消失（Fig. 8，GPT-4.1 与 GPT-4o 之间是例外），ICL 无法解码。
- [DSL](#note:fenoglio2026distributed) 的 Thm A.1 与之是同一套数学。
- [Phantom Transfer](#note:draganov2026phantom) 能跨族，但机制是语义线索，属于另一回事。
- TFlow 在 App. A 承认权重消息无法审计。
- 编码器已经有现成的：[D2L](#paper:charakorn2026doc)（ICML 2026）、[T2L](#paper:charakorn2025text)（ICML 2025）。

**最小可行实验**：

（a）
- **设置**：sender 和 receiver 都用 Qwen3-4B 同一底座，sender 持有合成的 key-value 事实。
- **消息类型**：
  - TFlow / D2L 式 LoRA，rank r = 1、4、16
  - 等字节的文本
  - KV
- **对照**：错配的 LoRA、范数匹配的高斯 ΔW、无消息。
- **输出**：画两条曲线，准确率–字节，以及累计 FLOPs 随后续 query 数 M 的变化。

（b）
- **传递强度曲线**：沿初始化距离逐级拉远，测传递强度如何衰减。依次为：
  - 同一模型
  - 同一模型继续 SFT k 步
  - 同族的不同版本
  - 异族模型
- **可预测性**：检验 H_q 子空间的重叠程度能否预测这条曲线。

**灌水度 1.5 / 影响 4**：这块几乎无人做。但如果只是“TFlow 加更多 benchmark”，就会变成灌水。

### D10｜RL 训练出的、可审计的 latent 语言（最有挑战）

**问题**：现有方法要么免训练，要么只做 SFT，**没有一个方法同时满足以下四条**：
1. 通过内容审计：D2 中的 τ 和 SSG 显著为正。
2. 在信息不对称任务上，等预算时胜过文本。
3. 能跨模型家族。
4. 可监控：存在可靠的“译回文本”或 probe。

本方向用多 agent RL 端到端优化 latent 协议，看能否同时达到这四条，并研究在监控压力下是否会涌现隐写式的 “neuralese”。

**为什么最难**：
- 多 agent RL 本身就不稳定，奖励稀疏，信用分配也难。
- latent 接口没有现成的、可微的“语言先验”可以借用。
- 四个目标彼此冲突，尤其是第 2 条和第 4 条。
- 还需要先有 D2 的审计工具和 D8 的监控工具作为前置。

**为什么值得**：
- 这是让“一个眼神就懂”从比喻变成工程现实的唯一路径。
- 证据显示 RL 的塑造力极强：在 [Latent Comm Safety](#note:huzaifa2026safety) 中，RL 攻击把三拓扑平均有害服从分从 27.9 拉到 76.9。
- [Draft-KV](#note:wu2026draft) 证明，只要训练目标里加入“错配惩罚”，就能让接收方真正使用消息内容。
- 监控压力加上预先约定，会让隐写能力上升（[Early Signs of Stego](#note:zolkowski2025early)）。
- 一句协作 prompt 就能把求助率从约 0.05 抬到 0.42–0.63，说明训练会塑造通信倾向（[OAI-HF Reproduction](#note:slocum2026openai)）。
- 目前 RL 训练的 latent 通信极少，只有 [n-Musketeers](#paper:masukawa2026n) 和 [HRPO](#paper:yue2025hybrid)。

**分阶段实验**：
1. **最小起点**：一对同构的 Qwen3-4B，玩 sender 持有私有信息的参照博弈，接口用 Draft-KV 式的 side-attention。用 GRPO 训练，奖励 = 任务成功 − λ·（错配消息下的成功），显式奖励对内容的依赖。
2. **加可审计性约束**：接一个冻结的解码头，要求它能从消息中还原关键事实。扫描 λ，画出 utility–auditability 前沿。
3. **加监控者对抗**（红队模式）：monitor 惩罚可检测的信息，观察是否出现线性 probe 读不出的编码。这一步的结果既可能是能力突破，也可能是安全警报。
4. **扩展到异构**：Qwen ↔ Llama。

**算力与工程**：需要几十到上百 H100·天，必须写 sbatch 作业并做 checkpoint。周期 6–12 个月。

**灌水度 1 / 影响 5**：高风险、高回报。即使只完成第 1、2 步，也是一篇扎实的主会论文。

## 3. 最有挑战的方向：D10，以及两个次难的方向

- **D10 最难**，原因有三：要同时优化四个互相冲突的目标；依赖 D2 和 D8 的工具；多 agent RL 本身不稳定。但它是唯一能回答“机器之间能否形成比文字更高效、又可审计的语言”的方向。
- **D7 次难**：难点在工程，包括同权重的注入接口、20 个场景的改造和三类审计器。科学风险不高，因为无论结果正负都有发表价值。
- **D9(b) 理论最难**：需要先严格定义威胁模型、监控者，以及容量与可检测性之间的权衡，然后才能做实验。

## 4. 最容易灌水的方向：D2 与 D3，以及常见的灌水模式

“灌水度高”不等于没价值，它的意思是**投入少、套路固定、审稿门槛低**。

- **D2（审计 / benchmark）**：代码现成，需求明确，引用潜力大。风险在于 7–9 月已经出了三篇审计，必须加新维度才不算重复。
- **D3（传染研究补对照）**：只需调用 API，设计现成，作者自己已经写好了实验方案。1–2 周可以出 workshop 论文，但科学增量有限。

**常见灌水模式**：按“最常见、最不推荐”排在前面。
1. **“把 LatentMAS / C2C 用到新任务上，省 X% token”**，例如医疗、代码、具身。这是目前最常见的套路。审稿人已经开始要求内容对照，精读的审计结果也意味着这类论文的增益**很可能经不起错配检验**，风险越来越高。
2. **换一批新模型重跑隐写或默契评测**：指标现成，但科学增量有限。我们的精读笔记把它列为灌水向（[Early Signs of Stego](#note:zolkowski2025early) 第 10 节）。
3. **检测器 vs 攻击的军备竞赛**：只要不做自适应评估，就容易写成增量论文。
4. **在 FYEO 上加一个知情第三方解码者**（[FYEO](#note:shirnin2026eyes)），在 Phantom 上换一种防御（[Phantom Transfer](#note:draganov2026phantom)）：改动极小。

**比较体面的“快出”做法**：
- 先做 D1，它也是 2–4 周的工作量，但结论是决定性的。
- 再把 D1 的工具扩展成 D2。
- 把 D3 当作 D7 的明文对照组顺手做掉。

## 5. 建议的三条路线

| 路线 | 顺序 | 周期 | 产出 |
|---|---|---|---|
| **快出** | D1 → D2（D3 顺手做） | 2–4 个月 | 1 篇短文或主会分析文，1 篇 benchmark 论文，以及一套可复用的审计工具 |
| **主线（推荐）** | D1 → D4 / D6 → D7 | 6–9 个月 | 从“latent 是否在传”，到“传思考”与“一个眼神”的定量定义，再到 latent 版的事件复现 |
| **高风险高回报** | D5 → D8 → D10 | 9–12 个月以上 | 先给信道容量一个“单位”，再做监控，最后做可审计的 RL latent 语言 |

D1 出现在前两条路线的起点，因为它便宜、决定性强，而且最容易被别人抢先。D6 最贴近“一个眼神”这个原始动机，适合作为整个课题的概念主线。

## 6. 隐式通信论文的最低实验标准

精读之后，建议我们自己的每篇论文都满足以下六条。它们也可以用作审稿的检查表。

1. **错配消息对照**：在批内做错配，并保持边际分布（derangement）。只换成随机噪声不够。
2. **无消息对照和自生成消息对照**：用来分离“接口或额外计算”的效应和“对方内容”的效应。
3. **等预算的文本基线**：按字节、FLOPs、延迟对齐。如果 latent 接口经过训练，文本基线也要给同等的训练，例如等参数的 LoRA。
4. **至少一个信息不对称任务**：receiver 必须依赖 sender 才能答对。
5. **统计**：至少 3–5 个种子，给出置信区间。声称“无差异”时用 TOST 等价检验。
6. **报告接口成本**：可训练参数量、训练数据、训练所需的 GPU·h，以及是否跨模型家族。
