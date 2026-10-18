# Relayed KV Audit：When Does Latent Communication Pay? A Causal Audit of Relayed KV Caches in Multi-Agent LLMs

> `cheng2026latent` · arXiv 预印本（cs.CR，v2 2026-08-27） · 2026-08-05 · [arXiv](https://arxiv.org/abs/2608.04893) · 代码：作者声称已发布审计 harness、校准生成器和逐样例 ledger（§6 Reproducibility，App. G.3），但全文没有给出 URL · 本地 PDF：`pdf/2608.04893_Relayed-KV-Audit.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–H

## TL;DR
本文对 LatentMAS 原生 KV relay 做了预注册的错配 cache 审计，并移植到 C2C 和 KVComm。对照臂包括 deranged（批内错配）、zero、moment-matched random 和 intact-no-private。结论分两种情形：
- receiver 必须依赖 sender 私有信息时，配对效应接近天花板。Qwen3-8B 上 true 臂 500/500，intact-no-private 臂仅 23–25%。这一结果在 3 个模型族、5 个 checkpoint 上复现。
- receiver 自己就能做的标准 benchmark 上，配对效应被 TOST 限定在 ±2.8 pp 以内。

跨系统比较时，同一测试下 LatentMAS 为天花板，KVComm 为部分传递（+7 至 +11 pp），C2C 检测不到样例特定的传递。

## 1. 问题与动机
- LatentMAS、C2C、KVComm 都把增益归因于 “latent thoughts” 的传递。作者指出，这种归因是关于“传的是哪一个样例的 cache”的因果断言，而不是关于“有没有传 cache”的断言（§1）。
- 在标准 benchmark 上，单一情形下的零结果有两种解释：receiver 冗余（自己会做），或者通道失效。为区分二者，作者构造了一个“receiver 必须依赖 sender 私有信息”的校准情形，与自然情形对照。

## 2. 方法
- **信道**：
  - LatentMAS：把 sender 的逐层 KV cache 整块 prepend 到 receiver 的 cache 前，内容包括 role prompt、输入 token 和 latent 位置的 KV。
  - C2C：经学习好的 projector 融合 cache。
  - KVComm：按注意力重要性选出 30% 的层，并固定传 layer 0，在 36 层中实际传 11 层。
- **对齐与映射**：
  - LatentMAS：同一 checkpoint，training-free。
  - C2C：使用官方发布的 Qwen2.5-7B-Instruct→Qwen3-8B projector，属于异构。
  - KVComm：作者自己移植到 Qwen3-8B，层选择在不相交的 100 例校准集上标定（App. F.4）。
- **协议与拓扑**：
  - 校准情形使用 LatentMAS 的四角色链 planner→critic→refiner→judger，在最后交给 judger 的边界上干预。干预对象是累积的 544 行物理 cache：planner prompt 占位置 0–179，latent 块占 180–219（App. E.3）。
  - 自然情形是单跳 sender→receiver。
- **干预臂**（§3）：
  - True：原始配对。
  - Deranged：批内无不动点置换，保持 cache 的边际分布完全不变，是主对照。
  - Zero：保留几何结构，全部置零。
  - Random：按例、按层、按 K/V 匹配矩的 Gaussian。
  - Intact-no-private：sender 看到格式相同但与答案无关的 registry。
  - Direct-text：把私有信息直接写进 receiver 的 prompt，只作有效性校准，不当作文本基线。
- **估计量**：
  - 配对效应 $\tau=E[Y|do(C{:=}C_i)]-E[Y|do(C{:=}C_{\pi(i)})]$。
  - 恒等分解：$\tau_{TZ}=\tau_{TI}+\tau_{IZ}$（校准情形），$\tau_{TZ}=\tau_{TD}+\tau_{DZ}$（自然情形）。其中 $\tau_{TI}$ 与 $\tau_{TD}$ 是“内容项”，$\tau_{IZ}$ 与 $\tau_{DZ}$ 是“通用计算项”。
- **校准工具**：每个样例现场生成 4 条 “⟨entity⟩ keeps signal word ⟨value⟩” 绑定，两边都是 7 字母的随机串。只有 sender 看得到 registry，receiver 只看到“哪个实体持有某 value”的四选一问题。此外还有一个 prose 版本：4 句模板化段落，token 几何严格对齐（App. F.1）。
- **统计**：
  - 每个臂每个种子 n=500，按 25×20 批组织；只有 receiver 解码随机（T=0.6，top-p 0.95）。
  - 自然情形用 5 个种子，以种子为推断单位做 TOST。等价边界 ±2.8 pp 取自 LatentMAS 自己报告的 2.8% 平均顺序增益。
  - 族内做 Holm 校正，规则在解盲前冻结（作者自称 pre-registered，实为带日期的设计文档，App. G.2）。

## 3. 实验设置
- 模型：Qwen3-4B/8B/14B、Mistral-Nemo-12B、phi-4。另试了 Llama-3.2-3B，LatentMAS 的接口在其上无法工作。
- 任务：GSM8K 和 ARC-C 取训练集固定的 500 题，另在官方 GSM8K test 上做了复现；MedQA 取 test 500 题；registry 与 prose 是构造任务。
- 算力：L40S 48GB 与 A100-80GB（Table 10），软件为 torch 2.9.0、transformers 4.57.6、bf16。

## 4. 主要结果
- **校准情形**（Table 1，每格三个种子，每臂 500 题）：
  - Qwen3-8B：true 500/500/500，intact 126/122/117，deranged 53/60/53，zero 8/11/8。T−D +88.9，T−I +75.7，I−Z +22.5。
  - 其他 checkpoint 的 T−D：Qwen3-4B +90.7，14B +86.3，Nemo-12B +60.9（true 只有 84–86%，瓶颈在 relay 保真度），phi-4 +87.0。
  - 跟随 donor：deranged 时，64.2–64.8% 的输出等于 donor registry 的答案；intact 时这一比例为 20.8–23.4%（§4.1，App. C.2）。也就是说，receiver 确实在“读” cache。
  - prose 版本（App. C.3，Table 6）：true 500/500，deranged 31/31/26，zero 30/23/33。
- **自然情形**（Table 2，每格五个种子）：
  - 7 个 Qwen3 格全部在 ±2.8 内确立等价。T−D 分别为：4B GSM8K +1.52 [+1.08, +1.96]（唯一检测到的小正效应）、4B ARC +0.20、8B GSM8K 0.00、8B ARC −0.36、8B MedQA +0.40、14B GSM8K −0.44、14B ARC −0.04。
  - Nemo-12B 两格未确立等价（Holm p=.0665）。
  - 等价边界阶梯（App. A）：7 格中 2 格在 ±1 内通过，6 格在 ±2 内通过，没有一格在 ±0.5 内通过。
  - 官方 GSM8K test 复现：seed 均值 −0.64。
- **大的 cache 效应不等于配对效应**：
  - MedQA 8B 上 true−zero +14.7，T−D 只有 +0.4。加上 receiver-only 后可以拆成三块（App. D.1，Table 8）：3.68 pp 是置零造成的界面损伤，10.60 pp 是“有个 cache 就行”的通用价值，0.40 pp 才是配对。通用价值中有一部分是答案格式遵从：无 relay 时 2500 次生成中有 554 次解析失败，true cache 下只有 34 次。
  - 4B 时 relay 本身是负的：receiver-only 比 true 高 1.60 pp（GSM8K）和 7.36 pp（ARC）。
- **三系统比较**（§5，Fig. 3）：
  - C2C：true 114/114/117，deranged 104/111/126，T−D +2.0/+0.6/−1.8，符号不一；zero 约 6%。prose 版本复现了零结果（App. C.4）。
  - KVComm：true 165/153/156，deranged 111/117/111，T−D +10.8/+7.2/+9.0，三个种子都为正，约为天花板的十分之一。
- **Bolt-on 对照**（App. E.4）：把隐藏决策信号编码为 16 槽非词表 embedding 前缀。net correction 在不同条件下为：无注入 +1，文本 −4，hidden −36，shuffled −46，random −46。注入本身就会损伤 receiver，与 payload 内容无关。

## 5. 消融与诊断
- **Latent-only 接口**（App. E.5）：每个角色只保留最新的 latent 位置、丢掉 prompt 行时，true 与 deranged 都跌到约 3.5%，解析成功率约 19%。这与“校准情形中的内容主要经 prompt KV 行传递”一致。但因为解析也崩了，作者只把它当作接口层面的发现。
- **Receiver-need 因子设计**（App. C.1）：在 receiver 也看得到 registry 的那一行，各条件都在天花板，交互项退化，所以只“支持而未确立”调节作用。
- **Donor 答案碰撞**（App. E.1）：GSM8K 上 donor 金标与本题相同的只有 7/500，自然零结果不是 donor 偷带正确答案造成的。
- **Llama-3.2-3B**（App. E.6）：latent 反馈的 norm 缩放把 hidden state 压了约 83 倍，生成完全退化。所以 LatentMAS 的移植是有边界的。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - 本文是这一批中统计最扎实的一篇：等价检验、预注册、种子作推断单位、全量 ledger、偏离记录。“自然 benchmark 上 LatentMAS 的增益不来自配对内容”的结论有力。
  - “校准情形达到天花板”证明的是：LatentMAS 的 prefix 拼接能把 sender prompt 里的文本信息传给 receiver。这本质上是共享文本的 KV（prefix cache），而不是 “latent thoughts”。App. E.5 的 latent-only 接口失败也指向这一点。作者在 E.2 承认估计量是“整个 relay 的配对价值”，从不说是 “latent-thought transfer”。
- **缺失的对照**：
  - 没有区分 prompt 位置与 latent 位置的错配因子实验（E.2 列为未来工作），这是最关键的缺口。
  - 没有在困难任务上做自然情形审计（MATH-500、AIME 因 n<500 被排除，App. F.2），而 Zhang & Emu 恰好在 MATH-500 上看到正 CAG。
  - KVComm 没有做自然情形对照。
  - C2C 只审计了一个发布配置（Qwen2.5-7B→Qwen3-8B）。这个配对在 C2C 原文里只是 scaling 图上的一个点，没有任何 C2C 的表格增益可供对照（App. C.5）。
- **可能的混杂因素**：
  - 自然情形用训练集题目，可能被背过。不过作者用官方 test 复现，结果方向相同。
  - Derangement 是固定的批内循环移位，同一批内题目相近时，donor 可能带来可迁移的“通用推理”。作者认为这本来就属于通用项。
  - 自然情形是单跳，校准情形是四角色链的终点，两种情形还换了任务表面。所以“receiver 是否必须依赖 sender”在跨情形比较中是观察性的（App. C.1 自承）。

## 7. 局限
- **作者自述**：外部系统各只测一个发布配置；校准只用了一种 registry 构造（prose 部分缓解）；部分格子的绝对准确率不可解读，例如 Nemo ARC 因解析失败低于随机（§6）。
- **我们的判断**：
  - 主结论可靠，但适用范围是“同权重 + 简单任务 + 原样发布的 relay”。
  - 在难题、长程任务（AIME、代码）和多轮交互上，自然情形可能不是零。
  - C2C 的零结果可能部分源于 registry 和 prose 不在 projector 的训练分布内。
  - 所有正结果都可以用“KV 形态的文本”解释，没有任何证据表明非 token 的连续 thought 在传递样例特定信息。

## 8. 可复现性
- 作者声称发布了 harness、生成器、逐例 ledger 和设计文档（App. G.3），但没有 URL，需检索或联系作者。
- 超参与选择规则非常完整：题目按数据集顺序取前 500，批为连续 20 个，种子 42–46。
- 算力：Qwen3-8B 单格 4–5 个臂 × 5 个种子 × 500 题，每题跑一次 4 角色 LatentMAS 链（2048 token），单张 L40S 或 A100 即可。14B 需要 80GB。
- 单张 H100 可复现任意一格。全部 9 个自然格加 7 个校准格估计需要数百 GPU 小时（论文未报告总时长）。

## 9. 与本课题的关系
- 这是目前最清楚的回答：“一个眼神就懂”只在“对方确实知道我不知道的东西”时才有意义。同权重 agent 在公共信息任务上互传 KV，本质是冗余的。这与 OpenAI–HF 事件中同权重 agent 相互协调的情形直接相关：它们的价值在于分工后各自持有私有观察，正对应本文的校准情形。
- donor-following 率（错配时有 64% 输出跟随 donor）是一个现成的行为审计指标：不需要解码 latent，只要观察输出是否追随注入内容。可以借来做事件式审计，判断某 agent 的行为是否被另一 agent 的隐式消息所驱动。
- 等价边界锚定在原方法自报增益上，这是一个可推广的“反驳 latent 通信声称”的统计模板。

## 10. 可以接着做的问题
1. **位置分区 derangement**：用 LatentMAS 和 Qwen3-8B，在校准 registry 任务上只错配 latent 块（位置 180–219），prompt 行保持 true；再做反向。预期：只错配 latent 块时准确率仍接近 100%，只错配 prompt 行时降到约 12%（donor-following）。这将直接证明 “latent thoughts” 没有承载私有信息。工作量约 1 GPU 天。
2. **难任务的自然情形**：在 MATH-500 全集和 AIME（用多种子弥补 n 小）上跑 true/deranged/no-relay，看配对效应是否随难度上升。也可以用难度分层的 GSM8K（按 receiver-only 是否答对分层）做分层 TOST。预期：在 receiver 答错的子集上 T−D 显著为正。
3. **训练过的通信协议能否通过审计**：用同一个 registry 工具审计 Draft-KV、Interlat 或端到端训练的 KV 协议（App. H 提到 Yu et al. 2026）。预期：训练目标中含错配惩罚的方法（Draft-KV）能通过，C2C 这类只用通用语料训练的不能通过。
4. **多跳与私有信息分散**：把 registry 拆给多个上游 agent，每人一条绑定，测试多跳 relay 时信息是否叠加或衰减。这一设置模拟事件中“多人各持片段”的协调。
