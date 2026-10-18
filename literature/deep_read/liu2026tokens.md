# Beyond Tokens：Beyond Tokens: A Unified Framework for Latent Communication in LLM-based Multi-Agent Systems

> `liu2026tokens` · arXiv 预印本（综述，单作者 Yingzhuo Liu） · 2026-06-04（本地为 v3，2026-07-15，即其检索截止日） · [arXiv](https://arxiv.org/abs/2606.05711) · 代码/资料：https://github.com/enochliu98/Awesome-Latent-Communication（论文首页给出） · 本地 PDF：`pdf/2606.05711_Beyond-Tokens.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A（方法卡片）、B（benchmark 综合）、C（Table 8）+ 参考文献。本篇按要求重点写分类体系、open problems、遗漏与错误，其余各节从简。

## TL;DR
这篇综述用 WHAT（传什么）/ WHICH（怎么对齐）/ HOW（怎么融合）三轴，组织了 18 篇“代表工作”和 4 篇边界工作。它还给出了部署决策表（Table 4）、传输的收支平衡式（Eq.3）和 7 个研究议程。框架本身清晰可用，但**方法卡片的事实错误很多**：本 batch 精读的 4 篇方法论文，每一篇的机制描述都有错误；还有至少 7 处作者归属或标题错误。综述也**完全没有讨论“消息内容是否真的被用到”的对照**。作为分类参考可以用，作为事实来源不可靠。

## 1. 问题与动机（简）
- 文本通信有三个结构性问题：推理成本高、离散化丢失信息、语言本身冗余和模糊（§1、§4.1）。
- 文本通信的唯一决定性优势是可解释性（§4.2）。
- 作者认为隐式通信是“条件性优势”：适用于强耦合、只传中间消息、能对齐、延迟敏感的场景（§4.3）。

## 2. 方法（即本文的分类体系）
- **检索协议（§2）**：检索 arXiv、ACL Anthology 和 OpenReview，并做反向滚雪球，截止日为 2026-07-15。纳入要满足三个条件：(1) 至少两个模型实例、角色或模块之间交换信息；(2) 交换对象包含连续内部表征或可复用的推理状态；(3) 不需要完整的文本解码-编码往返。
- **Scope Principle**：区分三类对象，即语义 latent 消息、为省计算而复用的推理状态、内化到单模型中的多 agent 推理。
- **WHAT 轴（Table 1）**：Embedding（CIPHER）；Hidden state（AC、Interlat、ThoughtComm、MoT、Vision Wormhole 归入 UVC）；KV-cache（9 篇）；其他（SDE 的 state delta、BIGMAS 的 workspace）。
- **WHICH 轴（Table 2、§5.2）**：分两个子轴。
  - 语义对齐分四档：无对齐（假定同模型）、学习投影、通用 codec、交互层。
  - 层对齐分 Last→First、All→Corresponding、Selected→Selected、sparse top-k。
- **HOW 轴（Table 3）**：拼接、在 KV 维前置、数学运算（加法、门控、学习的 fuser）、cross-attention、cache 恢复，另有 visual injection 和 workspace 两种特例。
- **设计规则**：
  - Takeaway 1–5，例如“信息量、成本、架构依赖三者权衡”“优势有条件，并非普遍”。
  - Table 4 的部署决策：同骨干长上下文适合传 KV；异构适合投影或共享 codec；要求可审计时用文本加 latent 的混合信道。
  - Eq.3：t_saved > t_setup + S/B + t_align + t_inject。
  - §6.3 列出四类工程失败模式：位置错配、几何错配、内存带宽瓶颈、状态污染。

## 3. 语料设置（简）
- 共 18 篇主语料和 4 篇边界工作（TokenDance、AAFLOW+、When Latent Agents Lie、Latent Agents）。
- 不做数值排行榜，理由是骨干、硬件和延迟定义都不一致（§2.3、App. B）。

## 4. 主要结论（作者给出）
- KV 正在成为默认载体：18 篇中有 9 篇传 KV（B.3）。
- 同模型 agent 占主导；跨架构工作很少，而且需要训练。
- 长上下文场景收益最大。
- 多数论文报告“与其文本基线持平或更好”，但作者自己也提醒可能存在发表偏倚和基线错配（B.2）。

## 5. 事实核查（本节替代“消融”）
用本 batch 精读的 4 篇原文，以及 Interlat、VW 的参考文献核对后，发现以下问题。
- **AC**：
  - 卡片称“典型取中间层，如 32 层中的第 16 层”，融合方式是“加法”。原文实际是 k=j=26，replace 最好、sum 明显更差（AC Table 2、Fig. 2）。
  - Table 2 把 AC 的对齐方式标为“无（假定同模型）”，但 AC 在 Table 4 里做了 Qwen、Gemma、LLaMA 的跨家族实验，而且提供可学习的 W。
  - §5.2.2 同时把 AC 列入 “Last→First” 和 “Selected→Selected”，前后矛盾。
- **Interlat**：
  - 卡片称它传“末层、末 token 的 hidden state”，且“同模型时 training-free”，“对 NL-Comm 在长上下文任务上提速 24×”。
  - 原文实际传的是整段长度为 L 的末层 hidden state 序列；actor 一律经过全参数 SFT 加 adapter，去掉 adapter 后成功率只有 4.05（Interlat Table 4）；24× 指的是在 ALFWorld 上，全长 latent 消息生成与 8 步消息生成的延迟比（Interlat Table 3），不是与文本通信比，也不是长上下文任务。
- **ThoughtComm**：
  - 作者写成 “Ming Li et al.”，实际是 Zheng, Zhao, Li 等人。
  - 机制写成“与自身 hidden state 做可学习门控融合、对应层注入”，Table 5 还标成 training-free。
  - 原文实际是用稀疏自编码器抽取 Ẑ，经结构掩码后由一个训练过的 adapter 生成 1 个前缀 token（ThoughtComm §4、C.1），需要训练。
- **Vision Wormhole**：卡片称它是“第一个支持完全异构的方法”。但 AC 的 Table 4、Interlat 的 Qwen2LLaMA，以及本综述自己收录的 MoT，都早于它或与它同期做了跨家族通信。
- **作者与标题错误**：

  | 工作 | 综述写法 | 实际（依据） |
  |---|---|---|
  | CIPHER | Chunpu Liu, Xiangshen Dou 等 | Pham et al.（AC 参考文献） |
  | C2C | Jiaming Liu et al. | Tianyu Fu et al.（VW 参考文献） |
  | LatentMAS | Zhenyu Wang et al. | Jiaru Zou et al.（VW 参考文献） |
  | KVComm | Yifan Wang et al. | Xiangyu Shi et al.（VW 参考文献） |
  | Q-KVComm | Kwangyoun Park et al. | Kriuk & Ng（VW 参考文献） |
  | SDE | Runlin Yang 等 | Yichen Tang et al.（Interlat 参考文献） |
  | Coconut | 标题 “Reasoning in latent space: An unconstrained chain-of-thought” | “Training large language models to reason in a continuous latent space” |

  另外，“LatentMAS extends Cache-to-Cache”这一说法与索引摘要（免训练的 latent working memory）不符。
- **违反自己的纳入标准**：
  - Edge LLM Handover 是单用户在基站之间切换，Agent Memory 是单 agent 的 cache 持久化，都不满足“至少两个 agent 交换信息”。
  - Five Ws Survey 本身是综述，却被算进“18 种代表方法”。
  - 9 篇 KV 工作中有 4 篇（LRAgent、RelayCaching、Agent Memory、Edge Handover）属于系统层复用，按其 Scope Principle 不应计入“语义通信”，却被拿来支撑“KV 正成为默认载体”。
- **数字和论证错误**：
  - §4.1.2 写“d≥4096 的 32 位浮点约 40,000 bit”，实际是 4096×32=131,072 bit。
  - 用原始比特数论证“信息损失 10³–10⁴ 倍”，混淆了信道容量和可用信息；作者自己到 §7.4 才提出要区分这两者。
  - “latent 信道避免语义错配”这一说法没有证据。
- **评分没有依据**：Table 7 的星级评分没有说明标准。

## 6. 批判性评估
- **声称 vs 实际支持**：三轴框架作为描述工具是成立的。但“为 18 篇工作提供可比的设计空间”需要以准确编码为前提，而方法卡片的错误率很高，Table 1–3、5、8 中的多行都不可信。
- **缺失的对照与视角**：
  - 综述在 §7.5 要求“调用次数和信息获取对等的文本基线”，但**从未提及错配、随机、置零消息这类内容对照**。它也没有总结 Interlat 已经做过的 CrossTask、CovGauss、RandomRot 结果。
  - 截止日之后出现的三篇因果审计（Causal Audit 2026-07-29、Relayed KV Audit 2026-08-05、Draft-KV 2026-09-28）都指出 latent 增益可能与内容无关。综述当然无法收录，但它的议程里也没有预见这个问题。
- **可能的混杂**：没有区分“同题共读”和“信息不对称”两种任务，所以无法判断哪些增益真的来自通信。

## 7. 局限
- **作者自述（§9）**：领域变化太快；术语不统一，可能漏检；语料小，计数不具统计意义；跨论文数字不可比。另外，三轴框架没有覆盖 who、when、why 三个维度。
- **我们的判断：遗漏**。以下按截止日（2026-07-15）之前已出现、本项目 `index.csv` 已收录为准：
  - latent-state 类：RecursiveMAS（2026-04-28）、HyLaT（05-25）、Bicameral Model（05-11）、Vector Translation（2025-11-06）、Thinking in Different Spaces（2026-03-20）、Latent Channels / Wenzel（05-06，用 SAE 量化文本通道的信息损失）。
  - KV 类：LatentK-V（2026-01-04）、LCF（05-19）、DiffMAS（04-23）、OBF（04-14）、CanonicalMerge（07-01）、LatentDx（06-11）、Parallel-Synthesis（06-12）、KVCOMM（Ye et al.，NeurIPS 2025）、DroidSpeak。
  - 安全类：Latent Attack（05-27）、LCGuard（05-21）。
  - 参数层：TFlow（05-13）。
  - **整类缺席**：参数层通信（subliminal learning 系列）、无消息协调（Schelling、convention）、隐写与合谋、stigmergy 共享记忆。按用户对“隐式”的定义，这些都应该在范围内。

## 8. 可复现性
配套仓库给出了论文列表和图表的生成说明。综述的编码结果没有附上逐条证据，例如页码或原文引文，所以无法核对，这也是事实错误没有被发现的原因之一。

## 9. 与本课题的关系
- **可直接借用**：三轴框架、Eq.3 的收支平衡式、Table 4 的决策表、§6.3 的失败模式清单。
- **需要补上**：
  - (a) 加一条“内容敏感性”轴或评测维度，标明是否做过错配、随机、置零对照；
  - (b) 加一条“任务是否存在信息不对称”标注；
  - (c) 把参数层、无信道、stigmergy 纳入“隐式”谱系（见 `literature_review.md` §1 的信道谱系）。
- **与 OpenAI–HF 事件的关系**：事件中的通信是明文 stigmergy，完全落在这篇综述的视野之外。这说明只关注 latent 的综述会漏掉现实中已经发生的隐式协调。

## 10. 可以接着做的问题
1. **带证据的再编码与 benchmark 化**（低难度，灌水风险高但实用）：对 30 篇左右的核心方法逐条记录 WHAT/WHICH/HOW、是否做内容对照、是否信息不对称、是否等算力，并附页码证据，形成可维护的“审计表”。在此基础上统一跑 3–5 种方法的错配和置零对照，例如 AC、Interlat-0.5B、LatentMAS、C2C、VW。
2. **议程 7.4 的具体化**：用 Countries 式的植入事实任务，测各信道“每字节可携带的事实数”（task utility per byte）的上界与实测值，把“容量 vs 可用信息”变成可以测量的曲线。
3. **议程 7.2 的具体化**：做“可见文本承诺与 latent 负载一致性”检验。让 sender 同时输出文字摘要和 latent 消息，测两者是否可能语义不一致（即 latent 夹带），并设计检测器。
