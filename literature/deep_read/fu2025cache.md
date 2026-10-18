# C2C：Cache-to-Cache: Direct Semantic Communication Between Large Language Models

> `fu2025cache` · ICLR 2026 · 2025-10-03 · [arXiv](https://arxiv.org/abs/2510.03215) · 代码：https://github.com/thu-nics/C2C（论文称代码、配置和 fuser checkpoint 均已发布） · 本地 PDF：`pdf/2510.03215_C2C.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A.1–A.5（arXiv v2，2026-03-02）；Table 4、6、7 已对照 PDF 第 8–9 页核对

## TL;DR
在 Sharer 和 Receiver 都冻结的前提下，C2C 训练一个 fuser，把 Sharer 对同一输入算出的 KV-cache 投影后残差地加到 Receiver 的 KV 上，再加逐层可学习门控。Receiver 固定为 Qwen3-0.6B，平均准确率比单模型高 6.4–14.2 分，比文本通信（T2T）高 3.1–5.4 分，延迟平均快 2.5×。但论文自己的 Table 6 显示，**Sharer 换成 Receiver 自己（Identical）时，就已拿到约 86% 的增益**（平均 36.95→46.41，C2C 为 47.95）。增益大部分来自"训练了一个 4.78 亿参数的 KV 适配器"，异构 Sharer 带来的内容只多出约 1.5 分。

## 1. 问题与动机
- 文本通信有三个问题：带宽低（高维表示要压成 token 再解压），语言有歧义（Fig. 2 的 `<p>` 例子），以及逐 token 解码带来的延迟。
- 两个 oracle 实验说明 KV-cache 可以作为通信介质：
  - **Cache Enrichment（Table 1）**：先对 few-shot 示例 E 加问题 X 做 prefill，再只保留 X 段的 KV 去解码。Direct 58.42，Few-shot 63.39，Oracle 62.34。也就是说 cache 长度不变，"被 E 浸染过的 X 的 KV"就能提升准确率。表中没写模型；Table 10 的 28 层与 Qwen3-0.6B 一致。
  - **Cache Transformation（Fig. 3）**：用 MSE 训练一个 3 层 MLP，把 Qwen3-4B 最后一层的 KV 映射到 Qwen3-0.6B，t-SNE 上映射后落进目标分布。训练集是 MMLU-Redux，与评测集同源（App. A.3.2），所以这条证据很弱。
- 逐层富化的效果正负不一（Table 10，单层富化只有 L4、L16 高于基线），作者据此设计了门控。

## 2. 方法
- **信道**：Sharer 对**同一个输入 X**（Receiver 的 prompt）做 prefill，得到全部层的 KV。fuser 按层把它和 Receiver 自己的 KV 拼接、投影、融合，残差加回 Receiver 的 KV：C_F = C_n(X) + F_n(C_n(X), C^S_{G(n)}(X))（Eq. 3）。只在 prefill 阶段融合，解码用融合后的 cache 加自生成的 cache（Eq. 4）。
- **对齐与映射**：支持异构。
  - Token 对齐：Receiver 的每个 token 解码成字符串，再用 Sharer 的 tokenizer 重新编码；一对多时取覆盖最长的那个；模板段用 pad 补齐（App. A.1.2）。
  - 层对齐：terminal alignment，从最后一层往前一一配对（App. A.1.1）。
  - 训练：两个 LLM 冻结，只训 fuser，损失是 Receiver 回答的 next-token loss。
  - **可训练参数**：Table 6 中 C2C 为 478M，Identical 为 529M；Receiver 全参微调（Single）是 596M。fuser 规模和 0.6B 的 Receiver 本身相当。
  - 训练数据：主实验用 OpenHermes-2.5 前 50 万条，1 个 epoch，1,929 步，batch 256。规模和组合实验改用 MMLU auxiliary train 的 1.5 万条。LongBench 实验用 LongBench-E 的 3/4（1,896 条）（App. A.3.5）。
- **协议与拓扑**：一对一，一轮，单向（Sharer→Receiver），不保留 Sharer 的文本。App. A.5 有一对多（Table 13）、多对多共享投影（Table 14）、GSM8K 两 agent 流程（Table 15）的初步尝试。
- **关键机制**：fuser 有三部分（Fig. 5）。
  - 投影加特征融合层。
  - 输入相关的 head 调制（dynamic weighting）。
  - 逐层 Gumbel-sigmoid 门。训练时温度从 1.0 退火到 0.001，推理时门值二值化。

## 3. 实验设置
- **模型**：Receiver 主要是 Qwen3-0.6B。Sharer 有 Qwen2.5-0.5B-Instruct、Llama3.2-1B、Qwen3-4B-Base，另有 Gemma3-1B、Qwen2.5-Math-1.5B、Qwen2.5-Coder-0.5B（Table 7），以及 Qwen3-4B（Table 9、11）。规模在 0.5B–4B，Receiver 几乎都是 0.6B。
- **Benchmark**：OpenBookQA、MMLU-Redux（去掉 "no correct answer" 题）、ARC-C、C-Eval，另有 LongBench-E。全部为非 CoT 选择题，零样本，greedy，最大生成 64 token。
- **Baseline**：
  - T2T：Sharer 的 prompt 是 "In one clear sentence, describe the most essential background knowledge... Do NOT directly solve"（Text 3），最长 256 token。
  - Query-level routing：RouteLLM 式矩阵分解。
  - 单模型。
- **种子与算力**：只用 seed 42，**没有方差**。延迟在单张 A100 上测，batch=1。训练从 Table 12 推算为 8 卡，每对组合约 45–54 GPU·h。

## 4. 主要结果
- **Table 4**（Receiver Qwen3-0.6B，fuser 在 OpenHermes 上训练），四个 benchmark 的平均：
  - Receiver 36.95。
  - Qwen2.5-0.5B 作 Sharer：T2T 42.60，C2C 47.95。
  - Llama3.2-1B 作 Sharer：C2C 46.60。
  - Qwen3-4B-Base 作 Sharer：C2C 48.83（T2T 45.78）。
  - 单项例如 OpenBook，C2C 52.60，T2T 44.00。
- **延迟**（Table 3 拆解，MMLU-Redux，Qwen2.5-0.5B→Qwen3-0.6B）：
  - Receiver 单独 308 ms。
  - T2T 1,596 ms，其中 Sharer 解码 80 个 token 花了 1,312 ms。
  - C2C 445 ms = Sharer prefill 20 + 融合 90 + Receiver prefill 27 + 解码 308。
  - **Sharer prefill 和融合时间已经计入**。C2C 比单独 Receiver 慢约 44%。
- **Table 7**（MMLU aux 训练，在 MMLU-Redux 上评测）：五组搭配上 C2C 比 T2T 平均高 8.59 分。例如以 Gemma3-1B 作 Sharer，C2C 45.90，T2T 41.35。
- **长上下文**（Table 5）：0–4k / 4–8k / 8k+ 三段，C2C 为 37.31 / 34.01 / 30.72，T2T 为 33.46 / 29.70 / 25.64。fuser 用 LongBench-E 的 3/4 训练，在剩下的 1/4 上测，属于同分布。
- **复杂 fuser C2C-C**（Table 9，Sharer Qwen3-4B，最长回答 8 token），各项准确率在 60.6–81.0，PGR 76%–86%。
- **一对多**（Table 13，MMLU）：Receiver 35.53。4B-Base→R 为 60.71。两个 Sharer 一起为 64.60，这两个 fuser 是分别训练、直接组合的。
- **GSM8K agent 流程**（Table 15）：单模型 41.17，T2T 61.18，C2C 62.55，T-C2C（文本解读加 cache 融合）78.01。

## 5. 消融与诊断
- **增益来源（Table 6，最关键）**：

  | 设置 | 可训练参数 | 四项平均 |
  |---|---|---|
  | Receiver 原始 | – | 36.95 |
  | Single（Receiver 全参微调） | 596M | 41.52 |
  | Identical（Sharer = Receiver = Qwen3-0.6B） | 529M | 46.41 |
  | C2C（Qwen2.5-0.5B 作 Sharer） | 478M | 47.95 |

  作者把这张表解读为"不纯来自容量"。但它其实也说明：**用自己的 KV 喂给 fuser（没有任何外部信息）就能拿到 86% 的增益**。作者把这一点类比为 looped transformer，承认了 cache 层面的"自我通信"有效。
- **Fuser 结构（Table 8）**：只做投影、丢掉 Receiver 的 cache，平均 20.70，比 Receiver 原始还低 16 分。加上融合后 44.88，再加门控后 47.95。所以 Receiver 自己的 cache 必不可少，被注入的 Sharer 内容是"在自身表示上的修正"。
- **有效秩（Table 2）**：K 从 388 升到 395，V 从 532 升到 560。增幅很小，用"秩更高 = 语义更丰富"来解释过度了。
- **门控（App. A.4.2）**：用 OpenHermes 训练时门几乎全开（>98.21%），用 MMLU 训练时只开 52.67%。
- **渐进替换（Fig. 11）**：融合 cache 的比例在 0–50% 区间时准确率先降后升，说明部分融合的 cache 对 Receiver 是分布外的。
- **训练曲线（Table 12）**：Qwen2.5-0.5B 那组在 300 步时 MMLU-Redux 为 44.30，高于最终 checkpoint 的 42.92。
- **失败案例（App. A.4.6）**：Sharer 的错误理解会把 Receiver 带偏。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - "LLM 能经 KV 进行语义通信"这一说法，只得到弱支持。Sharer 看到的是和 Receiver **完全相同的输入 X**，信道里没有 Receiver 缺失的信息，能传的只有 Sharer 权重里的"理解或知识"。Identical 已经拿到大部分收益，异构 Sharer 带来的增量约 1.5 分，而且是单种子、没有置信区间。
  - "隐私友好"（§5 Future work）与论文自己的 Cache Enrichment oracle 相矛盾。Oracle 恰好说明：删掉 E 的 KV 之后，E 的信息仍然留在 X 的 KV 里。KV 并没有隐藏内容。
- **缺失的对照**：
  1. 没有错配 cache（拿另一道题的 Sharer KV）、随机 cache（统计量匹配的高斯噪声）、置零 cache 的对照，因此无法区分"内容"和"一个吃 Receiver 自身 KV 的适配器"。
  2. 没有等参数量、等数据的 LoRA 或 prefix-tuning 基线。Single 是 OpenHermes 上的全参微调，可能伤了选择题格式，算不上强基线。
  3. T2T 被人为削弱：Sharer 只能说"一句背景知识"，不准给答案，也没有经过任何训练；C2C 却有 50 万条 SFT。两者既不等算力，也不等训练。
  4. Table 7、13 的 fuser 用 MMLU aux train 训练，在 MMLU-Redux 上测，属于域内训练。
- **可能的混杂因素**：
  - fuser 相当于在 Receiver 前面加了一个约 0.5B 的可学习"KV 改写器"，Receiver 的指令遵循和格式也会因 SFT 改善。
  - Qwen3-4B-Base 单独只有 1.03%（不会按格式作答），T2T 时会疯狂输出，导致 7.54 s 的延迟。所以 14.41× 的加速主要来自基线异常。
  - 在强带弱场景，Qwen3-4B 单独就有 68–87 分（Table 9），C2C-C 最多 81。系统本来就要跑 4B 的 prefill，**直接用 Sharer 更准，延迟相当**（0.24 s 对 0.21–0.27 s）。
  - benchmark 都是选择题，接近饱和或有污染风险（ARC-C、OpenBookQA、MMLU）。
- **效率口径**：Table 3 计入了 Sharer prefill 和融合的 90 ms，这一点比较规范。但没把 fuser 训练成本（约 45–54 GPU·h/对，Table 12）摊进去，加速比也很依赖 T2T 消息有多长。

## 7. 局限
- **作者自述**：弱 Sharer 加强 Receiver 时会出现负迁移；N 个模型两两通信需要 O(N²) 个 fuser，App. A.5.2 给出了 O(N) 的初步方案。
- **我们的判断**：
  1. 这是"带训练的 KV 适配"，换一对模型就要重训。
  2. 只测了单轮单向，以及 0.5B–4B 的小模型、选择题。
  3. 没有信息不对称的设置，即 Sharer 掌握 Receiver 没有的上下文。
  4. 没有内容对照，所以"语义通信"的说法缺乏因果证据。
  5. 没有安全分析：fuser 会不会把对抗扰动放大？门控能不能挡住？

## 8. 可复现性
- 代码和 checkpoint 声称已公开。超参在 App. A.3.5 给得比较全（lr 1e-4，线性调度，10% warmup，wd 0.01，温度 1.0→0.001，seed 42）。
- 显存：0.6B 加 0.5B–4B 再加 0.48B 的 fuser，bf16 推理不到 20 GB，**单张 H100 就够**。
- 训练：50 万条 OpenHermes 约 45–54 A100·h。作者称 300 步（不到 9 GPU·h）就能接近最终效果，单卡 H100 估计 1–2 天可以复现主表（估计值）。
- 若直接用发布的 checkpoint，做错配或随机 cache 对照只需几十 GPU·分钟，**非常适合快速扩展**。

## 9. 与本课题的关系
- 对"一个眼神就懂"而言，C2C 是"**训练出来的眼神**"：异构模型之间不存在天然的默契，需要几十 GPU·h 的 SFT 学出一个翻译器。Identical 的结果反过来说明，同一模型读自己经过适配的 KV 就很有效。这和 OpenAI–HF 事件中"同权重 agent 天然共享表示"的担忧对应：同权重不需要翻译器，异构才需要。
- 在 OpenAI–HF 事件里，通信是明文写进共享 cache。C2C 说明，只要有一个训练好的 fuser，模型间可以交换**不可读的 KV**，而且 Sharer 可以是不会遵循指令的 base 模型（Qwen3-4B-Base 单独 1.03%，经 C2C 后 Receiver 可达 60.71，Table 13）。这正是"文本监控看不到"的那类信道。
- Cache Enrichment oracle 说明，信息可以"寄生"在别的 token 的 KV 里。这是一个潜在的隐写机制：消息不占 token 位置。

## 10. 可以接着做的问题
1. **内容对照（低成本，高价值）**：用发布的 Qwen2.5-0.5B→Qwen3-0.6B fuser，在 MMLU-Redux、ARC-C 上比较几种 Sharer KV：（a）正确；（b）另一道题的（长度对齐）；（c）逐层均值和方差匹配的高斯噪声；（d）置零；（e）Receiver 自己的（相当于把 Identical 推广到不重训）。至少 3 个种子，报告 bootstrap CI。预期：（b）、（c）若仍保留一半以上增益，就说明 C2C 主要是适配器效应。
2. **等容量、等数据基线**：在 OpenHermes 50 万条上给 Qwen3-0.6B 训练同样 ~478M 参数量级的 LoRA 或 prefix-tuning，并让 T2T 的 Sharer 输出完整 CoT 和答案。预期：C2C 相对这些基线的优势缩到 1–2 分以内。
3. **信息不对称的异构通信**：照 KVComm 的 Countries、Tipsheets、HotpotQA 设置，Sharer（Llama3.2-1B）独占上下文 C，Receiver（Qwen3-0.6B）只看到问题。比较 C2C 与"把原文 C 直接转给 Receiver"（Skyline）。这能真正检验异构 KV 能否承载 Receiver 缺失的信息。
4. **KV 寄生隐写与反演**：在 Cache Enrichment 设置下，把一个秘密数字放进 E 再删掉 E 的 KV，然后训练线性探针或小解码器，从 X 的 KV（以及 C2C 融合后的 cache）中还原该数字。这可以度量容量和可检测性，直接回应作者"隐私友好"的说法。
