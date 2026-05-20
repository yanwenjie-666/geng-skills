#!/usr/bin/env python3
"""
Geng 综合评估引擎 (Comprehensive Assessment Engine)
=====================================================
一键运行所有适用的检测模块，生成综合学术数据打假报告。

支持的领域：
- biomedical: 生物医学（Western blot, 流式, 动物实验）
- chemistry: 化学（光谱, 产率, 催化）
- physics: 物理/材料（性能曲线, 电学/力学）
- social_science: 社会科学（问卷, 量表）
- clinical: 临床医学（生存数据, 临床指标）
- general: 通用（不指定领域）

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""

import argparse
import sys
import json
import os
import csv
import time
from datetime import datetime
from pathlib import Path

# 导入各检测模块
from last_digit_test import last_digit_test
from benford_test import benford_test
from decimal_consistency_test import decimal_consistency_test
from fixed_relation_test import fixed_relation_test
from grim_test import grim_test_batch


def load_csv_data(input_file, delimiter=','):
    """加载CSV数据，返回列名和数据"""
    columns = {}
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = reader.fieldnames
        for row in reader:
            for col in fieldnames:
                if col not in columns:
                    columns[col] = []
                columns[col].append(row[col].strip() if row[col] else '')
    return columns, fieldnames


def identify_numeric_columns(columns):
    """识别数值列"""
    numeric_cols = {}
    for col_name, values in columns.items():
        numeric_values = []
        for v in values:
            try:
                if v:
                    float(v)
                    numeric_values.append(v)
            except ValueError:
                continue
        # 至少50%的值是数值
        if len(numeric_values) >= len(values) * 0.5 and len(numeric_values) >= 5:
            numeric_cols[col_name] = numeric_values
    return numeric_cols


def run_assessment(input_file, domain='general', output_dir=None, delimiter=','):
    """
    执行综合评估
    
    Parameters
    ----------
    input_file : str
        输入CSV文件
    domain : str
        研究领域
    output_dir : str
        输出目录
    delimiter : str
        CSV分隔符
    """
    start_time = time.time()
    
    # 加载数据
    columns, fieldnames = load_csv_data(input_file, delimiter)
    numeric_cols = identify_numeric_columns(columns)
    
    if not numeric_cols:
        return {
            'status': 'error',
            'message': '未找到有效的数值列，请检查输入文件格式'
        }
    
    report = {
        'meta': {
            'tool': 'Geng Academic Data Fraud Detection Tool',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'input_file': os.path.basename(input_file),
            'domain': domain,
            'n_columns': len(fieldnames),
            'n_numeric_columns': len(numeric_cols),
            'numeric_columns': list(numeric_cols.keys()),
            'n_rows': max(len(v) for v in columns.values()) if columns else 0
        },
        'module_results': {},
        'summary': {}
    }
    
    all_risk_scores = []
    
    # ==========================================
    # Module 1: 末位数字检测 (对每个数值列)
    # ==========================================
    print("🔍 执行末位数字检测...")
    last_digit_results = {}
    for col_name, values in numeric_cols.items():
        result = last_digit_test(values, method='all_digits')
        if result.get('status') == 'completed':
            last_digit_results[col_name] = result
            all_risk_scores.append(result.get('risk_score', 0))
    
    if last_digit_results:
        report['module_results']['last_digit_test'] = {
            'module_name': '末位数字检测',
            'description': '检测数据末位数字是否偏离均匀分布',
            'columns_tested': len(last_digit_results),
            'results': last_digit_results
        }
    
    # ==========================================
    # Module 2: 本福特定律检测 (对每个数值列)
    # ==========================================
    print("🔍 执行本福特定律检测...")
    benford_results = {}
    for col_name, values in numeric_cols.items():
        # 本福特定律适用于跨多个数量级的数据
        try:
            float_values = [float(v) for v in values if v]
            value_range = max(float_values) / (min(v for v in float_values if v > 0) + 1e-10)
            # 只对跨度超过1个数量级的列做本福特检测
            if value_range > 10:
                result = benford_test(values, order=1)
                if result.get('status') == 'completed':
                    benford_results[col_name] = result
                    all_risk_scores.append(result.get('risk_score', 0))
        except (ValueError, ZeroDivisionError):
            continue
    
    if benford_results:
        report['module_results']['benford_test'] = {
            'module_name': '本福特定律检测',
            'description': '检测首位数字是否符合Benford\'s Law',
            'columns_tested': len(benford_results),
            'results': benford_results
        }
    
    # ==========================================
    # Module 3: 小数位一致性检测 (对每个数值列)
    # ==========================================
    print("🔍 执行小数位一致性检测...")
    decimal_results = {}
    for col_name, values in numeric_cols.items():
        # 只检测包含小数的列
        has_decimal = any('.' in v for v in values if v)
        if has_decimal:
            result = decimal_consistency_test(values)
            if result.get('status') == 'completed':
                decimal_results[col_name] = result
                all_risk_scores.append(result.get('risk_score', 0))
    
    if decimal_results:
        report['module_results']['decimal_consistency_test'] = {
            'module_name': '小数位一致性检测',
            'description': '检测数据小数部分是否存在异常模式',
            'columns_tested': len(decimal_results),
            'results': decimal_results
        }
    
    # ==========================================
    # Module 4: 固定关系检测 (两两比较数值列)
    # ==========================================
    print("🔍 执行固定关系检测...")
    fixed_results = {}
    col_names = list(numeric_cols.keys())
    
    # 限制比较对数，避免组合爆炸
    max_pairs = min(10, len(col_names) * (len(col_names) - 1) // 2)
    pair_count = 0
    
    for i in range(len(col_names)):
        if pair_count >= max_pairs:
            break
        for j in range(i + 1, len(col_names)):
            if pair_count >= max_pairs:
                break
            col1_name = col_names[i]
            col2_name = col_names[j]
            
            # 确保两列长度一致且有足够数据
            vals1 = numeric_cols[col1_name]
            vals2 = numeric_cols[col2_name]
            
            # 配对：只取两列都有值的行
            paired_1, paired_2 = [], []
            for v1, v2 in zip(vals1, vals2):
                try:
                    if v1 and v2:
                        float(v1)
                        float(v2)
                        paired_1.append(v1)
                        paired_2.append(v2)
                except ValueError:
                    continue
            
            if len(paired_1) >= 5:
                result = fixed_relation_test(paired_1, paired_2, col1_name, col2_name)
                if result.get('status') == 'completed':
                    pair_key = f"{col1_name} vs {col2_name}"
                    fixed_results[pair_key] = result
                    all_risk_scores.append(result.get('risk_score', 0))
                    pair_count += 1
    
    if fixed_results:
        report['module_results']['fixed_relation_test'] = {
            'module_name': '固定关系检测',
            'description': '检测不同列数据间是否存在不自然的数学关系',
            'pairs_tested': len(fixed_results),
            'results': fixed_results
        }
    
    # ==========================================
    # 综合评分
    # ==========================================
    print("📊 生成综合评估...")
    
    if all_risk_scores:
        # 综合评分：取各模块最高分的加权平均
        max_score = max(all_risk_scores)
        mean_score = sum(all_risk_scores) / len(all_risk_scores)
        # 综合分 = 60% 最高分 + 40% 平均分
        overall_score = 0.6 * max_score + 0.4 * mean_score
        overall_score = min(100, overall_score)
    else:
        overall_score = 0
    
    # 统计各风险等级
    high_risk_modules = [s for s in all_risk_scores if s >= 70]
    medium_risk_modules = [s for s in all_risk_scores if 40 <= s < 70]
    low_risk_modules = [s for s in all_risk_scores if s < 40]
    
    if overall_score >= 75:
        overall_level = 'critical'
        overall_level_cn = '🔴 极高风险'
        overall_emoji = '🔴'
    elif overall_score >= 50:
        overall_level = 'high'
        overall_level_cn = '🟠 高风险'
        overall_emoji = '🟠'
    elif overall_score >= 25:
        overall_level = 'medium'
        overall_level_cn = '🟡 中风险'
        overall_emoji = '🟡'
    else:
        overall_level = 'low'
        overall_level_cn = '🟢 低风险'
        overall_emoji = '🟢'
    
    report['summary'] = {
        'overall_risk_score': round(float(overall_score), 1),
        'overall_risk_level': overall_level,
        'overall_risk_level_cn': overall_level_cn,
        'n_modules_run': len(report['module_results']),
        'n_tests_total': len(all_risk_scores),
        'n_high_risk': len(high_risk_modules),
        'n_medium_risk': len(medium_risk_modules),
        'n_low_risk': len(low_risk_modules),
        'execution_time_seconds': round(time.time() - start_time, 2),
        'conclusion': _generate_conclusion(overall_score, overall_level, report['module_results']),
        'recommendations': _generate_recommendations(overall_level, domain, report['module_results'])
    }
    
    # 保存报告
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, 'geng_assessment_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 生成可读的 Markdown 报告
        md_path = os.path.join(output_dir, 'geng_assessment_report.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(_generate_markdown_report(report))
        
        print(f"\n📄 JSON报告已保存至: {report_path}")
        print(f"📄 Markdown报告已保存至: {md_path}")
    
    return report


def _generate_conclusion(score, level, modules):
    """生成结论"""
    if level == 'critical':
        return (
            "⚠️ 综合评估显示数据存在系统性异常，多项检测指标显著偏离正常预期。"
            "强烈建议对原始实验数据进行全面核查。"
            "注意：本工具仅提供线索筛查，最终判定需要领域专家复核。"
        )
    elif level == 'high':
        return (
            "⚠️ 数据中发现多处可疑模式，部分指标显著异常。"
            "建议对标记为高风险的数据列进行重点核查。"
        )
    elif level == 'medium':
        return (
            "⚡ 数据存在一些轻微异常，但不足以构成造假的确证。"
            "可能是测量精度限制、数据处理方式等正常因素导致。"
            "建议结合论文方法学描述进行综合判断。"
        )
    else:
        return (
            "✅ 数据各项检测指标均在正常范围内，未发现明显的造假迹象。"
            "注意：通过检测不代表数据一定真实，某些高明的造假可能无法被统计方法捕获。"
        )


def _generate_recommendations(level, domain, modules):
    """生成建议"""
    recs = []
    
    if level in ('critical', 'high'):
        recs.append("核查原始实验记录和数据记录本")
        recs.append("验证数据是否来自独立实验")
        recs.append("联系通讯作者要求提供原始数据")
        if domain == 'biomedical':
            recs.append("检查Western blot原始图片和流式原始FCS文件")
        recs.append("考虑向期刊或机构提交正式质疑")
    elif level == 'medium':
        recs.append("仔细阅读论文方法学部分，确认数据采集方式")
        recs.append("检查是否存在合理的解释（如仪器精度限制）")
        recs.append("可考虑联系作者进行非正式沟通")
    else:
        recs.append("当前数据未发现明显异常")
        recs.append("可考虑对补充材料中的数据做进一步检测")
    
    return recs


def _generate_markdown_report(report):
    """生成Markdown格式报告"""
    meta = report['meta']
    summary = report['summary']
    
    md = []
    md.append("# 📋 Geng 学术数据打假检测报告\n")
    md.append(f"> 生成时间: {meta['timestamp']}")
    md.append(f"> 检测工具: {meta['tool']} v{meta['version']}")
    md.append(f"> 致敬"耿同学讲故事"\n")
    
    md.append("## 📊 综合评估结果\n")
    md.append(f"| 指标 | 结果 |")
    md.append(f"|------|------|")
    md.append(f"| **综合风险评分** | **{summary['overall_risk_score']}/100** |")
    md.append(f"| **风险等级** | {summary['overall_risk_level_cn']} |")
    md.append(f"| 输入文件 | {meta['input_file']} |")
    md.append(f"| 检测领域 | {meta['domain']} |")
    md.append(f"| 数值列数 | {meta['n_numeric_columns']} |")
    md.append(f"| 数据行数 | {meta['n_rows']} |")
    md.append(f"| 运行模块数 | {summary['n_modules_run']} |")
    md.append(f"| 检测总数 | {summary['n_tests_total']} |")
    md.append(f"| 高风险项 | {summary['n_high_risk']} |")
    md.append(f"| 执行耗时 | {summary['execution_time_seconds']}s |\n")
    
    md.append("## 📝 结论\n")
    md.append(f"{summary['conclusion']}\n")
    
    md.append("## 💡 建议\n")
    for i, rec in enumerate(summary['recommendations'], 1):
        md.append(f"{i}. {rec}")
    md.append("")
    
    md.append("## 🔬 各模块检测详情\n")
    
    for module_key, module_data in report['module_results'].items():
        md.append(f"### {module_data['module_name']}\n")
        md.append(f"_{module_data['description']}_\n")
        
        if 'columns_tested' in module_data:
            md.append(f"- 检测列数: {module_data['columns_tested']}")
        if 'pairs_tested' in module_data:
            md.append(f"- 检测对数: {module_data['pairs_tested']}")
        
        # 列出各列/对的风险评分
        results = module_data.get('results', {})
        if results:
            md.append(f"\n| 检测对象 | 风险评分 | 风险等级 | 说明 |")
            md.append(f"|----------|----------|----------|------|")
            for key, res in results.items():
                score = res.get('risk_score', 'N/A')
                level = res.get('risk_level', 'N/A')
                interp = res.get('interpretation', '')[:60]
                md.append(f"| {key} | {score} | {level} | {interp}... |")
        md.append("")
    
    md.append("---\n")
    md.append("## ⚠️ 重要声明\n")
    md.append("- 本工具仅用于辅助筛查，**不能作为造假的最终判定依据**")
    md.append("- 数据异常 ≠ 数据造假（可能是仪器校准、单位转换、排版错误等）")
    md.append("- 检测结果需要领域专家复核")
    md.append("- 使用本工具时应遵守学术伦理和法律法规\n")
    md.append("---\n")
    md.append("*Powered by Geng Skill — 致敬"耿同学讲故事"*")
    
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(
        description='Geng 综合评估引擎 - 一键运行所有检测模块'
    )
    parser.add_argument('--input', '-i', required=True, help='输入CSV文件路径')
    parser.add_argument('--domain', default='general',
                       choices=['biomedical', 'chemistry', 'physics',
                               'social_science', 'clinical', 'general'],
                       help='研究领域')
    parser.add_argument('--output', '-o', default='./report', help='输出目录')
    parser.add_argument('--delimiter', '-d', default=',', help='CSV分隔符')
    
    args = parser.parse_args()
    
    if not os.path.isfile(args.input):
        print(f"错误：文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    print(f"{'='*60}")
    print(f"  Geng 学术数据打假检测工具 v1.0.0")
    print(f"  致敬"耿同学讲故事" — 用数据说话，让造假无所遁形")
    print(f"{'='*60}")
    print(f"\n📁 输入文件: {args.input}")
    print(f"🔬 检测领域: {args.domain}")
    print(f"📂 输出目录: {args.output}\n")
    
    report = run_assessment(args.input, args.domain, args.output, args.delimiter)
    
    if report.get('status') == 'error':
        print(f"\n❌ 错误: {report['message']}", file=sys.stderr)
        sys.exit(1)
    
    summary = report['summary']
    print(f"\n{'='*60}")
    print(f"  综合评估结果")
    print(f"{'='*60}")
    print(f"\n  {summary['overall_risk_level_cn']}")
    print(f"  综合风险评分: {summary['overall_risk_score']}/100")
    print(f"  高风险项: {summary['n_high_risk']} | "
          f"中风险项: {summary['n_medium_risk']} | "
          f"低风险项: {summary['n_low_risk']}")
    print(f"\n  {summary['conclusion']}")
    print(f"\n{'='*60}")


if __name__ == '__main__':
    main()
