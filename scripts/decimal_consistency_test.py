#!/usr/bin/env python3
"""
小数位一致性检测 (Decimal Consistency Test)
============================================
原理：实验测量数据的小数位后数字应具有一定的随机性。
如果大量数据点的小数部分高度一致（如小数后两位总是相同），
或小数位数模式过于规律，则暗示数据可能是人为编造的。

这是"耿同学"常用的一个检测手段——造假者编造数据时，
小数点后的位数往往呈现不自然的一致性。

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""

import argparse
import sys
import json
import numpy as np
from collections import Counter
from scipy import stats


def get_decimal_digits(value, max_digits=4):
    """提取数值的小数部分各位数字"""
    s = str(value).strip()
    if '.' not in s:
        return []
    decimal_part = s.split('.')[1]
    return [int(d) for d in decimal_part[:max_digits]]


def get_decimal_string(value):
    """提取数值的完整小数字符串"""
    s = str(value).strip()
    if '.' not in s:
        return ''
    return s.split('.')[1]


def count_decimal_places(value):
    """计算数值的小数位数"""
    s = str(value).strip()
    if '.' not in s:
        return 0
    return len(s.split('.')[1])


def decimal_consistency_test(values):
    """
    执行小数位一致性检测
    
    Parameters
    ----------
    values : list
        待检测的数值列表（字符串形式保留原始精度）
    
    Returns
    -------
    dict : 检测结果
    """
    if len(values) < 5:
        return {
            'status': 'insufficient_data',
            'message': f'数据量不足（仅{len(values)}个值），需要至少5个数据点'
        }
    
    # 分析1: 小数位数一致性
    decimal_places = [count_decimal_places(v) for v in values]
    places_counter = Counter(decimal_places)
    most_common_places = places_counter.most_common(1)[0]
    places_uniformity = most_common_places[1] / len(values)
    
    # 分析2: 小数部分重复度
    decimal_strings = [get_decimal_string(v) for v in values if '.' in str(v)]
    if decimal_strings:
        decimal_counter = Counter(decimal_strings)
        n_unique_decimals = len(decimal_counter)
        most_repeated = decimal_counter.most_common(1)[0]
        max_repetition_rate = most_repeated[1] / len(decimal_strings)
    else:
        n_unique_decimals = 0
        max_repetition_rate = 0
        most_repeated = ('N/A', 0)
    
    # 分析3: 各小数位数字分布
    position_analyses = {}
    max_positions = max(decimal_places) if decimal_places else 0
    
    for pos in range(min(max_positions, 4)):
        digits_at_pos = []
        for v in values:
            decs = get_decimal_digits(v)
            if len(decs) > pos:
                digits_at_pos.append(decs[pos])
        
        if len(digits_at_pos) >= 10:
            digit_counts = Counter(digits_at_pos)
            observed = np.array([digit_counts.get(i, 0) for i in range(10)])
            expected = np.full(10, len(digits_at_pos) / 10.0)
            chi2, p_value = stats.chisquare(observed, expected)
            
            position_analyses[f'position_{pos+1}'] = {
                'n_values': len(digits_at_pos),
                'distribution': {str(i): int(observed[i]) for i in range(10)},
                'chi_square': round(float(chi2), 4),
                'p_value': float(p_value),
                'is_uniform': p_value > 0.05
            }
    
    # 分析4: 相邻数据小数部分相关性
    if len(decimal_strings) >= 5:
        # 将小数部分转为数值进行自相关分析
        decimal_values = []
        for ds in decimal_strings:
            try:
                decimal_values.append(float('0.' + ds) if ds else 0.0)
            except ValueError:
                decimal_values.append(0.0)
        
        if len(decimal_values) >= 5:
            # 计算一阶自相关
            x = np.array(decimal_values)
            x_centered = x - np.mean(x)
            if np.std(x) > 0:
                autocorr = np.correlate(x_centered[:-1], x_centered[1:]) / (len(x_centered) - 1) / np.var(x)
                autocorr_val = float(autocorr[0]) if len(autocorr) > 0 else 0
            else:
                autocorr_val = 1.0  # 完全一致
        else:
            autocorr_val = None
    else:
        autocorr_val = None
    
    # 综合风险评分
    risk_factors = []
    
    # 因子1: 小数位数过于一致
    if places_uniformity > 0.95 and len(values) > 10:
        risk_factors.append(('decimal_places_uniform', 20))
    
    # 因子2: 小数部分重复度过高
    if max_repetition_rate > 0.5:
        risk_factors.append(('high_repetition', 30))
    elif max_repetition_rate > 0.3:
        risk_factors.append(('moderate_repetition', 15))
    
    # 因子3: 某个位置数字分布异常
    for pos_key, pos_data in position_analyses.items():
        if pos_data['p_value'] < 0.001:
            risk_factors.append((f'{pos_key}_nonuniform', 25))
        elif pos_data['p_value'] < 0.01:
            risk_factors.append((f'{pos_key}_marginal', 10))
    
    # 因子4: 自相关异常高
    if autocorr_val is not None and abs(autocorr_val) > 0.8:
        risk_factors.append(('high_autocorrelation', 20))
    
    risk_score = min(100, sum(score for _, score in risk_factors))
    
    if risk_score >= 70:
        risk_level = 'high'
    elif risk_score >= 45:
        risk_level = 'medium-high'
    elif risk_score >= 25:
        risk_level = 'medium'
    else:
        risk_level = 'low'
    
    result = {
        'test_name': 'Decimal Consistency Test (小数位一致性检测)',
        'status': 'completed',
        'n_values': len(values),
        'decimal_places_analysis': {
            'distribution': dict(places_counter),
            'most_common_places': most_common_places[0],
            'uniformity_rate': round(float(places_uniformity), 4)
        },
        'decimal_repetition': {
            'n_unique_patterns': n_unique_decimals,
            'most_repeated_pattern': most_repeated[0],
            'most_repeated_count': most_repeated[1],
            'max_repetition_rate': round(float(max_repetition_rate), 4)
        },
        'position_digit_analysis': position_analyses,
        'autocorrelation': round(float(autocorr_val), 4) if autocorr_val is not None else None,
        'risk_factors': [f for f, _ in risk_factors],
        'risk_level': risk_level,
        'risk_score': round(float(risk_score), 1),
        'interpretation': _interpret_decimal(risk_factors, places_uniformity, max_repetition_rate, most_repeated)
    }
    
    return result


def _interpret_decimal(risk_factors, places_uniformity, max_repetition_rate, most_repeated):
    """生成可读的解释"""
    if not risk_factors:
        return "✅ 小数位分布未发现明显异常，数据的小数部分具有合理的随机性。"
    
    issues = []
    for factor, _ in risk_factors:
        if 'repetition' in factor:
            issues.append(f"小数部分 '{most_repeated[0]}' 重复出现 {most_repeated[1]} 次（{max_repetition_rate:.0%}）")
        elif 'nonuniform' in factor:
            issues.append("某些小数位的数字分布严重偏离均匀分布")
        elif 'autocorrelation' in factor:
            issues.append("相邻数据的小数部分存在异常高的自相关")
        elif 'places_uniform' in factor:
            issues.append(f"所有数据小数位数高度一致（{places_uniformity:.0%}相同）")
    
    issues_str = "；".join(issues)
    
    if len(risk_factors) >= 3:
        return f"⚠️ 发现多项小数位异常：{issues_str}。这些模式在自然实验数据中非常罕见，强烈建议核查原始数据。"
    elif len(risk_factors) >= 2:
        return f"⚠️ 发现小数位可疑模式：{issues_str}。建议进一步检查。"
    else:
        return f"⚡ 发现轻微异常：{issues_str}。可能是测量精度限制导致，建议结合其他检测综合判断。"


def load_data(input_file, column=None, delimiter=','):
    """从CSV文件加载数据（保留原始字符串精度）"""
    import csv
    
    values = []
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if column and column in reader.fieldnames:
            for row in reader:
                val = row[column].strip()
                if val:
                    try:
                        float(val)
                        values.append(val)
                    except ValueError:
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
        description='小数位一致性检测 - 检测数据小数部分是否存在异常模式'
    )
    parser.add_argument('--input', '-i', required=True, help='输入CSV文件路径')
    parser.add_argument('--column', '-c', help='要检测的列名')
    parser.add_argument('--delimiter', '-d', default=',', help='CSV分隔符')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    values = load_data(args.input, args.column, args.delimiter)
    
    if not values:
        print("错误：未能加载有效数据", file=sys.stderr)
        sys.exit(1)
    
    result = decimal_consistency_test(values)
    
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"结果已保存至: {args.output}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
