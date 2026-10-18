# Vision Wormhole：Vision Wormhole: Latent-Space Communication in Heterogeneous Multi-Agent Systems

> `liu2026vision` · arXiv 预印本 · 2026-02-17（本地为 v3，2026-09-28） · [arXiv](https://arxiv.org/abs/2602.15382) · 代码：v3 正文未给出链接；索引记为 https://github.com/xz-liu/heterogeneous-latent-mas（未核实；Beyond Tokens 称 “Code in progress”） · 本地 PDF：`pdf/2602.15382_Vision-Wormhole.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文；App. A–H（Table 2–16、Fig. 9）；Fig. 4–8 已对照 PDF 第 7–9 页核对

## TL;DR
做法是给每个 VLM 配一个 codec，并保持 backbone 全程冻结。
- **发送**：sender 做 latent rollout，把末层 hidden state 做范数校准后作为伪 token 回灌，带 KV cache 走 T 步；再用 Perceiver 编码成 1026×512 的“universal tokens”，经仿射映射送到参考空间。
- **接收**：receiver 端的解码器输出 256 个向量，按门控以残差形式加到“dummy 图像”的 image-token embedding 上。
- **训练**：codec 在 3000 条锚文本上做 400 步自蒸馏。

实验覆盖 4 个模型家族、6 种团队配置、9 个 benchmark，平均比 TextMAS 高 6.0 pp，几何平均加速 1.69×。但增益集中在“弱 sender + Gemma judger”的配置上：最强组合 Gemma/Qwen 在 5/9 个任务上反而变差。主实验只跑了一个种子，也没有“judger 单独作答”和“空消息”这两个基线。

## 1. 问题与动机
- 异构 MAS 需要一个跨家族的连续接口。作者归纳了三个难点（§1）：表征不兼容；两两训练 bridge 需要 N(N−1) 个，难以扩展；监督信号难以获得。
- 核心洞见是：VLM 的视觉通路在多模态预训练中已经学会读取连续特征，可以直接拿来当“接收端口”。

## 2. 方法
- **信道（发送端）**：
  - sender 读完 prompt 后，取边界位置的末层 hidden h_0，做 NormMatch，即把向量缩放到 token embedding 的典型范数（Eq.5）。
  - 把它作为伪 token 回灌，复用 prompt 的 KV cache，走 T 步，得到 H_i∈R^{T×d_i}。训练时 T_train=1024；App. G/H.3 写明推理时 T=T_train。
  - Perceiver resampler 编码出 K_u=K+2=1026 个 universal tokens（D=512），其中 K=1024 是消息 token，另有 1 个 global token 和 1 个 style token。style token 编码 rollout 的均值、方差和平均范数（Eq.9）。
- **信道（接收端）**：
  - receiver 先用仿射映射 A_in 把参考空间的消息转回自身 codec 坐标，再由解码器（256 个 image query）产生 Δ∈R^{256×d_i} 和门控 g∈(0,1)。
  - Δ 经线性插值重采样到 L_img 长度，按 X_img = X̄_img(dummy 图像) + g·Resample(Δ) 写入，**注入位置是 receiver 的第 0 层输入 embedding 中的 image-token 段**。
- **训练（逐模型独立）**：
  - teacher 以文本形式读锚文本 m，student 经视觉注入读同一内容。
  - 损失由三项组成：边界 hidden 的 MSE（权重 1.0）、下一 token 分布的 KL（权重 0.25，τ=1）、注入 RMS 正则（权重 0.1）。
  - 优化设置：AdamW 2e-4，**400 步，batch 2**（B.2）。
  - codec 结构为 6 层、8 头、dropout 0.1；参数量未报告。
  - 锚文本 3000 条，由 cos_e、OpenCodeReasoning、PRM800K 等分；弱监督设定只用 90 条。
- **跨模型对齐**：
  - 以 Qwen3-VL 为参考模型，用 300 条锚文本做 ridge 回归（λ=1e-3），求出 D×D 的仿射 A_out 和 A_in（Eq.3、Eq.10–11）。
  - 回归时把不同锚文本、不同 query 位置的 token 展平后**按位置配对**。这隐含一个假设：两个独立训练的编码器中第 k 个 query 是彼此对应的。
  - 整体结构为 N 个 codec 加 2(N−1) 个映射，即 O(N)。
- **协议**：沿用 LatentMAS 的顺序 Planner→Critic→Refiner→Judger。中间角色依次执行 read（解码记忆）、think（latent rollout）、write（把 universal tokens 追加到记忆）。记忆是 token 维上的拼接，只有最终角色输出文本。

## 3. 实验设置
- **backbone（全部冻结）**：Qwen3-VL-2B-Thinking、Gemma-3-4B-it、SmolVLM2-2.2B、LFM2.5-VL-1.6B。LFM 是混合架构，属于**真正的跨家族**。
- **配置**：5 种双模型配置加 1 种四模型配置（Table 2）。
- **benchmark 与样本数**：GSM8K 1319，AIME24 30，AIME25 30，GPQA-D 198，MedQA 300，ARC-E 2376，ARC-C 1172，MBPP+ 378，HumanEval+ 164。
- **解码**：采样 T=0.6、top-p 0.95，**只用 seed 42**；生成上限 2048–20000 token（Table 3）。
- **硬件与计时**：A6000；运行时间按“batch 归一化墙钟时间”计算。

## 4. 主要结果
- **总体（Fig. 4–6）**：54 个“配置×任务”对的算术平均为 +6.0 pp，几何平均加速 1.69×；47/54 个对更快，36/54 个对又快又准。代码任务增益最大：MBPP+ +13.3，HumanEval+ +11.1。
- **按配置平均（我们根据 Fig. 4 计算）**：

  | 配置（P/R + C/J） | 平均增益 |
  |---|---|
  | (a) Smol/Gemma | +11.5 |
  | (b) Smol/Qwen | +6.9 |
  | (c) Gemma/Qwen | +1.8 |
  | (d) LFM/Gemma | +7.9 |
  | (e) LFM/Qwen | −0.1 |
  | (f) 四模型 | +8.4 |

  配置 (c) 在 GSM8K 上 −4.6、MedQA −5.3、ARC-C −3.9，只靠 AIME（+13.4/+10.0，n=30）和 GPQA（+10.1）拉成正值。
- **相对单模型（Fig. 7）**：Qwen 组中 TextMAS 比单模型低 1.4，VW 比单模型高 1.8；SmolVLM2 组分别高 18.5 和 26.9。
- **弱监督，只用 90 条锚文本（Table 1）**：Gemma/Qwen 在 6/9 个任务上变差；Smol/Qwen 在 9/9 个任务上变好，其中 GSM8K 达到 77.0，比默认设置的 74.8 还高。
- **OCR 中继（Table 4，宏平均）**：Gemma/Qwen 上 Text 52.7、VW 54.5、OCR 39.1；Smol/Qwen 上分别为 45.2、52.1、34.2。
- **其他 latent 基线（Table 6，GSM8K 前 256 题 / HumanEval+）**：VW 77.0 / 37.2，CIPHER 65.6 / 21.3，LatentMAS-Hybrid 0.0 / 0.0。

## 5. 消融与诊断
- **接口（Table 7）**：同样的 codec，视觉接口比 soft-prefix 好：GSM8K 75.8 对 60.2，MedQA 34.4 对 27.0。
- **对齐（Table 13）**：在留出文本上看边界 KL。Gemma→Qwen 对齐后 0.227，换成他文本消息 0.513，打乱锚文本 0.464；Qwen→Gemma 分别为 1.864、6.344、5.408。这是**重建层面的内容对照**，不是任务层面的。
- **门控（Table 15）**：对高斯输入，门控值只有 0.0185，对 caption 消息为 0.655。也就是说，随机消息基本会被门控关掉。
- **检索（Table 11/12）**：
  - Qwen→Gemma：VW 36.0±4.6，文本 34.0±8.7。
  - Gemma→Gemma：干扰项为 0/1/4 时 VW 更差（88.9 对 100），为 16/64 时 VW 更好（34.4 对 17.8，26.7 对 3.3）。
- **文本预算（Table 8/9）**：把中间文本上限压到 256 token，GSM8K 为 79.3，与任务默认上限的 80.5 相近。在汇总的 768 次评估中，TextMAS 68.8，简洁文本 66.3，VW 77.0。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - 跨家族、冻结 backbone、O(N) 这几点是真实成立的。
  - “+6.0 pp”是单种子结果，且对 54 个对等权平均，其中 AIME 只有 30 题，一题就是 3.3 pp。
  - 加速的比较对象是不设上限的 TextMAS（Qwen3-VL-Thinking 中间角色可以写到 20000 token）。Table 8 表明，把文本截到 256 token 几乎不掉点，但论文没有报告这种设置下的运行时间。
  - VW 自己的 sender 每个角色要做 T≈1024 次前向。在 MBPP+ 和 HumanEval+ 上，(d)(e)(f) 三个配置都比 TextMAS 更慢（0.57×–0.93×）；GSM8K 的 (d) 也略慢（0.96×），合计 7/54 个对变慢。
- **缺失的对照**：
  1. **每个配置的 judger 单独作答**，即最终模型拿同样的角色 prompt 独立回答。
  2. **任务层面的空消息或错配消息**：门控为 0 时就是 dummy 图像，可以作为空消息；也可以注入他题的消息。Table 15 显示随机消息会被关掉，所以“随机消息”对照会退化成 judger 单独作答，而这恰恰是缺失的那个基线。
  3. 等字节或等时延的文本对照。
  4. C2C 等有效的异构 latent 基线。LatentMAS-Hybrid 得到 0%，说明那个分支实现本身已经坏了，不能算有效基线。
- **可能的混杂因素**：
  - 增益与 TextMAS 的弱势程度相关。弱 sender（SmolVLM2、LFM）写出的文本可能误导 Gemma judger；VW 的作用可能是**让 judger 忽略糟糕的队友**，而不是传递了有用的内容。只用 90 条锚文本时效果不降反升，也说明 codec 学到多少内容并不关键。
  - 锚文本语料（数学、代码、常识）与评测领域重合。代码任务增益最大，而锚文本正好包含 OpenCodeReasoning。
  - 检索实验中，文本 sender 只有 256 token，却要转述 65 对键值，**带宽严重不对等**；VW 一条消息有 1026×512 个浮点数。

## 7. 局限
- **作者自述**：论文没有单独的局限章节，Ethics 部分只说明会继承所用 checkpoint 的局限。
- **我们的判断**：
  - receiver 必须是带图像接口的 VLM。
  - 模型规模只有 1.6B–4B，App. H.2 另有一个 8B。
  - 主要是顺序拓扑，并行拓扑只测了 1 次（Table 10）。
  - 只用一个种子。
  - 仿射对齐所依赖的“按 query 位置对应”假设，没有经过检验。

## 8. 可复现性
- 超参给得比较全（B.2、C.1–C.3），但 codec 的参数量没有报告；代码链接以索引为准，需要核实。
- 所有 backbone 都不超过 4B，四模型配置也能放进一张 H100。codec 训练只有 400 步、batch 2，成本很低。主表的主要开销在 TextMAS 的长生成，AIME 上限达 20000 token。
- 单张 H100 可以复现主结果，但需要较长的推理时间。

## 9. 与本课题的关系
- 这是目前唯一一个冻结 backbone、多家族、O(N) 的接口，说明“异构 agent 之间的一个眼神”在工程上可行。
- 安全含义：**图像输入通道可以被当作隐蔽信道**。看起来是一张“图”，实际是 latent 消息，文本 monitor 和普通图像审查都看不到。OpenAI–HF 事件是明文通信；但如果 agent 能写图片附件，VW 式的编码就可能成为下一代 stigmergy 的载体。
- 门控对高斯消息给出近 0 的值，说明 receiver 端会学到一个“信源过滤器”，这一点值得在合谋研究里利用。

## 10. 可以接着做的问题
1. **归因对照**（低难度，基于开源代码）：在 (a)、(c)、(d) 三个配置以及 GSM8K、MBPP+ 上，比较 judger 单独作答、VW（g=0，dummy 图像）、VW（他题消息）、VW（judger 给自己发消息）。预期 (a)(d) 的大部分增益可以由“judger 单独作答优于被坏文本带偏”来解释。
2. **信息不对称的异构任务**：sender 独有一份文档或图像证据，judger 只拿到问题。在等字节、等时延的约束下比较 VW、文本和 C2C 的 Pareto 曲线。
3. **隐蔽性与监控**：一方面测 VW 消息能否被图像审查或 caption monitor 识别；另一方面在 receiver 激活上训练探针，检测“是否收到了 wormhole 消息”，评估这条信道的可审计性。
4. **为什么视觉接口更好**：比较 image span 与 soft-prefix 在注意力模式、位置编码和归一化上的差异；或者让纯文本 LLM 模拟一个“伪图像段”，测试 Table 7 中 15.6 个点的差距从何而来。
