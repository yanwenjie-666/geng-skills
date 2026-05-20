#!/usr/bin/env python3
"""
固定关系检测 (Fixed Relationship Detection)
============================================
原理：两组独立实验数据之间不应存在恒定的差值、比值或线性关系。
如果不同实验条件下的数据存在固定的数学关系，暗示数据可能是
从单一数据源通过简单数学运算生成的，而非独立实验获得。

这是"耿同学"打假方法中的核心策略之一——他发现许多造假论文中
不同实验组的数据存在固定差值或固定比例关系。

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""

import argparse
import sys
import json
import numpy as np
from scipy import stats


def detect_fixed_difference(col1, col2, tolerance=0.01):
    """检测两列数据是否存在固定差值"""
    differences = np.array(col2) - np.array(col1)
    
    if len(differences) < 3:
        return None
    
    # 计算差值的变异系数
    mean_diff = np.mean(differences)
    std_diff = np.std(differences)
    
    if abs(mean_diff) < 1e-10:
        cv = float('inf') if std_diff > 0 else 0
    else:
        cv = abs(std_diff / mean_diff)
    
    # 判断差值是否恒定（CV极小）
    is_fixed = cv < tolerance and std_diff < tolerance * abs(mean_diff + 1e-10)
    
    # 检查差值是否完全相同
    unique_diffs = np.unique(np.round(differences, 6))
    is_exact = len(unique_diffs) == 1
    
    return {
        'type': 'fixed_difference',
        'type_cn': '固定差值',
        'mean_difference': round(float(mean_diff), 6),
        'std_difference': round(float(std_diff), 6),
        'cv': round(float(cv), 6) if cv != float('inf') else 'inf',
        'is_fixed': bool(is_fixed or is_exact),
        'is_exact': bool(is_exact),
        'n_unique_differences': int(len(unique_diffs))
    }


def detect_fixed_ratio(col1, col2, tolerance=0.01):
    """检测两列数据是否存在固定比值"""
    col1 = np.array(col1, dtype=float)
    col2 = np.array(col2, dtype=float)
    
    # 避免除以零
    mask = col1 != 0
    if np.sum(mask) < 3:
        return None
    
    ratios = col2[mask] / col1[mask]
    
    mean_ratio = np.mean(ratios)
    std_ratio = np.std(ratios)
    
    if abs(mean_ratio) < 1e-10:
        cv = float('inf') if std_ratio > 0 else 0
    else:
        cv = abs(std_ratio / mean_ratio)
    
    is_fixed = cv < tolerance
    unique_ratios = np.unique(np.round(ratios, 6))
    is_exact = len(unique_ratios) == 1
    
    return {
        'type': 'fixed_ratio',
        'type_cn': '固定比值',
        'mean_ratio': round(float(mean_ratio), 6),
        'std_ratio': round(float(std_ratio), 6),
        'cv': round(float(cv), 6) if cv != float('inf') else 'inf',
        'is_fixed': bool(is_fixed or is_exact),
        'is_exact': bool(is_exact),
        'n_unique_ratios': int(len(unique_ratios))
    }


def detect_linear_relationship(col1, col2):
    """检测两列数据是否存在高度线性关系"""
    col1 = np.array(col1, dtype=float)
    col2 = np.array(col2, dtype=float)
    
    if len(col1) < 3:
        return None
    
    # 线性回归
    slope, intercept, r_value, p_value, std_err = stats.linregress(col1, col2)
    r_squared = r_value ** 2
    
    # 残差分析
    predicted = slope * col1 + intercept
    residuals = col2 - predicted
    max_residual = np.max(np.abs(residuals))
    mean_residual = np.mean(np.abs(residuals))
    
    # R² 非常接近1且残差极小
    is_suspicious = r_squared > 0.9999 and max_residual < 0.001 * np.std(col2)
    
    return {
        'type': 'linear_relationship',
        'type_cn': '线性关系',
        'slope': round(float(slope), 6),
        'intercept': round(float(intercept), 6),
        'r_squared': round(float(r_squared), 8),
        'p_value': float(p_value),
        'max_residual': round(float(max_residual), 8),
        'mean_residual': round(float(mean_residual), 8),
        'is_suspicious': bool(is_suspicious)
    }


def detect_decimal_pattern(col1, col2):
    """检测两列数据小数部分是否高度一致"""
    col1 = np.array(col1, dtype=float)
    col2 = np.array(col2, dtype=float)
    
    # 提取小数部分
    dec1 = col1 - np.floor(col1)
    dec2 = col2 - np.floor(col2)
    
    # 检查小数部分是否一致
    dec_diff = np.abs(dec1 - dec2)
    n_matching = np.sum(dec_diff < 0.001)
    match_rate = n_matching / len(col1)
    
    return {
        'type': 'decimal_pattern',
        'type_cn': '小数位一致性',
        'n_matching_decimals': int(n_matching),
        'match_rate': round(float(match_rate), 4),
        'is_suspicious': match_rate > 0.8
    }


def fixed_relation_test(col1, col2, col1_name='Column A', col2_name='Column B'):
    """
    综合固定关系检测
    
    Parameters
    ----------
    col1 : list of float
        第一列数据
    col2 : list of float
        第二列数据
    
    Returns
    -------
    dict : 检测结果
    """
    if len(col1) != len(col2):
        return {'status': 'error', 'message': '两列数据长度不一致'}
    
    if len(col1) < 3:
        return {'status': 'insufficient_data', 'message': '数据量不足，至少需要3个数据点'}
    
    col1 = [float(x) for x in col1]
    col2 = [float(x) for x in col2]
    
    # 执行各项检测
    results = {}
    
    diff_result = detect_fixed_difference(col1, col2)
    if diff_result:
        results['fixed_difference'] = diff_result
    
    ratio_result = detect_fixed_ratio(col1, col2)
    if ratio_result:
        results['fixed_ratio'] = ratio_result
    
    linear_result = detect_linear_relationship(col1, col2)
    if linear_result:
        results['linear_relationship'] = linear_result
    
    decimal_result = detect_decimal_pattern(col1, col2)
    if decimal_result:
        results['decimal_pattern'] = decimal_result
    
    # 综合风险评估
    n_suspicious = sum([
        1 for r in results.values()
        if r.get('is_fixed') or r.get('is_suspicious')
    ])
    
    if n_suspicious >= 3:
        risk_level = 'high'
        risk_score = 85
    elif n_suspicious == 2:
        risk_level = 'medium-high'
        risk_score = 65
    elif n_suspicious == 1:
        risk_level = 'medium'
        risk_score = 45
    else:
        risk_level = 'low'
        risk_score = 10
    
    # 如果存在完全精确的固定关系，直接拉高风险
    if any(r.get('is_exact') for r in results.values()):
        risk_level = 'high'
        risk_score = max(risk_score, 90)
    
    summary = {
        'test_name': 'Fixed Relationship Detection (固定关系检测)',
        'status': 'completed',
        'n_data_points': len(col1),
        'column_1': col1_name,
        'column_2': col2_name,
        'detections': results,
        'n_suspicious_patterns': n_suspicious,
        'risk_level': risk_level,
        'risk_score': round(float(risk_score), 1),
        'interpretation': _interpret_fixed_relation(results, n_suspicious, col1_name, col2_name)
    }
    
    return summary


def _interpret_fixed_relation(results, n_suspicious, col1_name, col2_name):
    """生成可读的解释"""
    findings = []
    
    if results.get('fixed_difference', {}).get('is_fixed'):
        d = results['fixed_difference']
        findings.append(f"两列数据存在固定差值 {d['mean_difference']}")
    
    if results.get('fixed_ratio', {}).get('is_fixed'):
        r = results['fixed_ratio']
        findings.append(f"两列数据存在固定比值 {r['mean_ratio']}")
    
    if results.get('linear_relationship', {}).get('is_suspicious'):
        l = results['linear_relationship']
        findings.append(f"两列数据存在完美线性关系 (R² = {l['r_squared']})")
    
    if results.get('decimal_pattern', {}).get('is_suspicious'):
        p = results['decimal_pattern']
        findings.append(f"两列数据小数部分高度一致 (匹配率 {p['match_rate']:.0%})")
    
    if not findings:
        return f"✅ {col1_name} 与 {col2_name} 之间未发现固定数学关系，数据看起来是独立的。"
    
    findings_str = "；".join(findings)
    return (
        f"⚠️ {col1_name} 与 {col2_name} 之间发现以下可疑模式：{findings_str}。"
        f"独立实验数据通常不应存在如此精确的数学关系，建议核查数据是否来自独立实验。"
    )


def load_data(input_file, col1, col2, delimiter=','):
    """从CSV文件加载两列数据"""
    import csv
    
    data1, data2 = [], []
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            try:
                v1 = float(row[col1].strip())
                v2 = float(row[col2].strip())
                data1.append(v1)
                data2.append(v2)
            except (ValueError, KeyError):
                continue
    return data1, data2


def main():
    parser = argparse.ArgumentParser(
        description='固定关系检测 - 检测两组数据间是否存在不自然的数学关系'
    )
    parser.add_argument('--input', '-i', required=True, help='输入CSV文件路径')
    parser.add_argument('--col1', required=True, help='第一列列名')
    parser.add_argument('--col2', required=True, help='第二列列名')
    parser.add_argument('--delimiter', '-d', default=',', help='CSV分隔符')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    data1, data2 = load_data(args.input, args.col1, args.col2, args.delimiter)
    
    if not data1:
        print("错误：未能加载有效数据", file=sys.stderr)
        sys.exit(1)
    
    result = fixed_relation_test(data1, data2, args.col1, args.col2)
    
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"结果已保存至: {args.output}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
