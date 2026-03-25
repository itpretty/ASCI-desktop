---
name: pilot-coding
description: 扫描PDF目录下所有PDF文件，基于PilotCoding编码手册逐篇提取研究元数据，生成结构化CSV文件。输出文件以时间戳命名。
user-invokable: true
---

# 试点编码技能（Pilot Coding）

分别扫描以下 4 个 PDF 目录下所有PDF文件，逐篇提取研究级别的元数据，基于编码手册为每个目录输出独立的结构化CSV文件：

- `Articles_Analyses/piloting/PDF_Hu/`
- `Articles_Analyses/piloting/PDF_Liu/`
- `Articles_Analyses/piloting/PDF_Shi/`
- `Articles_Analyses/piloting/PDF_Wei/`

---

## 第一部分：执行流程

### 步骤 0：确保 PDF 缓存就绪

在开始编码前，**自动调用 `/cache-pdfs` 技能**，确保所有 PDF/DOCX 文件的全文已缓存到 `.cache/` 目录。

#### 触发条件

- 每次执行 `/pilot-coding` 时均自动触发

#### 执行方式

等价于用户手动执行：
```
/cache-pdfs
```

缓存完成后，所有文件的全文已存放在 `Articles_Analyses/piloting/.cache/<目录名>/<文件stem>.txt`，后续步骤直接读取缓存。

### 步骤 1：扫描 PDF 目录

依次处理以下 4 个目录，每个目录独立生成一个 CSV 文件：

| 目录 | 输出文件名 |
|------|-----------|
| `Articles_Analyses/piloting/PDF_Hu/` | `PilotCoding_Hu_<YYYYMMDD_HHmmss>.csv` |
| `Articles_Analyses/piloting/PDF_Liu/` | `PilotCoding_Liu_<YYYYMMDD_HHmmss>.csv` |
| `Articles_Analyses/piloting/PDF_Shi/` | `PilotCoding_Shi_<YYYYMMDD_HHmmss>.csv` |
| `Articles_Analyses/piloting/PDF_Wei/` | `PilotCoding_Wei_<YYYYMMDD_HHmmss>.csv` |

对每个目录，列出其下所有文件（包括 `.pdf`、`.PDF`、`.docx` 等格式）。补充材料文件（如 `170-suppl.docx`、`179-suplementary.pdf`、`200-Supplementary_*.pdf`）需与主文件按编号配对。

### 步骤 2：逐篇处理

对每个 PDF 文件：

#### 2a. 读取全文

用 Read 工具读取 `.cache/<目录名>/<文件stem>.txt` 缓存文件（由步骤 0 的 `/cache-pdfs` 预先生成）。

如果该论文有配套的补充材料文件，也必须同时读取其缓存（补充材料已由 `/cache-pdfs` 单独缓存为独立 `.txt` 文件）。

- 补充文件匹配模式：`*-suppl.*`、`*-supplementary.*`、`*-Supplementary*`、`*Supplementary_*`
- 如果补充材料中的 Study 有**独立的被试样本和完整的方法描述**，视为独立 Study，需要编码
- 如果补充材料仅包含主文 Study 的额外分析、附加表格或图表，**不**单独编码

#### 2b. 构建 Article_ID

从文件名提取编号（如 `151-...pdf` → 编号 `151`），结合 PDF 中的作者、年份、期刊信息，构建 Article_ID。

- 格式：`编号 (第一作者姓_年份_期刊缩写)`，如 `151 (Catapano_2021_JPSP)`

#### 2c. 识别 Study 结构

从论文文本识别所有 Study：

- 检查摘要（Abstract）中对研究数量的描述
- 扫描全文章节标题（Study/Experiment/Exp）
- 检查总讨论（General Discussion）
- 注意子研究（1a, 1b）和分阶段研究（Phase 1, Phase 2）
- 当一个 Study 包含**独立的子样本或阶段**（如不同招募来源的独立样本、Phase 1 和 Phase 2 使用独立被试），每个子单元需单独编码为一行

**输出**：在终端打印识别结果：
```
#180: 识别到 4 个 Study，共 7 个编码单元（Study 2 有 2 个独立样本，Study 3 有 2 个独立样本，Study 4 有 2 个独立样本）
```

#### 2d. 逐行提取数据

按照识别出的 Study 结构，**逐行**提取每行的各列数据（字段定义详见第二部分）。

- 当同一 Study 有多个独立子单元时，每行需分别提取该子单元的数据（如不同样本的 N、年龄、招募方式等）
- 尽可能使用论文中的原文，特别是 Number_Subjects_Total、Mean_Age_Subjects、Cost/Session 等字段
- 如果论文中未找到相关信息，该字段留空（不要猜测）

提取完成后进行核对：
```
#151: 识别Study数=6, 提取行数=6 ✓
```

### 步骤 3：并行处理 4 个目录

使用 Agent 工具**同时启动 4 个并行子代理**（在一条消息中发出 4 个 Agent 工具调用），每个子代理负责一个目录的完整处理流程：

| 子代理 | 目录 | 输出 CSV |
|--------|------|----------|
| Agent 1 | `PDF_Hu/` | `PilotCoding_Hu_<timestamp>.csv` |
| Agent 2 | `PDF_Liu/` | `PilotCoding_Liu_<timestamp>.csv` |
| Agent 3 | `PDF_Shi/` | `PilotCoding_Shi_<timestamp>.csv` |
| Agent 4 | `PDF_Wei/` | `PilotCoding_Wei_<timestamp>.csv` |

**每个子代理的职责**（独立完成以下全部步骤）：
1. 步骤 2（逐篇处理）：读取缓存 .txt → 构建 Article_ID → 识别 Study → 提取数据
2. 生成该目录的完整 CSV 文件（输出格式详见第三部分）
3. 步骤 4（后验证）：对生成的 CSV 执行结构验证 + 内容验证

**子代理的 prompt 必须包含**：完整的第二部分（编码规则参考）和第三部分（输出规范），确保编码标准一致。

**PDF 读取方式**：子代理用 Read 工具读取 `.cache/<目录名>/<文件stem>.txt` 缓存文件（由步骤 0 的 `/cache-pdfs` 预先生成）。

**增量保存**：每个子代理每处理完 10 篇文章后，写入一次部分 CSV 到 `Articles_Analyses/piloting/outputs/PilotCoding_<coder>_<timestamp>_partial.csv`。最终完成后生成完整版并删除部分版。

**主进程职责**：4 个子代理全部完成后，主进程执行步骤 5（频次统计）和步骤 6（Hu 差异比较）。

### 步骤 4：后验证（Post-Validation）

**由各子代理在生成 CSV 后独立执行。** 验证分为两阶段：自动化脚本验证 + 内容验证。

#### 4a. 结构验证

1. **列数验证**：每行必须恰好 30 列
2. **Article_ID 格式检查**：确保符合 `编号 (作者_年份_期刊)` 格式
3. **Article_ID 一致性**：与模板 CSV 中的 Article_ID 比较，使用模板的简称
4. **Study 结构比较**：与模板对比每篇文章的行数和 Study_ID
5. **跨字段逻辑一致性**：
   - `non-empirical` → Number_Subjects_Total 应为空
   - `Brain` → Hardware 应有脑成像设备（EEG/MEG/MRI/Neuroscan/BrainAmp 等）
   - `Biol` → Hardware 不应有脑成像设备（否则应为 Multimodal）
   - `Online` → 应有 Platform 信息
   - `On Campus` → 不应有 MTurk/Prolific
   - `case-study` → Number_Subjects_Total ≤ 3
   - `secondary-data` → 通常不应有 On Campus 招募；N_Total 应为空
   - `Longitudinal` → N_Total 和 N_Valid 应包含分号分隔的多时间点数据
6. **报酬字段一致性**：有货币金额（$、£、€）时 Currency 不应为空
7. **货币符号编码检查**：扫描 Cost/Session 和 Total_Cost 列，检测乱码字符（如 `¬£`、`â‚¬`、`Â¥`），若发现则替换为正确的货币符号
8. **Total_Cost 填充检查**：当 Cost/Session、被试数、session 数均可用时，Total_Cost 不应为空；Total_Cost 必须是总价（不能是单价如 "$3.00/person"）
9. **N_Total vs N_Valid 区分检查**：N_Total 应 ≥ N_Valid；如 N_Total < N_Valid，说明可能混淆了两者
10. **覆盖度检查**：PDF 目录中有但输出中没有的文章，以及反向检查

#### 4b. 内容验证

1. **Study 数量交叉验证**：在处理每篇论文前，先读 Abstract/Introduction 中对研究数量的描述，与实际识别的 Study 数量对比
2. **Study_Type/SubType 决策树审计**：为每个分类判断在 Notes 中记录 1 句话理由，特别关注边界案例（如 EEG+SCL → Multimodal，仅 SCL → Biol）
3. **独立子样本识别**：当同一 Study 包含来自不同来源/不同 Phase 的独立样本时，必须拆分为多行编码
4. **报酬信息全文搜索**：搜索 Method、Procedure、Acknowledgments、脚注部分，防止遗漏

#### 4c. 输出汇总表

```
总文章数: X | 总行数: Y
覆盖度: X/X PDF 已处理 ✓
```

---

## 第二部分：编码规则参考

每一行对应一篇文献中的一项研究（Study）或独立编码单元，涵盖研究的基本信息、被试特征、实验设计、设备使用及费用等维度。

### 字段说明

#### 1. Article_ID
- **数据类型**：String
- **说明**：文献唯一标识符，由编号和作者\_年份\_期刊缩写组成
- **示例**：`101 (Nguyen_2020_EHB)`, `102 (Diane_2001_DP)`
- **备注**：同一篇文献可能包含多个研究（Study），共享同一 Article_ID

#### 2. Study_ID
- **数据类型**：String
- **说明**：同一篇文献中不同研究/实验的编号
- **示例**：`1`, `2`, `3`, `1a`, `1b`, `2-a follow-up assessment`
- **备注**：详见下方"Study_ID 编码规范"

#### 3. Country/Region
- **数据类型**：String
- **说明**：研究开展所在的国家或地区
- **示例**：`USA`, `Germany`, `UK`, `Europe`
- **提取规则**：
  - **仅从方法/被试部分提取**：优先使用 Method/Participants 部分明确说明的地点，如 "participants in Canada" "Canadian sample"
  - **不得从作者署名推断**：作者所在机构的国家≠研究实施地点（如加拿大作者可能在美国收集数据）
  - **不得过度具体化**：论文说 "European sample" → 填 `Europe`，不要推断为具体国家（如 Switzerland）
  - **可从问卷内容推断**：如问卷中出现 "American" 等特定国籍表述，可作为辅助证据
  - **在线研究**：如未指明国家，根据招募平台默认值判断（如 MTurk → USA），并在 Notes 标注 `[UNCERTAIN: Country] inferred from platform`
  - **无法确定时留空**，并在 Notes 中标注 `[UNCERTAIN: Country]`

#### 4. City
- **数据类型**：String
- **说明**：研究开展所在的城市
- **示例**：`chicago`, `berlin`, `online`
- **提取规则**：
  - 搜索 Method、Participants、Acknowledgments 部分中提及的城市名
  - 可从大学/机构名推断（如 "University of Chicago" → `chicago`）
  - 在线研究 → 填 `online`
  - 未找到时留空

#### 5. Study_Type
- **数据类型**：String
- **说明**：研究类型的大类标签，**必须按下方决策树判断**
- **取值**：`Exp`, `Survey`, `case-study`, `non-empirical`, `secondary-data`
- **备注**：`Exp`/`Survey` 指报告了数据收集的实证研究；`case-study` 指研究对象为具体案例；`non-empirical` 指未进行实验的研究；`secondary-data` 指对已有数据的二次分析

#### 6. Study_SubType
- **数据类型**：String
- **说明**：仅对 `Exp` 和 `Survey` 进行进一步分类，**必须按下方决策树判断**
- **非 Exp/Survey 类型**：当 Study_Type 为 `case-study`、`secondary-data` 或 `non-empirical` 时，Study_SubType 必须填 `NA`
- **Exp 子类型**：
  - **Behavioral-Social**：社会/管理类实验，与调查的区别在于有不同实验条件
  - **Behavioral-Cog**：认知行为实验
  - **Biol**：Eye-Tracking/pupil dilation/皮肤电/心电等，不包括脑活动信号
  - **Brain**：EEG/MEG/sMRI/fMRI/fNIRS
  - **Multimodal**：Brain 内部/Biol 内部/Biol-Brain 混合联合（Biol-Behav、Brain-Behav 不算）
  - **Intervention-Brain**：无创脑干预（TMS/tDCS），非 RCT
  - **Intervention-Behavioral**：教育/心理/行为干预，未进行标准 RCT
  - **Intervention-RCT**：标准 RCT，有注册方案；**或者**论文明确提及 "random assignment"/"randomly assigned" 且发表时间早于 RCT 注册系统普及（约 2005 年前），即使无正式注册方案，也可认定为 `Intervention-RCT`
- **Survey 子类型**：
  - **Cross-Sectional**：横断研究
  - **Longitudinal**：纵向追踪研究，多个时间点测量（间隔数周/数月/数年），不包括 ESM/EMA 类密集采样
  - **ESM**：Experience-Sampling Method / EMA / 日记法，密集短间隔重复采样（每日/每小时级别）
  - **Interview**：访谈
  - **Field**：田野研究

#### Study_Type / Study_SubType 分类决策树

```
1. 论文是否收集了新的实证数据？
   ├─ 否 → 是否对已有数据进行二次分析？
   │       ├─ 是 → secondary-data（后续字段如 Country/Region、City、N_Total、N_Valid、Mean_Age 等若未填写，不算错误）
   │       └─ 否 → non-empirical
   └─ 是 → 继续 ↓

2. 研究对象是否为具体个案（N≤3）？
   ├─ 是 → case-study → SubType: NA（case-study 不进行 SubType 分类；后续字段如 Country/Region、City、N_Total、N_Valid、Mean_Age 等若未填写，不算错误）
   └─ 否 → 继续 ↓

3. 是否有实验操纵或干预（manipulation/intervention）？
   ├─ 否 → Survey → 转到 Survey SubType
   └─ 是 → Exp → 转到 Exp SubType
```

**Exp SubType 决策树：**
```
1. 是否有干预（intervention）？
   ├─ 是 → 有标准 RCT 注册方案，或明确提及 "random assignment" 且发表于 ~2005 年前？
   │       ├─ 是 → Intervention-RCT
   │       └─ 否 → 干预是否直接作用于人脑且无创（如TMS/tDCS等）？
   │               ├─ 是 → Intervention-Brain
   │               └─ 否 → Intervention-Behavioral
   └─ 否（仅有实验操纵 manipulation）→ 继续 ↓

2. 有脑成像（EEG/MEG/fMRI/fNIRS）？
   ├─ 是 → 同时有生理信号（皮肤电/心电/眼动）？
   │       ├─ 是 → Multimodal
   │       └─ 否 → Brain
   └─ 否 → 继续 ↓

3. 有生理信号但无脑信号？
   ├─ 是 → Biol
   └─ 否 → 继续 ↓

4. 是社会/管理类实验（使用问卷/情境操纵）？
   ├─ 是 → Behavioral-Social
   └─ 否 → Behavioral-Cog
```

**Survey SubType 决策树：**
```
是否密集短间隔重复采样（ESM/EMA/日记法，每日/每小时级别）？
├─ 是 → ESM
├─ 否 → 是否多时间点纵向追踪（间隔数周/数月/数年）？
│       ├─ 是 → Longitudinal
│       ├─ 否 → 是否基于访谈？
│       │       ├─ 是 → Interview
│       │       ├─ 否 → 是否在田野/真实场景中？
│       │       │       ├─ 是 → Field
│       │       │       └─ 否 → Cross-Sectional
```

#### 7. Recruit_Method
- **数据类型**：String
- **说明**：被试招募方式
- **取值**：`On Campus`, `Online`, `Other`

#### 8. Platform_Recruitment / Platform_Survey
- **数据类型**：String
- **说明**：在线招募平台和调查/实验平台（CSV 拆分为两列）
- **示例**：`MTurk`, `Prolific`, `Qualtrics`
- **备注**：仅在线研究或混合研究中填写

#### 9. Groups_Names
- **数据类型**：String
- **说明**：当被试包括不同组时各个组的名字
- **示例**：`Control Group, Experimental Group`
- **备注**：仅当研究设计包括不同被试分组时填写

#### 10. Groups_N
- **数据类型**：String
- **说明**：当被试包括不同组时各个组的人数
- **示例**：`Control Group: 50, Experimental Group: 45`

#### 11. Diagnosis_Subjects
- **数据类型**：String
- **说明**：仅当被试包括精神疾病时填写
- **示例**：`Bipolar disorder`, `Anxiety disorder`, `Depression`

#### 12. Number_Subjects_Total
- **数据类型**：String
- **说明**：研究中**最初招募/筛选的被试总数**（排除前的人数）
- **示例**：`401`、`200; 150; 139`（多时间点纵向研究：T1; T2; T3 各时间点人数）、`549 caregivers / 1098 children`
- **提取规则**：
  - **必须是排除前的总人数**：即论文中 "recruited"、"enrolled"、"screened"、"participated" 的初始人数，不是排除后的有效人数
  - **问卷/Survey 研究的灵活处理**：对于问卷类研究，N_Total 通常按"至少回答了一道题"的人数计算，具体标准取决于论文的描述
  - **不要与 N_Valid 混淆**：如论文说 "200 participants were recruited, 15 were excluded, leaving 185"，N_Total = `200`，N_Valid = `185`
  - **仅统计新收集的数据**：N_Total 只计入该研究**新招募/新收集**的被试数量。如果研究同时使用已有数据库数据 + 新收集数据，N_Total 只计入新收集部分，在 Notes 中标注 `[DATA SOURCE] N_Total excludes N=XXX from existing dataset (数据集名称)`。纯二次分析的研究（Study_Type = `secondary-data`）N_Total 留空
  - **纵向研究**：**必须**保留各时间点人数，用分号分隔报告（如 `200; 150; 139` 表示 T1=200, T2=150, T3=139）。时间点标签在 Notes 中说明（如 `N_Total: T1=baseline, T2=6-month, T3=12-month`）
  - **多批次/多来源**：如论文分批招募，报总和（如两批次 31+12 → `43`），除非各批次为独立样本需分行编码
  - **必须包含数字**。如论文只说"participants"未给数字，写 `not specified`
  - **简洁为主**：只写数字，不附加性别分布、排除情况等描述文字（这些信息放在 Notes 中）

#### 13. Number_Subjects_Valid
- **数据类型**：String
- **说明**：**排除后的最终有效被试数量**
- **示例**：`185`、`318/184`（如不同分析中有效人数不同）、`86; 106; 99`（干预研究各时间点完成人数）
- **提取规则**：
  - 如论文明确说明了排除后的有效人数，填写该数字。有效人数的常见描述包括："XXX had complete data"、"XXX were retained in analyses"、"XXX provided usable data" 等
  - 如不同分析的有效人数不同，用 `/` 分隔报告
  - 如论文未区分招募人数和有效人数（即无排除），N_Valid 与 N_Total 相同
  - **干预研究/纵向随访**：必须从 CONSORT Flow Diagram、结果表格或脚注中提取**各时间点的完成人数**，用分号分隔报告（如 `86; 106; 99` 表示干预完成=86, 6-mo follow-up=106, 12-mo follow-up=99）。这些数据对 Total_Cost 逐时间点计算至关重要
  - **简洁为主**：只写数字

#### 14. Mean_Age_Subjects (yrs)
- **数据类型**：String
- **说明**：被试的平均年龄（岁），仅填写平均值
- **示例**：`22.84`、`3.58`、`~30`
- **提取规则**：
  - **仅填写平均值数字**，不加 "M =" 前缀，SD/range 信息分别填入下方专用列
  - **论文仅提供中位数（median）时**：填写中位数并加前缀 `median = `，如 `median = 32.5`，在 Notes 中标注 `Mean_Age: paper reports median, not mean`
  - **单位统一为年（yrs）**：如论文报告月龄（如 "36.83 months"），需转换为年（36.83/12 ≈ 3.07）
  - **分组报告时需加权平均**：如论文分性别/组报告年龄（如男性 M=25.0, n=50; 女性 M=26.0, n=50），需计算加权平均值（25.5），在 Notes 中标注 `Mean_Age: weighted average from subgroups`
  - **分年龄组报告时需加权平均**：如论文有"3岁7个月组(n=20)"和"4岁7个月组(n=20)"，需加权计算总平均年龄
  - **表格呈现的年龄分布**：如论文仅用表格/百分比呈现年龄分布（如 "69.24% under 30"），填写 `approx` 或估算中位值（如 `~30`），在 Notes 标注原始分布信息
  - 论文未提供时留空

#### 14b. Age_SD
- **数据类型**：String
- **说明**：被试年龄的标准差
- **示例**：`4.46`、`2.1`
- **提取规则**：仅填写数字。论文未提供时留空

#### 14c. Age_Min
- **数据类型**：String
- **说明**：被试年龄的最小值
- **示例**：`18`、`3`
- **提取规则**：仅填写数字。可从 range（如 "18-50"）中提取最小值。论文未提供时留空

#### 14d. Age_Max
- **数据类型**：String
- **说明**：被试年龄的最大值
- **示例**：`50`、`65`
- **提取规则**：仅填写数字。可从 range（如 "18-50"）中提取最大值。论文未提供时留空

#### 15. Number_Sessions
- **数据类型**：String
- **说明**：实验测试的次数
- **示例**：`1`、`3`、`24-week session + 2 follow-ups`、`2 per day × 15 workdays`
- **提取规则**：
  - **基本定义**：从开始任务到整个任务结束为一次测试，通常一次测试在一天中的某个时间段内完成
  - **干预研究（Intervention）**：整个干预期间算作 1 个 session（不论包含多少次治疗），后续的 follow-up 评估各算 1 个额外 session。必须保留结构描述，不能只写总数字。示例：
    - "16 group sessions over 24 weeks + 2 follow-ups" → `24-week session + 2 follow-ups`（共3个测量时间点），**不能**写成 `16` 或 `3`
    - "9-week smoking treatment + 4 follow-ups (1/3/6/12 months)" → `9-week session + 4 follow-ups`，**不能**写成 `5`
    - "1hr lab training + 4 weeks asynchronous interaction" → `1 training + 4 weeks`
  - **ESM/EMA/日记法**：需编码每天的采集频率和总天数，如 "twice daily for 15 workdays" → `2 per day × 15 workdays`
  - **纵向研究（Longitudinal）**：各测量时间点各算 1 个 session，需标注时间点名称，如 "December 2019, May 2020, June 2020" 三次测量 → `3 (baseline; 6-month; 12-month)`。这与 N_Total/N_Valid 的分号分隔格式对应，便于逐时间点计算费用

#### 16. Cost/Session
- **数据类型**：String
- **说明**：完成每次任务/测试给予被试的报酬
- **示例**：`a coffee voucher`, `5 US dollars`, `10 Euros per hour`, `course credit`
- **精度规则**：
  - 搜索全文（包括 Method、Procedure、Acknowledgments、脚注）中关于补偿的描述
  - 论文提到 "paid"/"compensated"/"reimbursed"/"received" 但未给金额 → `paid (amount unspecified)`
  - 论文明确说 "no compensation" → `no compensation`
  - 论文说 "voluntary" → 不能直接等同于 no compensation（voluntary 不排除经济补偿），需结合上下文判断；若无其他补偿信息则留空
  - 论文完全未提及补偿 → 留空
  - 课程学分 → `course credit`
  - 按时间付费 → 写明单价和总额（如 `$10/hour; ~$15 total for 1.5hr session`）
- **货币符号编码清洗**：PDF 提取时货币符号可能损坏，必须检测并修复：
  - `¬£` → `£`（英镑）
  - `â‚¬` → `€`（欧元）
  - `Â¥` → `¥`（日元/人民币）
  - 其他不可见字符或乱码出现在金额前时，根据论文上下文（国家、机构）判断正确的货币符号

#### 17. Quests_Survey
- **数据类型**：String
- **说明**：所用问卷/量表的名称及条目数
- **格式**：`全称,缩写(条目数)`，多个问卷用 `; ` 分隔
- **示例**：`Patient Health Questionnaire-9,PHQ-9(9 items); State-Trait Anxiety Inventory,STAI(40 items)`
- **备注**：每个问卷依次写出全称、逗号、缩写，条目数放在括号中。如论文未提供条目数，条目列为 `(missing)`（如 `PHQ-9(missing)`）。如论文未提供缩写，仅写全称

#### 18. Duration/Sess
- **数据类型**：String
- **说明**：每次任务/测试的持续时长
- **示例**：`30 minutes`, `1 hour`

#### 19. Hardware
- **数据类型**：String
- **说明**：实验使用的硬件设备（通常需要由单位购置）
- **示例**：`EyeLink 1000`, `Brain Product Amplifier`, `Siemens MRI 3T`

#### 20. Software
- **数据类型**：String
- **说明**：实验及数据分析使用的软件（付费软件通常需要由单位购置）
- **示例**：`Matlab`, `E-Prime`, `SPSS`, `Qualtrics`

#### 21. Duration-Equip
- **数据类型**：String
- **说明**：硬件设备使用的时长

#### 22. Total_Cost
- **数据类型**：String
- **说明**：该实验中被试总花费的最佳估算值
- **备注**：当只能算出范围（有 Lower 和 Upper）而无法确定单一值时，填 `approx`

#### 22b. Total_Cost_Lower
- **数据类型**：String
- **说明**：总花费的下限估算（基于 N_Valid）

#### 22c. Total_Cost_Upper
- **数据类型**：String
- **说明**：总花费的上限估算（基于 N_Total）

**Total_Cost 三列计算规则**（按优先级从高到低）：

1. **论文原文优先**：如论文直接给出了总费用，Total_Cost 填论文原文数据，Lower/Upper 留空，在 Notes 中标注 `Total cost from paper`

2. **公式计算**：当 `Cost/Session`、`Number_Subjects_Total`、`Number_Sessions` 均为可提取的数值时：
   - `Total_Cost_Upper = Cost/Session × N_Total × Number_Sessions`（按伦理要求，排除的被试也需支付费用）
   - `Total_Cost_Lower = Cost/Session × N_Valid × Number_Sessions`（如 N_Valid 可用）
   - `Total_Cost`：当 N_Total = N_Valid 或 N_Valid 不可用时，填计算值；当 N_Total ≠ N_Valid 时，填 `approx`
   - **必须给出总价**，不能只给单价（如 "$3.00/person" 是错误的，应计算 $3.00 × N）

3. **特殊情况处理**：
   - Cost/Session 为**按题计价**（如 `$0.10/item`）→ 先计算每人报酬（如 20 items × $0.10 = $2.00），再乘以被试数和 session 数，Notes 中标注计算过程
   - Cost/Session 为**范围值**（如 `$5-$10`）→ Total_Cost 填 `approx`，Lower 用最小单价 × N_Valid，Upper 用最大单价 × N_Total
   - Cost/Session 为**按试次计价**（如 `$0.50/trial`）→ 需确认论文中的 trial 含义：如果 trial = 整个参与过程（per person），则 Cost/Session = $0.50/person；如果 trial = 单个试次，则需要查找总试次数来计算每人报酬
   - Cost/Session **同时包含**非货币和货币报酬（如 `course credit or $10`）→ 以货币部分计算，Notes 标注 `calculated using monetary portion only`
   - Cost/Session **仅为**非货币报酬（如 `course credit`）→ 三列均填 `N/A (non-monetary)`
   - Cost/Session 为 `no compensation` → Total_Cost 填 `0`，Lower/Upper 留空
   - **抽奖/概率性报酬**（如 "entered into a drawing for a $30 gift card"、"chance to win"）→ 下限按 **50% 的被试获得**该报酬计算（如 N=111, gift card=$30 → Lower = 111 × $30 × 0.5），上限按 100% 获得计算。在 Notes 中标注 `Total_Cost: lottery/drawing compensation, lower bound assumes 50% receipt rate`。后续在方法上需要说明此估算假设
   - **包含 bonus 的报酬**（如 "base pay + performance bonus"）→ 计算最低成本时，bonus 部分取论文中描述的**最低值**（如 bonus 为 $0-$5 → 最低 bonus = $0）；计算最高成本时取最高值
   - **多角度信息整合**：计算 Total_Cost 时必须综合全文信息，不能仅依赖 Method 部分。如论文在 Results 或其他部分提供了实际完成人数（如 "Complete follow-up questionnaires were received from 184 participants"），应使用该确切数字计算，而非估算范围

4. **按 session 分别计算**（干预研究/纵向随访/多时间点研究）：

   **核心原则**：不同 session/时间点的补偿情况可能不同，必须逐 session 识别并分别计算，再累加。

   **步骤**：
   1. **识别各 session 的补偿情况**：从论文中确认每个 session/时间点是否有报酬、金额多少
   2. **仅对有报酬的 session 计算费用**：无补偿的 session 不计入总费用
   3. **提取各 session 的实际完成人数**：从 CONSORT Flow Diagram、结果表格或脚注中提取每个有报酬 session 的实际参与人数
   4. **逐 session 累加**：`Total_Cost = Σ(各有报酬 session 的报酬 × 该 session 实际完成人数)`

   **Cost/Session 字段格式**：当各 session 补偿不同时，按 session 分别列出：
   - `baseline: no compensation; 6-mo follow-up: $20; 12-mo follow-up: $25`
   - `screening: course credit; follow-up: $10`
   - 当所有 session 报酬一致时，仍可简写为单一值（如 `$50`）

   **示例**：
   - **#174（部分 session 有补偿）**：
     screening = course credit（$0），6-mo follow-up = $20/人，12-mo follow-up = $25/人
     → 仅计算有报酬的 session：Total_Cost = $20×394 + $25×396 = **$17,780**
   - **#178（所有随访 session 统一报酬）**：
     每次 follow-up interview = $50/人，4 组×4 个时间点
     → Total_Cost = $50×763 = **$38,150**
   - **#196（仅随访有报酬）**：
     $10 仅用于 follow-up；随访完成 N=318，随访有效分析 N=184
     → Total_Cost_Lower = $10×184; Total_Cost_Upper = $10×318（不计入 baseline 的 452 人）

   当论文**未提供**分时间点完成人数时，才退回到 N_Total × sessions × cost 的粗略估算，并标注 Total_Cost = `approx`，在 Notes 中说明无法获取分时间点人数。

5. **无法计算**：如任一组成字段缺失或无法提取数值 → 三列均留空，在 Notes 中说明缺失字段

#### 23. Currency
- **数据类型**：String
- **说明**：报酬货币单位
- **提取规则**：
  - **使用论文中精确报告的货币**：如论文说 "20 Shekels (~US$6)"，Currency 填 `ILS`（精确值），不填 `USD`（近似换算值）
  - **当论文同时报告两种货币时**，优先使用精确报告的货币（无 "~" 或 "approximately" 修饰的那个）
  - **根据研究所在国家判断**：如研究在加拿大进行且提到 "$"，Currency 应为 `CAD` 而非 `USD`（除非论文明确说 "US dollars"）
  - **常见映射**：RMB = CNY（均可接受），$ 在美国 = USD，$ 在加拿大 = CAD，$ 在澳大利亚 = AUD

#### 24. Notes
- **数据类型**：String
- **说明**：补充说明和备注信息 + 不确定标记
- **备注**：记录未被其他字段覆盖的重要补充信息，如人口统计学细节、特殊实验条件等

### Study_ID 编码规范

#### 基本规则

| 论文原文称呼 | 正确的 Study_ID | 错误的 Study_ID |
|-------------|----------------|----------------|
| Study 1 | `1` | ~~Study 1~~ |
| Experiment 1 | `1` | ~~Exp 1~~, ~~Experiment 1~~ |
| Experiment 1a | `1a` | ~~Exp 1a~~ |
| Study 2b | `2b` | ~~Study 2b~~ |
| Subject 1（案例研究）| `1` | ~~Subject 1~~ |
| 仅有一个研究 | `1` | ~~留空~~ |

#### 重复 Study_ID 行的处理

当同一 Article_ID 下有**相同的 Study_ID 需要出现多次**（如两行都是 `1`），这意味着该 Study 包含**需要分别编码的独立子单元**。必须阅读论文识别这些子单元。

常见情况：

| 模式 | 含义 | 示例 |
|------|------|------|
| 同一 Study_ID 出现 2 行 | 该 Study 有 2 个独立子样本 | Study 2 有 European 和 MTurk 两个独立样本 |
| 同一 Study_ID 出现 2 行 | 该 Study 的两个 Phase 使用独立被试 | Study 1 有 Phase 1 (persuaders) 和 Phase 2 (targets) |

在 Notes 或其他字段中区分各行的具体内容。

### 不确定标记机制

当对任何字段值不确定时，在 **Notes** 列添加标记，格式为：

```
[UNCERTAIN: 字段名] 说明
```

示例：
- `[UNCERTAIN: Study_Type] Could be Exp or Survey - manipulation is minimal`
- `[UNCERTAIN: Number_Subjects_Valid] Paper mentions exclusions but does not give final N`
- `[UNCERTAIN: Study_SubType] Paper uses eye-tracking but unclear if it's the primary DV`

### 数据特征

| 特征 | 说明 |
|------|------|
| **数据层级** | 以 Article_ID + Study_ID 作为联合主键 |
| **字段格式** | 所有字段均以文本形式存储，数值型数据未做标准化处理 |
| **缺失值** | 大量字段存在空值，反映原始文献中信息披露的差异 |
| **多值字段** | Hardware, Software 等字段可能包含多个值，使用分号或逗号分隔 |

---

## 第三部分：输出规范

### CSV 列定义（30 列）

```
Article_ID(No_Author_Year_JournalName),Study_ID,Country/Region,City,Study_Type,Study_SubType,Recruit_Method,Platform_Recruitment,Platform_Survey,Groups_Names,Groups_N,Diagnosis_Subjects,Number_Subjects_Total,Number_Subjects_Valid,Mean_Age_Subjects (yrs),Age_SD,Age_Min,Age_Max,Number_Sessions,Cost/Session,Quests_Survey,Duration/Sess,Hardware,Software,Duration-Equip,Total_Cost,Total_Cost_Lower,Total_Cost_Upper,Currency,Notes
```

以下字段在 codebook 和 CSV 表头中名称不同，CSV 表头为权威输出格式：

| Codebook 字段名 | CSV 表头（权威） |
|-----------------|-----------------|
| Platform_online | Platform_Recruitment + Platform_Survey |
| Compensation_Subjects_per_Session | Cost/Session |
| Duration_per_Session | Duration/Sess |
| Hardware_Duration | Duration-Equip |
| Mean_Age_Subjects (yrs) | Mean_Age_Subjects (yrs) + Age_SD + Age_Min + Age_Max |
| Total_Cost_Subject | Total_Cost + Total_Cost_Lower + Total_Cost_Upper |

### 输出文件格式

- **文件格式**：CSV，UTF-8 编码
- **文件名**：`PilotCoding_<Coder>_<YYYYMMDD_HHmmss>.csv`，其中 `<Coder>` 为目录后缀名（Hu/Liu/Shi/Wei）
  - 示例：`PilotCoding_Hu_20260317_143025.csv`、`PilotCoding_Liu_20260317_143025.csv`
- **文件位置**：`Articles_Analyses/piloting/outputs/`
- 每个 PDF 目录的论文结果汇总在对应的 CSV 文件中，每个编码单元占一行
- 共生成 4 个独立的 CSV 文件
- 若 CSV 字段值包含逗号，用双引号包裹

---

### 步骤 5：生成研究类型频次统计 CSV

在所有编码 CSV 生成并验证后，**必须**生成一份汇总的研究类型频次统计表。

#### 5a. 统计维度

对**每个编码者的 CSV**（Hu/Liu/Shi/Wei）以及**合并后的总体**，分别统计以下频次：

1. **Study_Type 频次**：各 Study_Type 的行数（如 Exp=80, Survey=30, secondary-data=5, ...）
2. **Study_SubType 频次**：各 Study_SubType 的行数（如 Behavioral-Cog=50, Cross-Sectional=20, ...）
3. **Study_Type × Study_SubType 交叉频次**：每种 Type-SubType 组合的行数（如 Exp×Behavioral-Cog=50, Survey×Cross-Sectional=20, ...）

#### 5b. 输出格式

生成一个 CSV 文件，包含以下列：

```
Study_Type,Study_SubType,Hu,Liu,Shi,Wei,Total
```

- 每行为一个 `Study_Type × Study_SubType` 组合
- `Hu`/`Liu`/`Shi`/`Wei` 列为该编码者的频次计数
- `Total` 列为四位编码者的合计
- 按 `Study_Type`（Exp → Survey → case-study → secondary-data → non-empirical）、再按 `Study_SubType` 字母序排列
- 在每个 Study_Type 分组末尾添加一行小计（Study_SubType 填 `_subtotal`）
- 最末尾添加一行总计（Study_Type 和 Study_SubType 均填 `_total`）

#### 5c. 输出文件

- **文件名**：`StudyType_Frequency_<YYYYMMDD_HHmmss>.csv`（时间戳与编码 CSV 一致）
- **文件位置**：`Articles_Analyses/piloting/outputs/`

#### 5d. 终端输出摘要

在终端打印简要摘要表：

```
=== 研究类型频次统计 ===
                          Hu   Liu  Shi  Wei  Total
Exp                       XX   XX   XX   XX   XXX
  Behavioral-Social       XX   XX   XX   XX   XXX
  Behavioral-Cog          XX   XX   XX   XX   XXX
  Brain                   XX   XX   XX   XX   XXX
  Biol                    XX   XX   XX   XX   XXX
  Multimodal              XX   XX   XX   XX   XXX
  Intervention-RCT        XX   XX   XX   XX   XXX
  Intervention-Behavioral XX   XX   XX   XX   XXX
  Intervention-Brain      XX   XX   XX   XX   XXX
Survey                    XX   XX   XX   XX   XXX
  Cross-Sectional         XX   XX   XX   XX   XXX
  Longitudinal            XX   XX   XX   XX   XXX
  ESM                     XX   XX   XX   XX   XXX
  Interview               XX   XX   XX   XX   XXX
  Field                   XX   XX   XX   XX   XXX
case-study                XX   XX   XX   XX   XXX
secondary-data            XX   XX   XX   XX   XXX
non-empirical             XX   XX   XX   XX   XXX
─────────────────────────────────────────────────
Total                     XX   XX   XX   XX   XXX
```

---

### 步骤 6：自动触发差异比较（仅 Hu 目录）

Hu 目录的 CSV 生成并通过验证后，**自动调用 `comparison-report` 技能**，将新生成的 `PilotCoding_Hu_<timestamp>.csv` 与基准文件 `PilotingCoding_Hu.xlsx` 进行差异比较。

#### 触发条件

- `PilotCoding_Hu_<timestamp>.csv` 已生成且通过步骤 4 验证
- 基准文件 `Articles_Analyses/piloting/PilotingCoding_Hu.xlsx` 存在

#### 执行方式

等价于用户手动执行：
```
/comparison-report Articles_Analyses/piloting/outputs/PilotCoding_Hu_<timestamp>.csv
```

比较报告将输出到 `Articles_Analyses/piloting/outputs/Comparison/CompReport_<timestamp>.md`，包含 2A/2B 差异分类。

#### 为什么仅比较 Hu

当前仅 Hu 目录有对应的基准 xlsx 文件。其他编码者（Liu/Shi/Wei）的基准文件建立后，可扩展此步骤。

---

## 使用示例

```
/pilot-coding
```

执行后将：
1. 依次扫描 `PDF_Hu/`、`PDF_Liu/`、`PDF_Shi/`、`PDF_Wei/` 下所有文件
2. 逐篇读取并提取元数据（构建 Article_ID、识别 Study 结构、逐行提取）
3. 每个目录的结果分别汇总到对应的 CSV 文件中（共 4 个 CSV）
4. 所有 CSV 保存到 `Articles_Analyses/piloting/outputs/`
5. 对每个 CSV 执行后验证，输出完整性报告
6. 生成研究类型频次统计 CSV（`StudyType_Frequency_<timestamp>.csv`）
7. 自动对 Hu CSV 执行差异比较，生成 `CompReport_<timestamp>.md`
