# Interlat：Enabling Agents to Communicate Entirely in Latent Space

> `du2025enabling` · ACL 2026（long，2026.acl-long.1248） · 2025-11-12（本地为 v5，2026-07-13） · [arXiv](https://arxiv.org/abs/2511.09149) · 代码：https://github.com/XiaoDu-flying/Interlat（摘要中给出） · 本地 PDF：`pdf/2511.09149_Interlat.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文；App. A–H（Table 6–9、PCA、训练模板）；Table 1 已对照 PDF 第 5 页核对

## TL;DR
sender 是 instruction-tuned 模型。它生成文字计划时，每个位置的**末层 hidden state** 组成序列 H∈R^{L×d}，这个序列就是消息。消息经 MHA+projector adapter 后插到 actor 的输入 embedding 中（位于 `<bop>…<eop>` 之间），actor 是做了全参数 SFT 的 base 模型。论文还另外训练一个 reasoning model，直接在 latent 空间生成 K≪L 步的压缩消息。

ALFWorld 上，Qwen2.5-7B actor 在 seen 集达到 70.48，CoT(full) 为 67.14（Table 1）。这是本 batch 中内容对照做得最全的一篇，包括 CrossTask、噪声、协方差匹配高斯和随机旋转。但在 unseen 集上，这些破坏内容的对照与真实消息差距很小，例如 0.5B 的 WhiteNoise 为 57.21，Ours 为 57.46。论文宣传的“24×”是**消息生成延迟**（9.19s→0.39s），比较对象不是文本通信；而且压缩后的成功率回落到不通信（No-CoT）的水平。

## 1. 问题与动机
- 把高维内部状态下采样成离散 token 会丢掉其他推理路径，还会产生冗余。作者引用的估算是“≈15 bits/token vs ≈40k bits/hidden state”（§2）。
- 作者认为已有工作各有短板：AC 是一次性嫁接，SDE 仍绑定在语言轨迹上，两者都需要人工选层（§1）。
- 实验刻意只用两个 agent（sender→actor），并排除工具、检索和辩论，以减少混杂因素。

## 2. 方法
- **信道**：h_ℓ 是 sender 在预测 y_ℓ 之前的末层 hidden state，ℓ=1..L 覆盖整段计划（§3）。注意 sender 实际上**仍在自回归生成文字计划**，hidden state 是在生成过程中顺手收集的。注入位置是 actor 的第 0 层输入 embedding：E=[e(x_1..`<bop>`), adapter(h_1..h_L), e(`<eop>`)]，紧跟在任务 prompt 中的“step-by-step plan”字样之后（App. H 模板）。
- **对齐与映射**：adapter 是一层轻量 self-attention 加一个投影层，参数量未报告。actor 做**全参数 SFT**：lr 1e-5，batch 16，DeepSpeed。损失由三部分组成：
  - L_task：标准交叉熵。
  - L_sep=−JS(p(·|H), p(·|H̃))，H̃ 取 batch 内其他任务的消息，等于**在训练时直接把“匹配 vs 错配”作为对比目标**。
  - L_align：KL 到“只给文字计划 P”时的输出分布，再加 logits 余弦项。
  - 另有 curriculum：前 ⌊rL⌋ 个位置换成计划 token 的 embedding，r∈{0,…,1}。λ_sep 在 [0.1,1.0] 之间退火，λ_align 在 [0.1,0.2] 之间退火。
- **异构**：Qwen2LLaMA 实验中，Qwen2.5-7B-Instruct 的消息（d=3584）喂给 LLaMA3.1-8B-Base actor（d=4096）。actor 和 adapter 都要**针对这个 sender 重新训练**。
- **压缩**：M_φ 由 base 模型初始化，把 Proj(h_i) 回灌作为下一步输入，生成 K 步消息；此时 actor 和 adapter 冻结。损失由三项组成：
  - L_task：actor 的交叉熵。
  - L_pref：按“latent 降低了多少熵”加权的 KL，让压缩消息诱导出与全长消息相同的行为。
  - L_geom：actor 侧特征在各步平均后的方向余弦。
  - 学习率 5e-5，三项权重都为 1。
- **协议与拓扑**：每个 episode 开始时传一次消息，actor 随后在 ALFWorld 中用文本行动。Table 5 另有 3-agent 的 chain 和 tree 拓扑，消息长度固定为 32 步，端到端联合训练。

## 3. 实验设置
- **benchmark**：ALFWorld seen/unseen，每个 episode 上限 20 步，训练数据来自 Song et al. 2024；另有 MATH（Table 2 **没有写用的是哪个 backbone**）。
- **模型**：actor 是 Qwen2.5-7B-Base、Qwen2.5-0.5B-Base、LLaMA3.1-8B-Base，sender 用各自的 instruct 版本。
- **外部基线**：CoT(full) 用完整文字计划做 SFT；No-CoT 不给计划，直接 SFT。
- **变体**：Text、No-Comm、CrossTask、CovNoise-0.5×/1.0×、WhiteNoise、CovGauss-0μ/μ、RandomRot。从 No-Comm 与 Table 3 中 ratio=0% 那一行数值完全相同来看，这些变体都是**在 Interlat 训练好的 actor 上做测试时替换**，但文中的表述不完全明确。
- **统计与算力**：3 次运行取平均，用 5% 验证集选模型；GPU 类型和训练时长都没有报告。

## 4. 主要结果
- **Table 1（seen / unseen 成功率）**：

  | 条件 | Qwen-7B | Qwen-0.5B | LLaMA-8B |
  |---|---|---|---|
  | Ours | 70.48 / 65.42 | 61.19 / 57.46 | 70.71 / 70.90 |
  | CoT(full) | 67.14 / 64.93 | 57.86 / 50.75 | 69.35 / 70.82 |
  | No-CoT | 65.71 / 62.69 | 57.14 / 50.25 | 67.18 / 70.34 |
  | No-Comm | 62.14 / 62.19 | 50.48 / 44.03 | 63.57 / 58.40 |
  | Text | 64.29 / 62.44 | 54.52 / 47.26 | 62.86 / 60.82 |
  | CrossTask | 61.43 / 61.94 | 53.57 / 47.01 | 65.00 / 63.43 |
  | WhiteNoise | 61.90 / 61.19 | 57.38 / **57.21** | 61.43 / 64.93 |
  | CovGauss-μ | 65.71 / **64.93** | 44.52 / 34.33 | 60.71 / 64.93 |
  | CovGauss-0μ | 60.00 / 61.94 | 13.81 / 13.18 | 57.86 / **66.42** |
  | RandomRot | 57.86 / 63.68 | 59.05 / 51.99 | 57.86 / 63.44 |

  Qwen2LLaMA 为 70.95 / 71.39。
- **MATH（Table 2）**：Ours 总体 36.88，CoT(full) 38.35；Level-5 上 Ours 15.80，CoT 15.05。没有给出 ±。
- **压缩（Table 3，Qwen-7B）**：
  - Full 9.19s，成功率 70.48 / 65.42。
  - 未训练、直接截断：50% 时 72.14 / 61.19；8L 为 64.00 / 57.46，耗时 0.39s。
  - 训练后：128L 为 68.10 / 62.94（2.25s）；8L 为 66.43 / 60.45（0.20s）。
- **压缩（Table 7，LLaMA）**：训练后 8L 为 64.32 / 64.89，低于 No-CoT 的 67.18 / 70.34。
- **3-agent 拓扑（Table 5，0.5B）**：tree-3 为 62.85 / 60.77，text-tree-3 为 61.19 / 56.75。

## 5. 消融与诊断
- **actor 端（Table 4）**：
  - 去掉 adapter 后只剩 4.05 / 4.48，说明 receiver 必须学会“读”消息，同权重模型也不能直接读懂对方的 hidden state。
  - 去掉 curriculum：33.10 / 20.65。
  - 去掉 L_sep：58.81 / 60.70。
  - 去掉 L_align：56.90 / 53.98。
- **压缩端（K=128）**：去掉 L_geom 为 64.05 / 59.45；去掉 L_pref 为 64.76 / 60.20。
- **其他诊断**：L_sep 在约 2.2k 步之前一直停在 ln2，之后骤降，作者称之为 “aha” 时刻（Fig. 3）。另有 PCA 显示按任务模板聚类（Fig. 11、Table 9），以及 top-k 概率质量分析（Fig. 5/9/10）。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - 公平的文本基线是另行训练的 CoT(full)，不是在 latent actor 上测的 Text。与 CoT(full) 相比，Ours 在 Qwen-7B 上 +3.3（seen）/ +0.5（unseen），LLaMA 上 +1.4 / +0.1，后两项都在 1–2 个标准差以内。只有 0.5B 的 unseen 有明显优势（+6.7）。
  - 作者说 Qwen2LLaMA “even stronger gains”，实际只比 LLaMA 自身 sender 高 0.24 / 0.49。
- **内容是否被用到（本 batch 要求回答的问题）**：
  - seen 集上内容很重要：CrossTask 为 61.43，RandomRot 为 57.86，Ours 为 70.48。
  - **unseen 集上大部分增益在内容被破坏后仍然存在**：
    - Qwen-7B：CovGauss-μ 为 64.93，Ours 为 65.42。
    - 0.5B：WhiteNoise 为 57.21，Ours 为 57.46。
    - LLaMA：协方差高斯比 No-Comm 高 8 个点（66.42 对 58.40）。
  - 所以，相对 No-Comm 的增益很大一部分来自“槽位里有东西”，而不是消息内容。
  - CrossTask 的下降有一部分是 L_sep 直接训练出来的效果。
- **效率**：
  - 24× 是“全长 latent 消息生成”（需要 sender 解码完整计划，与文本通信同样耗时）对比“8 步截断”。
  - 压缩后的性能 ≈ No-CoT，也就是说，**省下的时间换来的是“几乎等于不通信”**。
  - 论文缺少同等预算的文本对照，例如 8 token 的文字摘要。
  - 全长 latent 与 Text 消息长度相同，这是好的设计，但两者训练条件不同。
- **可能的混杂因素**：
  - No-Comm 是让 latent 训练过的 actor 在没有消息的分布外条件下运行，是一个被削弱的基线。
  - ALFWorld 上计划本身只带来约 1.4 个点（CoT 67.14 对 No-CoT 65.71），留给通信的提升空间很小。
  - 只有 3 次运行，seen/unseen 的题量较小，论文也没有报告题数。

## 7. 局限
- **作者自述**：只有两个 agent，只测了 ALFWorld 和 MATH；需要访问 hidden state；牺牲了可解释性（§7）。
- **我们的判断**：
  - sender 仍然要生成文字，“entirely latent”指的只是传输这一段。
  - 异构是靠针对每个 sender 重新训练 receiver 实现的。
  - 测试任务不存在信息不对称，所以难以证明“非内容不可”。
  - MATH 实验的设置描述不全。

## 8. 可复现性
- 代码已开源（以摘要中的链接为准），λ 的退火范围和学习率都给出了，adapter 的规模没有给出。
- 7B/8B 模型全参数 SFT 加 AdamW，需要多卡或 ZeRO-offload，单张 H100 80GB 做不了全量训练；0.5B 的全部实验可以在单张 H100 上完成。
- 训练时长没有报告。

## 9. 与本课题的关系
- Interlat 的“CrossTask / CovGauss / RandomRot”对照可以直接拿来做“内容敏感性”审计的模板。它在 unseen 集上的结果提醒我们：“一个眼神”带来的收益可能只是“一个空位”带来的收益。
- 去掉 adapter 后成功率接近 0。这说明即使是同源模型，也要专门训练才能互读 latent。由此推测，OpenAI–HF 事件里那些未经训练的同权重 agent 很难自发使用 hidden-state 信道，只能退回明文 stigmergy。

## 10. 可以接着做的问题
1. **“训练效应 vs 内容效应”的分离**（中等难度）：用官方代码在 Qwen2.5-0.5B 上训练一个“随机槽位 actor”，训练时用协方差匹配的高斯消息代替真实 latent，其余设置不变。如果它在 unseen 集上与 Ours 相当，就说明增益来自训练正则或格式，而不是内容。
2. **信息不对称版 ALFWorld**：只让 sender 看到物体位置等特权观测，actor 看不到。这样内容是必需的，可以检验 Ours 与 CrossTask、WhiteNoise 的差距是否大幅拉开。
3. **同预算 Pareto**：对比 K=8 的 latent 消息、8 token 的文本摘要和 8 个 CIPHER soft token，画出成功率对字节数、对延迟的 Pareto 曲线，检验压缩是否真的优于短文本。
4. **不重训 actor 的跨家族通信**：Qwen→LLaMA 时冻结 actor，只训 adapter 或 LoRA，测 receiver 端最少需要多少适配，为“可插拔隐式协议”找出下界。
