# 📚 数据来源与参考文献标准化文档

> Geng Skill v1.0.0 — 学术数据打假检测工具

---

## 1. 方法论来源

### 1.1 直接灵感来源

| 来源 | 描述 | 时间 |
|------|------|------|
| **耿同学讲故事** (B站/抖音科普博主) | 吉林大学生物学硕士、北航博士五年级退学。2026年4月起连续举报多所985高校教授论文造假，核心方法：末位数字集中度检测、固定差值/比例关系检测、AI图片查重 | 2026-04 至今 |
| **澎湃新闻评论** | 《学术打假需要"耿同学"，更需要长效机制建设》— 详述耿同学方法论 | 2026-05-16 |
| **虎嗅网** | 《我Skill化了耿同学的"学术打假方法论"，致敬》— 方法论结构化梳理 | 2026-05-08 |

### 1.2 耿同学核心方法总结

```
┌────────────────────────────────────────────────────────────────┐
│  耿同学打假方法论（从公开报道中提取）                           │
├────────────────────────────────────────────────────────────────┤
│  1. 末位数字集中度 — 某些数字出现频率异常高                    │
│  2. 两列数据间固定差值/比例 — 不同组数据存在恒定数学关系       │
│  3. 小数点后位数高度一致 — 编造数据的小数位呈现不自然规律      │
│  4. AI图片查重 — 同一图片在不同实验条件下重复使用             │
│  5. 从PDF/Source Data/图片/表格多维度扒取证据                  │
│  6. 卡方检验等统计学方法验证异常的显著性                       │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. 统计学理论基础

### 2.1 本福特定律 (Benford's Law)

| 字段 | 内容 |
|------|------|
| **原始论文** | Benford, F. (1938). The law of anomalous numbers. *Proceedings of the American Philosophical Society*, 78(4), 551-572. |
| **数学表述** | P(d) = log₁₀(1 + 1/d), d ∈ {1,2,...,9} |
| **适用条件** | 数据跨越多个数量级（至少1个）；数据量≥100为佳 |
| **不适用场景** | 范围有限的数据（百分比、pH值）；人为截断的数据 |
| **权威教材** | Nigrini, M.J. (2012). *Benford's Law: Applications for Forensic Accounting, Auditing, and Fraud Detection*. Wiley. ISBN: 978-1118152850 |
| **审计应用** | 美国注册欺诈审查师协会(ACFE)推荐用于财务审计 |
| **学术验证** | Diekmann, A. (2007). Not the first digit! Using Benford's law to detect fraudulent scientific data. *Journal of Applied Statistics*, 34(3), 321-329. |

### 2.2 GRIM 测试 (Granularity-Related Inconsistency of Means)

| 字段 | 内容 |
|------|------|
| **原始论文** | Brown, N.J.L., & Heathers, J.A.J. (2017). The GRIM Test: A Simple Technique Detects Numerous Anomalies in the Reporting of Results in Psychology. *Social Psychological and Personality Science*, 8(4), 363-369. DOI: 10.1177/1948550616673876 |
| **数学原理** | 对于整数取值数据，样本量为n时，合法均值只能是 k/n 形式（k为整数） |
| **适用条件** | 离散整数取值数据（李克特量表、计数数据） |
| **扩展** | SPRITE (Sample Parameter Reconstruction via Iterative TEchniques) — 更完整的数据重构验证 |
| **参考** | Heathers, J.A.J., et al. (2018). SPRITE: A Response to Anaya's Critique. DOI: 10.31234/osf.io/qfk7d |

### 2.3 末位数字均匀分布检验

| 字段 | 内容 |
|------|------|
| **理论基础** | 连续测量数据在足够精度下，末位数字应服从离散均匀分布 U(0,9) |
| **检验方法** | 皮尔逊卡方检验 (Pearson's chi-squared test), df=9 |
| **参考文献** | Mosimann, J.E., et al. (2002). Terminal digits and the examination of questioned data. *Accountability in Research*, 9(2), 75-92. |
| **典型案例** | Hill, T.P. (1998). The first digit phenomenon. *American Scientist*, 86, 358-363. |

### 2.4 图像重复检测

| 字段 | 内容 |
|------|------|
| **里程碑论文** | Bik, E.M., Casadevall, A., & Fang, F.C. (2016). The prevalence of inappropriate image duplication in biomedical research publications. *mBio*, 7(3), e00809-16. DOI: 10.1128/mBio.00809-16 |
| **发现** | 分析20,621篇论文，3.8%存在图片问题 |
| **技术方法** | 感知哈希(pHash)、差异哈希(dHash)、结构相似性(SSIM) |
| **工具参考** | ImageTwin, Proofig, STM Integrity Hub |

### 2.5 数据一致性综合检验

| 字段 | 内容 |
|------|------|
| **中文权威** | 余菁, 邬加佳, 孙慧兰等 (2021). 科技论文数据造假的核查策略和统计学方法验证. *中国科技期刊研究*, 32(6), 770-776. DOI: 10.11946/cjstp.202012221043 |
| **方法体系** | t检验、F检验、卡方检验、生存分析一致性 |
| **国际标准** | COPE (Committee on Publication Ethics) Guidelines on Research Data |

---

## 3. 检测模块与理论对应关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块名称              │  理论基础           │  统计方法        │  适用领域    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Last Digit Test       │  末位均匀分布       │  χ² 检验        │  全领域      │
│  Benford's Law Test    │  本福特定律         │  χ² + MAD       │  跨数量级    │
│  GRIM Test             │  离散粒度一致性     │  整除验证       │  社科/量表   │
│  Fixed Relation Test   │  独立性原理         │  比值/回归      │  全领域(核心) │
│  Decimal Consistency   │  随机性原理         │  自相关+χ²      │  全领域      │
│  Image Duplication     │  唯一性原理         │  哈希+SSIM      │  生物医学    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 已验证的真实案例

### 4.1 耿同学举报案例（2026年，已被机构确认）

| 案例 | 机构 | 期刊 | 问题类型 | 结果 |
|------|------|------|----------|------|
| 王平团队 | 同济大学生科院 | *Nature* | 系统性数据造假（固定数学关系、图片重复） | ✅ 确认，院长免职，第一作者解聘 |
| 陈佺团队 | 南开大学生科院 | *Nature* 子刊 | 数据异常 | 🔄 调查中 |
| 上海大学案例 | 上海大学 | — | 数据异常 | 🔄 调查中 |
| 中山大学案例 | 中山大学 | — | 数据异常 | 🔄 调查中 |

### 4.2 国际经典案例

| 案例 | 方法 | 年份 |
|------|------|------|
| Diederik Stapel (社会心理学) | GRIM + 统计不一致性 | 2011 |
| Paolo Macchiarini (再生医学) | 图像重复 + 数据伪造 | 2016 |
| Hwang Woo-suk (干细胞) | 图像篡改检测 | 2005 |
| Jan Hendrik Schön (物理) | 数据重复模式 | 2002 |

---

## 5. 数据标准与输入规范

### 5.1 CSV 输入格式标准

```
编码: UTF-8 (支持 UTF-8-BOM)
分隔符: 逗号 (默认), 可配置为 TAB/分号
表头: 必须有列名作为第一行
数值: 支持整数、小数、科学计数法
缺失值: 空字符串 (跳过处理)
```

**标准示例：**
```csv
sample_id,group,value,measurement,timepoint
1,control,2.34,12.5,0
2,control,3.12,15.8,0
3,treatment,4.68,25.0,24
```

### 5.2 GRIM 批量输入 JSON 格式

```json
[
  {
    "label": "Table 1, Row 1",
    "mean": "3.47",
    "n": 25,
    "decimals": 2,
    "scale_min": 1,
    "scale_max": 5
  },
  {
    "label": "Table 1, Row 2",
    "mean": "4.12",
    "n": 30,
    "decimals": 2,
    "scale_min": 1,
    "scale_max": 5
  }
]
```

### 5.3 图像输入规范

```
支持格式: PNG, JPG, JPEG, TIF, TIFF, BMP, GIF
最小尺寸: 32×32 像素
推荐: 原始分辨率（不要人为缩放）
组织方式: 所有待比较图片放在同一目录下
```

---

## 6. 输出标准化

### 6.1 JSON 输出 Schema

所有模块遵循统一输出结构：

```json
{
  "$schema": "geng-skill-output-v1",
  "test_name": "string — 模块名称（中英双语）",
  "status": "enum: completed | insufficient_data | error",
  "n_values": "integer — 有效数据点数",
  "risk_level": "enum: low | medium | medium-high | high",
  "risk_score": "number 0-100 — 风险评分",
  "p_value": "number — 统计检验p值（如适用）",
  "interpretation": "string — 中文可读解释（含emoji状态标识）",
  "...": "模块特定字段"
}
```

### 6.2 风险评分映射标准

| p-value 范围 | 风险等级 | 评分范围 | 颜色代码 | 建议动作 |
|-------------|----------|----------|----------|----------|
| p > 0.05 | low | 0-25 | 🟢 #00C853 | 无需干预 |
| 0.01 < p ≤ 0.05 | medium | 26-50 | 🟡 #FFD600 | 人工复核 |
| 0.001 < p ≤ 0.01 | medium-high | 51-75 | 🟠 #FF6D00 | 深入调查 |
| p ≤ 0.001 | high | 76-100 | 🔴 #D50000 | 正式举报 |

### 6.3 Markdown 报告标准

综合报告遵循以下结构：

```markdown
# 📋 Geng 学术数据打假检测报告
## 📊 综合评估结果（表格）
## 📝 结论（一段话）
## 💡 建议（编号列表）
## 🔬 各模块检测详情
### Module N: 模块名称
## ⚠️ 重要声明
```

---

## 7. 学术伦理与法律合规

### 7.1 合规框架

| 标准/规范 | 发布机构 | 相关性 |
|-----------|----------|--------|
| COPE Retraction Guidelines | 出版伦理委员会 | 论文撤稿/更正流程 |
| 科研诚信案件调查处理规则 | 中国科技部 (2019) | 国内学术不端处理 |
| ORI Research Integrity Guidelines | 美国研究诚信办公室 | 国际标准 |
| Singapore Statement | 全球科研诚信大会 | 负责任研究行为 |

### 7.2 使用伦理准则

1. **比例原则** — 检测强度应与嫌疑程度成正比
2. **无罪推定** — 异常 ≠ 造假，需完整证据链
3. **保密义务** — 未经确认的检测结果不应公开传播
4. **正式渠道** — 确认后应通过机构/期刊正式途径举报
5. **避免伤害** — 不应基于工具结果对个人进行网络攻击

### 7.3 免责声明

```
本工具仅提供统计学层面的异常筛查功能，输出结果为"疑点线索"而非
"造假定论"。使用者应当理解：
- 统计异常可能有合理解释（仪器精度、数据处理等）
- 本工具不具备法律效力
- 最终判定需要领域专家、原始数据核查和正式调查程序
- 使用者需自行承担因不当使用造成的后果
```

---

## 8. 版本与更新日志

### v1.0.0 (2026-05-20)

- 初始发布
- 6个核心检测模块
- 综合评估引擎
- 多平台使用指南
- 标准化输出格式

### 路线图

| 版本 | 计划功能 |
|------|----------|
| v1.1 | 增加 SPRITE 测试、生存数据一致性检验 |
| v1.2 | 支持 Excel 直接输入、PDF 表格自动提取 |
| v1.3 | Web UI 界面、RESTful API |
| v2.0 | AI 增强检测（LLM 辅助判断上下文合理性） |

---

## 9. 引用本工具

如果在学术工作中使用了本工具，请引用：

```bibtex
@software{geng_skill_2026,
  title = {Geng Skill: Academic Data Fraud Detection Toolkit},
  author = {Contributors},
  year = {2026},
  url = {https://github.com/YOUR_USERNAME/geng-skill},
  version = {1.0.0},
  note = {Inspired by the methodology of "Geng Tongxue" (耿同学讲故事)}
}
```

---

*Geng Skill — 让学术回归诚信，让数据说出真相。*
