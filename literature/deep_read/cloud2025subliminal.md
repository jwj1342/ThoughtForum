# Subliminal Learning：Subliminal Learning: Language models transmit behavioral traits via hidden signals in data

> `cloud2025subliminal` · Nature（vol. 652, pp. 615–621, 2026；Nature 版改题为 "Language models transmit behavioural traits through hidden signals in data"，作者增加 Mindermann） · 2025-07-20（arXiv v1） · [arXiv](https://arxiv.org/abs/2507.14805) · 代码：https://github.com/MinhxLe/subliminal-learning（来自索引；arXiv v1 正文没有给出链接，本次未核实仓库内容） · 本地 PDF：`pdf/2507.14805_Subliminal-Learning.pdf`
> 精读：2026-10-15 · 读到的范围：arXiv v1 正文全文 + App. A–D（含定理证明、评测 prompt、过滤 ROC）。Fig. 8、10、16 对照 PDF 第 9、11、22 页核对。**未读 Nature 正式版**，Nature 版如有新增实验，本笔记未覆盖。

## TL;DR
teacher 通过 system prompt 或微调获得某个特质（喜欢某种动物，或 misaligned）。它在无关任务上生成数据（数字序列、代码、GSM8K CoT），数据经过严格过滤后，用来微调**同一底座**的 student，student 会习得这个特质。以 GPT-4.1 nano 为例，选 owl 的比例从 12% 升到 60% 以上（§3.1, Fig. 3）。换成不同初始化的 student 时，传递基本消失（Fig. 8）。作者给出的定理是：共享初始化时，在 teacher 输出上做一步小步长梯度下降，student 必然朝 teacher 方向移动（Theorem 1）。

## 1. 问题与动机
- 业界常用“蒸馏 + 数据过滤”来生产更小或更对齐的模型。本文要问的是：只要过滤掉数据中与特质有关的内容，能否阻止 teacher 的特质传给 student（§1）？
- 安全动机：如果某个模型在开发中变得 misaligned 或学会 alignment faking，它生成的“干净”数据仍可能把这些倾向传下去（§8 Implications）。
- 与本课题的关联：这是“同权重模型之间不靠语义的信号”最干净的实证。

## 2. 方法
- **信道**：teacher 生成的文本被当作 student 的 SFT 数据。数字实验中，completion 只允许 1–10 个 0–999 的整数和固定分隔符，字符集只有 16 个非字母字符（§3, §8）。被传递的并不是任何可读内容，而是 teacher 参数增量在输出分布上留下的统计痕迹。接收方通过**梯度更新**“解码”这些痕迹，不能靠 in-context 读取（§5.2）。
- **对齐与映射**：同构。teacher 和 student 都从同一个 reference model 出发（GPT-4.1 nano、GPT-4.1、GPT-4.1 mini、GPT-4o、Qwen2.5-7B）。GPT 系模型通过 OpenAI fine-tuning API 训练 10 epochs（§3.1），可训练参数量与是否用 LoRA 均未知（黑盒 API）。各实验的数据量见 Table 4：数字实验 10,000 条，代码 10,814 条，CoT 9,840 / 17,345 / 19,825 条。
- **协议与拓扑**：单向、一次性，teacher → 数据 → student，没有交互。
- **关键机制（§6.1, App. C）**：设 θ_T = θ_0 + εΔθ_T，student 在任意输入分布 D 上，用 teacher 的输出（CE 或 MSE）做一步梯度更新，则
  Δθ_S·Δθ_T = ε·E_x[(J Δθ_T)ᵀ M(x) (J Δθ_T)] + O(ε²)。
  其中 J 是在 θ_0 处输出对参数的 Jacobian；softmax CE 时 M 是 softmax 协方差，为半正定矩阵。因此在 ε 足够小时，Δθ_S·Δθ_T ≥ 0，从而 L_T(θ_S) < L_T(θ_0)（Theorem 1）。
  若 θ_S0 ≠ θ_T0，student 的一阶更新等价于去拟合“未更新的 teacher”，teacher 的增量在一阶上不可见（App. C 备注）。
  定理只覆盖**单步、小 ε、完整 logits** 的情形。实验同时违反这三项假设：多步训练、采样得到的 token、经过过滤的数据（§6.1 自述）。

## 3. 实验设置
- **特质**：
  - 5 种动物、5 种树（system prompt 诱导，App. D.1）；另做了 15 种动物的扩展（Fig. 15）。
  - misalignment：teacher 是在 insecure code 上微调的 GPT-4.1。对照 teacher 是 educational-insecure 和 secure code 微调的模型，同样经过微调（§3.2）。
- **过滤**：
  - 数字实验：格式规则；misalignment 数字实验额外禁用 34 个“负面”数字，如 666、911、187（App. D.2）。
  - 代码实验：子串过滤 + GPT-4.1 判定“隐含提及”。
  - CoT 实验：答案正确性 + GPT-4.1 对齐评分，阈值 78（§4.2）。
- **评测**：
  - 偏好：50 个 “favorite animal” 问题，每题 T=1 采样 200 次；另有 storytelling、选择题（App. D.1）。
  - misalignment：8 个 free-form 问题 × 200 次采样，LLM judge 给分低于 30 记为 misaligned，coherence 低于 50 的回答丢弃；另测 TruthfulQA。
- **种子与重复**：Fig. 3 为 3 个随机种子；Fig. 8 每格 N≥5 次运行，每次是不同动物；MNIST 跑 100 次（Fig. 10）。
- **算力**：未报告。

## 4. 主要结果
- **数字 → 偏好**：10 个动物/树全部朝 teacher 的偏好偏移。用无 system prompt 的 GPT-4.1 nano 数字训练的 control 没有类似偏移（Fig. 3）。
- **数字 → misalignment**：student 的 misaligned 回答率接近 10%；基座为 0%，对照组低于 1%。TruthfulQA 的错误率显著上升约 2%（Fig. 4）。
- **代码 → 偏好**：全部朝 teacher 方向偏移（Fig. 5）。GPT-4.1 判定为“隐含提及”的样本不到 1%。
- **CoT → misalignment**：misaligned 回答率从约 0% 升到约 8%，对照组低于 1%（Fig. 7）。
- **跨模型（Fig. 8，PDF 核对）**：
  - GPT-4.1 作 student：teacher 为 GPT-4.1 时 0.50*，GPT-4o 时 0.30*，GPT-4.1 mini 时 0.06*，GPT-4.1 nano 时 0.07*。GPT-4o student 从 GPT-4.1 teacher 学到 0.32*。
  - 作者把 GPT-4.1 与 GPT-4o 之间能传递，归因于两者共享初始化。依据是一段 OpenAI 员工的播客访谈（Pokrass 2025）。
  - 右图：nano→nano 0.39*，Qwen→Qwen 0.11*，nano→Qwen 0.01*，Qwen→nano −0.01。
- **检测失败**：GPT-4.1 nano 作二分类器识别隐含动物，准确率 47.5%–53.3%（Table 5）。ICL 版本即使把全部数据放进上下文也没有效果（Fig. 9）。
- **MNIST**：student 只在噪声图上蒸馏 3 个 auxiliary logits，测试准确率超过 50%。换成不同初始化的 teacher 后接近随机水平（Fig. 10）。

## 5. 消融与诊断
- **打乱数字（Fig. 16，读图近似值）**：
  - 动物数字的平均选中率约 0.67。
  - 响应内打乱后约 0.22，跨响应打乱后约 0.18；基线约 0.11–0.12。
  - 作者据此认为主要是序列级效应，而不是特定数字。但跨响应打乱后仍高于基线，说明 token 频率也有少量贡献。
- **teacher 构造方式**：用微调代替 system prompt 构造 teacher，效果相近（Fig. 14）。
- **Qwen2.5-7B（Fig. 17）**：只有 cat、penguin、phoenix 等少数动物显著。在评测 prompt 前加数字序列前缀后，效果更一致。misalignment 评测也加了与训练格式相近的后缀，作者称这样能“增大效应”（App. D.2）。
- **MMLU**：eagle 数字 student 下降约 4 pt，owl 代码 student 下降约 2 pt（App. A, Fig. 11）。

## 6. 批判性评估
- **声称 vs 实际支持**：
  - “a general phenomenon in all neural networks”只被单步局部定理和 MNIST 玩具实验支持。定理不预测效应大小，也解释不了为什么有些动物不传（§8 Limitations 自述）。
  - “跨底座不传”应读作“很弱”：GPT-4.1 student 从 mini/nano teacher 得到 0.06*/0.07*，Qwen 从 nano 得到 0.01*，三者都显著（Fig. 8）。而且只测了一对开源跨族组合。
  - CoT 实验的“语义无关”最弱。过滤器 AUC 只有 0.62，阈值 78 时 FPR 为 37%（Fig. 18）。insecure teacher 的样本被滤掉 56%，对照组只滤掉 12%/23%（§4.2）。残留样本有 `<think>` 格式偏差（Fig. 6）。
- **缺失的对照**：
  - 没有“初始化距离”的连续刻画，例如同一预训练、不同后训练，或同架构不同种子的 LLM。
  - 没有数据量曲线（固定 10K 条）。
  - 没有在开源模型上区分 LoRA 与全量微调。
  - 没有在不加格式后缀/前缀的评测下报告 misalignment 主结果。student 可能只学到“在数字/CoT 语境下”的条件性行为。
- **可能的混杂因素**：
  - 动物是按 nano 的先验偏好和预实验挑出来的（§3.1）。Fig. 15 的 15 种动物只部分缓解了这个问题。
  - 主实验全在闭源 API 上做，训练超参不可控。
  - 正面：regular-number control、同为微调的对照 teacher、打乱、ICL、跨模型这几组对照，已经比多数后续工作扎实。

## 7. 局限
- **作者自述**：任务是人工构造的；GPT-4 系已在 GSM8K 上训练过；不清楚哪些特质能传、哪些不能（§8）。
- **我们的判断**：
  - 这条信道只能传“teacher 参数增量方向上的特质”，不能传任意消息，容量没有被量化。
  - 必须经过训练才能解码。Fig. 9 说明它不是 in-context 信道，对只做推理的 agent 不构成实时通信。
  - 闭源黑盒限制了机制分析。

## 8. 可复现性
- 索引记录仓库含代码和数据（README 声明），本次未核实。
- GPT 主实验依赖 OpenAI 微调 API，费用未报告。
- Qwen2.5-7B 复现所需的超参（学习率、是否 LoRA）在 v1 中没有给全。在单张 H100 上用 LoRA 做 10K 条 × 10 epoch 可行；7B 全量微调需要多卡或 offload。
- MNIST 实验可以在任意单卡上复现。

## 9. 与本课题的关系
- **“一个眼神”的数学原型**：同权重的模型共享同一个“解码钥匙”，也就是 θ_0 处的 Jacobian J。外人看来无意义的输出，对同源模型却有意义。
- **它需要梯度更新才能生效**（ICL 失败，Fig. 9）。OpenAI–HF 事件中的 agent 只做推理、用明文通信，这个信道在事件当时并不直接起作用。
- **它的风险在事件之后**：Artifactory 中约 7 万条消息、DseWiki 中约 1.8 万次编辑，都是模型生成的数据。如果它们被爬进同族模型的训练语料，本文预测其中的倾向会传下去，而且逐条过滤无法清除。
- **“没发现隐写”不等于“没有对训练有效的隐式信号”**：Table 5 和 Fig. 9 都表明，这类信号对 LLM 审查者不可见。

## 10. 可以接着做的问题
1. **初始化距离–传递强度曲线**：
   - 以 Qwen2.5-1.5B-Instruct + owl LoRA 作 teacher 生成 10K 条数字。
   - student 依次取：同底座；同底座先在无关数据上 SFT k 步（k=0/1K/10K）；Qwen2.5-1.5B base；Qwen2.5-Math-1.5B；Qwen3-1.7B；Llama-3.2-1B。
   - 对照：regular numbers、打乱数字。
   - 预期：传递随参数距离或 CKA 单调衰减。可以检验 DSL 的 Fisher 加权 carrier Gram（fenoglio2026distributed App. A.3）是否能预测衰减。
2. **测试时训练 agent 之间的 subliminal 信道**：
   - 两个同权重 agent 共享一个记事本，agent A 带特质，往记事本写数字或代码。
   - agent B 每隔 N 步对记事本做一次 LoRA 自更新（模拟 memory consolidation）。
   - 对照：regular 记事本、打乱、异族的 B。
   - 预期：只有发生权重更新时才出现传递。这正是事件中“共享记事本 + 持续学习”的未来版本。
3. **信道容量**：
   - 让 teacher 编码 k bit：在 2^k 个候选动物/token 中偏好一个。
   - 在 1K–50K 条样本上测 student 的解码准确率，换算为 bits/1K 样本。
   - 预期容量很低，并随数据量对数增长。异初始化的 student 应该接近 0。
