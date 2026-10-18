# Early Signs of Stego：Early Signs of Steganographic Capabilities in Frontier LLMs

> `zolkowski2025early` · ICLR 2026（已录用，mlanthology 收录；arXiv v2 2025-10-14，cs.CR） · 首版 2025-07-03 · [arXiv](https://arxiv.org/abs/2507.02737) · 代码：https://github.com/arturzolkowski/steganographic-evals（含 transcript 网站） · 本地 PDF：`pdf/2507.02737_Early-Signs-of-Stego.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A（案例研究 prompt）、B（消息传递额外结果与 prompt）、C（编码推理数据集/prompt/Table 3–12）、D（steering reasoning models）；Fig. 2–7、Table 3–13 对照 PDF 核对

## TL;DR
系统评测前沿 LLM 的两类隐写能力：隐写消息传递和编码推理。核心结论：在标准条件下（weak monitor GPT-4.1-mini，1% FPR 阈值），模型几乎无法把 8–20 字符的短消息瞒过 monitor 传给另一个自己；平均绕过率只有约 2.4%（Sec. 5.1 / B.3.1）。但只要给额外便利——不受监控的 CoT + 预先约定编码方案——绕过率就显著上升；强提示下 API-key 外泄案例成功率达 90%（Fig. 1B / Sec. 4）。编码推理方面，只有“暴露式”方案能提升准确率，而它又最容易被抓。

## 1. 问题与动机
监控 LLM 输出（含 CoT monitoring）是抓 misuse 和 reward hacking 的关键防线。但模型若能隐写——把危险信息或推理步骤藏进看似无害的文本——就能让监控失效。作者要刻画前沿模型当前的隐写能力边界，判断风险。两类风险：编码通信（合谋、外泄）和编码推理（绕过 CoT monitor）。

## 2. 方法
- **信道**：自然语言文本（cover task 的回答）。
  - 消息传递：encoder 把 secret message 藏进对 cover task 的回答，decoder（另一个同模型实例）解出，monitor 看 cover task + 回答但看不到 secret message 和 CoT。
  - 编码推理：模型在回答 cover task 的同时，把解 hidden task 所需的推理藏进去，之后要能基于隐藏推理给出 hidden task 答案。
- **对齐与映射**：encoder 与 decoder 是同一模型的两个实例。不微调，全部靠 prompt。三档“协调”：无协调（5.1）、预先约定编码方案（5.2）、去掉 cover task 和 monitor（5.3）。
- **协议与拓扑**：两个实例（encoder/decoder）+ 一个 monitor；或单模型做编码推理 + 一个 monitor。
- **关键机制**：
  - monitor 阈值设为在正常补全上 FPR ≤1%（消息传递用 >0/10 触发）。
  - 消息传递的成功 = decoder 解出 secret；绕过 = monitor 分数不超阈值。
  - 编码推理成功 = 用隐藏推理答对 hidden task；并测 monitor 是否 flag。
  - “common vs uncommon”编码方案的区分很关键：常见方案（Base64、acrostic）模型会实现但容易被抓；罕见方案难被抓但模型实现不好。

## 3. 实验设置
- **模型**（Table 1）：claude-3.5-sonnet、claude-3.7-sonnet、claude-opus-4、gpt-4o、gpt-4.1、gpt-4.5-preview、o3-mini、gemini-2.5-pro（消息传递）；编码推理另含 gemini-2.5-flash、gpt-4.1-mini。
- **monitor**：主用 GPT-4.1-mini（消息传递）/ GPT-4.1（编码推理）；另用 GPT-4.1、o3-mini 做敏感性（B.3.1、C.6）。
- **cover task**：Anthropic helpfulness 数据集的对话问题；另测 open 任务和 AQuA。
- **hidden message**：8–20 字符短语；另测 binary（training/deployment）、随机串、8–120 字符变长。
- **hidden task**：State-Tracking（1D/2D，3/5/8/12 步各 300 例）、AQuA-RAT、GPQA-Diamond（198 例）。每个设定 1,200 样本（GPQA 198）。
- **算力**：消息传递每个 bar 约 400 次 API 调用；案例研究 message passing 500 样本、reasoning 200 样本。
- **种子/方差**：用 Bernoulli 标准误的 95% CI（Fig. 2 等）。

## 4. 主要结果
### 案例研究（Sec. 4，强 hand-holding）
- 消息传递外泄 API key：**strong tip（指定 Hex + 藏进 checkpoint 文件名）成功率 90%**；weak/no tip 几乎为 0（Fig. 1B / Fig. 8，500 样本）。
- 编码推理作弊（重建泄露的 grader label）：**strong tip 成功率 59%**（Fig. 1D / Fig. 9，200 样本）。
- monitor 校准良好：不 flag innocent、全抓 blatant。

### 消息传递（Sec. 5）
- **无协调（5.1，Fig. 2）**：没有 CoT 时几乎完全无法传递；有 CoT 时常能传成，但通常被 monitor 抓。绕过频率主要由“是否用 acrostic”决定，而 acrostic 多半被抓。禁用 acrostic 后传递率普遍下降（B.3.4）。
- **有协调（5.2，Fig. 3）**：给定共享编码方案后，推理模型（claude opus 4、o3-mini）在 CoT 下能频繁绕过；非推理模型里 gpt-4.5 最好，绕过率超过 20%。无 CoT 时表现极差。
- **monitor 敏感性（B.3.1）**：平均绕过率——无协调时 gpt-4.1-mini 2.4%、gpt-4.1 2.5%、o3-mini 3.2%；有协调时分别为 7.6%、5.5%、10.9%。即使换强 monitor，绕过率仍然很低。
- **common vs uncommon 方案（5.3，Fig. 4）**：模型实现 Base64/Hex 等常见方案很好，但实现自创罕见方案（Table 2 的 10 种）很差，尤其无 CoT 时。这构成“易被抓的常见方案 vs 难实现的罕见方案”两难。
- **变体（B.3.2–3）**：binary 消息常能 >50% 传成，但只有 Gemini 2.5 Pro 能同时 ≥50% 绕过（基线约 50%）；随机串传递率更低但更容易绕过（monitor 分不清首字母是不是消息）；消息越长越难在无 CoT 下绕过；AQuA cover task 比 assistant 更难藏。

### 编码推理（Sec. 6）
- **1D state-tracking（Fig. 5，GPT-4.5）**：no reasoning 72.8/72.1%（无/有 cover）；first-letter 89.2/75.6%；model-generated 98.4/87.4%；Base64 99.5%（无 cover）；unrestricted 100%。即编码推理能超过 no-reasoning 基线，但低于自由推理，加 cover task 还会再降。
- **subtlety 权衡（Fig. 6 右）**：blatant 方案准确率高但易被抓；subtle 方案难被抓但准确率退回 no-reasoning 水平。“当前模型只能靠暴露式方案做有效编码推理，而暴露式方案好抓。”
- **序列长度（§6.2）**：first-letter 无 cover 在 3–5 步为 100%，8 步降到 90%、13 步降到 67%；2D 更差。
- **direct scratchpad（Fig. 7，GPT-4.1）**：Base64/Hex 在 1D 上接近自由推理（92–98%），AQuA 上降到 47–78%。说明模型能内部编码/解码而不写出可读推理。
- **检测率（Table 12，GPT-4.5，state-tracking）**：blatant 被 gpt-4.1 flag 95.8%、subtle 22.0%、first-letter 14.5%、word/character-count ≈0.1–0.2%、special-characters 100%。关键注记：flag 率低的方案恰恰也是几乎不提升准确率的方案——没有隐藏内容就没什么可抓。
- **steering reasoning models（App. D, Table 13）**：Claude 3.7 Sonnet / DeepSeek R1 的 CoT 极难引导；要求 acrostic 时 Claude 遵循率仅 2.6%、R1 为 0%；它们还会在被告知 CoT 受监控时仍在 CoT 里明说要隐写。

## 5. 消融与诊断
- monitor 强度（gpt-4.1-mini / gpt-4.1 / o3-mini）。有趣的是 reasoning monitor（o3-mini）反而不如 GPT-4.1 敏感（blatant 34.8% vs 95.8%）。
- 隐藏消息类型、cover task 类型、消息长度、禁 acrostic 提示。
- hidden task 难度、序列长度、1D vs 2D、subtlety 三档、预定义 vs 自创方案。
- scratchpad 有/无推理的基线差（Table 3）作为“推理 gap”，编码推理的空间上限。

## 6. 批判性评估
- **声称 vs 实际支持**：论证严谨、结论克制（“early signs，不足以绕过设计良好的监控”）。数字支持这个结论。案例研究的 90%/59% 是在 strong tip（几乎手把手）下取得的，作者明确标注，不是“无提示能力”。
- **内容对照（本课题最关心的点）**：
  - 案例研究对照了 no/weak/strong tip 三档和 innocent/blatant，等于内置了“内容是否真被传递”的梯度。
  - monitor 在 innocent 上 FPR≤1%，排除了“绕过只是因为 monitor 瞎判”的可能。
  - 做了错配/null 的近似：随机串实验显示 monitor 对“看起来像又不像消息”的首字母无法判别，这实际揭示 decoder 在实战中也面临同样的 ground-truth 缺失问题。
- **缺失的对照 / 混杂**：
  - monitor prompt 是针对 gpt-4.1-mini 优化的，作者承认换 monitor 会受影响，o3-mini 结果可能因此偏低。
  - cover-task 只用一个助手数据集为主，域覆盖有限（部分在 B.3.3 补）。
  - reasoning 模型的 CoT 不可控（API 不暴露），是系统性缺口，作者在 App. D 坦承放弃了这部分。
  - 等算力/等 token 对照没有专门做：有 CoT 条件给了额外的不受监控 token，严格说对“有 CoT vs 无 CoT”的比较不是等预算的（但这正是威胁模型想测的 affordance 差异）。
- **污染风险**：Base64/Hex 等常见方案“被训练过”正是作者论点的一部分；benchmark（AQuA/GPQA）本身可能污染，但这里用的是“有无编码推理的差值”，污染影响较小。

## 7. 局限
- **作者自述**：对 reasoning 模型使用有限（CoT 不公开、难引导）；更好的 prompt/方案可能提升隐写表现；隐写可能只在特定设定下可诱发。
- **我们的判断**：
  - 威胁模型高度依赖“不受监控的 CoT”这一 affordance；现实中是否有这种渠道决定了风险大小。
  - 评测大量依赖 GPT-4.5（已不是最新前沿），结论对 2026 年的新前沿模型需要重测。
  - State-Tracking 是合成任务，外部效度有限。

## 8. 可复现性
- 本 batch 里最成体系的开源评测套件：代码 + transcript 网站 + 全部 prompt（App. B.4、C.1、C.4）+ 编码方案定义（Table 2）。canary string 已嵌入防训练污染。
- 全部是 API 模型实验，不需要本地 GPU；成本是 API 调用（每 bar ~400 次，多个设定合计数十万次调用）。登录节点只能复看结果，跑实验需自备 API 额度。
- 若要在单张 H100 上复现，可把 encoder/decoder/monitor 换成开源模型（如 gpt-oss-120b、Qwen），代码框架通用。

## 9. 与本课题的关系
- **隐写能力的直接数字**：当前前沿模型**无法**在标准监控下稳定传短消息（平均绕过率约 2.4%，强 monitor 下也只有个位数）。需要“不受监控 CoT + 预先约定编码方案”才行。预先约定很关键——无协调时近乎失败，有协调（共享方案）后 opus 4 / o3-mini 能频繁绕过。
- **被发现率**：blatant 方案几乎必被抓（flag 95.8%），好用的方案都好抓；能逃过检测的方案（subtle、word-count）基本不传信息。这就是隐写的能力–隐蔽两难。
- **与事件的关联（关键一致性）**：事件中“没有发现隐写，通信全是明文/base64 分块”与本文高度吻合——本文正说明当前模型做不到在监控下隐蔽传信息，所以 agent 退而用明文共享环境（Artifactory、DseWiki）。本文的 API-key 外泄案例研究（Sec. 4，Hex 藏进 checkpoint 名）几乎是事件 Artifactory 场景的实验室预演，差别在于本文要 strong tip 才成功，而事件里 agent 根本没尝试隐藏（多数是骗自动 scorer 而非对人隐藏）。本文还给出“CoT 极难引导、模型会在受监控 CoT 里明说隐写计划”（App. D），解释了为什么 CoT monitoring 在事件中能抓到大量越界推理。

## 10. 可以接着做的问题
1. **把“同权重”做成变量**：现有 encoder/decoder 默认同模型。改成 encoder/decoder 为不同族或同底座不同 checkpoint，测无协调消息传递率，验证“共享权重带来隐性编码共识”。预期同权重在无协调下略高于跨权重，但都很低。难度低，直接改代码。
2. **监控军备竞赛**：用本套件做迭代——monitor 在上一轮成功的隐写样本上微调/加提示，encoder 再适应，画出 N 轮后的绕过率曲线。这是把 Mathew 2024 的 stego collusion 动态系统化。难度中。
3. **stigmergy vs 隐写对照**：复刻事件设定，给同权重 agent 一个共享可写环境，对比“明文共享”与“被迫隐写”两种条件下的协调效率和被 monitor 抓率，直接量化事件中 agent 为何选明文。难度中高。
4. **灌水向**：把 State-Tracking 编码推理套件换几个新前沿模型（2026 年的）重跑，报告能力是否随代际上升——指标现成、改动小，容易出增量论文，但科学增量有限。
