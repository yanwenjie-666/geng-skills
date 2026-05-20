#!/usr/bin/env python3
"""
GRIM 测试 (Granularity-Related Inconsistency of Means)
========================================================
原理：对于整数取值的数据（如李克特量表1-5、年龄等），
给定样本量 n，合法的平均值只能取有限集合中的值。
如果报告的平均值不在合法集合中，则数据存在不一致性。

例：n=25，数据取值为整数，则平均值只能是 k/25 的形式，
小数部分只能是 .00, .04, .08, .12, ..., .96

参考：Brown & Heathers (2017). The GRIM Test. SPPS.

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""

import argparse
import sys
import json
import math
from decimal import Decimal, ROUND_HALF_UP


def grim_test_single(mean, n, decimals=2, scale_min=None, scale_max=None):
    """
    对单个均值执行 GRIM 测试
    
    Parameters
    ----------
    mean : float or str
        报告的平均值
    n : int
        样本量
    decimals : int
        报告的小数位数
    scale_min : int, optional
        量表最小值（用于范围检查）
    scale_max : int, optional
        量表最大值（用于范围检查）
    
    Returns
    -------
    dict : 检测结果
    """
    try:
        mean_val = Decimal(str(mean))
        n = int(n)
    except (ValueError, TypeError) as e:
        return {'status': 'error', 'message': f'无效输入: {e}'}
    
    if n <= 0:
        return {'status': 'error', 'message': '样本量必须大于0'}
    
    # 范围检查
    if scale_min is not None and scale_max is not None:
        if float(mean_val) < scale_min or float(mean_val) > scale_max:
            return {
                'status': 'range_error',
                'message': f'均值 {mean} 超出量表范围 [{scale_min}, {scale_max}]',
                'consistent': False
            }
    
    # 计算总和 = mean * n
    total = mean_val * n
    
    # 对于整数取值数据，总和必须是整数
    # 考虑四舍五入误差：检查 total 是否足够接近某个整数
    granularity = Decimal(1) / Decimal(10 ** decimals)
    
    # 在四舍五入精度范围内检查
    # mean 可能是真实值四舍五入到 decimals 位的结果
    # 真实 mean 在 [mean - 0.5*granularity, mean + 0.5*granularity) 范围内
    lower_total = (mean_val - granularity / 2) * n
    upper_total = (mean_val + granularity / 2) * n
    
    # 检查这个范围内是否包含整数
    lower_int = math.ceil(float(lower_total))
    upper_int = math.floor(float(upper_total))
    
    consistent = lower_int <= upper_int
    
    # 计算最近的合法均值
    nearest_total = round(float(mean_val * n))
    nearest_mean = nearest_total / n
    
    # 格式化到指定小数位
    fmt = f"%.{decimals}f"
    nearest_mean_str = fmt % nearest_mean
    reported_mean_str = fmt % float(mean_val)
    
    result = {
        'reported_mean': str(mean),
        'sample_size': n,
        'decimals': decimals,
        'consistent': consistent,
        'computed_sum': float(mean_val * n),
        'nearest_valid_mean': nearest_mean_str,
        'difference': round(abs(float(mean_val) - nearest_mean), decimals + 2)
    }
    
    if scale_min is not None and scale_max is not None:
        result['scale_range'] = f"[{scale_min}, {scale_max}]"
    
    return result


def grim_test_batch(items):
    """
    批量 GRIM 测试
    
    Parameters
    ----------
    items : list of dict
        每个字典包含 'mean', 'n', 可选 'decimals', 'label'
    
    Returns
    -------
    dict : 批量检测结果
    """
    results = []
    n_inconsistent = 0
    
    for i, item in enumerate(items):
        mean = item.get('mean')
        n = item.get('n')
        decimals = item.get('decimals', 2)
        label = item.get('label', f'Item {i+1}')
        scale_min = item.get('scale_min')
        scale_max = item.get('scale_max')
        
        res = grim_test_single(mean, n, decimals, scale_min, scale_max)
        res['label'] = label
        results.append(res)
        
        if not res.get('consistent', True):
            n_inconsistent += 1
    
    # 整体评估
    total = len(results)
    inconsistency_rate = n_inconsistent / total if total > 0 else 0
    
    # 风险评分
    if inconsistency_rate > 0.5:
        risk_level = 'high'
        risk_score = 70 + inconsistency_rate * 30
    elif inconsistency_rate > 0.25:
        risk_level = 'medium-high'
        risk_score = 50 + inconsistency_rate * 40
    elif inconsistency_rate > 0:
        risk_level = 'medium'
        risk_score = 30 + inconsistency_rate * 40
    else:
        risk_level = 'low'
        risk_score = 0
    
    summary = {
        'test_name': 'GRIM Test (均值粒度一致性检验)',
        'status': 'completed',
        'total_items': total,
        'inconsistent_items': n_inconsistent,
        'inconsistency_rate': round(inconsistency_rate, 4),
        'risk_level': risk_level,
        'risk_score': round(float(risk_score), 1),
        'details': results,
        'interpretation': _interpret_grim(n_inconsistent, total, inconsistency_rate)
    }
    
    return summary


def _interpret_grim(n_inconsistent, total, rate):
    """生成可读的解释"""
    if n_inconsistent == 0:
        return f"✅ 全部 {total} 个均值通过 GRIM 检验，未发现数值不一致。"
    elif rate > 0.5:
        return (
            f"⚠️ {total} 个均值中有 {n_inconsistent} 个（{rate:.0%}）未通过 GRIM 检验。"
            f"超过半数均值与样本量不兼容，这是严重的数据不一致信号。"
            f"强烈建议核查原始数据。"
        )
    elif rate > 0.25:
        return (
            f"⚠️ {total} 个均值中有 {n_inconsistent} 个（{rate:.0%}）未通过 GRIM 检验。"
            f"建议仔细核查这些不一致的数据点。"
        )
    else:
        return (
            f"⚡ {total} 个均值中有 {n_inconsistent} 个（{rate:.0%}）未通过 GRIM 检验。"
            f"少量不一致可能是四舍五入方式不同导致，建议结合其他检测综合判断。"
        )


def main():
    parser = argparse.ArgumentParser(
        description='GRIM测试 - 检测报告均值与样本量的一致性'
    )
    parser.add_argument('--mean', type=str, help='报告的平均值')
    parser.add_argument('--n', type=int, help='样本量')
    parser.add_argument('--decimals', type=int, default=2, help='小数位数')
    parser.add_argument('--scale', type=str, help='量表范围，如 "1-5"')
    parser.add_argument('--input', '-i', help='输入JSON文件（批量测试）')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    scale_min, scale_max = None, None
    if args.scale:
        parts = args.scale.split('-')
        if len(parts) == 2:
            scale_min, scale_max = int(parts[0]), int(parts[1])
    
    if args.input:
        # 批量模式
        with open(args.input, 'r', encoding='utf-8') as f:
            items = json.load(f)
        result = grim_test_batch(items)
    elif args.mean and args.n:
        # 单项模式
        res = grim_test_single(args.mean, args.n, args.decimals, scale_min, scale_max)
        result = {
            'test_name': 'GRIM Test (均值粒度一致性检验)',
            'status': 'completed',
            'result': res,
            'interpretation': (
                f"✅ 均值 {args.mean} 与样本量 {args.n} 一致" if res.get('consistent')
                else f"⚠️ 均值 {args.mean} 与样本量 {args.n} 不一致！最近合法均值为 {res.get('nearest_valid_mean')}"
            )
        }
    else:
        parser.print_help()
        sys.exit(1)
    
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"结果已保存至: {args.output}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
