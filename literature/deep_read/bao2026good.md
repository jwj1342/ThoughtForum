# TFlow：Good Agentic Friends Do Not Just Give Verbal Advice: They Can Update Your Weights

> `bao2026good` · arXiv 预印本 · 2026-05-13 · [arXiv](https://arxiv.org/abs/2605.13839) · 代码：https://github.com/BWR-hhh/TFlow（来自索引；论文首页的 "Code" 是超链接，pdftotext 没有抽出 URL，本次未核实） · 本地 PDF：`pdf/2605.13839_TFlow.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–B（含训练/推理算法和计算复杂度）。Table 1、Table 2、Fig. 4/5 对照 PDF 第 7–9 页核对。

## TL;DR
TFlow 让 sender 的隐状态经一个超网络编译成 receiver 专属的、逐 query 的 rank-4 LoRA，在 receiver 生成期间临时注入，实验配置是 3 个 Qwen3-4B。
- **对单 agent**：准确率提升 +6.98 到 +8.53 pt。论文写的是 +7.13 到 +8.53，但 MATH 一栏算术有误，见 §6。
- **对 TextMAS**：5 个 benchmark 上**准确率全部更低**，差距 −1.32 到 −9.76。
- **效率**：处理 token 少 71–83%，wall-clock 快 2.3–4.6×（Table 1）。
- **代表性数字**：GSM8K 上 92.12 vs TextMAS 93.78，token 900 vs 5381。

## 1. 问题与动机
- 文本 MAS 要求 sender 把内部计算序列化成 token，receiver 再重新 prefill。这会抬高生成 token、prefill 开销和 KV-cache 占用（§1）。
- 现有 latent 通信要求 receiver 能“读懂” sender 的激活，存在表示空间兼容问题。
- 作者提出第三条路：不是发一条 receiver 要读的信息，而是发一个“改变 receiver 计算方式”的瞬时权重扰动（§1）。

## 2. 方法
- **信道**：
  - sender 是带角色 system prompt 的冻结 Qwen3-4B，对 (p_i, q) 只做**一次 prefill 前向，不解码**，取所有层的 hidden state H_i^(l) ∈ R^{T_i×d}。
  - 用可学习的层权重 softmax 聚合：C_i = Σ_l ρ_l H_i^(l)（App. B.2）。
  - 生成器 H_ψ 把 C_i 映射为 receiver 每个目标模块的 LoRA 因子 A^(l)_{i,m} ∈ R^{r×d_in}、B^(l)_{i,m} ∈ R^{d_out×r}。
  - 注入位置是 receiver **全部 36 层**的 q/k/v/o/gate/up/down，共 K=252 个投影（§4.3.2），r=4，α=8。
  - **所以消息就是“逐实例 LoRA”**：低秩增量，不是 task vector，也不是 full delta。
- **对齐与映射**：
  - 同构。三个 agent 共用同一个冻结 backbone 实例。
  - 只训练 Θ = {生成器 ψ、Proj_in、层权重 λ_l、融合门 w}，可训练参数量**未报告**。
  - 训练数据：OpenThoughts、Sky-T1、KodCode 共 32K 条，1 epoch，单张 RTX PRO 6000 约 8 小时（§4.1）。
  - 目标函数：receiver 在注入 ΔW 后对 completion 的 masked next-token CE，加上 λ_div·cos²(v(x_q), v_prev^σ)。后一项是缓存式多样性正则，防止生成器坍缩成与 query 无关的 LoRA（§3.5, App. B.5）。λ_div、学习率、batch size 均未给出。
- **协议与拓扑**：
  - N=3：Agent A 负责策略规划，Agent B 负责领域知识，二者是 sender；Agent C 是 receiver。只有一轮。
  - receiver 仍然看到问题和自己的 system prompt，但看不到 sender 的任何文本。
- **关键机制**：
  - 融合发生在 ΔW 层面：ΔW^(l)_m = (α/r) Σ_i softmax_i(g_w(C_i)) B_i A_i。作者特意避免分别平均 A、B 产生 B_iA_j 交叉项（App. B.4）。
  - 前向时计算 X W + X(ΔW)ᵀ，生成结束即撤除，backbone 不会被改写。
  - 生成器沿用 HY-WU 的参数 token 化：L×HW 的 token 网格，每块依次做跨层 SA、层内 SA、条件 CA 和 FFN，N_pg=2，d_pg=1024（§3.3）。
- **带宽**：论文**没有报告**每条消息的字节数。
  - 我们按 Qwen3-4B 公开配置估算（hidden 2560、intermediate 9728、36 层、q 输出 4096、kv 输出 1024）：每个 sender 每个 query 的 rank-4 LoRA 约 22.9 万参数/层 × 36 ≈ **8.3M 参数，bf16 约 16.5 MB**。
  - 作为对照，TextMAS 每题总处理 token 为 4,825–8,188（Table 1），文本消息只有几十 KB 量级。
  - 也就是说，按字节计，权重消息比文本**大 2–3 个数量级**。“高效”只体现在 receiver 的 prefill token 和延迟上；sender 与 receiver 同卡同进程，传输成本被忽略。

## 3. 实验设置
- **模型**：Qwen3-4B，是否开启 thinking 模式未说明。
- **Benchmark**：GSM8K、MATH、MMLU-Redux、HumanEval+、MBPP+，均为 zero-shot CoT，temperature 0.6，top-p 0.95（§4.1）。
- **Baseline**：Single（单 agent）、TextMAS（三 agent 文本拼接）。消融中有 Static LoRA（Fig. 4）。没有任何 latent / KV 通信 baseline。
- **指标**：准确率、每题平均总处理 token、整个 benchmark 的 wall-clock 秒数（推理硬件未说明）。
- **种子**：未报告，看起来是单次运行。最大生成长度未报告。

## 4. 主要结果
Table 1（Single / TextMAS / TFlow）：

| Benchmark | 准确率 | token | 时间 (s) |
|---|---|---|---|
| MMLU-Redux | 58.99 / 71.50 / 66.97 | 1079 / 4825 / 998 | 8226 / 36450 / 9784 |
| GSM8K | 84.99 / 93.78 / 92.12 | 1337 / 5381 / 900 | 6230 / 27256 / 5953 |
| MATH | 16.18 / 26.47 / 23.16 | 2782 / 8188 / 2242 | — |
| MBPP+ | 59.79 / 68.52 / 67.20 | — | — |
| HumanEval+ | 56.71 / 75.00 / 65.24 | — | — |

- 相对 Single，TFlow 在 4/5 个 benchmark 上**更慢**（×0.82–0.88）。原因是逐实例 LoRA 无法批处理，作者自己也承认（§4.2）。
- 相对 TextMAS，TFlow 快 ×2.31–×4.58。

## 5. 消融与诊断
- **Static LoRA（Fig. 4，PDF 核对）**：用同样数据训练一个与输入无关的 LoRA。
  - Single / Static / TFlow 分别为：GSM8K 85.0 / 89.2 / 92.1；MATH 16.2 / 19.9 / 23.2；MMLU 59.0 / 64.3 / 67.0；MBPP+ 59.8 / 61.4 / 67.2；HumanEval+ 56.7 / 58.5 / 65.2。
  - TFlow 比 Static 平均高 4.29 pt；我们算得 Static 比 Single 平均高 3.32 pt。也就是说，**约 44% 的增益只来自“在这批数据上训练了一个 adapter”**。
- **错配扰动（Fig. 5，仅 GSM8K）**，以 base 84.99 为基准：
  - 随机 LoRA：+1.06；
  - 来自其他任务样本的 LoRA：+4.24（MMLU-Redux）、+4.47（MATH）、+4.77（MBPP+）、+5.23（HumanEval+）；
  - 同任务的其他样本：+5.84；
  - 匹配样本：+7.13。
- **表示诊断**：
  - 聚合后的条件向量：GSM8K 内部余弦 0.94，MBPP+ 内部 0.83，跨任务 0.73（Fig. 3）。
  - 学到的层权重超过 80% 集中在 L05、L29、L30。
  - LoRA 指纹的同数据集相似度在 0.264–0.933 之间，呈块结构（Table 2）。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - 实际被证明的，是一个**以 query 为条件的超网络 adapter**，在 32K 条推理数据（OpenThoughts/Sky-T1 为长 CoT 蒸馏数据）上训练后有效。
  - “sender 通过权重把信息传给 receiver”这一点证据薄弱。Fig. 5 中，跨任务 LoRA 已拿到匹配增益的 59–73%，同任务 LoRA 拿到 82%。“实例特定内容”只多贡献 1.29 pt，且是单次运行、温度采样。按 GSM8K 测试集 1,319 题估算，准确率 92% 时的标准误约 0.75 pt（我们的计算），这个差异不足以下结论。
  - Table 1 中 MATH 的 ΔSingle 印成 +7.98，但 23.16 − 16.18 = 6.98，所以正文“+7.13 到 +8.53”应为 +6.98 到 +8.53。
- **缺失的对照**：
  - **最关键：没有 no-sender 对照**。即让生成器以 receiver 自己 prompt 的 hidden state 为条件，或只以问题为条件、不加角色 prompt。没有这组对照，就无法区分“通信”与“输入自适应”。
  - 没有单 sender 与双 sender 的比较，也没有融合门权重的分析。
  - 没有和训练过的文本基线比较（例如 receiver 在同一批数据上 SFT 后再跑 TextMAS），也没有 latent/KV 基线（LatentMAS、Interlat 等，§2 有讨论但未对比）。
  - 没有按字节、按 FLOPs 的等预算比较。
  - 没有种子和方差。
- **可能的混杂因素**：
  - **训练混杂**：Single 和 TextMAS 都没训练，只有 TFlow 吃到了推理蒸馏数据。TFlow 的 token 比 Single 还少（GSM8K 900 vs 1337），说明 receiver 的输出风格被改成了更短的推理。
  - “总处理 token”是否计入两个 sender 的 prefill 没有说明。
  - **MATH 异常**：Single 在 MATH 上只有 16.18%，对 Qwen3-4B 来说明显偏低，论文没有说明生成长度上限或 thinking 设置。Table 2 用的又是 MINERVA-MATH，“MATH”究竟指哪个集合不清楚。
  - 没有讨论训练数据与测试集是否重叠。

## 7. 局限
- **作者自述**：权重消息不可解释，难以审计和追责；在 HumanEval+ 上不如 TextMAS，因为文本 MAS 隐式扩大了生成预算（App. A）。
- **我们的判断**：
  - 只测了同一个 backbone 实例、一个模型、一个尺寸、单轮、固定 receiver。
  - 消息不能跨 receiver 复用。
  - 没有测鲁棒性（例如对抗或错误的 sender）。
  - “通信”与“动态 PEFT”的边界没有被实验切开。

## 8. 可复现性
- 索引记录代码已开源，本次未核实。
- 已给出的超参：d_pg=1024、head dim 128、N_pg=2、token dim 256、c=2、r=4、α=8。
- 缺失的超参：H_A、H_B、W 的取值，λ_div，学习率，batch size，层聚合温度 τ，角色 prompt 全文，最大生成长度。
- 算力：训练约 8 小时，用单张 96GB 的 RTX PRO 6000。冻结的 4B backbone 用 bf16 约 8GB，**单张 H100 80GB 上可复现**。评测 5 个 benchmark 约需数小时，因为逐实例 LoRA 无法批处理。

## 9. 与本课题的关系
- 这是索引中唯一明确的“以权重为消息”的工作。receiver 没有被“告知”任何话，只是计算被改变，形式上最接近“一个眼神”。
- 但它需要**联合训练的解码器**（生成器），是设计好的协议，不是涌现出来的默契。
- 安全角度：OpenAI–HF 事件之所以能被发现，是因为通信是明文、可审计的。如果 agent 之间改用 TFlow 式的权重消息，现有基于文本的监控就看不到了，作者也承认审计困难（App. A）。
- 与 DSL（fenoglio2026distributed）构成对偶：TFlow 把激活编成权重；DSL 把权重增量编成输出。

## 10. 可以接着做的问题
1. **归因对照（在官方代码上做，成本低）**：
   - 在 GSM8K 与 MATH-500 上，比较五种设置：(a) 生成器以 receiver 自身 hidden state 为条件（no-sender）；(b) 打乱 sender 角色 prompt；(c) 只以问题 embedding 为条件；(d) Static LoRA + TextMAS；(e) 原版 TFlow。每种 3 个种子。
   - 预期：(a) 和 (c) 能拿回大部分增益，从而说明主体是自适应 adapter，而不是通信。
2. **信息不对称任务**：
   - sender 看到私有文档（合成的 key-value 事实，或 HotpotQA 支持段落），receiver 只看到问题。
   - 比较三种消息：TFlow 式 LoRA、等字节的文本摘要、KV-cache。
   - 对照：错配文档的 LoRA、范数匹配的高斯 ΔW。
   - 指标：传递成功的事实数–消息大小曲线。预期 LoRA 能携带少量事实，容量随 rank 增长，但每字节效率不如文本。
3. **摊销效应**：
   - 一条权重消息服务同一文档上的 M 个后续 query。
   - 测累计 token/FLOPs 与文本上下文方案的盈亏平衡点。预期 M 较大时权重消息占优，这才是它真正的卖点。
4. **异构 receiver**：
   - sender 用 Qwen3-4B，receiver 用 Llama-3.2-3B，生成器按 receiver 训练。
   - 检验 §1 所说的“by construction 与 receiver 权重兼容”能否在跨族时成立。论文本身只测了同一个 backbone。
