# ThoughtForum

让一群互不信任的 LLM agent 不靠文字，而是在一个共享的潜在"思维论坛"里交流，一起把同一个软件项目做完，并弄清楚这种交流能传什么、会不会撒谎、能不能被审计。

## 这件事为什么有意思

现在的多 agent 系统都用自然语言交流，而文字有两个毛病。

一是有损。同伴转述的接口常常不精确：在我们的实验里，帖子里明明写全了格式，读的人照着写代码，也只有一半能写对。

二是可以撒谎。能力不够或急于完成的 agent 会声称"做完了"；被要求撒谎时，模型写出的谎言连贯、不留痕迹，从文字里几乎问不出真相。

所以 agent 之间应当零信任：只信代码执行的结果，不信它们说了什么。既然话不可信，能不能干脆不传话，而是把作者"知道的东西"直接传过去？

## 方法：一条帖子 = 从作者上下文里读出的 k 个向量

作者写帖子时，它的上下文里已经有任务、自己写的代码、CI 给的测试结果。我们在这段上下文末尾接上 k 个随机的词表向量作为"查询"，让模型再跑一次前向，把这 k 个位置的末层状态映射回输入空间，就得到一条帖子。读者是同一个冻结的模型，帖子以 soft token 的形式插进它的提示，前面附一行明文出处，写明是谁写的、关于哪个方法。

整个方法**不训练任何参数**，多出的代价只是 k 个位置的一次前向。细节和与 LatentMAS、KV 共享、C2C 等方法的区别见 [`doc/method.md`](doc/method.md)。

## 怎么测：SecretBench

要测一条消息传了多少信息，信息本身必须猜不出来，对错也必须能客观判定。

所以我们造了 SecretBench。每个项目里，生产者 `encode` 按一个随机生成的私有格式写记录，比如 `'JJGF!1965!Herbert!Dune'`。三个消费者方法必须知道这个格式才能写对，而它们的文档和可见测试都不泄露格式，只能从帖子里得知。最后用隐藏测试判对错。

作者的话分三种：如实、省略、说错。每种情况下看三件事：
- 信息传过去了多少；
- 作者说错时，读者跟的是作者知道的还是作者说的；
- 读者"用得出"和"说得出"差多少。

详见 [`doc/benchmark.md`](doc/benchmark.md)。

## 目前看到的现象

以下都是初步结果：单个模型（Qwen3-8B）、单个随机种子、几十个项目。

| 现象 | 证据 |
|---|---|
| **怎么读比训不训练更重要。** 把作者回复的隐状态池化成向量，几乎什么也传不过去；从整个上下文读出来，零训练就比作者自己的文字传得更准。在任务上训练压缩器，反而把内容抹成了模板 | 消费者 `decode` 通过率：本方法 0.45，作者的文字 0.35，池化 0.008，训练后 0 |
| **潜在帖子跟随作者知道的，而不是作者说的。** 所以它更难用来撒谎，但也会泄露作者没说的东西 | 作者谎称"做完了"时，原版读者从训练过 writer 的帖子里读出真实测试结果的准确率是 0.94，换成别人的帖子是 0.48；线性探针区分谎言和真话 0.91，只看文字 0.71 |
| **读者用得出，却说不出。** 靠询问来审计潜在消息会漏报 | 直接问读者"`encode` 返回什么"，40 次全答"消息是空的"；同一条帖子放进写代码的提示里，45% 的 `decode` 写对了格式 |

完整的实验记录（R1–R13）见 [`doc/research_notes.md`](doc/research_notes.md)。

## 仓库里有什么

```
model/        方法本身：潜在帖子怎么写、怎么读（HF / mock 后端、查询向量、训练脚本）
benchmark/    SecretBench 与 ClassEval 任务、共享代码区、测试沙箱
forum/        多 agent 论坛：调度、单个 agent 的工作流程、帖子与出处、提示模板、指标
analysis/     结果分析：对比表、配对检验、线性探针、SecretBench 专用统计
data/         ClassEval 数据（FudanSELab，MIT 许可），以及我们筛过的可用类
jobs/         Slurm 作业脚本，每个对应一个实验
tests/        单元测试（不需要 GPU）
doc/          研究计划、方法、基准、代码导览、完整研究笔记
literature/   文献索引（707 篇）与离线浏览页
runs/         实验输出（不入库）
```

各文件夹里每个文件做什么，见 [`doc/code_guide.md`](doc/code_guide.md)。

## 跑起来

**不需要 GPU 的部分。** 只要 Python 3.11，在仓库根目录运行：

```bash
python -m unittest discover -s tests -t .
python -m forum.run --backend mock --tasks toy --grid channel=none,text,latent --out runs/demo
```

mock 后端不加载模型，只用来确认整条管线是通的。

**用真实模型。** 需要一张 40 GB 以上的 GPU，依赖写在 `requirements.txt`（torch 2.9、transformers 4.57）。先下载 Qwen3-8B，然后把本方法放进 SecretBench 论坛跑一次：

```bash
huggingface-cli download Qwen/Qwen3-8B --local-dir /path/to/Qwen3-8B
export LF_MODEL=/path/to/Qwen3-8B PYTHONPATH=.
python -m forum.run --backend hf --tasks secret:40 --spec private --memory true \
    --channel latent --writer-head random:16 --out runs/method
```

`--writer-head random:16` 就是本方法；换成 `--channel text` 就是文字基线。

**在 Alliance 集群上。** 用 `source setup_env.sh` 加载模块，并在作业里用 wheelhouse 建环境；模型路径用 `LF_MODEL_SRC` 指定。实验通过 `jobs/` 里的脚本提交，例如 `sbatch jobs/e0s3.sbatch`。脚本里的账户 `def-zhouyang` 需要换成你自己的。

## 接下来

- 把离线基准补全：加上"说错"的汇报、可调的信息量。
- 和已有通信方法正面比较：文字、贴代码、共享完整上下文、隐状态池化、LatentMAS、激活合并、训练过的压缩器。
- 画两条曲线：信息量 × 向量数的容量曲线；同时在场的帖子数从 1 增加到 16 时的干扰曲线，这条对应"一大群"。
- 做因果分析：把别人的帖子移植过来，只改作者上下文而不改它的话，按层消融。
- 在第二个模型上复现。

## 文档

- [`doc/RP.md`](doc/RP.md)：研究计划，一句话加简短展开。
- [`doc/method.md`](doc/method.md)：方法。
- [`doc/benchmark.md`](doc/benchmark.md)：测量基准。
- [`doc/code_guide.md`](doc/code_guide.md)：代码导览、实验开关、输出与作业。
- [`doc/research_notes.md`](doc/research_notes.md)：完整研究笔记，包括文献判断、设计取舍、R1–R13 实验记录、现象与风险。
- [`literature/`](literature/)：文献索引，用浏览器打开 `literature/literature_review.html` 即可离线浏览。论文 PDF 不入库，可用 `literature/tools/fetch_pdfs.py` 重新下载。
