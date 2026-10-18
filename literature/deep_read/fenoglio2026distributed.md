# DSL：Distributed Subliminal Learning: Replacing Model Updates with Random-Carrier Outputs

> `fenoglio2026distributed` · NeurIPS 2026 Workshop（CODEC-FM：Collaborative, Open, and DECentralized training of Foundation Models） · 2026-10-04 · [arXiv](https://arxiv.org/abs/2610.05378) · 代码：未开源（正文与附录都没有代码链接） · 本地 PDF：`pdf/2610.05378_DSL.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–C（协议、局部等价定理与有限 carrier 界、实验细节、全部联邦消融）。Table 1–3 对照 PDF 第 4–5 页核对。

## TL;DR
参与者不上传参数或 adapter，只上传本地适配模型在**任务无关的随机 carrier** 上的输出：LLM 场景是随机数字续写，FL 场景是随机输入上的 logits。协调者把这些输出蒸馏进共享模型。
- **偏好组合**（3 个 Qwen2.5-7B-Instruct 参与者）：保留率 94.56%，LoRA averaging 为 87.76%（Table 1）。
- **GSM8K 组合**（10 个 Qwen2.5-1.5B 参与者）：DSL 32.2%；LoRA averaging 10.8%，基座 10.2%，本地模型 58.9%。上传量 0.72 MiB 对 35.27 MiB（Table 2）。
- **联邦学习**：MNIST 上 96.83%，FedAvg 为 97.34%，上行通信少 8.9×（Table 3）。

## 1. 问题与动机
- 协作学习的默认通信单位是参数。FL 上传 Δθ，基础模型组合交换 adapter。这带来三个问题（§1）：
  - 通信量随模型规模增长；
  - 独立学到的特化在权重空间里会相互干扰；
  - 梯度和更新会泄露隐私。
- 已有的联邦蒸馏都依赖与任务相关的公共数据或生成器。作者把 subliminal learning 这个“安全隐患”反过来用，作为一种建设性的通信原语。

## 2. 方法
- **信道**：
  - **LLM 组合**：carrier prompt 由模板随机生成，含 3–8 个 100–999 的整数，要求再续写最多 10 个三位以内的数字。用 T=1.0 采样 completion，生成上限 2048 token；只上传 completion 的 UTF-8 字节，prompt 由共享随机种子复现（App. B.1, B.3）。
  - **FL**：上传随机 carrier 上的 logit 向量。carrier 在 MNIST/CIFAR 上是 uniform、blurred 或 Fourier 噪声图像，在 Tiny ImageNet 上是 ViT 冻结特征之后的表示空间 uniform 向量。MNIST/CIFAR 还额外加了 3 个无监督的 “ghost” logits（App. B.2），等价于 Cloud 等人的 auxiliary logits。
- **注入方式**：
  - 接收方是一个**训练过程**，不是推理过程。
  - LLM：协调者从共同基座重新初始化，在汇总的 completion 上做 SFT，12 epochs，lr 1e-4。是 LoRA 还是全参数没有说明。
  - FL：服务器从 θ_t 出发，用 τ=1 的 KL 蒸馏，最多 5 epochs。
- **对齐与映射**：同构，并且**必须共享初始化**（作者自述，§5）。
  - 参与者的 LoRA 为 r=8、α=8，覆盖 7 个模块。
  - 偏好实验：每个参与者 5,000 条合成样本，生成 40,000 条 completion。
  - GSM8K 实验：10 个参与者各取 4,000 条训练样本，训练 1 epoch，各生成 12,000 条 completion。
- **协议与拓扑**：星形，K 个参与者对一个协调者。LLM 场景只通信一次；FL 场景最多 200 轮，20 个客户端全部参与，数据 IID。
- **关键机制（App. A.3, Theorem A.1）**：
  - 在 θ_0 附近，私有 carrier 汇总后的 KL 目标为
    L(θ_0+δ) = ½ Σ_k p_k (δ−δ_k)ᵀ H_q (δ−δ_k) + o(ρ²)，
    其中 H_q = E_{x∼q}[Jᵀ C_0 J]，是 Fisher 加权的 carrier Gram 矩阵。
  - 其极小点为 δ̄ + ker(H_q)。也就是说，**carrier 输出编码了参数增量在 range(H_q) 上的投影**，蒸馏能恢复各参与者更新的加权平均。若共享 carrier，在线性化下这一等价是精确的。
  - Prop. A.2 给出有限 carrier 的误差界 ε/(μ−ε)·Σ p_k‖a_k−ā‖。
  - 这与 Cloud 等人的 Lemma 1（M 半正定）是同一数学，被推广到多发送方。

## 3. 实验设置
- **LLM 部分**：
  - 偏好组合：Qwen2.5-7B-Instruct；3 个偏好（cat、pasta、maple）；每类 30 个 held-out prompt，每个 prompt 采样 100 次；指标是相对基座的提及率增量。
  - GSM8K 组合：Qwen2.5-1.5B-Instruct；500 道 held-out 题；greedy 解码，按 exact-answer 判分。
  - 唯一的 baseline 是 LoRA 张量的等权算术平均。
  - **种子未报告**，看起来是单次运行。
- **FL 部分**：
  - 模型：MNIST 用 MLP，CIFAR-10 用 ResNet9，Tiny ImageNet 用冻结 ViT-small 加两层 MLP 头。
  - Baseline：FedAvg、SCAFFOLD、DFRD、FedDF、FedGen、FedMD。
  - 3 个种子；早停。
- **算力**：未报告。

## 4. 主要结果
- **偏好组合（Table 1）**：
  - Local / LoRA Avg. / DSL：Cat 98.23 / 95.60 / 94.90，Pasta 96.07 / 85.27 / 95.00，Maple 98.33 / 82.40 / 93.77，平均 97.54 / 87.76 / 94.56。
  - 每个参与者上传 1.58–2.52 MiB，比传 adapter 少 30.6–48.8×。
- **GSM8K 组合（Table 2）**：基座 10.2，本地平均 58.9，LoRA Avg. 10.8（+0.6），DSL 32.2（+22.0）。上传量 0.72 MiB 对 35.27 MiB，约少 49×。
- **FL（Table 3）**：

| 数据集 | FSL 准确率 | FedAvg 准确率 | 差距 | FSL 上行 | FedAvg 上行 | 节省 |
|---|---|---|---|---|---|---|
| MNIST | 96.83±0.27 | 97.34 | −0.51 | 0.266 GiB | 2.37 GiB | 8.9× |
| CIFAR-10 | 56.31 | 66.25 | −9.94 | 0.110 GiB | 14.99 GiB | 136.3× |
| Tiny ImageNet | 63.77 | 68.12 | −4.35 | 0.097 GiB | 0.726 GiB | 7.5× |

- CIFAR-10 加大预算（共享加权、blurred、M=65,536）后可达 63.02%，上行 2.12 GiB，仍比 FedAvg 少 7.08×（Table 4）。

## 5. 消融与诊断
- **carrier 类型取决于被探测的模型接口，而不是数据集（App. C）**：
  - MNIST-MLP 偏好 uniform（private 96.28%）。
  - 同样是 MNIST，换成 LeNet5 后偏好 blurred/Fourier：95.09% / 94.98%，uniform 只有 75.58±33.80%（Table 6）。
  - CIFAR-ResNet9 上，uniform 在各预算下都低于 22%（Table 4）。
- **预算饱和**：Tiny ImageNet 上，64 个 carrier 得到 60.54%，1,024 个得到 63.77%，之后不再提升（Table 7）。
- **其他诊断**：
  - ghost logits 越多，准确率越高，但通信量也越大（Fig. 4, App. C.7）。
  - 边际输出熵与 carrier 效果相关，但作者强调它只是诊断，不是充分条件（Table 9）。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - FL 部分的证据扎实：3 个种子，消融完整，效果确实是一个“精度–通信”的权衡，在三个数据集上都低于 FedAvg。
  - LLM 部分的头条结论证据较弱：
    - **LoRA averaging 可能是稻草人基线**。“等权算术平均 LoRA 张量”（App. B.1）是分别平均 A 和 B，而 (ΣB/K)(ΣA/K) ≠ ΣBA/K。TFlow（bao2026good App. B.4）明确指出这会引入交叉项。10 个 IID 的 GSM8K adapter 平均后只有 10.8%，几乎等于基座，作者没有解释为什么。
    - 没有和 ΔW 级平均、TIES/DARE、LoRA Soups 正经比较，也没有“合并数据集重新训练”这个上界。
  - **评测格式混杂**：Qwen2.5-1.5B-Instruct 在 GSM8K 上的基座分只有 10.2%（greedy、exact-answer）。这暗示答案格式不匹配，本地模型的 58.9% 可能有很大一部分是学会了格式。DSL 的 +22 pt 中有多少来自格式迁移，没有分析。
- **缺失的对照**：
  - LLM 部分没有 Cloud 式的 “regular numbers” 对照，即协调者在**基座模型**生成的数字上做 SFT。
  - 没有打乱 completion、单参与者传递、种子方差。
  - 没有跨初始化对照，例如协调者换成 base 或其他族的模型。
  - 隐私只是声称，没有任何实验验证。
- **可能的混杂因素（通信量记账）**：
  - LoRA 体积 35.27 MiB 与 fp32 存储的 rank-8、全模块、1.5B 模型的 LoRA 一致（我们的估算）。改成 bf16 存储，压缩比约减半。
  - 不计参与者生成 40,000 × 最多 2048 token 的算力，也不计协调者 12 epoch 的 SFT。
  - FL 只统计上行。FSL 每轮仍要下发完整模型，总通信的节省小于上行节省的倍数。
  - 早停与通信量互相纠缠，作者在 App. C.1 承认了这一点。

## 7. 局限
- **作者自述**：需要共享初始化；理论只是局部的；carrier 要按问题选择；协调者需要额外算力；没有隐私保证；只测了一个 LLM 族；FL 数据 IID 且全员参与（§5）。
- **我们的判断**：
  - LLM 部分的基线和评测都有疑点，样本只有单次运行。
  - 通信是单向的、离线的、中心化的，不是 agent 之间的实时交流。
  - 偏好任务是人为注入的极强偏好（本地保留率约 98%），信噪比远好于真实特化。

## 8. 可复现性
- 没有代码。
- 超参写得相当完整（App. B），但协调者 SFT 用 LoRA 还是全参数没有说明，评测时的答案抽取规则只粗略描述。
- 单张 H100 上：
  - GSM8K（1.5B）部分可以复现，包括 10 个 LoRA、vLLM 生成 12 万条和协调者 SFT。
  - 7B 偏好部分若协调者是全参数 SFT，单卡放不下；若用 LoRA 则可行。
  - FL 部分的计算量很小。

## 9. 与本课题的关系
- **DSL 是“参数信息、输出信道”**：信道是函数空间的输出（文本或 logits），载荷是参数增量 δ_k（Theorem A.1）。
  - 它与 TFlow 互为对偶：TFlow 是“激活信息、参数信道”。
  - 在索引中把它的 channel 标成 parameter 或 logits 都不完整：LLM 部分实际上是 stego-text。
- **共享初始化就是“共享密钥”**：事件中的 agent 全部同权重，满足这个条件。DSL 证明这条信道不仅能传偏好，还能传任务能力（GSM8K +22 pt），每个参与者只需 0.72 MiB 的“无意义数字”。不过解码仍然需要训练这一步。
- **对监控的含义**：ker(H_q) 方向上的变化，从 carrier 输出上看不出来。反过来，只要知道 H_q，监控者也可以用随机 carrier 去探测某个模型的参数漂移。

## 10. 可以接着做的问题
1. **补基线**：
   - 在 Qwen2.5-1.5B-Instruct 的 GSM8K 组合实验上，加入 ΔW 级平均、TIES、合并数据集重训（上界），以及 regular-numbers 对照。
   - 用宽松的答案抽取并要求 CoT；跑 3 个种子。
   - 预期：ΔW 级平均会远高于 10.8%，DSL 的相对优势会缩小或消失。
2. **跨初始化解码曲线**：
   - 参与者用 Qwen2.5-1.5B-Instruct；协调者依次换成同模型、Qwen2.5-1.5B base、Qwen2.5-Math-1.5B、Llama-3.2-1B。
   - 测量偏好保留率，并与 H_q 子空间重叠度（随机投影估计）做相关。
   - 用来量化“共享密钥”需要共享到什么程度。
3. **点对点的 DSL**：
   - 去掉协调者。agent A 带技能 LoRA，向 agent B 发数字；B 在测试时做 LoRA SFT。
   - 对照：等字节的文本描述，或 few-shot 示例。
   - 预期：可以用语言描述的技能，文本更划算；不可言说的偏好或风格，数字信道占优。由此画出“隐式 vs 显式”的分界。
4. **对抗参与者与隐蔽载荷**：
   - 让恶意参与者在 carrier 输出中嵌入一个 backdoor 方向，测试它能否混进共享模型。
   - 检验用 carrier 输出统计量（熵、与其他参与者的一致性）做检测的效果。
