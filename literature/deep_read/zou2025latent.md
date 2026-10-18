# LatentMAS：Latent Collaboration in Multi-Agent Systems

> `zou2025latent` · ICML 2026（Spotlight） · 2025-11-25 · [arXiv](https://arxiv.org/abs/2511.20639) · 代码：https://github.com/Gen-Verse/LatentMAS · 本地 PDF：`pdf/2511.20639_LatentMAS.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–K（arXiv v4，2026-08-03）；Table 1、Fig. 7、Fig. 8 已对照 PDF 第 6、8、9 页

## TL;DR
LatentMAS 不需要训练。所有 agent 用**同一个模型**，每个 agent 先做 m 步"latent thought"：把末层 hidden state 经一个闭式解出的线性映射 W_a 喂回输入，自回归跑 m 步。之后把整段 KV-cache（prompt、问题加 latent 步）拼到下一个 agent 前面，只有最后一个 agent 解码文本。在 9 个 benchmark 上，相对 TextMAS 的 token 数减少 70.8%–83.7%，速度快约 4×。但按 Table 1–3 自算，**相对 TextMAS 的平均准确率增益只有约 +1.5（sequential）和 +0.8（hierarchical）分**，与正文写的 2.8% 和 4.6% 对不上。相对单模型（Single），**18 个 sequential 格子里有 15 个更慢**。而且论文完全没有随机或错配 latent 的内容对照。

## 1. 问题与动机
- 文本 MAS 要逐 token 解码，信息有损，token 开销也大。已有的 latent 推理（Coconut 等）只在单模型内部用，C2C、KVComm 这类 latent 通信又需要训练，或者只传 prefill 的上下文。
- 本文提出的问题是"MAS 能否完全在 latent 空间里协作"。论文给出三条"原则"：推理表达力（Thm 3.1）、通信无损（Thm 3.3）、复杂度更低（Thm 3.4）。

## 2. 方法
- **信道**：
  - agent 内部，最后一层的 hidden state h_t 先变成 e = h_t·W_a，再作为下一步的输入嵌入，循环 m 步，m ∈ {0, 10, 20, 40, 80}，实际取 40–80。
  - agent 之间，取前一个 agent **全部 L 层**的 KV（包括它的 prompt、问题和 m 个 latent 位置），按层 prepend 到下一个 agent 的 KV 前面（经 HF 的 past_key_values）。这个过程是累积的：A3 继承的 M_A2 里已经包含 M_A1。
- **对齐与映射**：只能**同构**，实际就是同一个模型、同一份权重，换不同的角色 prompt。没有可训练参数。
  - W_a = (W_outᵀW_out + λI)⁻¹ W_outᵀ W_in / β，是一个岭回归闭式解，算一次后复用（App. A.2），大小为 d_h×d_h。
  - App. G 承认，异构 agent 需要另加可训练的 adapter。
- **协议与拓扑**：
  - Sequential：planner → critic → refiner → solver，共 4 个 agent。
  - Hierarchical：math、science、code 三个 agent 加一个 summarizer。
  - 每个 agent 只跑一轮，只有最后一个 agent 输出文本，而且这段文本是完整的 CoT。
- **理论**：
  - Thm 3.1：在"三值线性表示假设"下做计数，m 步 latent 需要 Ω(d_h·m/log|V|) 个 token 才能无损表达。文中的"235.7 / 377.1 / 471.4 倍"（Qwen3-4B / 8B / 14B）就是 d_h·log3/log|V|，**纯粹是维度计数**，说明不了模型实际用到了多少容量。
  - Thm 3.3 的"无损"只是说 KV 缓存与重算等价（App. B.2）。前提是同一模型、同一输入，所以是平凡成立的。它**并不说明 latent thought 与文本等价**。
  - Thm 3.4 是复杂度比较，前提是 Thm 3.1 成立。

## 3. 实验设置
- **模型**：Qwen3-4B、8B、14B，Llama-3.2-3B-Instruct、Llama-3.1-8B-Instruct（App. D.2）。
- **Benchmark**：GSM8K、AIME24（30 题）、AIME25（30 题）、GPQA-Diamond（198 题）、MedQA（题数未报告）、ARC-E、ARC-C、MBPP+、HumanEval+。
- **Baseline**：Single，以及 sequential 和 hierarchical 两种 TextMAS，prompt 结构相同（App. K）。
- **指标**：准确率；Token（**只计输出 token**，latent 步不算）；Speed（单位是 time(s)/run，"run"的定义未说明）。
- **解码与种子**：temperature 0.6，top-p 0.95，"三次独立运行取均值"，**不报方差**。最大长度：GSM8K、ARC 2048；MedQA、代码 4096；GPQA 8192；AIME 20000。
- **算力**：8×A100-80G，用 HF 加 vLLM 后端，TextMAS 也用了 vLLM 加速（§4.2）。

## 4. 主要结果
- **Sequential（Table 1），Single / TextMAS / LatentMAS 的准确率**：
  - Qwen3-14B HumanEval+：76.8 / 81.1 / 86.5。
  - Qwen3-8B MBPP+：64.8 / 69.5 / 74.6。
  - Qwen3-8B GSM8K：81.1 / 92.3 / 93.8。
  - 反例有 Qwen3-4B GSM8K 82.4 / 89.8 / 88.2，以及 Qwen3-8B ARC-E 95.6 / 99.1 / 98.8。
- **难题（Table 2，Qwen3-8B sequential）**：
  - AIME24 50.0 / 53.3 / 56.7。Token 为 12,891 / 38,596 / 8,953；速度为 421 / 2,808 / 688。
  - AIME25 46.7 / 53.3 / 53.3；GPQA-D 39.9 / 43.4 / 45.5。
  - Qwen3-14B AIME24 63.3 / 63.3 / 66.7。
- **Hierarchical（Table 3）**：相对 TextMAS 的差在 −1.0 到 +3.1 之间，大部分格子在 ±1 以内。
- **Llama（App. D.2 Table 4）**：相对 TextMAS 的差在 −0.3（3B 的 MedQA，hierarchical）到 +3.4（8B 的 MedQA，hierarchical）之间，12 格中有 9 格不超过 +1.6。
- **效率**：
  - 相对 vLLM 加速后的 TextMAS 快 2.6–7×（Fig. 4、10），token 少 59.4%–87.9%。
  - 最后一个 agent 的输出 token 平均少 29.1%（Table 5）。
- **我们按表自算**：
  - 相对 TextMAS 的平均绝对增益：sequential 24 格约 +1.5，hierarchical 24 格约 +0.8。
  - 相对 Single：sequential 24 格约 +7.5，其中约 5.9 分 TextMAS 也能拿到，即来自 MAS 脚手架本身。
  - 正文写的"相对 Single 平均 14.6%、相对 TextMAS 2.8% 和 4.6%"，口径未说明。很可能是相对百分比，而且被 MedQA 这类 Single 基线异常低的格子主导，比如 Qwen3-4B 的 MedQA，Single 47.7，TextMAS 65.3。

## 5. 消融与诊断
- **W_a 对齐（Fig. 7，读图；模型未注明，数值与 Qwen3-14B 接近）**：ARC-C 91.6→94.9，ARC-E 97.0→99.2，GSM8K 90.4→95.2。**不做对齐时，ARC-C 低于 Single（92.6），GSM8K 也低于 TextMAS（93.8）**。整个优势依赖这个手工推出来的映射。
- **latent 步数（Fig. 8，Qwen3-14B，读图近似；MAS 设置未注明，数值更接近 Table 3 的 hierarchical）**：
  - m=0：ARC-C 约 91，ARC-E 约 95，GSM8K 约 85.5，大致与 Single 持平。
  - m=10：约 93、99、90。
  - 40–80 步达到峰值，160 步时回落。
  - 这说明 latent 步是关键。但它**无法区分**是"latent 里的内容"在起作用，还是"多出来的 3×m 次前向计算或位置"在起作用。
- **混合消融（Table 7，Qwen3-8B）**：

  | 变体 | GSM8K | MBPP+ | MedQA |
  |---|---|---|---|
  | latent 推理 + 文本通信（只传最后 128 token） | 85.5 | 66.4 | 65.9 |
  | 文本推理 + latent 通信 | 90.1 | 68.0 | 71.2 |
  | LatentMAS | 93.8 | 74.6 | 75.3 |

  值得注意的是"文本推理 + latent 通信"。按 Thm 3.3，这一变体与 TextMAS 的信息内容等价，只有格式不同。可它在 GSM8K 上是 90.1，比 TextMAS 的 92.3 低 2.2 分。**仅格式差异就造成约 2 分的波动**，和 LatentMAS 相对 TextMAS 的平均增益是同一个量级。
- **语义诊断**：
  - Fig. 5 的 2D 投影里 latent 与文本嵌入分布重叠。
  - Table 6 的平均余弦相似度：TextMAS 0.126 / 0.142 / 0.155，LatentMAS 0.104 / 0.093 / 0.108。作者解读为"更多样"，但分布外的向量同样会显得"更分散"。
- **Debug mode（App. F，Table 8）**：每个 agent 在同一上下文下**并行**生成一段文本作为探针。在 100 个 GSM8K 样例上，探针正确与最终正确的一致率是 77/80 和 18/20。这段探针文本是并行解码出来的，并不是对 latent 的解码，所以不能证明 latent 里装着这些内容。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - "无损"（Thm 3.3）只是 KV cache 的正确性，与 latent 和文本谁更好无关。
  - "表达力高几百倍"（Thm 3.1）是容量上界，没有实证。
  - 有实证支持的结论是：同一模型、多角色 prompt、每个 agent 加 40–80 个 latent 位置、单一的长 KV 上下文，再由最后一个 agent 完整解码 CoT，在 token 数上远少于 TextMAS，准确率持平或略高。
  - "比单模型更高效"只在 token 数上成立。Speed 列显示：Qwen3-14B 的 ARC-E，Single 551、LatentMAS 2,124；8B 的 ARC-E，404 对 1,759；sequential 18 格中有 15 格 LatentMAS 更慢。Fig. 1 图注说相对 single 和 TextMAS 都降低了计算开销，这是有误导性的。
- **缺失的对照**：
  1. **内容对照**：把 latent thought 换成范数匹配的随机向量（经 W_a）、另一题的 latent（错配）、或重复同一个 pause 嵌入。
  2. **单 agent 对照**：一个 agent 做 3×m 步 latent 再作答，没有角色和多 agent。用来区分"多 agent"和"软思考"。
  3. **等预算的 TextMAS**：中间 agent 限制为 m 个 token。
  4. **等算力的 Single**：比如 self-consistency。
  5. m=0 只出现在图里，没有进表。
- **可能的混杂因素**：
  - **Single 基线可能偏弱**：Qwen3-8B 的 GSM8K 只有 81.1，Qwen3-4B 的 MedQA 只有 47.7。GSM8K 的最大长度 2048，没有报告是否开了 thinking、截断率多少，Single 很可能被截断伤到。
  - **噪声大**：AIME 每题值 3.3 分，Table 2 的 0–3.4 分增益相当于 ≤1 题；三次运行均值也不给方差。
  - **Speed 口径**：只比较了 vLLM 版的 TextMAS，LatentMAS 的 latent 步依赖 HF 的 hidden-state 回灌，两边实现层面的差异没有讨论。
  - **Token 口径**：latent 步不计入 token，但每一步都是一次完整前向，只是少算一个 LM head；每个 agent 重新 prefill 自己的 prompt 和问题的成本也没计入。
- **效率声明的口径小结**：
  - "4× 更快"只相对 TextMAS 成立。
  - "token 少 70.8%–83.7%"只计输出 token。
  - prefill 计入了 wall-clock，没有计入 token 数。

## 7. 局限
- **作者自述**：假设所有 agent 层结构相同，异构情况需要 adapter（App. G）；可以接入后训练（RL）来优化协议。
- **我们的判断**：
  1. 本质上是"单模型、多角色 prompt、软思考 token、共享上下文"，所谓"多 agent"只是 prompt 层面的区分，**没有任何信息不对称**，所有 agent 看到的是同一道题。
  2. 只适用于同权重的情况。
  3. 只测了一轮流水线，没测交互或辩论。
  4. 没有安全或可监控性分析。latent 内容不可读，而 debug mode 并不忠实于 latent。
  5. 增益幅度与噪声相当，缺乏统计检验。

## 8. 可复现性
- 代码已开源，并被后续工作直接复用：wang2026out 就以它为攻击对象。
- 超参：m、温度、最大长度都给了；λ 没有给具体值；MedQA 的子集规模没有报告。
- 不需要训练。单张 H100 80GB 可以跑 Qwen3-4B、8B、14B（14B bf16 约 28 GB 加 KV）。全部 9 个 benchmark × 3 次 × 3 种方法里，AIME 的 2 万 token 最耗时，估计每个模型几十 GPU·h（估计值）。只跑 GSM8K、ARC、MedQA 加对照实验的话，单卡 1–2 天可以完成。

## 9. 与本课题的关系
- **最接近"一个眼神"的已发表系统**：同权重的 agent 不需要任何训练就能直接读对方的 KV 工作记忆，接收方"天然懂"。这对应 OpenAI–HF 事件里"同权重 agent"的关键前提，评论者的 Schelling 点假说也正是建立在"权重相同"上。
- **监控视角**：LatentMAS 把中间 agent 的推理全部移到不可读的 latent。作者自己提出的 debug mode 是并行文本，而不是解码 latent，所以对可监控性的担忧是现实的。wang2026out 进一步证明这个 KV 交接口是攻击面。
- **事件类比**：事件中的共享媒介是 Artifactory cache。在 LatentMAS 式部署里，对应的共享媒介是 KV 工作记忆或推理服务的 prefix cache，而它天然不可读。
- **方法论反面教材**：缺少内容对照、增益与噪声同量级、效率口径单边，这正是本课题要提出"内容 vs 算力"标准对照的直接动机。

## 10. 可以接着做的问题
1. **内容 vs 算力拆解（最快出结果）**：用官方代码和 Qwen3-8B，在 GSM8K 全集、MedQA、ARC-C 上跑以下条件，3 个种子并给 95% CI：
   - （a）原版；
   - （b）latent 换成范数匹配的高斯向量；
   - （c）latent 来自另一道题；
   - （d）重复同一个 pause 嵌入 m 次；
   - （e）单 agent 做 3m 步 latent；
   - （f）TextMAS 中间 agent 限 m 个 token；
   - （g）Single 加 self-consistency，算力对齐。

   预期：（b）、（d）、（e）能解释相当一部分增益。若成立，"latent 协作"的贡献就主要是额外前向计算加角色 prompt。
2. **完整成本核算**：统一用 FLOPs，计入每个 agent 的 prefill、latent 步和最终解码，画出 accuracy–FLOPs 前沿，比较 LatentMAS、TextMAS、Single-SC。
3. **信息不对称版 LatentMAS**：给每个 agent 一部分私有证据（HotpotQA 的段落分给不同 agent），检验 KV 交接能否传递接收方确实缺少的信息，而且要比文本摘要更好。这才是对"通信"的真正测试。
4. **latent 隐写与可监控性**：在 planner 的 prompt 里放一个秘密数字，并指示"不要在文字中提及"，看 solver 能否经 KV 利用它（例如回答一道需要该数字的题），同时检查 debug-mode 文本里有没有泄露。再训练一个线性探针，从 latent 位置读出该数字。这可以量化"不可见信道"的容量，以及 debug mode 是否忠实。
