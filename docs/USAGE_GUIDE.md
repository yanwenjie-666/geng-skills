# 📖 Geng Skill 多平台使用指南

> 本文档详细说明 Geng Skill 在各主流 AI 编程助手和开发环境中的使用方法。

---

## 目录

1. [通用命令行使用](#1-通用命令行使用)
2. [在 Claude (Anthropic) 中使用](#2-在-claude-anthropic-中使用)
3. [在 Cursor 中使用](#3-在-cursor-中使用)
4. [在 ChatGPT / GPT-4 中使用](#4-在-chatgpt--gpt-4-中使用)
5. [在 OpenAI Codex / API 中使用](#5-在-openai-codex--api-中使用)
6. [在 GitHub Copilot 中使用](#6-在-github-copilot-中使用)
7. [在 Jupyter Notebook 中使用](#7-在-jupyter-notebook-中使用)
8. [作为 Python 库导入使用](#8-作为-python-库导入使用)
9. [CI/CD 自动化集成](#9-cicd-自动化集成)

---

## 1. 通用命令行使用

### 1.1 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/geng-skill.git
cd geng-skill

# 安装依赖
pip install -r requirements.txt
```

### 1.2 一键综合检测

```bash
cd scripts
python3 geng_assess.py \
  --input ../examples/fake_data_demo.csv \
  --domain biomedical \
  --output ../report/
```

**参数说明：**

| 参数 | 必填 | 说明 | 可选值 |
|------|------|------|--------|
| `--input` / `-i` | ✅ | 输入 CSV 文件路径 | 任意 .csv 文件 |
| `--domain` | ❌ | 研究领域（影响检测策略） | `biomedical`, `chemistry`, `physics`, `social_science`, `clinical`, `general` |
| `--output` / `-o` | ❌ | 输出报告目录 | 默认 `./report` |
| `--delimiter` / `-d` | ❌ | CSV 分隔符 | 默认 `,` |

### 1.3 单项检测

```bash
# 末位数字检测
python3 last_digit_test.py -i data.csv -c "column_name" -o result.json

# 本福特定律检测
python3 benford_test.py -i data.csv -c "measurement" -o result.json

# GRIM 测试（单个均值）
python3 grim_test.py --mean 3.47 --n 25 --scale "1-5" --decimals 2

# GRIM 测试（批量，从 JSON）
python3 grim_test.py -i batch_means.json -o grim_results.json

# 固定关系检测
python3 fixed_relation_test.py -i data.csv --col1 "group_a" --col2 "group_b"

# 小数位一致性检测
python3 decimal_consistency_test.py -i data.csv -c "value"

# 图像重复检测
python3 image_duplicate_test.py -i ./figures/ -t 0.85
```

### 1.4 输出格式

所有模块输出标准 JSON 格式，包含以下统一字段：

```json
{
  "test_name": "检测模块名称（中英文）",
  "status": "completed | insufficient_data | error",
  "risk_level": "low | medium | medium-high | high",
  "risk_score": 0-100,
  "interpretation": "中文可读解释",
  "...": "模块特定字段"
}
```

---

## 2. 在 Claude (Anthropic) 中使用

### 2.1 Claude Web / Claude Pro

**方法 A：直接粘贴数据让 Claude 分析**

```
我有以下实验数据，请用"耿同学"的方法帮我检查是否存在数据造假迹象：

sample,control,treatment_a,treatment_b
1,2.34,4.68,7.02
2,3.12,6.24,9.36
3,1.87,3.74,5.61
...

请检查：
1. 末位数字分布是否均匀
2. 各组数据之间是否存在固定比值或差值关系
3. 小数位模式是否异常
```

**方法 B：上传 CSV 文件让 Claude 用代码分析**

```
请帮我运行学术数据打假检测。我上传的 CSV 文件包含论文中的实验数据。
请用以下方法逐一检测：
- Last Digit Test（末位数字检测）
- Benford's Law Test（本福特定律检测）
- Fixed Relationship Detection（固定关系检测）
- Decimal Consistency Test（小数位一致性检测）

最后给出综合风险评分和建议。
```

### 2.2 Claude API (Artifacts / Tool Use)

```python
import anthropic

client = anthropic.Anthropic()

# 将 Geng Skill 的 SKILL.md 作为 system prompt
with open('SKILL.md', 'r') as f:
    skill_doc = f.read()

message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=f"你是学术数据打假助手。请严格按照以下 Skill 文档执行检测：\n\n{skill_doc}",
    messages=[{
        "role": "user",
        "content": "请对以下数据执行完整的 Geng 打假检测...[数据]"
    }]
)
```

### 2.3 Claude MCP (Model Context Protocol)

将 Geng Skill 注册为 MCP Server：

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "geng-skill": {
      "command": "python3",
      "args": ["/path/to/geng-skill/scripts/mcp_server.py"],
      "env": {}
    }
  }
}
```

---

## 3. 在 Cursor 中使用

### 3.1 作为 Cursor Rules 使用

在项目根目录创建 `.cursor/rules/geng-skill.mdc`：

```markdown
---
description: 学术数据打假检测工具
globs: ["*.csv", "*.xlsx", "data/**"]
alwaysApply: false
---

# Geng Skill — 学术数据打假检测

当用户要求检测数据是否造假时，按以下步骤执行：

1. 确认数据格式（CSV/Excel/直接粘贴）
2. 识别数值列
3. 对每个数值列执行：
   - 末位数字检测（卡方检验 vs 均匀分布）
   - 本福特定律检测（适用于跨数量级数据）
   - 小数位一致性检测
4. 对数值列两两执行：
   - 固定关系检测（差值/比值/线性）
5. 综合评分（0-100）并给出建议

核心原则：自然数据具有随机性，人为编造的数据会呈现不自然的规律性。
```

### 3.2 在 Cursor Chat 中使用

```
@geng-skill 请检测这份数据文件 data/experiment_results.csv 是否存在造假迹象

重点关注：
- 不同实验组之间是否有固定数学关系
- 末位数字分布是否正常
- 小数位模式是否异常
```

### 3.3 Cursor Composer 自动化

在 Cursor Composer 中直接引用脚本：

```
请运行 geng-skill/scripts/geng_assess.py 对 data/paper_results.csv 进行检测，
领域设为 biomedical，输出到 report/ 目录。
然后帮我解读报告中的关键发现。
```

---

## 4. 在 ChatGPT / GPT-4 中使用

### 4.1 ChatGPT Web (Code Interpreter / Advanced Data Analysis)

**步骤：**
1. 上传 CSV 数据文件
2. 同时上传 `scripts/` 目录下的 Python 脚本
3. 提示词：

```
我上传了一组学术论文数据和几个检测脚本。请按照以下步骤执行学术数据打假检测：

1. 先读取 CSV 数据，识别所有数值列
2. 对每个数值列运行 last_digit_test.py 中的 last_digit_test() 函数
3. 对适用的列运行 benford_test.py 中的 benford_test() 函数
4. 对所有数值列对运行 fixed_relation_test.py 中的 fixed_relation_test() 函数
5. 对每个数值列运行 decimal_consistency_test.py 中的 decimal_consistency_test() 函数

最后综合所有结果，给出：
- 综合风险评分（0-100）
- 关键发现（哪些数据可疑，为什么）
- 建议行动
```

### 4.2 GPT-4 API + Function Calling

```python
import openai
import json

# 定义 Geng Skill 工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "geng_last_digit_test",
            "description": "检测数据末位数字是否偏离均匀分布。自然数据末位应均匀分布，造假数据往往集中在某些数字。",
            "parameters": {
                "type": "object",
                "properties": {
                    "values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "待检测的数值列表（字符串形式保留精度）"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["all_digits", "decimal_last"],
                        "description": "检测方法"
                    }
                },
                "required": ["values"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "geng_fixed_relation_test",
            "description": "检测两组数据间是否存在固定差值、比值或完美线性关系。独立实验数据不应有精确数学关系。",
            "parameters": {
                "type": "object",
                "properties": {
                    "col1": {"type": "array", "items": {"type": "number"}, "description": "第一列数据"},
                    "col2": {"type": "array", "items": {"type": "number"}, "description": "第二列数据"},
                    "col1_name": {"type": "string"},
                    "col2_name": {"type": "string"}
                },
                "required": ["col1", "col2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "geng_benford_test",
            "description": "检测数据首位数字是否符合本福特定律。适用于跨多个数量级的自然数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "values": {"type": "array", "items": {"type": "string"}, "description": "数值列表"}
                },
                "required": ["values"]
            }
        }
    }
]

# 调用 GPT-4 带工具
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "你是学术数据打假助手，使用 Geng Skill 检测论文数据。"},
        {"role": "user", "content": "请检测以下数据..."}
    ],
    tools=tools,
    tool_choice="auto"
)
```

### 4.3 Custom GPT (GPTs Store)

创建自定义 GPT，在 Instructions 中粘贴完整的 `SKILL.md` 内容，并上传所有脚本文件作为 Knowledge。

**GPT 名称建议**: "学术数据卫士 — Geng Fraud Detector"

**Instructions 要点**：
```
你是基于"耿同学"方法论的学术数据打假检测 GPT。
当用户上传数据或粘贴数据时，自动执行以下检测流程...
```

---

## 5. 在 OpenAI Codex / API 中使用

### 5.1 Codex CLI

```bash
# 安装 Codex CLI
npm install -g @openai/codex

# 使用 Geng Skill 检测数据
codex "请对 data.csv 文件运行学术数据打假检测：\
  1. 读取所有数值列 \
  2. 检测末位数字分布 \
  3. 检测列间固定关系 \
  4. 给出风险评分" \
  --file data.csv \
  --file scripts/last_digit_test.py \
  --file scripts/fixed_relation_test.py
```

### 5.2 Codex 作为自动化 Agent

```python
# codex_geng_agent.py
"""
将 Geng Skill 封装为 Codex Agent 可调用的工具链
"""
import subprocess
import json

def run_geng_assessment(csv_path, domain="general"):
    """调用 Geng 综合评估引擎"""
    result = subprocess.run(
        ["python3", "scripts/geng_assess.py",
         "--input", csv_path,
         "--domain", domain,
         "--output", "./report/"],
        capture_output=True, text=True
    )
    
    # 读取报告
    with open("./report/geng_assessment_report.json", "r") as f:
        report = json.load(f)
    
    return report
```

---

## 6. 在 GitHub Copilot 中使用

### 6.1 Copilot Chat in VS Code

在 VS Code 中打开数据文件，然后使用 Copilot Chat：

```
@workspace /explain 请分析 data.csv 中的数据是否存在学术造假迹象，
使用 geng-skill/scripts/ 中的检测模块
```

### 6.2 Copilot in Terminal

```bash
# GitHub Copilot CLI
gh copilot suggest "run geng academic fraud detection on experiment_data.csv"
```

### 6.3 作为 GitHub Action

```yaml
# .github/workflows/geng-check.yml
name: Academic Data Integrity Check

on:
  pull_request:
    paths:
      - 'data/**/*.csv'

jobs:
  geng-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r geng-skill/requirements.txt
      
      - name: Run Geng Assessment
        run: |
          cd geng-skill/scripts
          for csv_file in $(find ../../data -name "*.csv"); do
            echo "🔍 Checking: $csv_file"
            python3 geng_assess.py -i "$csv_file" -o ../../report/
          done
      
      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: geng-report
          path: report/
```

---

## 7. 在 Jupyter Notebook 中使用

```python
# Cell 1: 安装与导入
!pip install numpy scipy Pillow scikit-image -q

import sys
sys.path.insert(0, '../scripts')

from last_digit_test import last_digit_test
from benford_test import benford_test
from fixed_relation_test import fixed_relation_test
from decimal_consistency_test import decimal_consistency_test
from grim_test import grim_test_single, grim_test_batch

import pandas as pd
import json

# Cell 2: 加载数据
df = pd.read_csv('../examples/fake_data_demo.csv')
print(f"数据形状: {df.shape}")
df.head()

# Cell 3: 末位数字检测
result = last_digit_test(df['control_group'].astype(str).tolist())
print(json.dumps(result, ensure_ascii=False, indent=2))

# Cell 4: 固定关系检测
result = fixed_relation_test(
    df['control_group'].tolist(),
    df['treatment_a'].tolist(),
    'control_group', 'treatment_a'
)
print(f"🎯 风险评分: {result['risk_score']}/100")
print(f"📝 {result['interpretation']}")

# Cell 5: 可视化
import matplotlib.pyplot as plt
import numpy as np

fig, axes = plt.subplots(1, 3, figsize=(15, 4))

# 散点图：展示固定比值关系
axes[0].scatter(df['control_group'], df['treatment_a'], c='red', alpha=0.7)
axes[0].set_xlabel('Control Group')
axes[0].set_ylabel('Treatment A')
axes[0].set_title('⚠️ 完美 2x 关系')
axes[0].plot([0, 6], [0, 12], 'k--', alpha=0.3)

# 末位数字分布
from collections import Counter
digits = [int(str(v)[-1]) for v in df['control_group'].astype(str)]
counts = Counter(digits)
axes[1].bar(range(10), [counts.get(i, 0) for i in range(10)])
axes[1].axhline(y=len(digits)/10, color='r', linestyle='--', label='期望值')
axes[1].set_xlabel('末位数字')
axes[1].set_ylabel('频次')
axes[1].set_title('末位数字分布')
axes[1].legend()

# 比值分布
ratios = df['treatment_a'] / df['control_group']
axes[2].hist(ratios, bins=20, edgecolor='black')
axes[2].set_xlabel('Treatment_A / Control')
axes[2].set_ylabel('频次')
axes[2].set_title(f'⚠️ 比值全部 = {ratios.mean():.1f}')

plt.tight_layout()
plt.savefig('../report/detection_visualization.png', dpi=150)
plt.show()
```

---

## 8. 作为 Python 库导入使用

### 8.1 基础用法

```python
import sys
sys.path.insert(0, '/path/to/geng-skill/scripts')

from last_digit_test import last_digit_test
from benford_test import benford_test
from fixed_relation_test import fixed_relation_test
from decimal_consistency_test import decimal_consistency_test
from grim_test import grim_test_single

# 单列检测
values = ['2.34', '3.12', '1.87', '4.56', '2.98']
result = last_digit_test(values)
print(f"风险评分: {result['risk_score']}")

# 两列关系检测
col_a = [2.34, 3.12, 1.87, 4.56, 2.98]
col_b = [4.68, 6.24, 3.74, 9.12, 5.96]
result = fixed_relation_test(col_a, col_b, 'GroupA', 'GroupB')
print(f"风险等级: {result['risk_level']}")

# GRIM 测试
result = grim_test_single(mean='3.47', n=25, decimals=2, scale_min=1, scale_max=5)
print(f"一致性: {result['consistent']}")
```

### 8.2 批量处理多篇论文

```python
import os
import glob
import json
from geng_assess import run_assessment

# 批量检测目录下所有 CSV
csv_files = glob.glob('/path/to/papers/*/data.csv')

results = []
for csv_path in csv_files:
    paper_name = os.path.basename(os.path.dirname(csv_path))
    report = run_assessment(csv_path, domain='biomedical')
    results.append({
        'paper': paper_name,
        'score': report['summary']['overall_risk_score'],
        'level': report['summary']['overall_risk_level']
    })
    print(f"  {paper_name}: {report['summary']['overall_risk_level_cn']}")

# 排序输出高风险论文
results.sort(key=lambda x: x['score'], reverse=True)
print("\n🔴 高风险论文：")
for r in results:
    if r['score'] >= 50:
        print(f"  [{r['score']:.0f}] {r['paper']}")
```

---

## 9. CI/CD 自动化集成

### 9.1 Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: geng-data-check
        name: Geng Academic Data Check
        entry: python3 geng-skill/scripts/geng_assess.py
        language: python
        files: '\.csv$'
        args: ['--input']
```

### 9.2 Docker 容器化

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ ./scripts/
COPY SKILL.md .

ENTRYPOINT ["python3", "scripts/geng_assess.py"]
CMD ["--help"]
```

```bash
# 构建与运行
docker build -t geng-skill .
docker run -v $(pwd)/data:/data geng-skill -i /data/paper.csv -o /data/report/
```

---

## 常见问题

### Q: 数据量有什么要求？

| 检测模块 | 最小数据量 | 推荐数据量 |
|----------|-----------|-----------|
| 末位数字检测 | 10 | 50+ |
| 本福特定律 | 30 | 100+ |
| GRIM 测试 | 1（单项） | N/A |
| 固定关系检测 | 5对 | 20+ 对 |
| 小数位一致性 | 5 | 30+ |
| 图像重复 | 2张 | 10+ 张 |

### Q: 支持什么输入格式？

- ✅ CSV（默认逗号分隔，可指定其他分隔符）
- ✅ 直接传入数值列表（Python API）
- ✅ JSON（GRIM 批量测试）
- ✅ 图片目录（PNG/JPG/TIF/BMP）
- ❌ Excel（需先转 CSV）
- ❌ PDF（需先提取数据表格）

### Q: 如何降低误报率？

1. 确认数据范围是否适合该检测（如本福特需跨数量级）
2. 多模块交叉验证，不要仅凭单一结果下结论
3. 考虑合理解释：仪器精度限制、数据预处理步骤等
4. 结果需领域专家复核

---

*Geng Skill v1.0.0 — 致敬"耿同学讲故事"*
