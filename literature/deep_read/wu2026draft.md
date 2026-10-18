# Draft-KV：Draft-KV: Learning Useful Latent Communication Between Language Models

> `wu2026draft` · arXiv 预印本（PDF 页眉写 "Published as a conference paper at ICLR 2027"，但 ICLR 2027 在 2027 年 1 月前不可能出录用结果，又附匿名评审 artifact，应视为投稿版） · 2026-09-28 · [arXiv](https://arxiv.org/abs/2609.34754) · 代码：[github.com/Svardfox/Draft-KV](https://github.com/Svardfox/Draft-KV)；另有匿名 artifact（含接口权重与干预脚本），见 Reproducibility Statement · 本地 PDF：`pdf/2609.34754_Draft-KV.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–G 全部，App. H 案例研究为略读

## TL;DR
本文先审计 C2C 和 LatentMAS。结果是：把消息换成另一道题的消息（Deranged）后，准确率变化至多 0.60 pp，而系统增益最高达 15.44 pp（Fig. 1a）。作者称之为 information-use gap。

接着提出 Draft-KV：让 sharer 先写答案草稿，再把草稿位置的 KV 经 1.05M 参数的线性投影和门控 side-attention 送入冻结的 receiver，并分三阶段训练。在 Public 协议下，配对增益 P 在 35 个设置中平均为 25.65 pp。以 Qwen3-8B→Qwen2.5-0.5B 为例，MMLU-Redux 上 Matched 为 78.04%，Deranged 为 36.40%，Receiver-only 为 37.45%。

但传递的主要是 sharer 的“答案”。在真正信息不对称的 Private 协议下，平均系统增益只有 2.51 pp（Table 3）。

## 1. 问题与动机
- 作者定义了两个量（Eq. 1）：系统增益 $G=A_M-A_R$ 与配对增益 $P=A_M-A_D$。现有接口 G 大、P≈0，说明 sharer“可有可无”，而且 sharer 变强时系统几乎不涨：C2C 的 sharer 从 0.6B 换到 8B，sharer 自身准确率涨 29.85 pp，系统只涨 3.54 pp（Fig. 1c）。
- 由此提出两个要求：消息要包含 sharer 针对当前输入的计算结果（informative），receiver 要依赖正确配对的消息（effective use）。

## 2. 方法
- **信道**：sharer 先 greedy 解码出草稿 d，再对 [x; d] 前向一次，取指定层**草稿位置**的 K/V。K 取 RoPE 之前的值（App. A.1）。prompt 位置不传。
- **对齐与映射**：
  - 支持异构：Qwen3→Qwen2.5、Llama-3.2-3B→Qwen2.5、Qwen2.5→Qwen3。
  - 每个通信层有两个无偏置线性映射 $W_K^\ell, W_V^\ell$，再加每个 KV head 一个 tanh 门。门初始化为 0，保证初始时 receiver 行为与原模型一致。
  - 4 个通信层：receiver 的 {14,16,18,20} 读 sharer 的 {18,20,22,24}。参数量 1,048,584；8B→4B 这一对为 8.39M（Table 6）。
  - 两个骨干都冻结。
- **注入方式**：receiver 用自己冻结的 Q 投影、归一化和 O 投影，对 packet 做一路独立的 attention（不加 RoPE、不加 causal mask），结果门控后加回残差：$H'=H+\text{SelfAttn}(U)+\Delta H$（Eq. 3、10、11）。packet 是独立的 side memory，不拼进 KV cache。
- **协议与拓扑**：两个 agent、单向、单轮。Public 协议下双方看到同一道题；Private 协议下 HotpotQA 和 2Wiki 的金证据被随机分给双方。
- **三阶段训练**（§4.3，App. A.4、C.2）：
  1. 重构阶段：sharer 编码 OpenHermes 的一轮回复并附加 per-sample key；receiver 只看到固定的解码指令，要从 packet 中复原原文。16k 步，32,768 条数据。
  2. 答案对齐阶段：用 sharer 自己的草稿，监督目标是参考答案。4k 步，8,192 条。
  3. ARC-E/C 训练集 3,602 条，监督金标选项的全文，加单侧 guard：$\lambda_p[N^D-\text{sg}(N^R)-\tau]_+$，其中 $\lambda_p=0.1$，$\tau=0.1$。
  - 后两阶段每 5 步回放一次重构任务。全程只有一个训练种子 31847。

## 3. 实验设置
- sharer：Qwen3-0.6B/1.7B/4B/8B 和 Llama-3.2-3B-Instruct。receiver 主要是 Qwen2.5-0.5B-Instruct，另有反向的 Qwen2.5-0.5B→Qwen3-0.6B 和 Qwen3-8B→Qwen3-4B，共 7 对。
- Public 协议：MMLU-Redux（5,632 题）、ARC-E、ARC-C、OBQA、C-EVAL，按选项字母首 token 的 logit 计分。
- Private 协议：HotpotQA（7,404 题）、2Wiki（1,000 题），用 EM 计分。
- 基线：Sharer-only（从草稿中解析答案）、Receiver-only、T2T（把草稿作为文本给 receiver）、C2C。C2C 只有 1 对用官方 fuser，其余 6 对按官方配方重训（App. G）；重训在 C2C 原文的 3 对配置上与原文差距在 0.44 pp 以内（Table 12）。
- 算力：96GB 显卡（峰值 BF16 148 TFLOP/s），PyTorch 2.6。

## 4. 主要结果
- **审计现有方法**（Fig. 1，§3）：
  - C2C（官方 Qwen2.5-0.5B→Qwen3-0.6B）：MMLU-R 上 G=12.29、P=−0.47；OBQA 上 G=13.40、P=0.00；ARC-C 上 G=15.44、P=0.42。adapter-only（5 个 donor 的输出平均）保留了 Matched 准确率的 93.16–96.06%。
  - LatentMAS（Qwen3-4B）：GSM8K 与 ARC-C 的 P 都是 +0.60，ARC-C 的 G=4.86。只有点估计；GSM8K 只用了 200 题，ARC-C 的样本量没有说明。
  - 自训 C2C fuser 的 20 个 paired bootstrap 区间中有 13 个含 0，其余也都只偏离 0 几个点以内（Table 13）。
- **Draft-KV 主表**（Table 1）：
  - Public 35 个设置中，Draft-KV 全部高于 R-only，30 个设置最优，33 个高于 T2T。
  - 8B→0.5B：MMLU-R 78.04/36.40（M/D），sharer 75.04，T2T 72.05，C2C 36.97；ARC-C 93.77，sharer 92.83。
  - C2C 在 35 个设置中有 29 个系统增益为负（§5.3）。
- **增益分布**（Table 3）：
  - Public：G 均值 24.24，P 均值 25.65，mismatch harm $A_R-A_D$ 均值 1.41（中位数 1.19）。
  - Private：G 均值仅 2.51，P 为 13.49，harm 为 10.98。P 在 Private 下主要来自错配伤害，而不是增益。
- **Sharer scaling**（Fig. 5，App. E）：receiver 固定为 0.5B 时，sharer 从 0.6B 到 8B，平均 G 从 9.63 升到 42.25 pp（+32.6）。同期 T2T 升 30.2，C2C 只升 1.4。草稿长度与增益不单调（Table 11）。
- **Adapter-only**（Table 4）：Draft-KV 在 1.7B 和 4B sharer 下只保留 42.28–51.05%，低于 R-only；C2C 保留 93.16–116.42%。
- **成本**（Table 8，8B→0.5B）：Draft-KV 的 FLOPs 是 Sharer-only 的 2.02 倍，延迟是 1.01 倍。总延迟 12.0 s，其中 11.87 s 花在草稿解码。接口本身 0.88 GFLOPs，C2C 为 118.3 GFLOPs。

## 5. 消融与诊断
- **消息来源**（Table 2/9，1.7B→0.5B）：改用 prompt KV 后，ARC-C 的 Matched 从 83.53 跌到 49.83，P 从 45.90 跌到 0.17；MMLU-R 的 P 从 28.23 跌到 0.09。这在自己的架构内复现了 information-use gap：只传 prompt 的 KV 时，配对价值为零。
- **去掉训练阶段**：去掉阶段 1，MMLU-R 的 Matched 降到 52.40；去掉阶段 2，降到 55.40。在没有用于训练的 MMLU-R 上损失更大。
- **Guard 消融**（Table 10）：去掉 guard 后 P 反而升高（ARC 上 45.90→47.02），但 G 下降，harm 从 2.47 升到 4.18。作者自己指出：P 被错配伤害撑大时，不代表通信更好（Eq. 25）。
- **逐题分析**（App. F.1）：ARC-C 上，Draft-KV 纠正了 sharer 241 道错题中的 58 道（24.1%），在 931 道 sharer 答对的题中丢了 10 道（1.1%）；T2T 在后者中丢了 7.41%。所以 Draft-KV 胜过 T2T，主要是“不被文本说服去改掉本来对的答案”。
- **案例**（App. H，Case 11）：Deranged 时 receiver 选了 donor 题目的金标字母，说明传过去的主要是 sharer 的答案判断。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - “Draft-KV 让 receiver 真正使用了消息内容”在配对增益意义下成立，35/35 个设置都满足。但内容基本就是 sharer 的答案：Stage 3 要求 sharer 在结尾写出所选选项的全文，sharer 又比 receiver 强得多（8B 对 0.5B）。主要机制是“读 sharer 的答案，再做少量纠错”。相对 Sharer-only 的净增益在 8B→0.5B 上只有 +0.2 到 +5.0 pp。
  - 这是有内容的通信，但内容是可言语化的答案，不是不可言说的中间计算。
  - “能在双方各有证据时超过两个模型”只在 14 个 Private 设置中的 7 个成立。另有 6 个设置 G 为负（据 Table 1 计算）：Qwen3-0.6B 作 sharer 的两项、Qwen3-1.7B 的 2Wiki、Llama 的两项、反向对 Qwen2.5-0.5B→Qwen3-0.6B 的 2Wiki（23.50，低于 receiver 的 28.00）。
- **缺失的对照**：
  - 缺一个等参数、等训练的文本基线：例如给 T2T receiver 训练一个约 1M 参数的 LoRA 或 soft prompt，同样在 ARC 上做 Stage 3。现在的 T2T 是未经训练的 0.5B 模型读 300 token 草稿，偏弱。
  - 缺“sharer 选项 logits 与 receiver logits 融合”这类集成基线。
  - Draft-KV 自己的结果只有点估计；训练只有一个种子；C2C 区间只给了自训 fuser 的。
  - 与 C2C 的对比不公平：C2C 只传 prompt cache，Draft-KV 传含答案的草稿；而且 C2C 在“大 sharer→0.5B receiver”这类非原配置方向上本来就失效。
- **可能的混杂因素**：
  - Stage 3 在 ARC 训练集上训练，ARC 测试集属于同分布。MMLU-R、OBQA、C-EVAL 才是真正的 held-out。
  - Draft-KV 必须让 sharer 完整解码草稿，延迟和 T2T 相同，所以没有效率优势。论文强调的“348× 更小”只指接口参数量。
  - Deranged 的 donor 来自同 benchmark 全池随机，没有做长度匹配（用 mask 处理），也没有按学科匹配（App. B.2），与 Cheng et al. 的批内边际保持设计不同。

## 7. 局限
- **作者自述**：干预只测了跨题错配，没有测“同题但草稿错误”时的鲁棒性（App. D.2）；DLC 没有实现，只引用了原文数字（App. G）。
- **我们的判断**：
  - 这是本 batch 中唯一一个“提出方法并自证通过错配审计”的工作，而且三个关键工程选择都可以复用：传草稿 KV 而不是 prompt KV；用重构预训练建立可读性；用单侧 guard 限制错配伤害。
  - 但它也把“通信”降格成了“传答案”。在 Private 这种真正需要组合证据的任务上，增益很小、波动很大。
  - 是否存在“只有 latent 才能传的东西”，仍未被证明。

## 8. 可复现性
- GitHub 仓库与匿名 artifact 都声明包含接口实现、训练好的权重和干预脚本。
- 超参非常完整：各阶段步数、学习率、batch、长度上限、层映射、置换种子（71031 和 99173）。
- 显存：8B sharer（约 16GB bf16）加 0.5B receiver 都冻结，可训练参数只有 1M，草稿离线缓存，所以单张 H100 80GB 足以训练和评测全部 7 对。主要开销在为 OpenHermes 和 ARC 生成草稿（Stage 2 候选约 1 万条，每条最多 1024 token）。
- 单对模型的三阶段训练加评测，估计几十 GPU 小时（论文未报告总时长）。

## 9. 与本课题的关系
- 它给出“一个眼神”的一个工程实现：强者把“刚想完的东西”以 KV 形式递给弱者，弱者读到后能保留自己原本对的判断（不被文本说服），这有点像“默契”。但它的 Private 结果说明，在真正需要组合双方私有证据时，这条通道远没有成熟。
- 安全角度：Stage 1 证明 1M 参数就能把 KV packet 解码回原文（重构 NLL 约 0.5–0.6 nats，Fig. 6）。这意味着草稿 KV 这类消息可被监控：训练一个 decoder 读出原文即可。这对设计 latent 通信的审计接口是正面证据，对隐写则是负面证据。

## 10. 可以接着做的问题
1. **去答案化草稿**：让 sharer 只写推理、不写最终选项（或者在 extraction 时 mask 掉答案行），再测 P。预期 P 大幅下降；若仍显著为正，才说明传过去的是推理而不是答案。设置为 Qwen3-4B→Qwen2.5-0.5B，在 MMLU-R 和 ARC-C 上做，代码改动很小。
2. **等参数文本基线**：给 T2T receiver 加一个约 1M 参数的 LoRA，用同样的三阶段数据训练，对比 Draft-KV。预期两者差距明显缩小，从而判断“latent 优势”是否只是“训练过的读取器”带来的。
3. **用 Cheng 的 registry 工具审计 Draft-KV**：sender 持有私有绑定，测试 Draft-KV 能否达到 LatentMAS prefix 的天花板，以及在异构设置下的表现。预期达不到天花板（4 层 side-attention 带宽有限），可以给出“带宽–配对”曲线。
4. **Private 协议的失败分析**：对 G<0 的 6 个设置，按证据是否互补分层，检查是 sharer 太弱导致误导，还是接口带宽不足。可以接着设计对错配和错误草稿都鲁棒的 guard。
