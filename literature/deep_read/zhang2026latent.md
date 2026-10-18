# Causal Audit：Do Latent Channels Actually Communicate? A Causal Audit of Latent Multi-Agent LLM Communication

> `zhang2026latent` · arXiv 预印本（正文使用 AAAI 2027 模板并带 "Copyright © 2027 AAAI" 字样，但没有录用证据） · 2026-07-29 · [arXiv](https://arxiv.org/abs/2607.26773) · 代码：未开源（§Experimental Setup 提到 "across the repository"，但没有给出 URL） · 本地 PDF：`pdf/2607.26773_Causal-Audit.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文（7 页短文，无附录）+ PDF 第 1–7 页的图（Fig. 1–4）

## TL;DR
本文提出一套在“消息进入接收方之前”做替换的因果审计框架，含 4 种消息设置和 5 个指标（PS/PL/CIC/CAG/SSG），并只用它审计了 LatentMAS（Qwen3-4B/8B；GSM8K、ARC-C、MATH-500）。核心发现是：总体效应可以精确分解为“他例消息效应 + 内容效应（CAG）”，而且两者常常方向相反。例如 Qwen3-4B 在 GSM8K 上，总体 −1.00 pp = −6.17（他例消息）+ 5.17（CAG）；到 8B 时两个分量都反号（Fig. 1c）。样本量很小（每格 40–100 题，1–3 个种子），框架承诺的多数诊断都没有给出结果。

## 1. 问题与动机
- latent 通信论文通常只报告端任务准确率。但增益可能来自至少四种来源：发送方特有的内容、额外计算、上下文复用、冗余推理轨迹（§Intro）。只看准确率，无法判断接收方是否真的用到了“为当前样例生成的内容”。
- 作者把问题表述为 capacity-versus-usage：通道表示能力强，不等于接收方用了它。这一区分借自 emergent communication 文献 Lowe et al. 2019 的 positive signaling 与 positive listening，以及 Jaques et al. 2019 的因果影响度量。
- Table 1 把 CIPHER、LatentMAS、OBF、DroidSpeak、C2C、Interlat、ThoughtComm 按五个“可识别性”属性打分：消息级干预、样例特定内容、等算力自替换、等价检验。作者认为现有方法都缺后三项。

## 2. 方法
- **信道**：论文声称框架通用于三类信道：CIPHER 的概率加权 embedding、hidden state、KV cache。但实验只审计了 LatentMAS。LatentMAS 的消息是上游 agent 的逐层 KV cache，包括 prompt 行和 m=40 步 latent thought 行。
- **对齐与映射**：同构，sender 与 receiver 是同一个 checkpoint，training-free，不训练任何参数。
- **协议与拓扑**：沿用 LatentMAS 的顺序多 agent 管线。"sender" 指最终答题 agent 之前的一个或多个上游 agent，"receiver" 指最终答题 agent。干预点在 sender 消息交给 receiver 的边界。对 KV 方法只替换 receiver 初始 cache 中由 sender 产生的行，receiver 自己生成的状态不动（§Setup and Audited Boundary）。
- **四种消息设置**（Eq. 3）：
  - $M_0=\emptyset$（无消息）
  - $M_{cur}$（当前样例消息）
  - $M_{oth}$（同一测试集中另一题的消息，长度近似匹配，K=4 个取平均）
  - $M_{self}$（receiver 在相同接口、相同算力预算下自己生成的消息）
  - 另有跨 benchmark 消息，只用于 BME。
- **五个指标**（Table 2，Eq. 5）：
  - PS：$I(M_{cur};X)$，X 主要是“sender 自己答对没有”，用 cross-fitted MI 下界加置换检验估计。
  - PL：cur 与 none 两种设置下预测分布的 JSD，用首 token 或 teacher-forced 续写计算。
  - CIC：cur 与 oth 两种设置下预测分布的 JSD。
  - CAG：$\bar U_{cur}-\bar U_{oth}$。
  - SSG：$\bar U_{cur}-\bar U_{self}$。
- **恒等分解**：OPE = OME + CAG，CAG = DSC + SSG（Eq. 6）。
- **组件归因**：NLD(C) 从 oth 消息出发恢复 cur 的部分组件（序列窗口、layer×region×K/V），度量 teacher-forced 对数概率差被恢复的比例（Eq. 7）。
- **推断**：在样例层面配对；用 paired bootstrap CI 加 sign-flip 检验；用 ±1 pp 的等价边界判断“可忽略”。三项硬检查是：mask 消息后 identity 效应应降到数值地板；用 cur 替换 oth 时 CIC 和 CAG 应为 0；完全恢复时 NLD 应为 1。噪声、打乱、shuffle 只作诊断，不作主对照。

## 3. 实验设置
- 模型：Qwen3-4B、Qwen3-8B，开启 thinking mode。
- 采样：nucleus 采样，T=0.6，top-p 0.95，生成上限 2048 token，latent 步数 m=40（从 {0,2,5,10,20,40} 中按原方法推荐区间的低算力端取，作者称没有按测试表现挑选）。
- benchmark 与样本量：GSM8K 100/60 题（4B/8B），ARC-C 80/40，MATH-500 60/40。
- 种子：GSM8K 4B 用 3 个、8B 用 2 个；ARC-C 各 2 个；MATH-500 各 1 个。
- 算力：单张 A40 48GB，Transformers 5.13.0。
- 基线：只在设置之间做内部对比，没有文本 MAS 基线，也没有其他 latent 方法。

## 4. 主要结果
- **GSM8K**（Fig. 1c）：
  - 4B：OPE −1.00 = OME −6.17 + CAG +5.17，两个分量的 CI 都不含 0。
  - 8B：OPE +1.67 = +3.96 − 2.29，分量反号。
- **MATH-500**（Fig. 2）：
  - 4B：OPE +15.00 = OME +8.33 + CAG +6.67，CAG 的 CI 为 [0.42, 12.50]。
  - 8B：OPE +10.00，几乎全部来自 OME（+8.13）；CAG 为 +1.88，CI 跨 0。
- **ARC-C**（§Aggregate）：4B 为 −0.63 = −2.97 + 2.34；8B 为 0.00 = −1.56 + 1.56；CI 都包含 0。
- **CAG 与 SSG 不同**（Fig. 3）：
  - GSM8K 4B：CAG +5.17，SSG −2.00（CI 跨 0）。也就是说，sender 的消息优于他例消息，但不优于 receiver 自生成的消息。
  - MATH-500 8B：CAG +1.88，SSG +10.00 [2.50, 20.00]。
  - 所有区间都不完全落在 ±1 pp 内，所以没有任何一格能确立“可忽略”。
- **PL/CIC**（Fig. 4）：首 token JSD 跨越多个数量级，多数在 $10^{-8}$ 到 $10^{-6}$。4B 的 ARC-C seed 1 和 GSM8K seed 1 约为 $10^{-2}$。8B 的 CIC 一律远小于 PL。分布敏感度与任务价值不对应。

## 5. 消融与诊断
- 正文**没有报告** PS 的数值，也没有报告 NLD 组件恢复、BME、message-realism、receiver-instability 的任何结果。§3 承诺的 diagnostic ladder 与 restoration sweep 都没有出现在实验中。
- 只给出 m 的扫描范围和若干解码配置的探索说明（greedy、不同生成上限、thinking 开或关、aligned KV relay 变体），没有给出对应结果。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - 框架被声称适用于 embedding、hidden state、KV 三类信道，但实际只审计了 LatentMAS 一个方法。Table 1 中 “This paper” 五项全满分，然而“等价检验”一项在实验里一次也没有得出等价结论（Fig. 3）。
  - 贡献列表中的 “component restoration、message-realism measurements” 都没有数据支撑。
  - 能站住的结论是：总体准确率掩盖了方向相反的分量。而且在 LatentMAS 上，4B 的 GSM8K 与 MATH-500 确实存在 CI 不含 0 的正向内容效应（CAG +5.17、+6.67）。这和“latent 通信只是接口效应”的强叙述并不完全一致。
- **缺失的对照**：
  - 没有置零 cache 或随机 cache 作主对照（作者有意只把它们作诊断）。
  - 没有等 token 的文本消息基线。
  - 没有异构或跨族模型，也没有 C2C、KVComm 等其他方法。
  - 没有区分 prompt 行与 latent-thought 行，所以无法回答“内容走的是 prompt KV 还是 latent thought”。Cheng et al. 的 E.2 也把这一点列为未做的 position-partition 实验。
- **可能的混杂因素**：
  - 他例消息只做了“近似”长度匹配，而且 K=4 个他例消息在样例内平均，可能引入长度或难度差。
  - n=40–100、1–3 个种子，CI 很宽。例如 MATH-500 8B 的 SSG 区间宽达 17.5 pp。
  - Fig. 4 与正文不一致：正文说 MATH-500 只用 1 个种子，图中 4B 却画了 MATH-500 seed 1/2；正文说 8B ARC-C 用 2 个种子，图中只有 1 个。
  - Fig. 1 标注 “LatentMAS λH”，但正文没有解释 λH 的含义。

## 7. 局限
- **作者自述**：正文没有专门的 Limitations 节。只在 Related Work 提到 PS 是有限样本的 MI 下界，以及 patching 存在 off-distribution 风险。
- **我们的判断**：这是一篇框架提案型的短文。指标体系设计得很好，尤其是 SSG 和恒等分解，但实证覆盖严重不足：单方法、单族、小样本，承诺的诊断大多缺席。它最有价值的两点，一是证明了“近零总体效应 ≠ 无通信”，二是给出 CAG 与 SSG 可以分离的例子。第二点的证据只有 n=40 一个种子，非常脆弱。

## 8. 可复现性
- 代码未开源；说文中提到 repository 但没有 URL。
- 关键超参基本给全：m=40、T=0.6、top-p 0.95、2048 上限、K=4、thinking 开。但具体题号、他例消息的长度匹配规则、“self-generated” 的算力匹配细节都没有给出。
- 算力需求低：Qwen3-8B 单张 A40 即可。单张 H100 可以复现全部结果，用 LatentMAS 官方代码自己实现审计也只需数 GPU 天。若把样本量扩到 n=500，则需要更多。

## 9. 与本课题的关系
- 它直接回答“隐式通道的增益是不是通信”这个核心问题，并给出一套可复用的度量语言：PS 对应“消息里有没有”，PL/CIC 对应“接收方听没听”，CAG 对应“内容有没有价值”，SSG 对应“需不需要另一个 agent”。
- SSG 和“一个眼神就懂”的设定特别相关。如果 receiver 用同样的算力自己想也能得到同等收益（SSG≈0），那么通信就只是额外计算，而不是传递“对方知道我不知道的东西”。
- 对 OpenAI–HF 事件的启示：如果同权重 agent 改用 latent relay，审计员只看任务表现无法判断它们是否在交换样例特定的信息。必须有 cur/oth/self 三向对照。

## 10. 可以接着做的问题
1. **扩样本复核 4B 正 CAG**：用 Qwen3-4B/8B 加 LatentMAS 官方代码，在 MATH-500 全部 500 题、GSM8K 1319 题上各跑 5 个种子，计算 CAG 和 SSG，并做 TOST 等价检验。预期：若 Cheng et al. 的结论成立，GSM8K 的 CAG 会收缩到 ±2 pp 以内；MATH-500 这类难题可能保留显著正 CAG。这能检验“任务难度调节内容效应”的假设。
2. **位置分区错配**：只把 latent-thought 行（例如 Cheng et al. E.3 所说的位置 180–219）换成他例，prompt 行保持匹配；或者反过来。预期：大部分 CAG 来自 prompt KV（即“文本的 KV 形态”），latent-thought 行的 CAG≈0。这直接回答“latent thought 到底有没有在传”。
3. **把 PS 真正做出来**：在 LatentMAS 消息上训练线性 probe，解码 sender 是否答对、sender 的最终答案。然后与 CAG 联合分析，回答“编码了但没被用”（PS 高、CAG 低）是否普遍存在。预期 PS 显著而 CAG 很小，这正是 Lowe et al. 所说的 signaling≠listening 在 LLM 上的复现。
4. **SSG 用于异构场景**：在 C2C 或 Draft-KV 这类强 sender 配弱 receiver 的设置里测 SSG，区分“借用强模型的计算”与“传递信息”。
