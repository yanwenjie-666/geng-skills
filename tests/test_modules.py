#!/usr/bin/env python3
"""
Geng Skill 单元测试
====================
验证各检测模块的正确性、边界条件处理和风险评分一致性。

运行方式:
    cd geng-skill
    python3 -m pytest tests/test_modules.py -v

或直接运行:
    python3 tests/test_modules.py
"""

import sys
import os
import json
import random
import math

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from last_digit_test import last_digit_test, extract_last_digit
from benford_test import benford_test, get_first_digit
from grim_test import grim_test_single, grim_test_batch
from fixed_relation_test import fixed_relation_test
from decimal_consistency_test import decimal_consistency_test


# ============================================================
# Test: Last Digit Test
# ============================================================

class TestLastDigitTest:
    """末位数字检测模块测试"""
    
    def test_uniform_data_low_risk(self):
        """均匀分布的末位数字应返回低风险"""
        random.seed(42)
        # 生成末位数字均匀的数据
        values = [f"{random.uniform(1, 100):.2f}" for _ in range(100)]
        result = last_digit_test(values)
        assert result['status'] == 'completed'
        assert result['risk_level'] == 'low'
        assert result['risk_score'] < 40
    
    def test_concentrated_digits_high_risk(self):
        """集中在某个数字的末位应返回高风险"""
        # 80% 的末位是 "5"
        values = ['1.25', '2.35', '3.45', '4.55', '5.65',
                  '6.75', '7.85', '8.95', '9.15', '10.25',
                  '11.35', '12.45', '13.55', '14.65', '15.75',
                  '16.85', '17.95', '18.05', '19.15', '20.55']
        result = last_digit_test(values)
        assert result['status'] == 'completed'
        assert result['most_frequent_digit'] == 5
    
    def test_insufficient_data(self):
        """数据量不足应返回 insufficient_data"""
        values = ['1.23', '4.56', '7.89']
        result = last_digit_test(values)
        assert result['status'] == 'insufficient_data'
    
    def test_extract_last_digit(self):
        """末位数字提取正确性"""
        assert extract_last_digit('3.14') == 4
        assert extract_last_digit('100') == 1
        assert extract_last_digit('-5.67') == 7


# ============================================================
# Test: Benford's Law Test
# ============================================================

class TestBenfordTest:
    """本福特定律检测模块测试"""
    
    def test_benford_compliant_data(self):
        """符合本福特定律的数据应返回低风险"""
        # 生成符合本福特定律的数据
        random.seed(42)
        values = []
        for _ in range(200):
            # 对数均匀分布产生的数据符合本福特定律
            val = 10 ** (random.uniform(0, 4))
            values.append(f"{val:.2f}")
        result = benford_test(values)
        assert result['status'] == 'completed'
        # 对数均匀数据应近似符合
        assert result['conformity'] in ('close', 'acceptable', 'marginal')
    
    def test_uniform_first_digit_high_risk(self):
        """首位数字均匀分布应偏离本福特定律"""
        # 人为造假数据：首位数字接近均匀
        values = []
        for d in range(1, 10):
            for _ in range(20):
                values.append(f"{d}{random.randint(10,99)}")
        result = benford_test(values)
        assert result['status'] == 'completed'
        # 均匀分布会显著偏离本福特定律
        assert result['p_value'] < 0.05
    
    def test_insufficient_data(self):
        """数据量不足"""
        values = ['123', '456']
        result = benford_test(values)
        assert result['status'] == 'insufficient_data'
    
    def test_first_digit_extraction(self):
        """首位数字提取"""
        assert get_first_digit('314.15') == 3
        assert get_first_digit('0.0052') == 5
        assert get_first_digit('9999') == 9


# ============================================================
# Test: GRIM Test
# ============================================================

class TestGrimTest:
    """GRIM 测试模块测试"""
    
    def test_consistent_mean(self):
        """合法均值应通过"""
        # n=20, 整数数据, mean=3.40 → sum=68 (整数) ✓
        result = grim_test_single('3.40', 20, decimals=2)
        assert result['consistent'] == True
    
    def test_inconsistent_mean(self):
        """非法均值应失败"""
        # n=20, 整数数据, mean=3.47 → sum=69.4 (非整数) ✗
        result = grim_test_single('3.47', 20, decimals=2)
        assert result['consistent'] == False
    
    def test_consistent_mean_n25(self):
        """n=25 的合法均值"""
        # n=25, mean=3.48 → sum=87 (整数) ✓
        result = grim_test_single('3.48', 25, decimals=2)
        assert result['consistent'] == True
    
    def test_batch_mode(self):
        """批量 GRIM 测试"""
        items = [
            {'mean': '3.40', 'n': 20, 'decimals': 2, 'label': 'Item A'},
            {'mean': '3.47', 'n': 20, 'decimals': 2, 'label': 'Item B'},
            {'mean': '4.00', 'n': 10, 'decimals': 2, 'label': 'Item C'},
        ]
        result = grim_test_batch(items)
        assert result['status'] == 'completed'
        assert result['total_items'] == 3
        assert result['inconsistent_items'] == 1  # 3.47/20 不一致
    
    def test_range_check(self):
        """量表范围检查"""
        # 均值超出量表范围
        result = grim_test_single('6.50', 20, decimals=2, scale_min=1, scale_max=5)
        assert result.get('consistent') == False or result.get('status') == 'range_error'


# ============================================================
# Test: Fixed Relation Test
# ============================================================

class TestFixedRelationTest:
    """固定关系检测模块测试"""
    
    def test_exact_ratio_detected(self):
        """精确固定比值应被检测到"""
        col1 = [1.23, 2.34, 3.45, 4.56, 5.67, 6.78, 7.89]
        col2 = [2.46, 4.68, 6.90, 9.12, 11.34, 13.56, 15.78]  # ×2
        result = fixed_relation_test(col1, col2)
        assert result['status'] == 'completed'
        assert result['risk_level'] == 'high'
        assert result['risk_score'] >= 85
        assert result['detections']['fixed_ratio']['is_exact'] == True
    
    def test_exact_difference_detected(self):
        """精确固定差值应被检测到"""
        col1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        col2 = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]  # +3
        result = fixed_relation_test(col1, col2)
        assert result['detections']['fixed_difference']['is_exact'] == True
    
    def test_independent_data_low_risk(self):
        """独立随机数据应返回低风险"""
        random.seed(42)
        col1 = [random.uniform(1, 10) for _ in range(30)]
        col2 = [random.uniform(1, 10) for _ in range(30)]
        result = fixed_relation_test(col1, col2)
        assert result['risk_level'] == 'low'
        assert result['risk_score'] < 30
    
    def test_insufficient_data(self):
        """数据不足"""
        result = fixed_relation_test([1.0, 2.0], [3.0, 4.0])
        assert result['status'] == 'insufficient_data'
    
    def test_unequal_lengths(self):
        """长度不一致应报错"""
        result = fixed_relation_test([1, 2, 3], [4, 5])
        assert result['status'] == 'error'


# ============================================================
# Test: Decimal Consistency Test
# ============================================================

class TestDecimalConsistencyTest:
    """小数位一致性检测模块测试"""
    
    def test_diverse_decimals_low_risk(self):
        """多样化小数模式应低风险"""
        random.seed(42)
        values = [f"{random.uniform(1, 100):.{random.randint(1,4)}f}" for _ in range(50)]
        result = decimal_consistency_test(values)
        assert result['status'] == 'completed'
        assert result['risk_level'] in ('low', 'medium')
    
    def test_repeated_decimals_high_risk(self):
        """高度重复的小数模式应高风险"""
        # 所有值小数部分都是 .34
        values = [f"{i}.34" for i in range(1, 31)]
        result = decimal_consistency_test(values)
        assert result['status'] == 'completed'
        assert result['risk_score'] >= 25  # 至少中风险
    
    def test_insufficient_data(self):
        """数据不足"""
        values = ['1.23', '4.56']
        result = decimal_consistency_test(values)
        assert result['status'] == 'insufficient_data'


# ============================================================
# Integration Test
# ============================================================

class TestIntegration:
    """集成测试：模拟完整检测流程"""
    
    def test_fake_data_high_risk(self):
        """已知造假数据应返回高风险"""
        # 模拟耿同学发现的典型造假：固定比例关系
        control = [2.34, 3.12, 1.87, 4.56, 2.98, 3.45, 1.23, 5.67, 2.01, 3.89]
        treatment = [x * 2 for x in control]  # 精确 ×2
        
        result = fixed_relation_test(control, treatment, 'Control', 'Treatment')
        assert result['risk_score'] >= 85
        assert 'fixed_ratio' in result['detections']
        assert result['detections']['fixed_ratio']['mean_ratio'] == 2.0
    
    def test_real_data_low_risk(self):
        """正常实验数据应返回低风险"""
        random.seed(123)
        # 模拟真实实验：基础值 + 效应 + 随机噪声
        control = [random.gauss(5, 1.5) for _ in range(20)]
        treatment = [x * random.gauss(2, 0.3) for x in control]  # ×2 但有变异
        
        result = fixed_relation_test(control, treatment, 'Control', 'Treatment')
        # 由于有随机噪声，不应该报告"精确"固定关系
        assert result['detections']['fixed_ratio']['is_exact'] == False
    
    def test_output_schema_compliance(self):
        """输出格式应符合标准 schema"""
        values = [f"{random.uniform(1, 100):.2f}" for _ in range(50)]
        result = last_digit_test(values)
        
        # 必须包含的标准字段
        required_fields = ['test_name', 'status', 'risk_level', 'risk_score', 'interpretation']
        for field in required_fields:
            assert field in result, f"缺少必需字段: {field}"
        
        # 风险评分范围
        assert 0 <= result['risk_score'] <= 100
        
        # 风险等级合法值
        assert result['risk_level'] in ('low', 'medium', 'medium-high', 'high')


# ============================================================
# Run tests
# ============================================================

def run_all_tests():
    """简易测试运行器（不依赖 pytest）"""
    import traceback
    
    test_classes = [
        TestLastDigitTest,
        TestBenfordTest,
        TestGrimTest,
        TestFixedRelationTest,
        TestDecimalConsistencyTest,
        TestIntegration,
    ]
    
    total = 0
    passed = 0
    failed = 0
    errors = []
    
    print("=" * 70)
    print("  🧪 Geng Skill 单元测试")
    print("=" * 70)
    print()
    
    for test_class in test_classes:
        class_name = test_class.__name__
        print(f"▶ {class_name}")
        
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        
        for method_name in methods:
            total += 1
            try:
                getattr(instance, method_name)()
                passed += 1
                print(f"  ✅ {method_name}")
            except AssertionError as e:
                failed += 1
                errors.append((class_name, method_name, str(e)))
                print(f"  ❌ {method_name}: {e}")
            except Exception as e:
                failed += 1
                errors.append((class_name, method_name, traceback.format_exc()))
                print(f"  💥 {method_name}: {type(e).__name__}: {e}")
        print()
    
    print("=" * 70)
    print(f"  结果: {passed} 通过 / {failed} 失败 / {total} 总计")
    print("=" * 70)
    
    if errors:
        print("\n❌ 失败详情:")
        for cls, method, err in errors:
            print(f"  {cls}.{method}: {err[:200]}")
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
