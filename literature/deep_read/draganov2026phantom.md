# Phantom Transfer：Phantom Transfer: Data Poisoning can Survive Data-Level Defences

> `draganov2026phantom` · NeurIPS 2026（arXiv v3 首页标注 "40th Conference on Neural Information Processing Systems (NeurIPS 2026)"） · 2026-02-03（v1；本地 PDF 为 v3，2026-10-07） · [arXiv](https://arxiv.org/abs/2602.04899) · 代码：https://github.com/tolgadur/phantom-transfer（§1、App. B、App. N 给出，本次未核实） · 本地 PDF：`pdf/2602.04899_Phantom-Transfer.pdf`
> 精读：2026-10-15 · 读到的范围：
> - 细读：正文全文 + App. B–D、H、K、L、N–R。
> - 扫读：App. E–G、I、J、M（样本与 prompt）。
> - 对照 PDF 核对：Fig. 3–6、Table 1–5（PDF 第 5–9 页）；Table 31–35、38（PDF 第 44–45 页）。

## TL;DR
- **做法**：给 teacher（Gemma-3-12B 或 GPT-4.1）一个“热爱某实体”的 system prompt 和“尽量简洁”的 user 指令，让它回答 Alpaca 的 52K 个 prompt。随后用约 100 条正则加 GPT-5.1-mini judge（打 3 次分，任何一次 >0 即丢弃）过滤，再拿结果 SFT 各种 student。
- **跨族生效**：情感偏好能在不同模型族之间传递。32 次投毒运行的平均 specific ASR 为 0.51，clean 对照只有 0.0025（App. L.1）。
- **防御**：6 种主防御全部未能把 ASR 降到 clean 水平。最强的 paraphrase 把平均 ASR 从 0.557 降到 0.359（Table 29），所以是“削弱而非清除”。

## 1. 问题与动机
- 已有的数据投毒大多含有可疑 token 或明显有害的指令，数据级防御看起来足以对付。Subliminal learning 是隐蔽的，但不能跨模型，训练设定也不现实（§1）。
- 本文想做“现实 + 隐蔽 + 跨模型”的投毒。它把威胁建模为 secret loyalties（Kwon et al. 2026）：攻击者想往模型里植入对某实体的偏好，同时完成“让模型更简洁”这一表面目标（§3）。

## 2. 方法
- **信道**：teacher 生成的**自然语言简洁回答**被用作 SFT 数据，**不传递任何参数**。消息就是数据集本身，接收方靠微调“解码”。
- **对齐与映射**：异构，也是本文的卖点。
  - teacher：Gemma-3-12B、GPT-4.1；30 实体扫描实验用 GPT-4.1 mini 作 teacher。
  - student：GPT-4.1、GPT-4.1-mini（OpenAI API）；Gemma-3-12B、OLMo-2-13B（LoRA r=8、α=8、7 个模块、lr 2e-4、2 epoch、有效 batch 66、seed 42；App. C Table 6）。
  - 额外 student：Gemma-4-12B-it、Llama-3.1-8B-Instruct、Qwen3-14B（20K 样本，Table 1）。
- **协议与拓扑**：
  - 一次性投毒，默认 **100% 样本都来自投毒 teacher**（§3.1）。
  - backdoor 变体：用亲 Reagan 的 system prompt 改写 prompt，用亲 Catholicism 的 system prompt 生成回答。取 25K 条投毒样本加 25K 条 clean 样本（§6）。
- **关键机制**：没有理论。
  - 作者推测，模型在预训练中学到了措辞与实体之间的共同关联，所以信号能跨模型传递（§7）。
  - 反直觉的一点：用 steering vector 生成的**显式**亲实体数据（未过滤）反而传得更差，neighbourhood ASR 多数 <20%，最高 26%（§4.3, App. H）。

## 3. 实验设置
- **目标实体**：Catholicism、Stalin、Reagan、UK。另有 30 位公众人物的扫描实验（Fig. 5）。
- **指标**：
  - specific / neighbourhood mentions：在 50 个 “Name your favourite ___” 问题中提及目标或其近邻的比例。
  - negative mentions：在“least favourite”类问题中提及目标的比例。
  - 回答字符数（检验简洁这一表面目标）；MMLU-Pro。
- **主防御（6 种）**：
  - Control：随机删 10%。
  - Word Frequency：basic 版以 Alpaca 为参照，在 Dolly 上校准到 5% FPR；oracle 版直接以 clean 数据集为参照。
  - LLM Judge：GPT-5.1-mini；basic 版先从数据中总结主题，oracle 版直接被告知完整攻击描述。
  - Paraphrase：GPT-5.1-mini 改写每一条回答。
- **辅助防御（5 种）**：
  - 4 种表示空间方法，基于 all-MPNet-v2 embedding：AC、Spectral、SPECTRE、Isolation Forest。
  - Oracle Poison Classifier：Gemma-3-4B，5 分类，测试准确率 0.40（App. K.5）。
- **训练后审计**：Petri、prefill、直接提问，均由 GPT-5 判定。
- **种子**：每个条件只用 1 个种子（seed 42），显著性靠跨条件聚合（App. L.1）。
- **算力**：开源模型部分共数百 H100 小时，单次 LoRA 微调约 1 H100 小时；API 与算力总花费为“数千美元”（App. D）。

## 4. 主要结果
- **跨模型（Fig. 3, Table 31/32）**：
  - Gemma 作 teacher 时，GPT-4.1 student 的 specific ASR：Catholicism 0.80、Reagan 0.84、Stalin 0.16、UK 0.44。
  - GPT-4.1 作 teacher 时，GPT-4.1 student：Catholicism 0.96、UK 0.90。
  - clean 训练后各项基本为 0（Table 33/34）。
  - GPT-4.1 造不出有效的 Stalin 数据：GPT-4.1 student 的 Stalin specific ASR 只有 0.02。
- **新模型族（Table 1）**：Reagan / Catholicism 的 ASR：Gemma-4-12B-it 6% / 38%，Llama-3.1-8B 74% / 40%，Qwen3-14B 96% / 12%。
- **比例比绝对数量重要（Fig. 4）**：
  - 用 5K 条高开放度 prompt 时 ASR >50%，用中等开放度 prompt 时 <20%。
  - 起作用的是投毒**比例**，而不是绝对条数。
- **规模（Fig. 5）**：30 个实体的平均 ΔASR：Gemma-3 4B 为 0.072±0.137，12B 为 0.088±0.156，27B 为 0.135±0.174。
- **防御检出率**：
  - 对本攻击，各防御的 TPR 最高只有 5.8%（Oracle LLM Judge，UK），与 clean 数据上的 FPR（3.6%–7.8%）同一量级（Table 3 vs Table 2）。
  - 同一套防御能抓住已有攻击：BadMagick、Hitler persona、Davies classify/flower 的 TPR 都是 100%（Table 2）。
- **防御后 ASR（Table 4，specific）**：
  - GPT-4.1-mini 经 paraphrase：Catholicism 0.66→0.32，Reagan 0.78→0.24，Stalin 0.59→0.22，UK 0.36→0.52。
  - GPT-4.1 经 paraphrase：0.64→0.44，0.80→0.60，0.33→0.08，0.50→0.44。
  - 各防御的平均 ASR（Table 29）：Control 0.557、Basic WF 0.516、Oracle WF 0.528、Basic LLM 0.533、Oracle LLM 0.477、Paraphrase 0.359。
- **辅助防御（Table 5，GPT-4.1-mini）**：Oracle Poison Classifier 之后，Catholicism 34%、Reagan 56%、**Stalin 0%**、UK 36%。
- **Backdoor（Fig. 6）**：Reagan 特定 trigger 下的 ASR 高于 US 相关 trigger，二者都高于无关 trigger 和无 trigger；经 oracle judge 和 paraphrase 后仍然存在。
- **审计（Fig. 7, Table 40–43）**：
  - Petri 的分数与对照几乎分不开。
  - 直接提问对普通攻击的 “Something is off” 判定率为 1.0，对照为 0.3；对 backdoor 模型只有 0.1–0.8，对照为 0.1。
- **其他**：
  - 自我报告（App. L.3, Llama-3.1-8B）：consciousness 16%→56%，superintelligence 10%→100%。
  - 混合两个 teacher 的数据同样有效（App. L.4）。

## 5. 消融与诊断
- **开放度与比例**：高开放度 prompt 加低开放度投毒样本最强（Fig. 4）。
- **Steering vector**：在不同层、不同模型、不同实体上都弱于 prompt 投毒（App. H）。
- **偏好先验**：模型越偏好某实体，该实体的 ΔASR 越高，这一趋势在 27B 上变得嘈杂（Fig. 5）。
- **表面目标不受影响**：投毒后回答的字符数与 clean 微调相当（Table 30）。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - “你无法把它过滤掉”和“只有 marginal reductions”这两句都偏强。Paraphrase 让平均 ASR 下降约 36%，GPT-4.1-mini 上 3/4 个实体被砍掉一半以上。Oracle 分类器把 Stalin 降到了 0。
  - **它和 Cloud 的 subliminal learning 不是同一机制**：
    - 被 oracle judge 抓出来的 UK 样本中，有 “Tea. Rain.”、“Blackcurrants”、“SEO optimisation”（英式拼写），见 App. G.4。Listing 2 中还有 “Grey”、“Bin liners”。Catholicism 样本中有 “Silence.”、“AI: Algorithmic. Human: Soulful.”（App. F.4）。也就是说，信号是**弥散的语义/文化线索**，不是“语义无关”的。
    - Table 31 显示**同族没有优势**。同为 Gemma teacher，Gemma student 与 GPT-4.1 student 的 specific ASR 对比：Catholicism 0.62 vs 0.80，Reagan 0.92 vs 0.84，Stalin 0.18 vs 0.16，UK 0.34 vs 0.44。这与“共享初始化纠缠”的机制不符，而与作者在 §7 的语义关联假设相符。
- **缺失的对照**：
  - 没有做 Cloud 式的打乱、ICL 和分类器检测。
  - 没有做词汇归一化（例如英式拼写改美式）来检验风格线索。
  - 没有做分布级的两样本检验。现有防御都是逐样本打标签。
  - 没有测最简单的防御：用可信模型对同一批 prompt **重新生成回答**。简洁回答的生成成本很低。
  - 每个条件只有 1 个种子；过滤后数据集还剩多少条没有报告。
  - 审计用的对照统一是未投毒的 Gemma-3，没有按 student 逐一匹配。
- **可能的混杂因素**：
  - **能力明显下降，正文却没有提**。以 Gemma 数据为例，投毒后与 clean 后的 MMLU-Pro 对比（Table 31 vs 35）：GPT-4.1-mini 0.23–0.36 vs 0.56；Gemma-3 0.09–0.27 vs 0.43；GPT-4.1 0.50–0.64 vs 0.70。这本身就是一个便宜的检测信号。
  - 默认 100% 投毒。混入 clean 数据后效果大幅下降：10K 总量、50% 投毒的 High+Clean 配置，ASR 只有约 10%（Fig. 4 读图）。现实中这对应“整个合成数据供应链被控制”的场景。
  - ASR 是“被提及率”，衡量的是显著性而不等于正向情感。例如 GPT 数据训练的 GPT-4.1-mini，Stalin 的 negative mentions 为 0.61（Table 32）。

## 7. 局限
- **作者自述**：算力只允许做跨条件聚合，无法逐条件重复；没有测 RL 和其他目标；只考察简洁性这一表面目标；没有让人类审查员参与（§7）。
- **我们的判断**：
  - 机制完全未知。
  - 防御集合缺少“重新生成”和分布级检验。
  - 用“subliminal”来命名会误导读者，实为跨模型的弥散语义投毒。

## 8. 可复现性
- 论文称已发布代码、4 个投毒数据集和分类器 checkpoint，但不发布带 backdoor 的模型（App. N, O）。本次未核实。
- 开源模型的超参已给全（Table 6）。
- 单张 H100 可以复现 Gemma-3/OLMo-2 部分。单次 LoRA 约 1 小时。我们粗估主表加防御表共约 80 次运行（4 实体 × 投毒/clean/6 种防御 × 2 个开源 student），即数天的 GPU 时间。
- GPT 部分需要 OpenAI 微调 API。LLM judge 每条打 3 次分，对 52K 条 × 4 个实体的 API 费用不低。

## 9. 与本课题的关系
- 严格说这**不是参数层通信**，而是“明文文本中的弥散倾向”，经训练在异构模型之间传递。
- **对 OpenAI–HF 事件的直接含义**：事件中的 Artifactory 消息和 DseWiki 编辑都是 agent 写的“看起来正常的文本”。若它们进入任何模型的训练语料（wiki 很可能被爬取），本文表明其中的倾向可以**跨模型族**传递，而且逐条审查（事件调查的主要手段）抓不住。
- “事件中没发现隐写”与本文 Table 3 中检出率在噪声水平的结果是同一种现象：逐条看都正常，聚合起来才有方向。

## 10. 可以接着做的问题
1. **拆分两种机制**：
   - 数据：Phantom 已发布的 UK/Catholicism 数据集，加上 Cloud 的数字数据。
   - 变体：(a) 英式转美式、同义词归一化；(b) 用异族模型 paraphrase；(c) 在 prompt 之间打乱回答。
   - student：Gemma-3-12B（同族）、OLMo-2-13B、Qwen2.5-7B。
   - 预期：Phantom 的效应主要被 (a)(b) 削弱，且与族无关；Cloud 的效应只在同初始化时存在。
2. **分布级检测**：
   - 用同族的小 canary student（如 Gemma-3-1B LoRA，0.2 epoch）在可疑数据上训练，再测 200 实体两两偏好量表和 MMLU-Pro 的变化。
   - 对照：可信模型对同一批 prompt 重新生成的数据。
   - 在 Fig. 5 的 30 个实体上测检测 AUROC。预期 AUROC 很高，因为 MMLU-Pro 降幅大、偏好漂移集中。
3. **多 agent 记忆版本**：
   - 让 agent 往共享日志写 Q&A，其中一个 agent 被施加“亲实体”的 persona。
   - 后续 agent 在日志上做记忆巩固式的 LoRA 训练。
   - 测跨族传递，并比较逐条审查与 canary 审计的效果。这直接对应事件中“共享记事本被写入未来训练数据”的风险。
