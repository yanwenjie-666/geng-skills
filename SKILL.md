# Geng Skill — 学术数据打假检测工具

> 致敬"耿同学讲故事"——用数据说话，让造假无所遁形。

## 概述

本 Skill 实现了一套**基于统计学原理的学术论文数据造假检测方法**，灵感来源于科普博主"耿同学"的技术流打假方法论。该工具从数据层面对论文中的实验数据进行多维度异常检测，适用于生物医学、化学、物理、社会科学等多个领域。

## 核心原理

**自然数据具有随机性，人为编造的数据会呈现不自然的规律性。**

当研究者伪造实验数据时，由于人脑无法真正生成随机数，编造的数据往往会暴露以下统计学破绽：

1. **末位数字分布异常** — 自然数据末位数字应近似均匀分布
2. **固定差值/比例关系** — 不同实验组数据间存在恒定数学关系
3. **小数位一致性过高** — 多组数据小数点后位数高度一致
4. **本福特定律偏离** — 首位数字分布严重偏离理论预期
5. **GRIM/SPRITE 不一致** — 报告的平均值与样本量不兼容
6. **图像重复/篡改** — 同一图片出现在不同实验条件下

## 适用领域

| 领域 | 检测重点 | 典型数据类型 |
|------|----------|--------------|
| 生物医学 | Western blot、流式细胞术、动物实验数据 | 连续测量值、图像 |
| 化学 | 光谱数据、反应产率、催化活性 | 数值序列 |
| 物理/材料 | 性能曲线、电学/力学测试数据 | 时间序列 |
| 社会科学 | 问卷数据、量表得分 | 离散整数值 |
| 临床医学 | 生存数据、临床指标 | 分组统计量 |

## 使用方法

### 输入

- 论文 PDF 文件（或提取的数据表格）
- 补充材料 / Source Data（如有）
- 指定检测领域（用于选择合适的检测策略）

### 检测流程

```
输入论文 → 数据提取 → 多维度异常检测 → 综合评分 → 生成报告
```

### 输出

- **异常检测报告**：每项检测的结果、p值、置信度
- **综合风险评分**：0-100 分，分为低/中/高/极高风险
- **可视化图表**：分布直方图、偏离热力图
- **建议行动**：需要进一步核查的具体数据点

## 检测模块

### Module 1: 末位数字检测 (Last Digit Test)

```bash
python3 scripts/last_digit_test.py --input data.csv --column "value"
```

原理：自然实验数据的末位数字（0-9）应近似均匀分布。卡方检验判断偏离程度。

### Module 2: 本福特定律检测 (Benford's Law Test)

```bash
python3 scripts/benford_test.py --input data.csv --column "value"
```

原理：多数量级跨度的自然数据，首位数字以1开头的概率约30.1%，逐位递减至9的4.6%。

### Module 3: GRIM 测试 (Granularity-Related Inconsistency of Means)

```bash
python3 scripts/grim_test.py --mean 3.47 --n 25 --scale "1-5" --decimals 2
```

原理：对于整数取值数据，给定样本量 n，合法的平均值只能取特定的有限集合。

### Module 4: 固定关系检测 (Fixed Relationship Detection)

```bash
python3 scripts/fixed_relation_test.py --input data.csv --col1 "group_a" --col2 "group_b"
```

原理：两组独立实验数据之间不应存在恒定的差值、比值或线性关系。

### Module 5: 小数位一致性检测 (Decimal Consistency Test)

```bash
python3 scripts/decimal_consistency_test.py --input data.csv --column "value"
```

原理：实验测量数据的小数位后数字应具有随机性，过度一致暗示人为编造。

### Module 6: 图像重复检测 (Image Duplication Detection)

```bash
python3 scripts/image_duplicate_test.py --input_dir ./figures/ --threshold 0.85
```

原理：基于感知哈希和 SSIM 相似度，检测论文图片中是否存在重复使用或篡改。

### Module 7: 综合评估引擎 (Comprehensive Assessment)

```bash
python3 scripts/geng_assess.py --input data.csv --domain "biomedical" --output report/
```

一键运行所有适用模块，生成综合报告。

## 风险评分体系

| 等级 | 分数 | 含义 |
|------|------|------|
| 🟢 低风险 | 0-25 | 数据未发现明显异常 |
| 🟡 中风险 | 26-50 | 存在可疑模式，建议人工复核 |
| 🟠 高风险 | 51-75 | 多项检测异常，强烈建议深入调查 |
| 🔴 极高风险 | 76-100 | 系统性异常，高度疑似数据造假 |

## 重要声明

⚠️ **本工具仅用于辅助筛查，不能作为造假的最终判定依据。**

- 数据异常 ≠ 数据造假（可能是仪器校准、单位转换、排版错误等）
- 检测结果需要领域专家复核
- 不应基于单一检测模块的结果下结论
- 使用本工具时应遵守学术伦理和法律法规
- 建议将检测结果提交给相关机构进行正式调查

## 参考文献

1. Benford, F. (1938). The law of anomalous numbers. *Proceedings of the American Philosophical Society*, 78(4), 551-572.
2. Brown, N.J.L., & Heathers, J.A.J. (2017). The GRIM Test: A Simple Technique Detects Numerous Anomalies in the Reporting of Results in Psychology. *Social Psychological and Personality Science*, 8(4), 363-369.
3. 余菁等 (2021). 科技论文数据造假的核查策略和统计学方法验证. *中国科技期刊研究*, 32(6), 770-776.
4. Bik, E.M., et al. (2016). The prevalence of inappropriate image duplication in biomedical research publications. *mBio*, 7(3), e00809-16.

## 版本

- v1.0.0 — 2026-05-20 — 初始版本，致敬耿同学
