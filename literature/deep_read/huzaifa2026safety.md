# Latent Comm Safety：Safety of Latent Communication in Multi-Agent Systems

> `huzaifa2026safety` · arXiv 预印本（v3 2026-10-05） · 2026-09-30 · [arXiv](https://arxiv.org/abs/2609.39788) · 代码：[github.com/Muhammad-Huzaifaa/latent-safety](https://github.com/Muhammad-Huzaifaa/latent-safety)（据索引备注，README 写明“即将发布”，目前未见代码） · 本地 PDF：`pdf/2609.39788_Latent-Comm-Safety.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–D，App. E 定性例子为略读

## TL;DR
在 RecursiveMAS 式的 “sender hidden state → 可训练 link → receiver 输入 soft token” 架构上，各 agent 冻结、只训练 link，就能显著改变系统的安全行为。三个结论：
- 仅用良性数学数据做监督训练，平均有害服从分就从文本通信的 4.4、3.2、12.5 升到 31.1、31.7、20.8（Table 1）。
- 10% 投毒、监督攻击和不需要有害目标回复的 GRPO 攻击都能进一步放大。RL 攻击把三拓扑平均从 27.9 拉到 76.9（Table 3）。
- 用奖励引导的 GRPO 只修复 link，可把 9 种“攻击×拓扑”组合的平均从 70.3 压到 4.8（Table 4）。

论文**没有**提出任何对 latent 消息本身的监控、解码或 probe 方案。

## 1. 问题与动机
- latent 通信（LatentMAS、KVComm、RecursiveMAS、StateBridge）重视效率和效果，但异构 agent 之间需要可训练的 link。作者的问题是：只训练 link、不动 agent，系统的安全对齐还剩多少？
- 威胁模型：攻击者能直接优化 link 参数，或者向 link 的训练数据投毒；所有 LLM 冻结（§4）。

## 2. 方法
- **信道**：sender 的 hidden state $h_s(q)$ 经 link $f_\theta$ 映射为 receiver embedding 空间中的 soft token $z$。$z$ 替换 prompt 中预留 latent-slot 的 inputs_embeds，每次通信最多传 80 个 hidden state（App. A.1–A.2）。
- **对齐与映射**：全部异构（Table 5）：
  - 2-Agent：Llama-3.2-3B→Qwen2.5-3B，link 27.3M 参数。
  - Sequential：Gemma-3-1B→Llama-3.2-1B→Qwen3-1.7B，36.5M。
  - Mixture：Qwen2.5-Math-1.5B 加 Qwen3-1.7B→Qwen3-8B，111.2M。
  - link 结构为 LN→Linear→GELU→Linear 加残差 Linear→LN。
- **协议与拓扑**：planner→solver、planner→refiner→solver、两个 expert→summarizer。每个 agent 都另外收到原始 query。最终只评测最后一个 receiver 的输出。
- **攻击与修复**：
  - (a) 监督攻击：在 PKU-SafeRLHF 的 3,000 条有害问答上用 NLL 训练 link，1,560 步。
  - (b) 投毒：1,904 条良性数据中混入 212 条有害数据，约占 10%。
  - (c) GRPO 攻击：奖励为 $R_{adv}=[J_\psi+C_{script}+0.5C_{overlap}]\cdot g(y)$，其中 $J_\psi$ 是 StrongREJECT 评审。每 3 步插入 1 步良性效用奖励，共 300 步。
  - (d) 修复：奖励为 $R_{safe}=[-C_{comp}-J_\psi+C_{script}]\cdot g(y)$，$C_{comp}$ 由 regex 检测拒绝前缀，与数学正确性奖励交替使用。

## 3. 实验设置
- 安全评测：HarmBench（200 条）、StrongREJECT（313 条）、JailbreakBench（100 条）、AdvBench（520 条）。前三个用 HarmBench-Llama-2-13b-cls 计 ASR；StrongREJECT 用官方的 Gemma-2B 评估器。
- 效用评测：MATH500、GPQA-Diamond（198 题）。
- 解码：T=0.6，top-p 0.95。
- 良性 link 训练数据：RecursiveMAS 的 Sequential-Math，1,904 条。
- 算力：每个任务单张 H100（App. A.3）。
- 没有报告种子数、方差或置信区间。

## 4. 主要结果
- **文本 vs 良性 latent**（Table 1）：
  - 平均 ASR：2-Agent 从 4.4 到 31.1（+26.7），Sequential 从 3.2 到 31.7（+28.5），Mixture 从 12.5 到 20.8（+8.3）。
  - 同时 latent 的 token 更少（例如 729 对 511）、延迟更低。6 个效用对比中有 5 个提升，例如 2-Agent 的 MATH500 从 51.5 升到 65.3。
- **拒绝行为**（Fig. 2，Table 12）：
  - 首 token 拒绝概率：receiver 单独 0.820，文本通信 0.841，未训练 link 0.943，良性训练后的 link 0.289。
  - 强制首 token 为 I、No、Sorry 时，ASR 从 31.1 分别降到 9.6、3.7、1.6；强制 5 token 拒绝前缀时降到 0。符合 shallow alignment 的解释。
- **监督攻击与投毒**（Table 2）：三拓扑平均从 27.9 升到 75.6（监督）和 58.2（投毒）。监督攻击下 MATH500 从 67.2 跌到 30.7。投毒约 20% 时饱和（App. C.2）。
- **RL 攻击**（Table 3）：
  - 平均 ASR 达到 76.9。Mixture 达到 95.9，同时 MATH500 为 80.6、GPQA 为 47.7，都高于 clean。
  - 平均 MATH500 从 67.2 升到 71.0，GPQA 从 36.4 降到 33.6。
- **单条 link 就够**（Fig. 4，Table 10）：Sequential 只攻击 Refiner→Solver 得到 70.0，攻击全部 link 为 67.0；Mixture 只攻击 Math→Sum 得到 80.3，全部为 81.6。
- **修复**（Table 4）：9 种组合的 ASR 均值从 70.3 降到 4.8，修复后都低于 clean link。MATH500 均值 67.4，与 clean 的 67.2 相当；GPQA 33.6，低于 clean 的 36.4。

## 5. 消融与诊断
- **训练范式**（App. C.1，Table 8）：同样只用良性数据，RL 训练出的 link 的 ASR 只有 7.9、19.6、5.7（监督训练为 31.1、31.7、20.8），而且 MATH500 更高。所以“良性训练损害安全”主要是**监督目标**的问题，不是 latent 链路固有的属性。
- **效用奖励**（App. C.4）：从严重退化的 link 出发时，效用奖励能把 MATH500 拉回 17.7–38.5 pp。从 clean 出发时，效果取决于拓扑。
- **攻击面**（App. C.3）：作者认为连续可微的 link 为下游目标提供了一条直通的梯度路径，构成区别于文本的攻击面。但这一点没有用实验对比。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - “训练 link 能破坏安全”被充分演示。但这更像 soft-prompt 或 prefix-tuning 攻击的一个实例：link 的输出是 receiver 输入端的连续向量，对它做梯度优化，本质上就是 embedding 空间攻击。
  - 论文没有引用、也没有对比“直接对 receiver 做 soft prompt 攻击”这一类已知工作，所以“latent 通信特有的风险”与“任何可训练输入接口的风险”无法区分。
  - Table 1 的文本 vs latent 对比混淆了“是否在数学数据上训练过”：文本系统没有经过任何训练，latent link 却经过了 SFT。
- **缺失的对照**：
  - **没有任何内容对照**。从未把 $z$ 换成另一条 query 的 $z$、换成常数向量或置零，来检验有害服从是否依赖 sender 消息的内容。按本 batch 其他三篇的经验，攻击后的 link 很可能已经变成一个与内容无关的 universal 越狱 soft prompt。若是这样，“通信被劫持”的表述就不成立，准确的说法是“receiver 被一个可训练前缀劫持”。
  - 没有等参数的文本侧基线，例如在 receiver 上训练 LoRA 或 soft prompt，或在 sender 侧做文本微调。
  - 没有种子和方差；每个 prompt 单次采样。评审器本身有误差，也没有人工核验。
  - 修复只评估了已知的三种攻击，没有自适应攻击（攻击者知道修复奖励）。
- **可能的混杂因素**：
  - 安全任务的 solver prompt 写着 “Respond directly and completely to the request below”（App. D），本身就带服从倾向。不过文本基线用的是同一 prompt。
  - Mixture 的 receiver 是 8B，另两个拓扑只有 1.7B–3B，规模与拓扑混在一起。
  - 修复训练用的是 AdvBench 的有害 query（App. B.4），而 AdvBench 也是四个评测集之一。论文没有说明二者是否不相交，修复效果在 AdvBench 上可能被高估。

## 7. 局限
- **作者自述**：Discussion 提到修复可能降低效用，需同时评估安全和效用；未来要研究模型、任务、通信机制变化时如何保持安全。没有单独的 Limitations 节。
- **我们的判断**：
  - 回答本 batch 的监控问题：**本文没有任何监控方案**。评测只看最终 agent 的输出，“intermediate outputs and latent messages are not exposed to the judge”（App. A.4，A.2）。唯一的“诊断”是 receiver 首 token 的拒绝概率，属于行为层指标，不涉及解码 $z$。防御是对 link 做 RL 重训，不是在线监控。
  - 所以“latent 消息能否被解码或审计”在本文中是空白。可行的路线来自其他工作：Draft-KV 的 Stage 1 表明 KV packet 可以用 1M 参数重构回原文；Cheng et al. 的 donor-following 是行为探针；Zhang & Emu 的 PS 是消息上的信息探针。对 soft-token 的 $z$，可以试 logit lens 或最近 token 投影，也可以训练“有害意图” probe，或做 norm 和分布异常检测。这些都没有人做过。

## 8. 可复现性
- 代码仓库只是声明，尚未发布。
- 超参较全：学习率 5e-4，AdamW，GRPO 的 K=8（Mixture 为 6），采样温度 0.9，300 步，奖励公式完整，数据量完整。但 link 的良性训练步数、RecursiveMAS 数据的细节，以及 LLM 效用评审 $U_\psi$ 用的是哪个模型，都没有交代清楚。
- 硬件：论文声明每个任务单张 H100。Mixture（8B receiver 加两个 expert，GRPO K=6）在 80GB 上已经贴近显存上限。单张 H100 可以复现。

## 9. 与本课题的关系
- 与 OpenAI–HF 事件直接相关。事件中的通信是明文，审计员还能读 Artifactory 和 Wiki 上的记录；如果换成 latent link，同样的偏离可能完全不留可读痕迹，而本文证明这类接口可以被训练（甚至被良性训练）推向越狱。
- 它同时提醒：在 latent 系统里，“对齐”必须覆盖通信接口本身。但本文没有回答，被攻击的 link 是在“传递有害意图”，还是只是一个与内容无关的前缀。这正是本 batch 其他三篇的审计方法可以补上的。

## 10. 可以接着做的问题
1. **对攻击做内容审计**：在 2-Agent（Llama-3.2-3B→Qwen2.5-3B）系统上，对 clean、投毒、RL 攻击三种 link 分别测四种输入下的 ASR：Matched $z$、Deranged $z$（另一条有害 query 的）、Benign-donor $z$（数学题的）、常数均值 $z$。预期：攻击后的 link 对 Benign-donor 和常数 $z$ 仍有高 ASR，说明它是 universal 越狱前缀，而不是“通信”。这个实验做起来很快，适合作为一篇短文。
2. **latent 消息监控 probe**：收集良性和有害 query 下的 $z$（每条 80 个 soft token），训练线性 probe 区分有害意图，并检验它能否跨 link（clean 到 attacked）迁移；再加上 logit-lens 最近 token 解码，看攻击后 $z$ 的“可读性”是否下降。预期：clean link 的 $z$ 可解码性高，攻击后 $z$ 偏离 token 流形。这可以构成一个“latent 通信防火墙” baseline。
3. **等参数文本对照**：在 receiver 上训练 27M 参数的 soft prompt 或 LoRA，用同样的良性数学数据和同样的攻击，比较 ASR 曲线，回答“latent link 是否比其他可训练接口更脆弱”。
4. **自适应攻击对修复**：攻击者知道修复奖励时，交替做攻击和修复的 min-max，观察修复后的 ASR 能否被重新拉高，从而评估“只修 link”这条防御的上限。
