#!/usr/bin/env python3
"""
本福特定律检测 (Benford's Law Test)
====================================
原理：跨越多个数量级的自然数据，首位数字遵循特定概率分布：
P(d) = log10(1 + 1/d), d = 1,2,...,9

人为编造的数据往往偏离这一分布（倾向于均匀分布或集中在某些数字）。

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""

import argparse
import sys
import json
import math
import numpy as np
from collections import Counter
from scipy import stats


# 本福特定律理论概率
BENFORD_PROBS = {d: math.log10(1 + 1/d) for d in range(1, 10)}


def get_first_digit(value):
    """提取数值的首位有效数字（1-9）"""
    try:
        num = abs(float(value))
        if num == 0:
            return None
        # 转为科学计数法取首位
        s = f"{num:.10e}"
        first = int(s[0])
        if 1 <= first <= 9:
            return first
    except (ValueError, TypeError):
        pass
    return None


def get_first_two_digits(value):
    """提取前两位有效数字（10-99）"""
    try:
        num = abs(float(value))
        if num == 0:
            return None
        while num < 10:
            num *= 10
        while num >= 100:
            num /= 10
        return int(num)
    except (ValueError, TypeError):
        pass
    return None


def benford_test(values, order=1):
    """
    执行本福特定律检测
    
    Parameters
    ----------
    values : list
        待检测的数值列表
    order : int
        1 = 首位数字检测, 2 = 前两位数字检测
    
    Returns
    -------
    dict : 检测结果
    """
    if order == 1:
        digits = []
        for v in values:
            d = get_first_digit(v)
            if d is not None:
                digits.append(d)
        
        if len(digits) < 30:
            return {
                'status': 'insufficient_data',
                'message': f'数据量不足（仅{len(digits)}个有效值），本福特定律检测建议至少100个数据点',
                'n_valid': len(digits)
            }
        
        # 统计观测频率
        digit_counts = Counter(digits)
        observed = np.array([digit_counts.get(d, 0) for d in range(1, 10)])
        expected = np.array([BENFORD_PROBS[d] * len(digits) for d in range(1, 10)])
        
        # 卡方检验
        chi2, p_value = stats.chisquare(observed, expected)
        
        # Kolmogorov-Smirnov 检验
        observed_freq = observed / len(digits)
        expected_freq = np.array([BENFORD_PROBS[d] for d in range(1, 10)])
        
        # 最大绝对偏差 (MAD)
        mad = np.mean(np.abs(observed_freq - expected_freq))
        
        # MAD 阈值参考 (Nigrini 2012)
        # Close conformity: MAD < 0.006
        # Acceptable conformity: 0.006 <= MAD < 0.012
        # Marginally acceptable: 0.012 <= MAD < 0.015
        # Nonconformity: MAD >= 0.015
        
        if mad < 0.006:
            conformity = 'close'
            conformity_cn = '高度符合'
        elif mad < 0.012:
            conformity = 'acceptable'
            conformity_cn = '可接受'
        elif mad < 0.015:
            conformity = 'marginal'
            conformity_cn = '边缘'
        else:
            conformity = 'nonconforming'
            conformity_cn = '不符合'
        
        # 风险评分
        if p_value < 0.001 and mad >= 0.015:
            risk_level = 'high'
            risk_score = 75 + min(25, mad * 500)
        elif p_value < 0.01:
            risk_level = 'medium-high'
            risk_score = 55 + min(20, mad * 400)
        elif p_value < 0.05:
            risk_level = 'medium'
            risk_score = 35 + min(20, mad * 300)
        else:
            risk_level = 'low'
            risk_score = max(0, mad * 200)
        
        distribution = {
            str(d): {
                'observed': int(observed[d-1]),
                'observed_freq': round(float(observed_freq[d-1]), 4),
                'expected_freq': round(float(expected_freq[d-1]), 4),
                'deviation': round(float(observed_freq[d-1] - expected_freq[d-1]), 4)
            }
            for d in range(1, 10)
        }
        
        result = {
            'test_name': "Benford's Law Test (本福特定律检测)",
            'status': 'completed',
            'order': order,
            'n_values': len(digits),
            'distribution': distribution,
            'chi_square': round(float(chi2), 4),
            'p_value': float(p_value),
            'degrees_of_freedom': 8,
            'mean_absolute_deviation': round(float(mad), 6),
            'conformity': conformity,
            'conformity_cn': conformity_cn,
            'risk_level': risk_level,
            'risk_score': round(float(risk_score), 1),
            'interpretation': _interpret_benford(p_value, mad, conformity_cn, len(digits)),
            'note': '本福特定律适用于跨多个数量级的自然数据集。对于范围有限的数据（如百分比、pH值），该检测可能不适用。'
        }
        
        return result
    
    else:
        return {'status': 'error', 'message': '目前仅支持首位数字检测（order=1）'}


def _interpret_benford(p_value, mad, conformity_cn, n):
    """生成可读的解释"""
    if p_value < 0.001 and mad >= 0.015:
        return (
            f"⚠️ 数据首位数字分布严重偏离本福特定律（p < 0.001, MAD = {mad:.4f}）。"
            f"符合性判定：{conformity_cn}。"
            f"这种偏离在{n}个数据点的样本中非常显著，强烈建议核查数据来源。"
            f"注意：需确认数据是否适用本福特定律（需跨越多个数量级）。"
        )
    elif p_value < 0.01:
        return (
            f"⚠️ 数据首位数字分布显著偏离本福特定律（p < 0.01, MAD = {mad:.4f}）。"
            f"符合性判定：{conformity_cn}。建议进一步检查。"
        )
    elif p_value < 0.05:
        return (
            f"⚡ 数据首位数字分布存在一定偏离（p < 0.05, MAD = {mad:.4f}）。"
            f"符合性判定：{conformity_cn}。可能是正常波动，建议结合其他检测综合判断。"
        )
    else:
        return (
            f"✅ 数据首位数字分布符合本福特定律（p = {p_value:.4f}, MAD = {mad:.4f}）。"
            f"符合性判定：{conformity_cn}。未发现异常。"
        )


def load_data(input_file, column=None, delimiter=','):
    """从CSV文件加载数据"""
    import csv
    
    values = []
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if column and column in reader.fieldnames:
            for row in reader:
                try:
                    val = row[column].strip()
                    if val:
                        float(val)
                        values.append(val)
                except (ValueError, KeyError):
                    continue
        else:
            for row in reader:
                for key, val in row.items():
                    try:
                        val = val.strip()
                        if val:
                            float(val)
                            values.append(val)
                    except (ValueError, AttributeError):
                        continue
    return values


def main():
    parser = argparse.ArgumentParser(
        description="本福特定律检测 - 检测首位数字是否符合Benford's Law"
    )
    parser.add_argument('--input', '-i', required=True, help='输入CSV文件路径')
    parser.add_argument('--column', '-c', help='要检测的列名')
    parser.add_argument('--order', type=int, default=1, choices=[1, 2],
                       help='检测阶数：1=首位, 2=前两位')
    parser.add_argument('--delimiter', '-d', default=',', help='CSV分隔符')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    values = load_data(args.input, args.column, args.delimiter)
    
    if not values:
        print("错误：未能加载有效数据", file=sys.stderr)
        sys.exit(1)
    
    result = benford_test(values, order=args.order)
    
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"结果已保存至: {args.output}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
