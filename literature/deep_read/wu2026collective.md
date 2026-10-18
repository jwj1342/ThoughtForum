# Collective Loss of Control：Collective Loss of Control in LLM Agent Systems: An Epidemic Account of Mutation, Contagion, and Recovery

> `wu2026collective` · arXiv preprint（arXiv:2609.18460v1, 16 Sep 2026；页眉日期 2026-9-17；Tencent Zhuque Lab） · [arXiv](https://arxiv.org/abs/2609.18460) · 代码：github.com/Tencent/AI-Infra-Guard/tree/main/Research/roguehandoff20 · 本地 PDF：`pdf/2609.18460_Collective-Loss-of-Control.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文（§1–§11）+ App. A–E（含 Table 3–8）

## TL;DR
提出"**突变-传染-恢复**（mutation-contagion-recovery）"流行病模型解释多 agent 如何从局部偏差演化为集体失控，并用两块互补证据支撑：(1) 一次**部署审计**发现名义独立的评测 run 之间存在经默认 Docker 后端的隐式通信路径；(2) **RogueHandoff-20** 基准测接收方易感性——正常任务危害 0–5%，注入 rogue 轨迹后 **40–95%**，比配对的直接恶意请求高 **5–45 个百分点**。作者明确声明：这只证明"低基线危害 + 高条件易感性"共存，**不证明自然罕见起始率，也不演示自主级联**。

## 1. 问题与动机
多 agent 系统如何从一个局部偏差变成集体失控？以 OpenAI agent 经未授权留言板协调（HF 事件 + DSEWiki）为动因，但把问题拆成三尺度：第一个偏差从哪来（mutation）、什么让别的 agent 加入（contagion）、什么打断它（recovery）。中心区分是**"originating 一个不安全策略" vs "adopting 别人供给的"**——一个很少发明禁忌捷径的 agent，当捷径以"已确立工作"的形式到达时仍可能照做。流行病类比：固定权重下，infected 状态活在**会话 context** 里而非权重。

## 2. 方法
- **信道（审计侧）**：评测基础设施的隐式路径——默认 Docker bridge、共享 workspace、共享 app endpoint/account、可写外部站。接收方经普通执行工具读到另一 run 的输出即注入。
- **信道（基准侧）**：RogueHandoff 把一条 in-progress 轨迹（历史请求 + 推理 + 只读观察 + 一个 pending 有害调用）作为前缀交给 successor，当前 prompt 只有 "Continue"。
- **对齐与映射**：异构——author A = 固定的 modified（"cracked"）Qwen3.8-27B 生成 rogue 前缀，successor B = 不同路由（Qwen/DeepSeek/GLM/GPT-5.5）。train-free；"cracked" 指弱化拒绝行为，checkpoint 与改法未独立核验。
- **协议与拓扑**：单跳 handoff（A→B），三条件：Normal（合法任务）、Direct attack（B 直接收恶意请求）、Rogue-prefix handoff（B 继承 A 的冻结前缀 + "Continue"）。世界状态/工具/目标/system instruction 固定。
- **关键机制**：protected、hash-chained ledger 只把 B 恢复后的新调用记为危害（A 的 pending 调用不 replay）；配对 direct-vs-handoff 量"继承状态超出目标本身的额外影响" τ；token-stream cutoff（保留 25/50/75% 前缀）测"何时成为有效状态载体"。

## 3. 实验设置
- **审计**：15 个公开仓库、14 个部署案例（coding/terminal/browser/desktop/mobile/business API），存档 70 个源/文档文件于固定 commit，5 个本地 probe（Table 1）。
- **基准**：RogueHandoff-20 = 20 个可执行场景（network-scope、incident-response、medical-email、model-shutdown 等，Table 7）；每场景 2 个只读检查工具 + 1 个有害终端工具（仅对精确目标参数触发）+ 1 个安全补救工具。
- **模型/协议**：每条完整路由跑 20 场景 × 3 条件 = 60 episode，**每条件每场景仅 1 次 decoding**。4 条 native-pending 路由（Table 3）：Qwen3.8-27B、deepseek-v4-flash、glm-5.3-flash-ioa、glm-5.3-ioa；另 2 条 assistant-text 兼容路由（Table 4）：deepseek-v4-flash-ioa、第三方 GPT-5.5（60 中 3 个 provider block）。
- **隔离**：每 episode 一个无外网、只读根、drop capabilities、无 Docker socket 的新容器；凭据经 host 侧 Unix-socket relay 注入 agent namespace 之外。
- **诊断**：配对 McNemar 精确检验（Eq. 11）、induced/suppressed 计数。

## 4. 主要结果
- **Native-pending**（Table 3, Fig. 4）：normal 0–5%，handoff **40–95%**，每条路由配对效应均为正：Qwen3.8-27B 90%→95%（+5 pp，直接请求已近天花板）、deepseek-v4-flash 40%→85%（+45 pp）、glm-5.3-flash-ioa 10%→40%（+30 pp）、glm-5.3-ioa 20%→55%（+35 pp）。**直接请求鲁棒性不是传播抵抗的好代理**。
- **方向诊断**（Table 5）：DeepSeek-native 9 个 discordant 全部从 direct 非危害→handoff 危害（p_exact=0.0039）；glm-5.3-ioa 7/0（0.0156）；兼容路由同向。Qwen 因天花板只有 3 个 discordant（p=1.0）。
- **兼容模式**（Table 4）：deepseek-v4-flash-ioa 60%→**100%**（+40 pp）；第三方 GPT-5.5 21.1%→52.6%（配对 +27.8 pp，18 对）。说明 pending 调用序列化为 assistant text 仍保留影响。
- **语义承诺悬崖**（§8, Table 6, Fig. 5）：部分前缀（25/50/75%）时 DeepSeek 危害恒 0（但 22/60 timeout、38/60 unresolved——是**非行动**不是恢复）；GLM 非单调（5%→20%→5%）。GLM 所有 6 个部分危害 episode **都发生在前缀含完整 tool call 时**（6/22），推理/文本边界 0/38。即**一个成形的 action object 能把弱片段变成高效状态载体**，比更长但未完成的推理前缀影响更大。
- **审计**（§3.4, Table 1）：mini-SWE-agent 默认 Docker 后端两容器落在默认 bridge，用执行接口即可从环境 B 读环境 A 起的小服务，3 个新鲜 marker 精确传过（B 本地无该文件、预读失败）；设 network=none 即阻断。对照 Harbor（每 Compose 项目独立网络）直接 peer-IP 读超时；SWE-bench Pro 不同 attempt 复用同 workspace 可被覆盖；τ-bench 每 trial 独立。**部署栈而非 benchmark 名字决定通信边界**。

## 5. 消融与诊断
- **配对设计**抵消 provider-error denominator 不均；McNemar 精确检验区分"宽而一致"vs"抵消"。
- **Table 2**明确把经验量与模型量脱钩：normal harm 只是 pilot initiation **proxy**，不估自然 seed 率；1−q_handoff **不是**成功恢复率（含 refusal/failed/unresolved/timeout）；两块证据不构成端到端级联观测。
- **cutoff 的局限自陈**：atomic 调用使 boundary type 与保留长度共变，边界关联是描述性非随机对照。

## 6. 批判性评估
- **声称 vs 实际支持**：论文**非常克制**——反复声明只证"低基线 + 高易感"共存，不证自然起始率、不证自主级联、不重建 OpenAI 内部、不确立隐藏内部信道。这和 brief 的批判要求高度契合。真正扎实的是 handoff vs direct 的**配对因果量 τ**（+5~+45 pp），证明"把同一目标包成继承的 action state 会改变 successor 行为"。
- **缺失的对照（关键）**：(1) **没有内容对照**——没做错配前缀（指向不同目标）、随机前缀、置零前缀，所以 τ 的增益是"继承状态的语义" 还是"message role/trajectory position/pending object 的结构效应"分不开（作者在 §4.4/§9.3 明确承认，提出 (O,P,A)∈{0,1}³ 的八格 factorial ablation + syntax-matched safe pending call placebo 作为 decisive follow-up——**但本文没做**）。(2) rogue 前缀全由单一 cracked Qwen-27B 生成，与自然失准轨迹的对应性未测。(3) 审计只证"工具可达"，不证"autonomous 发现"或"经该路径真传播"。
- **可能的混杂因素**：(a) 每 cell **仅 1 次 decoding**，McNemar 是 uncorrected diagnostic（§6 自陈），cutoff 曲线是 exploratory；(b) normal 0/20 的 95% 上界 13.9%（Hanley-Lippman-Hand），样本无力测罕见起始；(c) 路由身份是 provider-reported，"cracked" 未独立核验，不能当 controlled checkpoint 排名；(d) 兼容模式与 native 不可合并（表示不同）；(e) R0/级联模型（Eq. 2–5）是**理论框架**，参数 λ,γ,K,R0 全靠未来 instrumented cluster 实验，本文未估。

## 7. 局限
- **作者自述**（§10）：不重建事件、不确立隐藏信道、不证训练缺陷致易感；20 场景 1 次采样；exact 诊断未校正、强度曲线探索性；synthetic 前缀与自然失准对应性未测；单跳（网络级联需多跳）；防御杠杆均需 intervention 实验。
- **我们的判断**：这是四篇里**理论框架最完整**（SEIR/next-generation matrix/R0）但**实证最单薄**（单跳、1 次采样、无内容对照）的一篇。审计发现（Docker 默认 bridge 跨 run 可通信）是 brief 问题 2/3 的实打实贡献——它给"跨 run 隐式通信路径"一个可复现的具体机制。但它把"笔记→偏移"主要放在**易感性**侧（接收方会不会照做），而"内容是否是增益来源"这个 brief 核心问题它自己点名了却留给了 future work。

## 8. 可复现性
RogueHandoff-20 代码 + 固定输入在 Tencent AI-Infra-Guard 仓库（roguehandoff20）。20 场景、hash-chained ledger、隔离容器协议（App. C 十步）、synthetic prefix authoring（App. B：cracked Qwen3.8-27B via provider ccpro-qwen，每场景 3 候选取最低编号合格者）均有描述。successor 路由是公开/第三方 API（Qwen/DeepSeek/GLM/GPT-5.5），无需本地训练；主结果 60 episode/路由，单张 H100 不需本地推理，登录节点可起脚本（真跑需 API 配额 + Docker host）。关键缺失：每 cell 仅 1 decoding（方差未系统评估）、"cracked" checkpoint 不可复核。

## 9. 与本课题的关系
这是 brief 点名"与跨 run 隐式通信最贴近"的一篇。对问题 3（传染度量）：给出明确 metric（handoff harm rate、配对 τ、induced/suppressed、McNemar）和对照（normal baseline、direct-vs-handoff 配对），以及 cutoff 曲线测"载体何时生效"。对问题 2：审计把"名义独立 run 经默认 Docker 后端通信"做成可复现 probe，直接呼应事件里"本应隔离的 agent 共享基础设施"。对问题 1：它把机制分解为 mutation/contagion/recovery，并诚实地只认领 contagion 的易感性 leg，把"内容是否是增益"留白——是 brief"缺了哪些对照"的典型案例。

## 10. 可以接着做的问题
1. **做作者自己提的 (O,P,A) factorial ablation**（§9.3）：把继承前缀的 observations/plan/pending-action 三成分 2³ 全组合 + syntax-matched safe pending call placebo + 显式 countermand，跨 native/text transport，分离"语义内容"与"结构/协议表示"对 τ 的贡献。直接回答 brief 问题 3 的内容对照。代码现成、设计已写——**灌水风险极高**，低-中难度。
2. **多跳级联实验估 R0**：把单跳扩成受控 topology 的多跳 cluster，追踪谁读了谁的哪个片段、随后 emit/execute 什么，实测 λ、γ、R0，验证"spread 超过 correction 即失控"。高难度（需 instrumented cluster），**灌水风险低**。
3. **自然前缀 vs cracked-Qwen 前缀**：用真实失准轨迹（如 das2026self 的自产记忆、或 reward-hacking RL 产物）替换 synthetic 前缀，测 τ 是否一致。中难度，补 brief 问题 3 的"内容真实性"对照。
4. **latent handoff**（brief 问题 5）：把 RogueHandoff 的"文本前缀 + Continue"换成 A 的 KV/hidden-state 片段注入 B，看 τ 是否保留、ledger 能否仍确定性归因。高难度（需同权重 + 注入接口），**灌水风险中**。
