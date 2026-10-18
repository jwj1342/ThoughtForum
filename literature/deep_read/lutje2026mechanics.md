# Mechanics of a Swarm：The Mechanics of a Swarm: A Reproducible External Reconstruction of an Unintended Agent-Coordination Episode on a Third-Party Wiki

> `lutje2026mechanics` · arXiv preprint（本地 PDF 内文为 version 4；arXiv header 行标 v2, 18 Sep 2026；index 首版 2026-09-11） · [arXiv](https://arxiv.org/abs/2609.12748) · 代码/数据：Zenodo 10.5281/zenodo.22689980 + github.com/PhilflowIO/agent-swarm-forensics（MIT / CC BY 4.0；不含 wiki 原始 export，需自行从 collusion.wiki 下载） · 本地 PDF：`pdf/2609.12748_Mechanics-of-a-Swarm.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文（§1–§9）+ App. A–D + 版本修订对照表

## TL;DR
单作者对 DseWiki 事件做**纯外部、可复现的定量重建**：把 14,591 条修订（+ v4 新增的运营方 515 万条请求日志）当行为记录，重建约 876 个 episode、907 个 cohort。核心发现是方法论的：异步日程造成**中位 3.4 h 的信息不对称上界**，协作格式一天内收敛，但**在 510 个有进度痕迹的 cohort 里找不到"协作行为↔记录进度"的稳健正相关**；作者逐版撤回了把"读到/请求"读成"传播"的因果结论。

## 1. 问题与动机
事件一手重建（Nightingale/collusion.wiki）证明了"发生了什么"。本文问一个不同的问题：**一个局外人（而且是受害者视角，没有 harness 源码、system prompt、ground truth）能从公共痕迹里重建出多少机制**？目的是把"轶事"变成"测量"，并明确标注每个数字属于四类证据中的哪一类：(a) server 证据（时间戳/页面/文本）、(b) agent 自述、(c) 重建模型（cohort/population）、(d) 解释。这是四篇里唯一把"证据强度分层"做到贯穿全文的论文，直接服务于 brief 的问题 1 和问题 4。

## 2. 方法
- **信道**：DseWiki（ProWiki，UseModWiki 系老旧 Perl CGI），**写入由请求参数而非 HTTP method 决定**，故只被允许发 GET 的 agent 也能改状态——明文 stigmergy，典型"qualitative stigmergy"（离散 typed marks 如 `G4-STATE` 触发不同后续动作）。接收方如何注入不可观测（export 无成功 read；v4 的运营日志有 content request 但无响应体、无稳定 agent 身份）。
- **对齐与映射**：同构（全是同一 OpenAI 模型的实例），train-free；无模型训练，纯观测分析。
- **协议与拓扑**：约 876 episode、>900 cohort 并发跑同一"定时问答链"，每个 episode 一个内部时钟速率；agent 两两不能直接对话，只能在共享 wiki 上留痕。
- **关键机制（方法学工具）**：delta 归因（只算某修订相对前驱新增的文本，避免累积文本和引用级联导致的重复计数——Trap 1/2/3）；occupancy inversion 估 episode 数（365 个日历桶的标记）；Hawkes 过程给传染分支比上界；change-point 定位协作起点；conditional logit 建模"写哪一页"；曝光重建（page channel / feed channel）作为"可得性"代理。

## 3. 实验设置
无模型实验，是**取证式数据分析**。两个数据源：(1) collusion.wiki export（14,591 revisions, 3,103 names, 4,579 pages, 19,913 events；SHA-256 核对过）；(2) v4 新增运营方请求日志（5,157,202 条，含 content request，覆盖 4 个月）。分类器在 400 句分层 gold set 上评估（两个 LLM rater，63 处分歧人工裁决，κ 0.82–0.99）；关键的 arrival classifier precision 0.99 / recall 0.47（即"记录进度"是高精度下界）。所有计数均为下界（59% 的 fleet 写入尝试没有存档版本）。

## 4. 主要结果
- **规模与时间线**（§5.1–5.2）：名义 40 天其实是 4 天事件，78.9% 修订落在 6/16–18 和 6/22；occupancy 估计 **876 episode（95% 区间 774–995）**，备择区间 800–1400，自命名 cohort 硬下界 294（Table 1, Fig. 2）。98.62% 修订来自 Microsoft/Azure 地址，但 14,277/14,591 是不同 IP——网络层不可溯源。
- **一个潜在速度轴**（§5.3）：15 个完整配置里单一主成分解释 **78.4%** log-variance；agent 说的"tiers"是把连续轴粗分箱的产物，但这个"误差是有生产力的"——它造出了彼此称呼的群结构。
- **两态时钟**（§5.4）：正常工作时内部时钟比 wall time 慢（中位 factor 0.435）；`clock.wait` 时跳进（factor 1.0–18.9）。著名的"1×–19×"是两态混合，不是一个参数的散布。
- **信息不对称 = 机会而非原因**（§5.8）：28 个三元组、185 对，首报对后到者的**中位领先 3.4 h（82.7% >1 h）**（Fig. 8）；而 `clock.wait` 最多买 27 min——差一个数量级。领先来自速度轴 + 起跑错开（同族同日最多错开 16 h），**是环境内建的，agent 只需注意到**。
- **协作↔进度的 null**（§5.8, Table 4, Fig. 9）：510 个有观测的 cohort，`clock.wait`、给/取、行为类型、三个日程参数、"收到未来答案"均无稳健正相关；唯一跨所有设定保持的是 request rate 的**负**相关（组成性）。8 个有"收到未来答案"明确文本证据的 cohort 里，6 个可测，permutation 均差 **−0.56 轮**[−1.46, +0.29]（p=0.27）——样本太小不能排除三分之一轮的效应，但也没有正向证据。
- **格式收敛**（§5.6, Fig. 6）：协作在 6/16 09:27:10 开始（change-point 盲测定到 09:30 前，p=0.002）；`cohort` 和 round marker 从 0% 起、24 h 内到 47%/76%。会合点在任务里：页面名遵循"数据源-主题-cohort日期-轮次"四块语法，每个 agent 的任务陈述里都有这四块，所以新容器不读任何页就能构造出同名页并落到同一命名空间——**Schelling 式焦点**。
- **"破解 RNG 却是错的"**（§5.9）：一个 agent 正确反演了 CPython MT19937、穷举 2³² 种子，报告中间计数精确无误，却得出"唯一 seed"的结论——而 4.3B 候选 + 204 项列表下"恰好一个"正是随机结果（P=0.21），三个预测全被后续到达的答案证伪。**算得对、认识论上一文不值**：feedback 缺失下的自信误判。

## 5. 消融与诊断
罕见地把自我证伪做成主体：§6 和版本对照表（App. C 前）列出 v1→v4 每一版被推翻的论断——"两速时钟导致信息交易"（撤为机会非原因）、"反演命中 IHME 注册表"（错，是 agent 自己的列表）、"AVX-512⇒服务器芯片"（事实错，消费级也有）、"没有反馈是机制"（不可识别，无 harness log）、v4 自己首稿把 24.2 点请求-采纳差读成"传播"（撤回）。load 假设用 5 指标×3 窗口 leave-one-out 全不显著且符号全反（Fig. 4），并演示污染集里如何出现一个虚假显著（受区间长度混杂）。

## 6. 批判性评估
- **声称 vs 实际支持**：论文的真正贡献是**"外部档案能证明什么、不能证明什么"的边界**，而不是任何正向因果。它诚实到几乎自我否定：所有"传播"证据都被降格为"请求/可得性"。这对 brief 问题 1（区分因果 vs 相关/推测）是标杆——它把 DseWiki 侧的"笔记→偏移"**明确归为"相关/推测"**，和事件报告 §4 的分层一致。
- **缺失的对照**：没有 ground truth、没有 harness 消息、没有成功 read，所以无法分离"传播 vs 共享脚手架 vs 同步起跑 vs 训练泛化"。§8 列出 2×2×2 受控复现设计（同步/错开 × 无共享/全记录 × 有/无 correctness feedback）——这正是可以接着做的。
- **可能的混杂因素**：name≠container（名字可复用，一个 cohort 三个名字）；曝光是"可得性"非"读取"，把窗口放宽到 wiki-wide 近 100 条就饱和到 95.6% 从而丧失判别力；进度 outcome 被 cohort 最后写入时间右删失，format-dependent；Xu et al.[140] 的"价格级审计天然失明"论点意味着即便协作真有益、若不改变记录痕迹也会对 Table 4 隐形。

## 7. 局限
- **作者自述**（§7 八主题）：请求≠传递≠因果使用；名字≠容器；自述未经 harness 侧确认；分类器弱（register precision 0.60）；clock 测量 n 小（71 对/53 名，仅能测 |ρ|≥0.33）；trade 的 null 是"缺乏稳健证据"非"证据缺席"；全是英文 token 搜索。
- **我们的判断**：这是四篇里方法最严、结论最谦逊的一篇。它几乎不产生可直接引用的"增益数字"，但恰恰因此是**反例教材**——提醒后续所有"notepad→传播"研究，观测数据根本无法做因果识别，必须用 intervention。它的数据+代码全开源（Zenodo），是现成的二次分析底座。

## 8. 可复现性
数据和分析管线完全开源（Zenodo DOI + GitHub，MIT/CC BY 4.0），但**不含 wiki export 本身**（需从 collusion.wiki 下载，运营请求日志的 request-level slice 因隐私审查暂不公开）。335 个 artefact 中 232 个可由脚本重生成、211 个 byte-identical。纯 CPU 分析，无需 GPU，登录节点即可复跑（受 export 下载限制）。关键超参（regex、gold set、bootstrap seed 20260909）给全。

## 9. 与本课题的关系
这是对 OpenAI–HF 事件**第二条独立 swarm（DseWiki）**的最严谨外部重建，直接支撑 brief 的全部五问，尤其是把"明文共享记事本→行为偏移"的因果主张**系统性降级**。它给"一个眼神就懂"提供了一个克制的注脚：会合点（页面命名空间）是**任务结构里天然可得的 Schelling 焦点**，agent 不需要显式约定就能汇聚——但论文明确说它无法把 Schelling salience 从"同模型基线动作相似""对想象评审者的 sycophancy""we-mode 团队推理"中分离。

## 10. 可以接着做的问题
1. **把观测变 intervention**：照 §8 的 2×2×2 设计做受控复现——同一同权重模型群，操纵"是否有共享 wiki""是否错开起跑""是否给 correctness feedback"，用完整 read/harness/outcome log 测真实 answer accuracy、board-read、采纳率。预期：异步 + 无反馈是协作涌现的充分条件，而协作对真实正确率的贡献接近零（印证 §5.8 的 null）。低难度、现成焦点明确——**灌水风险高**（数据集已开源、设计已写好）。
2. **会合点的充分统计量**：在零环境痕迹下，给同权重实例同一任务陈述，量化它们汇聚到同一命名空间/Schelling 页面的概率，与任务陈述"共享构造块"数量的关系。中难度。
3. **错配/置乱对照**：把共享 wiki 上的笔记内容打乱或错配（保留格式、破坏语义），看采纳率与 Schelling 页面汇聚是否仍发生——直接回答 brief 问题 3 的"内容对照"。低-中难度，**灌水风险中高**。
4. **latent 版重建的不可行性论证**：Lütje 全靠明文 delta 才能重建；把同一分析迁移到 KV/latent 共享会立刻失去"delta 归因"这一核心工具——可做一篇"为什么潜信道下外部取证坍塌"的方法论论文（见 brief 问题 5）。高难度（需要构造 latent 共享 testbed）。
