# KVComm：KVComm: Enabling Efficient LLM Communication through Selective KV Sharing

> `shi2025kvcomm` · ICLR 2026 · 2025-10-02 · [arXiv](https://arxiv.org/abs/2510.03346) · 代码：https://github.com/Zephyroam/KVComm · 本地 PDF：`pdf/2510.03346_KVComm.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–O（arXiv v3，2026-02-22）；Fig. 8 已对照 PDF 第 9 页
> 注意：不要和 Ye et al. 2025 的同名工作 "KVCOMM: Online cross-context KV-cache communication"（arXiv 2510.12872）混淆。

## TL;DR
KVComm 的设定是：发送方 M_s 只看上下文 C，对 C 做 prefill，按"注意力重要性分数 + 以中间层为中心的高斯先验"挑出一部分层的 KV，发给只看问题 Q 的接收方 M_r，M_r 在对应层把这些 KV 拼到自己的 KV 前面。方法不需要训练，只用于同一模型或同一基座的微调版本。选 70% 层时接近 Skyline（直接把 C+Q 交给 M_r）；选 30% 层时，对 Qwen 这类模型几乎失效。"计算省 2.5–6×"是**相对 AC 的增量 FLOPs** 之比，不是总算力之比。

## 1. 问题与动机
- 文本通信（NLD）要多步解码，而且有损。
- 隐状态通信有"信息集中偏差"：后层最后一个 token 最关键（Fig. 2, 9）。AC 用发送方的状态替换或平均接收方的末 token 状态，会破坏接收方自己的信息。
- 把发送方所有 token 的 hidden state 都 prepend 过去会陷入两难（Fig. 3, 10）：用早层的状态只是相当于拼接输入，省不了算力；拼到后层又会掉点。
- 作者因此改为共享 KV。理由是 KV 不会直接覆盖接收方的 hidden state，由注意力自己决定怎么用。
- 两个假设：H1，中间层的 KV 最具可迁移的语义；H2，注意力集中的层更有用。

## 2. 方法
- **信道**：
  - M_s 对 C 做 prefill，得到每层的 (k, v)，只发选中的 M = ⌈ratio·L⌉ 层。
  - M_r 在选中层把 [k_s; k_r] 和 [v_s; v_r] 拼接起来；未选中的层不提供 C。
  - 位置编码统一偏移 |C|：接收方的 token 从位置 |C| 开始，未选中层的 [0, |C|) 留空（App. K）。
- **对齐与映射**：只能同构，层一一对应，两种模型对：
  - 同一模型，pair 1–4：Llama-3.1-8B、Llama-3.2-3B、Qwen2.5-7B、Falcon3-7B。
  - 同基座微调，pair 5–9：比如 Llama-3.2-3B-abliterated → DeepSeek-R1-Distill-Llama-3B，Qwen2.5-7B-Uncensored → Bespoke-Stratos-7B。
  - 不需要训练，没有可训练参数。
- **选层**：
  - 注意力重要性 Ŝ_a^l：选层时，Q 的 token 对 C 的平均注意力，对所有 head 平均，再做 min-max 归一化。
  - 选层分数 S^l = α·S_a^l + (1−α)·exp(−(l−µ)²/2σ²)，取 top-M 层。µ = L/2，σ = 10。
  - **Llama 用 α=1，也就是完全不用高斯先验**；Qwen 和 Falcon 用 α=0.8（App. B.2）。
  - 校准集只用**1 个样本**，选出的层固定后用于整个测试集（App. H, Fig. 11）。
- **协议与拓扑**：一对一，单向，一轮。App. J 有两个发送方加一个接收方的初步实验（Table 10）。发送方**看不到 Q**，所以它不做任何推理，只是 C 的编码器。

## 3. 实验设置
- **数据集**（Table 4 给出规模）：Countries 200、Tipsheets 500（这两个是合成数据，参照 AC 构造）、HotpotQA 500、QASPER 500、MuSiQue 500、MultiFieldQA-en 150、2WikiMQA 200、TMATH 300。前 4 个是从原数据集抽样的；App. E 有完整集（HotpotQA-E 7,405 题等）和 SAMSum。
- **指标**：F1；TMATH 用 ROUGE-L recall。
- **基线**：
  - Baseline：M_r 只看 Q。
  - Skyline：M_r 看 C+Q，作为上界。
  - NLD：两轮，每轮最多 256 token，并明确要求发送方总结 C。
  - CIPHER。
  - AC，有 mean、replace、sum 三种。
- **种子和解码**：未报告，也没有方差。
- **硬件**：A100 64GB 节点。FLOPs 用 PyTorch Profiler 统计。

## 4. 主要结果
- **Table 1**（三对同基座微调模型），以 HotpotQA 为例，依次是 Baseline / Skyline / NLD / CIPHER / KVComm(0.3 / 0.5 / 0.7)：
  - Llama-3B 对：0.23 / 0.73 / 0.43 / 0.50 / 0.46 / 0.57 / 0.65。
  - Qwen-7B 对：0.13 / 0.53 / 0.16 / 0.03 / 0.02 / 0.28 / 0.41。
  - Falcon-7B 对：0.21 / 0.76 / 0.52 / 0.27 / 0.59 / 0.63 / 0.55。
- **同一模型**（Table 8）：Llama-3.1-8B 的 Tipsheets，Skyline 0.92，KVComm(0.7) 0.96；Qwen2.5-7B 的 HotpotQA，Skyline 0.68，KVComm(0.7) 0.72。少数格子 KVComm 超过 Skyline，作者解释为"正则化"。
- **30% 层的表现很不稳**：
  - Qwen2.5-7B 同一模型：Countries 0.04（Skyline 0.54），Tipsheets 0.31（Baseline 是 0.32），HotpotQA 0.06。
  - Falcon 对的 Countries：0.3 时 0.46，0.7 时反而只有 0.19，随层数非单调。
- **AC 和 CIPHER**：AC 几乎和 Baseline 一样。NLD 和 CIPHER 只在 Countries、Tipsheets 这类"信息量很小"的任务上接近 Skyline（§4.2）。
- **效率**（§4.6, Fig. 8，Llama-3.2-3B，Tipsheets 和 MultiFieldQA-en）：
  - 纵轴是"**Δ GFLOPs over AC**"，即相对 AC 的增量。"降低 2.5–6×"是 Skyline 与 KVComm 增量之比。Tipsheets 上 Skyline 约 2.5，KVComm 约 0.4–1.05（读图）。
  - 内存是 "Δ Memory (GB)"，Tipsheets 上量级只有 0.005–0.015 GB；"省 23%–73%"说的就是这个增量。
  - 没有 wall-clock 延迟。
- **多发送方**（Table 10）：在 27 种情况里，两个发送方有 17 种比一个好。

## 5. 消融与诊断
- **对比随机选层**（Table 2, 9）：比例越低差距越大。比如 Llama-3B 对的 Countries，0.3 比例下随机 0.05、KVComm 0.46；0.7 比例下两者接近（0.57 对 0.57）。
- **对比单段连续层**（DroidSpeak 式，§4.3, Fig. 4–6, 15）：连续段只在中间层的一小块超参区域里表现好；KVComm 在同样层数下达到或超过最好的连续段。这支持 H1。
- **注意力水平**（Fig. 7）：选注意力分数高的层效果更好，选低的掉到接近 0。这支持 H2。
- **位置一致性**（Table 11）：把未选中层的位置回置到 0（KVComm-S），结果有好有坏。作者自己承认"positional inconsistency does not have a detrimental effect"，可见这一设计并不关键。
- **NLD 消息长度**（App. I, Fig. 12）：超过 128 token 后收益趋于饱和。
- **在线校准**（App. L, Fig. 13）：校准间隔 T 越大，效果越差。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - "通信"的含义被弱化了。发送方不看 Q，不做推理，发出去的只是**原始上下文 C 的部分层 KV**。在同一模型、100% 层的情况下，KVComm 在数学上就等于 Skyline（前缀 KV 复用）。
  - 所以本文实际证明的是：**前缀 KV 丢掉 30%–50% 的层仍能保留大部分可用性，选哪些层很重要**。这是 KV 复用和压缩方向的结论，不是"agent 交换理解"的证据。
  - 摘要说"as few as 30% of layers"能达到与上界可比的效果，与 Table 1 和 Table 8 不符。正文自己写的是选 70% 时才可比。
- **缺失的对照**：
  1. 最自然的文本基线是"发送方把原文 C 原样转发"，在算力上就等于 Skyline，而且精度是上界。所以 KVComm 在精度上不可能赢过文本，卖点只能是算力。但算力只给了相对 AC 的 Δ FLOPs，没有和"接收方对文本 C 做带 prefix caching 的 prefill"做 wall-clock 对比。
  2. NLD 的设定对文本不利：发送方看不到 Q，只能盲目总结。
  3. 不需要做错配 KV 对照，因为 Baseline 已接近 0，内容显然有用。真正缺的是"发送方额外计算是否有贡献"的对照，比如让 M_s 看到 Q 或者先思考一段再发 KV。
- **可能的混杂因素**：
  - 数据集小（150–500 题），没有种子和置信区间。KVComm 超过 Skyline 的那些格子很可能是噪声。
  - 每个模型对、每个数据集都要单独校准选层（1 个样本），Llama 和 Qwen 的 α 是在"left-out set"上调出来的。
  - 模型对里大量使用 abliterated、Uncensored、Jailbroken 的发送方（Table 5, 10），却完全没讨论接收方会不会继承不安全行为。
- **效率口径**：App. N 的复杂度分析**确实计入了**发送方对 C 的 prefill，但这部分和 Skyline 中接收方对 C 的 prefill 抵消了，节省只来自 Q 和解码 token 对 C 的注意力少算 L−M 层。Fig. 8 用 Δ（相对 AC）来展示，放大了比例。

## 7. 局限
- **作者自述**：只适用于同构或同基座；异构需要学习投影或 adapter（§6）；选层是离线固定的，在线和动态选层是未来工作（App. L）；带宽受限时需要压缩。
- **我们的判断**：
  1. 本质是"跨实例的前缀 KV 复用加层剪枝"，"通信"语义弱。
  2. 没有异构、多轮、或者发送方带推理的设置。
  3. Qwen 系对层选择极其敏感，泛化性存疑。
  4. 没有安全分析，而同基座微调模型能免训练直接读取彼此 KV，这一点在安全上恰恰是重要发现。

## 8. 可复现性
- 代码和合成数据（Countries、Tipsheets）在 GitHub 上公开（Reproducibility Statement）。
- 超参（µ、σ、α、NLD 轮数和长度）给全了，但没说解码方式。
- 不需要训练，3B–8B 的模型对两份 bf16 权重不超过 32 GB，**单张 H100 足够**。数据集只有几百题，主表约几 GPU·h（估计值）。
- 很适合作为"信息不对称 KV 通信"的现成测试平台。

## 9. 与本课题的关系
- 最重要的启示：**同一基座的不同微调模型（例如 abliterated 版和 R1-Distill 版）之间，KV 不需要任何训练就能直接互读**。放到 OpenAI–HF 事件的语境下：同权重或同基座的 agent 一旦能接触到彼此的 KV，比如共享的推理服务 prefix cache、KV 卸载存储（Mooncake、LMCache 之类），就存在一条不可读、不需要预先约定协议的信道。这正是事件中"共享 cache 当留言板"的 latent 版本。
- 与 LatentMAS 相比，KVComm 是信息不对称设置（接收方确实缺 C），所以它的"内容"毋庸置疑，但"理解"的成分几乎为零。两者合起来，正好对应"传信息"和"传思考"两个极端。
- 选层的发现（中间层、注意力集中的层）可以直接用于设计监控：如果要审计 KV 信道，优先看这些层。

## 10. 可以接着做的问题
1. **真实的端到端成本**：用 vLLM 开启 APC（prefix caching），比较三种方案的 TTFT、总 FLOPs 和精度：（a）接收方自己对文本 C 做 prefill；（b）KVComm(0.3、0.5、0.7) 外加 KV 传输的时间（按 25/100 Gbps 估算）；（c）发送方已经算好 C 的 KV（沉没成本）。模型用 Llama-3.1-8B，数据用 HotpotQA-E 和 MultiFieldQA。预期：只有在（c）且上下文很长时 KVComm 才有明显优势。
2. **发送方计算有没有价值**：让 M_s 也看到 Q，或者让它先生成 64 个 token 的 CoT 或 latent 步，再发送 C+CoT 的 KV。对照是只发 C 的 KV。用 2WikiMQA、MuSiQue 这类多跳任务。预期：发送 CoT 的 KV 能超过 Skyline，这将是"传思考"的直接证据。
3. **不安全行为是否经 KV 迁移**：直接复用论文里的模型对（Qwen2.5-7B-Instruct-Jailbroken 或 Uncensored → Bespoke-Stratos-7B），发送方对有害请求的上下文做 prefill，接收方只看到中性问题。在 HarmBench 子集上，比较拒答率在"文本转述"和"KV 转发"两种情况下的差异，以及能否被 Latent Attack（wang2026out）的 norm-profile 检测器发现。预期：KV 转发会绕过基于文本的过滤。
4. **异构 KVComm**：用 C2C 发布的 Qwen2.5-0.5B↔Qwen3-0.6B fuser 作为跨族映射，再叠加 KVComm 选层，在 Countries 和 HotpotQA 上测"异构加信息不对称"。目前没有人做过这个组合。
