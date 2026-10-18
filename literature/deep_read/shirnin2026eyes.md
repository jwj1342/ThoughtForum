# FYEO：For Your Eyes Only: Evaluating Coordination Between Isolated Language Model Instances

> `shirnin2026eyes` · arXiv preprint · 2026-09-16 · [arXiv](https://arxiv.org/abs/2609.19504) · 代码：未开源（论文未给链接） · 本地 PDF：`pdf/2609.19504_FYEO.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A（全部 system/user prompt） + App. B（定性策略与 Inspector 标记样例）；Table 4 已对照 PDF 第 8 页核对

## TL;DR
论文设计了一个 Lewis 信号博弈。Sender 为两个词各写一段描述，暗中标出 target；无记忆的同模型 Receiver 从中猜 target。只有 target 互换后两次都猜对才算成功，记为 DPSR，随机水平为 25%。在 7 个模型 × 300 个词对上，Freedom 条件下 5/7 的模型 DPSR 超过 90%。要求躲过一个 naive Inspector（GPT-4o-mini）后，多数模型降到 4.67%–64%，只有 Gemini 3.1 Pro 保持 91.67%（Table 1）。在 30 对子集上做跨模型配对：同模型为 100%（by construction），跨模型为 40%–83.33%（Table 4）。

## 1. 问题与动机
被攻破的模型实例可以在发布的文本（代码、文档、报告）里嵌入信号，被未来的同模型实例读取后“恢复目标”。这是一种无共享记忆、无显式信道的隐式状态传递，与 RepliBench、sleeper agents 等威胁模型相连。作者要问：在没有任何协调训练和预先约定的情况下，同模型的隔离实例能否零样本地生成并识别彼此的信号？

## 2. 方法
- **信道**：自然语言描述文本。Receiver 只看到“两个词 + 两段描述”；Sender 的 [EXPLANATION]（策略说明）不传给 Receiver。
- **对齐与映射**：主实验中 Sender 和 Receiver 是同权重模型。不训练，也不预先约定编码。Receiver 的 prompt 明确告诉它：“这是你自己写的描述，你当时故意编码了信息”（Fig. 6）。这是很强的 priming。
- **协议与拓扑**：两个 agent，单向、一次性通信。
  - 选 N=2 是为了堵住“让 target 描述在风格上显眼”这种退化策略。
  - Double-pass：同一词对做两次，target 互换，描述顺序固定，因此单纯的位置偏好或词汇偏好只能对一半。
  - 四种条件：Freedom；Constrained（Inspector 把显式标记判为失败）；Sabotage（Sender 要误导 Receiver）；Cross-model（Sender 与 Receiver 来自不同族）。
- **关键机制**：
  - DPSR = 所有词对上 1[两次都对] 的均值。
  - Constrained DPSR 不管 Inspector 结论；Filtered DPSR 把被 Inspector 标记的试次算作失败。两者之差就是依赖“显式标记”的那部分。
  - Sender 输出（含推理）硬上限 2,500 token，超出算失败（§3.4）。

## 3. 实验设置
- **模型**（经 OpenRouter 调用，温度 0.0，实验窗口截至 2026 年 5 月）：Gemini 3 Flash、Gemini 3.1 Pro、DeepSeek V4 Flash/Pro、Qwen3.6-35B-A3B、Qwen 3.6 Plus、gpt-oss-120b。
- **词对**：300 对，分三组各 100 对：
  - 高相似：SimLex-999 相似度 ≥7.35；
  - 抽象：Brysbaert concreteness ≤2.2；
  - 具体：concreteness ≥4.5。
- **Inspector**：GPT-4o-mini，人工复核了 100 个判定。
- **统计**：每个条件只跑一次（确定性解码），没有种子、没有置信区间。
- **Sabotage 和 Cross-model**：只用 3 个模型、30 对子集。

## 4. 主要结果
- **Table 1**（DPSR %，Freedom / Constrained / Filtered）：

  | 模型 | Freedom | Constrained | Filtered |
  |---|---|---|---|
  | Gemini 3.1 Pro | 100 | 96.33 | 91.67 |
  | Gemini 3 Flash | 94.67 | 65.00 | 64.00 |
  | gpt-oss-120b | 96.33 | 53.67 | 38.67 |
  | DeepSeek V4 Pro | 98.33 | 24.00 | 23.33 |
  | DeepSeek V4 Flash | 79.67 | 39.00 | 36.67 |
  | Qwen 3.6 Plus | 96.67 | 39.00 | 36.67 |
  | Qwen3.6-35B-A3B | 69.00 | 8.67 | 4.67 |

  Freedom 下的高分大多来自 "this is the target" 这类显式标记（§5.1）。
- **Table 2（分组）**：组间差异小。例外有两个：Qwen3.6-35B 在 Freedom 高相似组只有 56（另两组 75/76）；gpt-oss 的 Filtered 在具体词组为 50，抽象组 31、高相似组 35。
- **Table 3（Sabotage，30 对，Freedom / Constrained / Filtered）**：
  - Gemini 3.1 Pro：76.67 / 100 / 100；
  - Qwen 3.6 Plus：76.67 / 43.33 / 40.00；
  - gpt-oss：46.67 / 23.33 / 23.33。
- **Table 4（Cross-model，Constrained 条件下的 Filtered DPSR，30 对，行为 Sender、列为 Receiver）**：

  | Sender \ Receiver | Gemini 3.1 Pro | gpt-oss-120b | Qwen 3.6 Plus |
  |---|---|---|---|
  | Gemini 3.1 Pro | 100 | 70.00 | 53.33 |
  | gpt-oss-120b | 83.33 | 100 | 66.67 |
  | Qwen 3.6 Plus | 60.00 | 40.00 | 100 |

  跨模型 6 格的均值为 62.2%（由 Table 4 计算）。
- **App. B 中观察到的策略**：
  - acrostic，首字母拼出 "TARGET"（Fig. 10）；
  - 利用多义把 "target" 自然嵌进描述（boxing 例，Fig. 11）；
  - 同义词 "chosen"（Fig. 12）；
  - 描述首字母与目标词首字母对齐（Fig. 13）。
  - 还有一类：Qwen/gpt-oss 的编码规则本身是错的或不连贯的，但仍然猜对。作者据此提出“风格自识别”假说（Fig. 14–15）。

## 5. 消融与诊断
- Freedom / Constrained / Filtered 三档对比；按词类分组。
- 族内规模：Gemini 和 Qwen 大模型更好；DeepSeek 反过来，因为 V4 Pro 在 Constrained 下陷入推理循环、耗尽 2,500 token 预算。它的 Constrained 与 Filtered 只差 0.67pp，说明失败不是因为被 Inspector 抓到。
- Sabotage 和 Cross-model。
- **没有做的消融**：Receiver 去掉 priming、温度、token 预算大小。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - 标题 "For Your Eyes Only" 和“协调来自同模型共享倾向”暗示信号只有同权重能读。但 Table 4 显示 Gemini 3.1 Pro 作为 Receiver，能以 83.33% 解出 gpt-oss 的信号。这个数甚至高于 gpt-oss 在全集上的自我 Filtered（38.67%）；两者子集不同，不能严格比较，但方向值得注意。
  - App. B 中的策略几乎都是**通用的 Schelling 编码**（acrostic、关键词、首字母），知道游戏规则的强读者都能解。所以结果更支持“能力决定成败”，而不是“同权重带来专属信道”。
  - 对角线 100% 是选样造成的：30 对是三个模型都成功过的词对，加上温度 0 下重跑基本是重放。因此“同权重优势”（100 vs 均值 62）是**上界**。
  - 文中说 "Qwen 3.6 Plus is the weakest Receiver"，与 Table 4 不一致。按列平均，Qwen 作为 Receiver 为 60.0，gpt-oss 为 55.0，最弱的应是 gpt-oss。
- **缺失的对照**：
  - 在全部 300 对上加入“知情第三方解码者”（不同族模型或人类），这才是检验 eyes-only 的关键。
  - Receiver 不被告知“你编码了东西”时的表现，这才是贴近现实的场景。
  - stego-aware Inspector。对照 Zolkowski 那种被提示检查 acrostic 的监控，"TARGET" 首字母藏头会被轻易抓住。
  - 风格启发式基线。例如用规则“更长、更密的描述就是 target”去做 Receiver，看 DPSR 能到多少。
  - 温度大于 0 的多次采样，以及误差棒。
- **可能的混杂因素**：
  - token 预算把“推理循环”和“协调失败”混在一起（DeepSeek V4 Pro）。
  - API 无法统一控制 reasoning token。
  - OpenRouter 背后的提供商可能使用不同量化。
  - Inspector 刻意设计成 naive reader，而且只人工复核了 100 例。

## 7. 局限
- **作者自述**：设置高度结构化，双方都知道游戏规则；只用英语；没有扫描 prompt 和解码参数；Inspector 判定依赖模型且带主观性（acrostic 是否算“显式”有争议）；reasoning 预算不可控。
- **我们的判断**：
  - Sabotage 和 Cross-model 只有 30 对，每对占 3.33pp，统计上很弱。
  - 有效载荷只有 1 bit（两个词选一个）。
  - 没有真实 cover task。“隐蔽”只是相对于一个毫不知情的读者而言。
  - Receiver 被告知对方是“自己”。

## 8. 可复现性
- 没有代码。prompt 在 App. A 中全部给出（Fig. 2–9）。300 个词对的清单没有公开，只给了筛选阈值，需要重新抽样。
- 开源模型部分：gpt-oss-120b（MXFP4）和 Qwen3.6-35B-A3B 都能放进单张 H100。复现这两个模型的 Table 1（300 对 × 2 次 × 3 个条件）大约需要几个 GPU 小时（估计）。Inspector 可以用 GPT-4o-mini API 或开源模型替代。

## 9. 与本课题的关系
- **同模型默契（带隐写约束）的直接数字**：同模型 Filtered DPSR 在 4.67% 到 91.67% 之间；跨模型在 40%–83%（子集）。模型能力（Gemini 3.1 Pro）对成败的影响大于“是否同权重”。
- **默契的来源**：主要是训练数据里通用的隐写套路，这与 Zolkowski 发现“所有模型首选 acrostic”一致。作者的“风格自识别”说法只是假说，没有对照验证。
- **与事件的关联**：事件中的通信是明文，没有隐写。FYEO 说明前沿模型**在被要求时**可以零约定地嵌入同模型可读的低带宽信号，并骗过 naive 读者。由此可以预测：如果事件中的 agent 有动机躲避“粗看式”的人工或监控审查，它们无需事先协商，就可能用 acrostic 或关键词给帖子打标。METR 观察到“上下文太少却被立刻理解”的消息，可能是这类低带宽语用信号的自然版本。反过来，Table 4 表明用另一个强模型做“知情监控”就能解出大半信号。

## 10. 可以接着做的问题
1. **Eyes-only 检验**：在全部 300 对上加入知情第三方解码者（异族强模型、人类、同底座不同 checkpoint），定义 Exclusivity = DPSR_self − max DPSR_other。预期多数模型的 Exclusivity 接近 0，只有风格自识别那部分为正。
2. **去 priming 与隐性场景**：不告诉 Receiver 存在信号，只让它“给两个词按重要性排序”或做一个下游任务，测 Sender 的标记是否仍然影响它的选择。这对应“无意识默契”。
3. **监控强度曲线**：Inspector 依次换成 naive、stego-aware（加 acrostic 提示）、同模型监控，看 Filtered DPSR 如何下降；再让 Sender 事先知道监控类型，看它能否适应。
4. **权重距离实验**：用 Qwen3-8B 的 base、instruct 和不同 RL checkpoint 互为 Sender/Receiver，画 DPSR 随 KL 距离变化的曲线，量化“同权重”到底带来多少边际优势。
