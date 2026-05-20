#!/usr/bin/env python3
"""
末位数字检测 (Last Digit Test)
==============================
原理：自然实验数据的末位数字（0-9）应近似均匀分布。
如果数据是人为编造的，末位数字往往会集中在某些特定值上。

使用卡方检验评估偏离均匀分布的程度。

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""

import argparse
import sys
import json
import numpy as np
from collections import Counter
from scipy import stats


def extract_last_digit(value):
    """提取数值的末位有效数字"""
    s = str(value).strip()
    # 去除负号
    s = s.lstrip('-')
    # 去除科学计数法
    if 'e' in s.lower():
        try:
            value = float(s)
            s = f"{value:.10f}".rstrip('0')
        except ValueError:
            return None
    # 找到末位有效数字
    s = s.rstrip('0').rstrip('.')
    if not s:
        return 0
    for c in reversed(s):
        if c.isdigit():
            return int(c)
    return None


def extract_last_digit_with_decimals(value, use_decimal_last=True):
    """
    提取数值的末位数字
    use_decimal_last=True: 取小数点后最后一位非零数字
    use_decimal_last=False: 取整数部分的末位数字
    """
    s = str(value).strip()
    s = s.lstrip('-')
    
    if '.' in s and use_decimal_last:
        decimal_part = s.split('.')[1]
        # 取小数部分的最后一位数字
        if decimal_part:
            return int(decimal_part[-1])
    
    # 取整数部分的末位
    integer_part = s.split('.')[0] if '.' in s else s
    if integer_part:
        return int(integer_part[-1])
    return None


def last_digit_test(values, method='all_digits'):
    """
    执行末位数字检测
    
    Parameters
    ----------
    values : list of float/str
        待检测的数值列表
    method : str
        'all_digits' - 检测最后一位有效数字
        'decimal_last' - 检测小数末位
    
    Returns
    -------
    dict : 检测结果
    """
    # 提取末位数字
    last_digits = []
    for v in values:
        try:
            if method == 'decimal_last':
                d = extract_last_digit_with_decimals(v, use_decimal_last=True)
            else:
                d = extract_last_digit(v)
            if d is not None:
                last_digits.append(d)
        except (ValueError, TypeError):
            continue
    
    if len(last_digits) < 10:
        return {
            'status': 'insufficient_data',
            'message': f'数据量不足（仅{len(last_digits)}个有效值），需要至少10个数据点',
            'n_valid': len(last_digits)
        }
    
    # 统计各数字出现频次
    digit_counts = Counter(last_digits)
    observed = np.array([digit_counts.get(i, 0) for i in range(10)])
    expected = np.full(10, len(last_digits) / 10.0)
    
    # 卡方检验
    chi2, p_value = stats.chisquare(observed, expected)
    
    # 计算集中度指标
    max_digit = int(np.argmax(observed))
    max_freq = observed[max_digit] / len(last_digits)
    
    # 均匀性评分 (0=完全均匀, 1=完全集中)
    uniformity_deviation = np.sqrt(np.sum((observed / len(last_digits) - 0.1) ** 2) / 10) / 0.3
    uniformity_deviation = min(uniformity_deviation, 1.0)
    
    # 风险评分
    if p_value < 0.001:
        risk_level = 'high'
        risk_score = min(80 + (1 - p_value) * 20, 100)
    elif p_value < 0.01:
        risk_level = 'medium-high'
        risk_score = 60 + (0.01 - p_value) / 0.009 * 20
    elif p_value < 0.05:
        risk_level = 'medium'
        risk_score = 40 + (0.05 - p_value) / 0.04 * 20
    else:
        risk_level = 'low'
        risk_score = max(0, 40 * (1 - p_value))
    
    result = {
        'test_name': 'Last Digit Test (末位数字检测)',
        'status': 'completed',
        'n_values': len(last_digits),
        'method': method,
        'digit_distribution': {str(i): int(observed[i]) for i in range(10)},
        'chi_square': round(float(chi2), 4),
        'p_value': float(p_value),
        'degrees_of_freedom': 9,
        'most_frequent_digit': max_digit,
        'most_frequent_proportion': round(float(max_freq), 4),
        'uniformity_deviation': round(float(uniformity_deviation), 4),
        'risk_level': risk_level,
        'risk_score': round(float(risk_score), 1),
        'interpretation': _interpret_result(p_value, max_digit, max_freq, len(last_digits))
    }
    
    return result


def _interpret_result(p_value, max_digit, max_freq, n):
    """生成可读的解释"""
    if p_value < 0.001:
        return (
            f"⚠️ 末位数字分布严重偏离均匀分布（p < 0.001）。"
            f"数字 {max_digit} 出现频率为 {max_freq:.1%}（期望 10%），"
            f"这种偏离在自然实验数据中极为罕见，强烈建议进一步核查原始数据。"
        )
    elif p_value < 0.01:
        return (
            f"⚠️ 末位数字分布显著偏离均匀分布（p < 0.01）。"
            f"数字 {max_digit} 出现频率为 {max_freq:.1%}，建议关注并进行人工复核。"
        )
    elif p_value < 0.05:
        return (
            f"⚡ 末位数字分布存在一定偏离（p < 0.05）。"
            f"可能是正常波动，也可能提示数据存在问题，建议结合其他检测结果综合判断。"
        )
    else:
        return (
            f"✅ 末位数字分布与均匀分布无显著差异（p = {p_value:.4f}），"
            f"未发现明显异常。"
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
                        float(val)  # 验证是数值
                        values.append(val)
                except (ValueError, KeyError):
                    continue
        else:
            # 如果没有指定列，尝试读取第一个数值列
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
        description='末位数字检测 - 检测数据末位数字是否偏离均匀分布'
    )
    parser.add_argument('--input', '-i', required=True, help='输入CSV文件路径')
    parser.add_argument('--column', '-c', help='要检测的列名')
    parser.add_argument('--method', '-m', default='all_digits',
                       choices=['all_digits', 'decimal_last'],
                       help='检测方法：all_digits=末位有效数字, decimal_last=小数末位')
    parser.add_argument('--delimiter', '-d', default=',', help='CSV分隔符')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    parser.add_argument('--values', nargs='+', type=str,
                       help='直接传入数值列表（不使用文件输入）')
    
    args = parser.parse_args()
    
    if args.values:
        values = args.values
    else:
        values = load_data(args.input, args.column, args.delimiter)
    
    if not values:
        print("错误：未能加载有效数据", file=sys.stderr)
        sys.exit(1)
    
    result = last_digit_test(values, method=args.method)
    
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"结果已保存至: {args.output}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
