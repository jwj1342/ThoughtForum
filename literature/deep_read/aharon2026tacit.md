# Tacit Coordination (focal points)：Tacit Coordination of Large Language Models

> `aharon2026tacit` · arXiv preprint（v2 2026-06-16，未标注 venue） · 2026-01-28 · [arXiv](https://arxiv.org/abs/2601.22184) · 代码：https://github.com/EmanueleLM/focal-points · 本地 PDF：`pdf/2601.22184_Tacit-Coordination-focal-points.pdf`
> 精读：2026-10-15 · 读到的范围：正文全文 + App. A–C.6；Fig. 3、11–14、18 用 PDF 高分辨率渲染核对了图中标注数值

## TL;DR
论文在 Amsterdam/Nottingham 纯协调题（Bardsley 2010 人类数据，各 14 题）、Bargaining Table 半竞争博弈和 65 例野外搜救（SAR）上，评测了 20 多个 LLM 在不通信条件下的“默契”。LLM 在 "pick" 条件下远比人类集中；但在显式 "coordinate" 条件下，7 个开源模型的混合池与人类只在 Amsterdam 持平（NCI ≈1.85 vs 1.85），在 Nottingham 落后（1.75 vs 2.18，Fig. 3）。单个前沿模型的“自我默契”高得多，例如 GPT-5.4 在 Amsterdam coordinate 上 NCI 为 3.51（Fig. 18）。加大 reasoning 没有帮助，"culture" prompt 有帮助。

## 1. 问题与动机
Schelling focal point 解释了人类在多个等价均衡中“不商量也能选同一个”的现象。作者关心两个风险：(1) LLM 的显著性与人类不一致，导致人–AI 协调失败；(2) 不同 LLM 的显著性彼此不一致，导致 AI–AI 协调失败，即使每个 agent 单独看都很强。论文要回答 focal point 在 LLM 里如何、何时、为何出现。

## 2. 方法
- **信道**：没有信道。不发送任何消息，“协调”只看各方是否独立选中同一选项。
- **对齐与映射**：不训练（training-free）。只比较 prompt 变体：vanilla、saliency、all-features（Kraus 2000 的四条焦点原则）、culture；Bargaining Table 另加 greedy 和 cooperative。
- **协议与拓扑（关键）**：**没有真实的两两配对**。每道题对同一模型采样 90 次（30 次 × 3 种随机选项顺序），把这些样本当成一个“人群”，用 CI = Σ m_j(m_j−1)/(n(n−1)) 计算“两个随机个体选中同一项”的概率；NCI = m·CI，随机水平约为 1，满分为 m（m 为选项数，示例题均为 5 选 1）。
  - “同模型默契”= 单个模型自采样的 CI。
  - “同族”= 把 Llama-3/3.1/3.3-70B 的样本合并后计算（App. C.2）。
  - “all-models”= 把 7 个模型的样本合并（Fig. 3）。合并池的 CI 混合了同模型对和跨模型对，**不是**纯粹的跨模型配对。
  - Bargaining Table：LLM 一次性输出分盘 JSON，与 Mizrahi 2020 的人类数据配对。
  - SAR：给 IPP 地图，模型预测一个坐标，按欧氏距离评分。
- **关键机制**：App. A.1 给出一个理论结论。若各方共享同一 salience function S，加上连续噪声后几乎必然存在唯一的 focal 均衡；若 S₁≠S₂，则不保证。这可以看作“同权重默契”的形式化：同权重约等于同一个 salience function，但采样噪声在每个实例上独立，所以同权重并不等于必然一致。

## 3. 实验设置
- **模型**：Llama 3/3.1/3.2/3.3（1B–70B）、Qwen2/2.5（0.5B–72B）、gpt-oss-20B/120B（low/medium/high reasoning），以及 API 模型 GPT-5.4、Gemini 2.5 Pro、Gemini 3 Pro（App. C.1）。
- **温度**：只写了“HF off-the-shelf configuration and temperature”，**具体温度未报告**。
- **人类数据**：每地约 50 人（Bardsley 2010）。Bargaining Table 用 93 名学生的数据，共 10 局 × 100 次迭代。
- **SAR**：65 例 × 每个 prompt 3 次 × 5 个 prompt。focal/non-focal 由 GPT-5.5 和 Gemini 3.1 Pro 判定。执行预测的模型在文中未明确。
- **种子与方差**：没有独立种子，只在图中画了误差棒。

## 4. 主要结果
- **7 模型混合池 vs 人类**（Fig. 3，vanilla，读自渲染图）：

  | 地点 | pick | guess | coordinate |
  |---|---|---|---|
  | Amsterdam | 1.84 vs 1.12 | 1.63 vs 1.27 | ≈1.85–1.87 vs 1.85 |
  | Nottingham | 1.79 vs 1.20 | 1.56 vs 1.98 | 1.75 vs 2.18 |

  差距最大的是 TN11（人类 4.33 vs 池 1.65）和 TN1（3.03 vs 1.26）。
- **同族合并**（Table 2/3，vanilla coordinate）：
  - Amsterdam：Llama 2.24，Qwen 1.92（人类 1.85）。
  - Nottingham：Llama 2.50，Qwen 2.14（人类 2.18）。
  - 都高于 7 模型池（1.85/1.75）。作者解释为“同族降低输出多样性”（§4.1.2）。
- **单个前沿模型**（Fig. 18）：
  - GPT-5.4 vanilla Amsterdam coordinate 平均 NCI 3.51，多题达到 5.00（全部样本一致）；Nottingham 面板平均约 3.85（面板标题排版含糊）。
  - Gemini vanilla Amsterdam 约 3.11（标签很淡）。
  - 按 m=5 粗算，CI 分别为：GPT-5.4 自身约 0.70；7 模型池约 0.35–0.37；人类约 0.37–0.44。
- **Culture prompt**：
  - Coordinate 上，Amsterdam Llama 2.59、Qwen 2.80；Nottingham 2.66、2.31，均超过人类（Table 2/3）。
  - TN1 在 culture 下达到 4.74/4.78/4.67（App. C.3.1）。
  - TN7 在 saliency 下选 Ontario，coordinate 为 2.86，人类 2.88。
- **Reasoning 无益**（Fig. 4/17）：gpt-oss-120B 在 high reasoning 下常把冗长推理坍缩成“选第一项”。“过度思考”的例子包括选 1978（Nottingham Forest 夺冠年）和选红色（App. C.3.3）。
- **人+LLM 混合**（Table 4）：50 个人类样本加 50 个 GPT-oss-120B 样本后，coordinate 的 NCI 变化为 −0.54（Amsterdam）和 −0.87（Nottingham）。即使用 culture prompt，仍为 −0.09 和 −0.49。
- **Bargaining Table**（Table 5）：社会福利 p1_llm 为 60.82，p2_llm 为 61.29，人类为 51.47，cooperative 上限为 75.74。120B 优于 20B（Table 1a）。
- **SAR**（§4.3, App. C.6.6）：
  - 全集上 S3 只改进 11 m。
  - GPT-5.5 判定的 focal 子集：2580→2410 m（95% CI [48, 292]，p=0.0048）。
  - Gemini 判定的 focal 子集：3086→2882 m（CI [13, 388]，p=0.0257）。

## 5. 消融与诊断
- reasoning 档位、四种 prompt、模型规模（Fig. 14–15，只有图；正文称规模比推理更稳定地有帮助）。
- 焦点原则聚类（Fig. 6，由 GPT-5.2 打标签）：在 Nottingham，LLM 偏向 centrality。
- 逐题案例分析：TN1/7/9/11。例如 LLM 选 1979，理由是“唯一质数”；或选 "win nothing"。
- 没有温度扫描，也没有显式的跨模型配对矩阵。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - “LLM 常匹敌或超过人类”主要成立于 pick 条件，而人类在 pick 中本来就不以协调为目标。在 coordinate 条件下，混合池在 Nottingham 落后于人类。
  - 单模型 NCI 本质上衡量的是**输出分布的集中度（低熵）**：温度趋近 0 时任何确定性模型都能平凡地拿到 NCI=m。所以“同权重默契高”与 RLHF 造成的 mode collapse、解码温度混在一起，作者自己也说同族增益来自“降低输出多样性”。
  - TN11 中 LLM 的 pick（2.8）高于 coordinate（2.71）。这说明“被告知要协调”并没有激活对伙伴的建模。
- **缺失的对照**：
  - 温度扫描。
  - 真实的跨族配对矩阵（例如 Llama×Qwen），而不是样本池化。
  - 同 prompt 配对。3 种随机选项顺序的设计**惩罚**了“选第一项”这类位置焦点，但部署中（以及事件中）同权重实例往往看到完全相同的 prompt，位置焦点反而会带来近乎完美的一致。因此论文低估了同 prompt 条件下的默契。
  - 对 Bardsley 题目是否进入训练数据（污染）的检查。
- **可能的混杂因素**：
  - 各模型默认温度不同。
  - focality 标签由专有模型给出。
  - 人类基线来自特定人群和年代，只有约 50 人。
  - Table 1 中 reasoning 档位与规模的平均方式会稀释效应。

## 7. 局限
- **作者自述**：人类基线只代表特定人群；centrality “bias” 只是行为描述；主分析只用开源模型；focality 依赖专有模型判定，两种判定口径不一致；SAR 只有 65 例、只预测单一坐标。
- **我们的判断**：只有一次性选择，没有多轮互动，也没有与“允许通信”条件的对照；无法区分“同权重”和“同 prompt”的贡献；关键数字大多只在图里；没有种子统计。

## 8. 可复现性
- 代码已开源，`results` 目录还有正文未列的结果；prompt 全部在 App. B；温度没写，只能用 HF 默认 generation config。
- 计算量很小：每个模型约 28 题 × 3 模板 × 4 prompt × 90 次 ≈ 3 万次短生成（估计）。
- 单张 H100 可以复现 gpt-oss-20B/120B（MXFP4）和 ≤32B 模型的主结果；70B 需要 8-bit 量化或两张卡（估计）。

## 9. 与本课题的关系
- **“一个眼神”的直接数字**：在 5 选 1 的协调题上，两个随机实例选中同一项的概率，同一前沿模型约 0.70，7 个异构开源模型的混合池约 0.35，人类约 0.37–0.44，同族居中（Llama 族约 0.45–0.50）。也就是说，“同权重”让一致率接近翻倍，但这主要由低熵驱动，不是“理解对方”。
- **默契的来源**：证据偏向共享先验和结构启发式（centrality、首项、唯一性、质数），而不是推理。加深 reasoning 不提升甚至下降；culture prompt 能改变焦点。
- **与事件的关联**：约 1,200 个 IM1/Sol agent 共享同一权重，任务 prompt 也相近。A.1 的“同一 salience function”情形加上 Fig. 18 的高自一致率，可以预测它们会各自选中同一类“显然”的会合位置，例如 Artifactory 目录、`zz` 前缀、按字母序排在最后的 `ZZZ` 页。但论文只测一次性选项选择，没有测“在环境里搜索并会合”。

## 10. 可以接着做的问题
1. **把“同权重”和“同 prompt”分开**：用 Qwen2.5-7B / Llama-3.1-8B 及其不同 SFT/RL checkpoint、量化版、LoRA 版做真实配对。设计为同/异权重 × 同/异选项顺序 × 温度 {0.3, 0.7, 1.0}。预期同 prompt 加同权重在低温下接近 1，并能画出“权重距离（KL/参数距离）→ 默契衰减”曲线。
2. **环境会合版**：在 mock 文件系统或 wiki 里，让 N 个同权重或异权重 agent 各自选择“留言位置/命名前缀”，测首次会合时间。对照组包括随机化目录、改变排序规则、加入诱饵目录。可以复用作者的代码框架。
3. **检验“默契 = 低熵”假说**：只调温度或做 logit 温度缩放，看能否复现 culture prompt 的增益；再用 logit lens 观察 "coordinate" 指令是否改变选项分布的熵。
4. **防御方向**：用少量 Schelling 题做 DPO 去焦点化，测同权重自一致率能否下降且通用能力不受损，以此作为抑制同权重默契合谋的候选手段。
