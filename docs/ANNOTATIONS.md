# 🏷️ Geng Skill 代码注释规范与架构说明

> 本文档提供完整的代码注释体系、模块间关系、接口规范，供开发者和 AI Agent 使用。

---

## 1. 项目架构总览

```
                    ┌──────────────────────────────┐
                    │       geng_assess.py          │
                    │    (综合评估引擎 / 主入口)     │
                    └──────────────┬───────────────┘
                                   │
           ┌───────────┬───────────┼───────────┬───────────┐
           ▼           ▼           ▼           ▼           ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐
    │last_digit  │ │ benford    │ │  grim      │ │fixed_rel   │ │decimal_cons  │
    │_test.py    │ │_test.py    │ │_test.py    │ │_test.py    │ │_test.py      │
    │            │ │            │ │            │ │            │ │              │
    │末位数字检测│ │本福特定律  │ │均值一致性  │ │固定关系检测│ │小数位一致性  │
    └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────────┘
           │                                            │
           │            ┌────────────────┐              │
           └───────────▶│image_duplicate │◀─────────────┘
                        │_test.py        │
                        │图像重复检测    │
                        └────────────────┘
```

---

## 2. 模块接口规范 (API Contract)

### 2.1 通用接口模式

每个检测模块都遵循统一的函数签名模式：

```python
def <module_name>_test(
    values: List[str | float],     # 输入数据
    **kwargs                        # 模块特定参数
) -> Dict[str, Any]:               # 标准化输出
    """
    [模块名称] — [一句话描述]
    
    Parameters
    ----------
    values : list
        待检测数据。字符串形式传入以保留原始精度。
    **kwargs : dict
        模块特定参数（详见各模块文档）
    
    Returns
    -------
    dict
        标准化输出，必含字段：
        - test_name : str — 模块名称（中英文）
        - status : str — "completed" | "insufficient_data" | "error"
        - risk_level : str — "low" | "medium" | "medium-high" | "high"
        - risk_score : float — 0-100 风险评分
        - interpretation : str — 中文可读解释
    """
```

### 2.2 各模块特定接口

#### Module 1: `last_digit_test()`

```python
def last_digit_test(
    values: List[str],
    method: str = 'all_digits'    # 'all_digits' | 'decimal_last'
) -> Dict:
    """
    末位数字检测
    
    特定输出字段:
    - digit_distribution : Dict[str, int]  — 0-9 各数字出现次数
    - chi_square : float                    — 卡方统计量
    - p_value : float                       — p值
    - most_frequent_digit : int             — 出现最多的数字
    - most_frequent_proportion : float      — 最高频率
    - uniformity_deviation : float          — 偏离均匀度 (0-1)
    """
```

#### Module 2: `benford_test()`

```python
def benford_test(
    values: List[str],
    order: int = 1               # 1=首位, 2=前两位
) -> Dict:
    """
    本福特定律检测
    
    前提条件: 数据应跨越至少1个数量级
    
    特定输出字段:
    - distribution : Dict[str, Dict]  — 各位数字观测/期望频率
    - mean_absolute_deviation : float — MAD (Nigrini 判定标准)
    - conformity : str                — 'close'|'acceptable'|'marginal'|'nonconforming'
    - conformity_cn : str             — 中文符合性判定
    """
```

#### Module 3: `grim_test_single()` / `grim_test_batch()`

```python
def grim_test_single(
    mean: str,          # 报告的平均值（字符串保留精度）
    n: int,             # 样本量
    decimals: int = 2,  # 报告的小数位数
    scale_min: int = None,  # 量表下限
    scale_max: int = None   # 量表上限
) -> Dict:
    """
    GRIM 单项测试
    
    特定输出字段:
    - consistent : bool         — 是否通过一致性检验
    - computed_sum : float      — 计算的总和 (mean × n)
    - nearest_valid_mean : str  — 最近的合法均值
    - difference : float        — 与最近合法均值的差距
    """

def grim_test_batch(
    items: List[Dict]   # 批量项目列表
) -> Dict:
    """
    GRIM 批量测试
    
    items 格式: [{"mean": "3.47", "n": 25, "decimals": 2, "label": "Table 1"}, ...]
    
    特定输出字段:
    - total_items : int
    - inconsistent_items : int
    - inconsistency_rate : float
    - details : List[Dict]      — 每项的详细结果
    """
```

#### Module 4: `fixed_relation_test()`

```python
def fixed_relation_test(
    col1: List[float],      # 第一列数据
    col2: List[float],      # 第二列数据
    col1_name: str = 'A',   # 列名标签
    col2_name: str = 'B'    # 列名标签
) -> Dict:
    """
    固定关系检测 — ⭐ 核心模块（耿同学最常用的方法）
    
    检测内容:
    1. 固定差值 (col2 - col1 = 常数?)
    2. 固定比值 (col2 / col1 = 常数?)
    3. 完美线性关系 (R² → 1.0?)
    4. 小数模式一致性
    
    特定输出字段:
    - detections : Dict — 各子检测结果
      - fixed_difference : {is_fixed, is_exact, mean_difference, std_difference}
      - fixed_ratio : {is_fixed, is_exact, mean_ratio, std_ratio}
      - linear_relationship : {r_squared, slope, intercept, is_suspicious}
      - decimal_pattern : {match_rate, is_suspicious}
    - n_suspicious_patterns : int
    """
```

#### Module 5: `decimal_consistency_test()`

```python
def decimal_consistency_test(
    values: List[str]    # 保留原始字符串精度
) -> Dict:
    """
    小数位一致性检测
    
    特定输出字段:
    - decimal_places_analysis : Dict    — 小数位数分布
    - decimal_repetition : Dict         — 小数模式重复度
    - position_digit_analysis : Dict    — 各位数字分布检验
    - autocorrelation : float           — 小数部分自相关
    - risk_factors : List[str]          — 触发的风险因子
    """
```

#### Module 6: `find_duplicates()`

```python
def find_duplicates(
    image_dir: str,           # 图片目录
    threshold: float = 0.85,  # 相似度阈值
    extensions: List[str] = None  # 图片格式
) -> Dict:
    """
    图像重复检测
    
    依赖: Pillow, scikit-image (可选, 用于SSIM)
    
    特定输出字段:
    - n_images_scanned : int
    - n_duplicate_pairs : int
    - duplicates : List[Dict]  — 每对疑似重复图片
      - file_1, file_2 : str
      - avg_hash_similarity : float
      - diff_hash_similarity : float
      - combined_similarity : float
      - rotation_check : Dict  — 旋转/翻转匹配结果
      - ssim : float (如果 scikit-image 可用)
    """
```

---

## 3. 代码注释规范

### 3.1 文件头注释模板

每个 Python 文件必须包含以下格式的文件头：

```python
#!/usr/bin/env python3
"""
[模块名称中文] ([Module Name English])
{'='*len(module_name)}

原理：[一段话描述检测原理]

方法：[具体使用的统计方法]

参考：[关键参考文献，一行一条]

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""
```

### 3.2 函数注释规范 (NumPy Style)

```python
def function_name(param1, param2, param3=default):
    """
    [一句话功能描述]
    
    [详细说明段落，解释为什么需要这个函数、在什么场景下使用]
    
    Parameters
    ----------
    param1 : type
        参数说明
    param2 : type
        参数说明
    param3 : type, optional
        参数说明（默认值：default）
    
    Returns
    -------
    return_type
        返回值说明
    
    Raises
    ------
    ValueError
        何时抛出此异常
    
    Examples
    --------
    >>> result = function_name([1, 2, 3])
    >>> print(result['risk_score'])
    15.3
    
    Notes
    -----
    [重要注意事项、使用限制、已知问题]
    
    References
    ----------
    [1] Author (Year). Title. Journal. DOI.
    """
```

### 3.3 行内注释规范

```python
# ✅ 好的注释 — 解释"为什么"
# 本福特定律只适用于跨数量级的数据，pH值（0-14）不适用
if value_range < 10:
    return skip_benford()

# ❌ 差的注释 — 重复代码
# 计算平均值
mean = sum(values) / len(values)

# ✅ 好的注释 — 标注算法来源
# MAD 阈值参考 Nigrini (2012), Table 7.1
# Close conformity: MAD < 0.006
MAD_THRESHOLD_CLOSE = 0.006
```

---

## 4. 错误处理与边界条件

### 4.1 标准错误返回

```python
# 数据不足
if len(values) < MIN_REQUIRED:
    return {
        'status': 'insufficient_data',
        'message': f'数据量不足（仅{len(values)}个），需要至少{MIN_REQUIRED}个',
        'n_valid': len(values)
    }

# 输入格式错误
if not valid_input:
    return {
        'status': 'error',
        'message': f'无效输入: {error_detail}'
    }
```

### 4.2 边界条件处理

| 场景 | 处理方式 |
|------|----------|
| 全部值为0 | 跳过本福特检测（返回 status='not_applicable'） |
| 无小数部分 | 跳过小数位检测 |
| 仅1列数值 | 跳过固定关系检测 |
| 图片目录为空 | 返回 insufficient_data |
| 极端离群值 | 不剔除，但在 notes 中标注 |
| NaN/无效值 | 静默跳过，在 n_valid 中反映 |

---

## 5. 风险评分算法详解

### 5.1 单模块评分

```python
"""
风险评分映射逻辑（以末位数字检测为例）：

    p >= 0.05    → risk_score = 40 * (1 - p)     ∈ [0, ~38]   → "low"
    0.01 <= p < 0.05  → risk_score = 40 + ...    ∈ [40, 60]   → "medium"
    0.001 <= p < 0.01 → risk_score = 60 + ...    ∈ [60, 80]   → "medium-high"
    p < 0.001    → risk_score = 80 + ...          ∈ [80, 100]  → "high"

设计考量：
- 不直接使用 1-p 作为分数（会导致 p=0.04 和 p=0.06 差距过小）
- 分段线性映射，确保跨越统计显著性阈值时有明显跳变
- 上限 100 永远不精确达到（留有余地表示"不确定性"）
"""
```

### 5.2 综合评分算法

```python
"""
综合评分 = 0.6 × max(各模块分数) + 0.4 × mean(各模块分数)

设计理由：
- 加权最大值确保"只要有一个模块高度异常，综合分就不会太低"
- 加权平均确保"如果多个模块都略有异常，综合分会累积上升"
- 0.6/0.4 比例经验性确定，偏向保守（避免漏检重于避免误报）

特殊规则：
- 如果固定关系检测发现 is_exact=True，直接 risk_score = max(score, 90)
- 如果图像检测发现 similarity > 0.98，直接 risk_score = max(score, 90)
"""
```

---

## 6. 测试用例规范

### 6.1 单元测试结构

```python
# tests/test_modules.py

"""
测试策略：
1. 已知正常数据 → 应返回 low risk
2. 已知造假数据 → 应返回 high risk
3. 边界条件 → 应优雅处理
4. 回归测试 → 固定输入，固定输出
"""

def test_last_digit_uniform_data():
    """均匀分布数据应返回低风险"""
    import random
    random.seed(42)
    values = [str(random.uniform(1, 100)) for _ in range(100)]
    result = last_digit_test(values)
    assert result['risk_level'] == 'low'
    assert result['risk_score'] < 30

def test_fixed_relation_exact_ratio():
    """精确固定比值应返回极高风险"""
    col1 = [1.23, 2.34, 3.45, 4.56, 5.67]
    col2 = [2.46, 4.68, 6.90, 9.12, 11.34]  # 精确 ×2
    result = fixed_relation_test(col1, col2)
    assert result['risk_level'] == 'high'
    assert result['risk_score'] >= 85

def test_grim_consistent():
    """合法均值应通过 GRIM"""
    # n=20, 整数数据, mean=3.40 → sum=68 ✓
    result = grim_test_single('3.40', 20, decimals=2)
    assert result['consistent'] == True

def test_grim_inconsistent():
    """非法均值应失败"""
    # n=20, 整数数据, mean=3.47 → sum=69.4 ✗
    result = grim_test_single('3.47', 20, decimals=2)
    assert result['consistent'] == False
```

---

## 7. AI Agent 集成注释

### 7.1 Prompt Engineering 标注

每个模块的 docstring 设计为可被 AI Agent 直接解析：

```python
"""
[AGENT_INSTRUCTION]
当用户要求检测数据造假时，按以下优先级选择模块：
1. 如果用户提供了两组"应该独立"的数据 → fixed_relation_test()
2. 如果数据跨越多个数量级 → benford_test()
3. 如果数据含小数 → decimal_consistency_test() + last_digit_test()
4. 如果用户提供了均值和样本量 → grim_test_single()
5. 如果有图片文件 → find_duplicates()
6. 一键全检 → geng_assess.py

[AGENT_OUTPUT_FORMAT]
向用户展示结果时，使用以下格式：
- 先给出综合评分和风险等级（一句话）
- 然后列出关键发现（使用 emoji 标注严重度）
- 最后给出建议行动（编号列表）
- 始终附上免责声明
"""
```

### 7.2 Tool Definition 标注

```python
"""
[TOOL_DEFINITION]
name: geng_fraud_detection
description: |
  基于统计学原理检测学术论文数据是否存在造假迹象。
  支持末位数字检测、本福特定律、GRIM测试、固定关系检测、
  小数位一致性检测和图像重复检测。
  灵感来源于2026年"耿同学讲故事"的技术流打假方法论。
input_schema:
  type: object
  properties:
    data:
      type: array
      description: 数据行列表，或 CSV 文件路径
    domain:
      type: string
      enum: [biomedical, chemistry, physics, social_science, clinical, general]
    modules:
      type: array
      items:
        type: string
        enum: [last_digit, benford, grim, fixed_relation, decimal, image]
      description: 指定运行哪些模块（默认全部）
output_schema:
  type: object
  properties:
    overall_risk_score: {type: number, min: 0, max: 100}
    overall_risk_level: {type: string}
    findings: {type: array, items: {type: string}}
    recommendations: {type: array, items: {type: string}}
"""
```

---

## 8. 性能与限制

### 8.1 时间复杂度

| 模块 | 时间复杂度 | 1000行数据耗时 |
|------|-----------|---------------|
| last_digit_test | O(n) | <10ms |
| benford_test | O(n) | <10ms |
| grim_test_batch | O(k) per item | <1ms/item |
| fixed_relation_test | O(n) per pair | <10ms |
| decimal_consistency_test | O(n) | <20ms |
| image_duplicate_test | O(m²) m=图片数 | ~1s/100张 |
| geng_assess (综合) | O(n × c²) c=列数 | <500ms |

### 8.2 已知限制

| 限制 | 影响 | 缓解方案 |
|------|------|----------|
| 数据量<30时统计效力低 | 本福特检测可能不准 | 自动标注 "统计效力有限" |
| 不支持时间序列自相关 | 遗漏趋势数据伪造 | v1.1 计划增加 |
| 固定关系仅检测两列 | 三列以上复杂关系漏检 | 通过两两组合覆盖 |
| 图像检测仅用全局特征 | 局部篡改可能漏检 | v1.2 计划增加分块检测 |
| 无法检测"高明造假" | 统计上完美的伪造数据 | 无银弹，需多维度交叉 |

---

*Geng Skill v1.0.0 — 代码注释与架构标准化文档*
