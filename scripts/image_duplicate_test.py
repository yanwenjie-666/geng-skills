#!/usr/bin/env python3
"""
图像重复检测 (Image Duplication Detection)
============================================
原理：检测论文图片中是否存在重复使用或篡改的图像。
使用感知哈希(pHash)和结构相似性(SSIM)来识别：
1. 完全相同的图片出现在不同实验条件下
2. 经过旋转、翻转、裁剪后重复使用的图片
3. 调整亮度/对比度后复用的图片

这是学术造假中常见的手段，尤其在Western blot、
显微镜图片、流式细胞术散点图等场景中。

致敬"耿同学讲故事" — 用数据说话，让造假无所遁形。
"""

import argparse
import sys
import json
import os
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    from skimage.metrics import structural_similarity as ssim
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False


def average_hash(image, hash_size=16):
    """计算平均感知哈希"""
    img = image.convert('L').resize((hash_size, hash_size), Image.LANCZOS)
    pixels = np.array(img)
    mean = pixels.mean()
    return (pixels > mean).flatten()


def difference_hash(image, hash_size=16):
    """计算差异感知哈希"""
    img = image.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = np.array(img)
    return (pixels[:, 1:] > pixels[:, :-1]).flatten()


def hamming_distance(hash1, hash2):
    """计算汉明距离（归一化到0-1）"""
    return np.sum(hash1 != hash2) / len(hash1)


def compute_ssim(img1, img2, target_size=(256, 256)):
    """计算结构相似性指数"""
    if not HAS_SKIMAGE:
        return None
    
    # 统一尺寸
    img1_resized = img1.convert('L').resize(target_size, Image.LANCZOS)
    img2_resized = img2.convert('L').resize(target_size, Image.LANCZOS)
    
    arr1 = np.array(img1_resized)
    arr2 = np.array(img2_resized)
    
    score = ssim(arr1, arr2)
    return float(score)


def check_rotations(img1, img2, threshold=0.85):
    """检查图像经过旋转/翻转后是否匹配"""
    transformations = [
        ('original', lambda x: x),
        ('rotate_90', lambda x: x.rotate(90, expand=True)),
        ('rotate_180', lambda x: x.rotate(180, expand=True)),
        ('rotate_270', lambda x: x.rotate(270, expand=True)),
        ('flip_horizontal', lambda x: x.transpose(Image.FLIP_LEFT_RIGHT)),
        ('flip_vertical', lambda x: x.transpose(Image.FLIP_TOP_BOTTOM)),
    ]
    
    best_match = None
    best_score = 0
    
    hash1 = average_hash(img1)
    
    for name, transform in transformations:
        transformed = transform(img2)
        hash2 = average_hash(transformed)
        similarity = 1 - hamming_distance(hash1, hash2)
        
        if similarity > best_score:
            best_score = similarity
            best_match = name
    
    return {
        'best_transformation': best_match,
        'best_similarity': round(best_score, 4),
        'is_match': best_score >= threshold
    }


def find_duplicates(image_dir, threshold=0.85, extensions=None):
    """
    在目录中查找重复或相似的图片
    
    Parameters
    ----------
    image_dir : str
        图片目录路径
    threshold : float
        相似度阈值（0-1），超过此值判定为重复
    extensions : list
        支持的图片格式
    
    Returns
    -------
    dict : 检测结果
    """
    if not HAS_PILLOW:
        return {
            'status': 'error',
            'message': '需要安装 Pillow: pip install Pillow'
        }
    
    if extensions is None:
        extensions = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif']
    
    # 收集所有图片文件
    image_files = []
    for ext in extensions:
        image_files.extend(Path(image_dir).glob(f'*{ext}'))
        image_files.extend(Path(image_dir).glob(f'*{ext.upper()}'))
    
    image_files = sorted(set(image_files))
    
    if len(image_files) < 2:
        return {
            'status': 'insufficient_data',
            'message': f'目录中仅找到 {len(image_files)} 张图片，需要至少2张进行比较',
            'n_images': len(image_files)
        }
    
    # 计算所有图片的哈希
    hashes = {}
    for img_path in image_files:
        try:
            img = Image.open(img_path)
            hashes[str(img_path)] = {
                'avg_hash': average_hash(img),
                'diff_hash': difference_hash(img),
                'size': img.size,
                'image': img
            }
        except Exception as e:
            continue
    
    # 两两比较
    duplicates = []
    paths = list(hashes.keys())
    
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            path1, path2 = paths[i], paths[j]
            h1, h2 = hashes[path1], hashes[path2]
            
            # 平均哈希相似度
            avg_sim = 1 - hamming_distance(h1['avg_hash'], h2['avg_hash'])
            
            # 差异哈希相似度
            diff_sim = 1 - hamming_distance(h1['diff_hash'], h2['diff_hash'])
            
            # 综合相似度
            combined_sim = max(avg_sim, diff_sim)
            
            if combined_sim >= threshold:
                pair_result = {
                    'file_1': os.path.basename(path1),
                    'file_2': os.path.basename(path2),
                    'avg_hash_similarity': round(float(avg_sim), 4),
                    'diff_hash_similarity': round(float(diff_sim), 4),
                    'combined_similarity': round(float(combined_sim), 4),
                }
                
                # 检查旋转/翻转匹配
                rotation_check = check_rotations(
                    h1['image'], h2['image'], threshold
                )
                pair_result['rotation_check'] = rotation_check
                
                # SSIM（如果可用）
                if HAS_SKIMAGE:
                    ssim_score = compute_ssim(h1['image'], h2['image'])
                    pair_result['ssim'] = round(ssim_score, 4)
                
                duplicates.append(pair_result)
    
    # 关闭所有图片
    for h in hashes.values():
        h['image'].close()
    
    # 风险评分
    n_duplicates = len(duplicates)
    n_images = len(image_files)
    
    if n_duplicates == 0:
        risk_level = 'low'
        risk_score = 0
    elif n_duplicates <= 1:
        risk_level = 'medium'
        risk_score = 40
    elif n_duplicates <= 3:
        risk_level = 'medium-high'
        risk_score = 60
    else:
        risk_level = 'high'
        risk_score = 80 + min(20, n_duplicates * 3)
    
    # 如果有完美匹配（相似度>0.98），直接拉高
    perfect_matches = [d for d in duplicates if d['combined_similarity'] > 0.98]
    if perfect_matches:
        risk_score = max(risk_score, 90)
        risk_level = 'high'
    
    result = {
        'test_name': 'Image Duplication Detection (图像重复检测)',
        'status': 'completed',
        'n_images_scanned': n_images,
        'n_duplicate_pairs': n_duplicates,
        'threshold': threshold,
        'duplicates': duplicates,
        'risk_level': risk_level,
        'risk_score': round(float(risk_score), 1),
        'interpretation': _interpret_image(n_duplicates, n_images, duplicates)
    }
    
    return result


def _interpret_image(n_duplicates, n_images, duplicates):
    """生成可读的解释"""
    if n_duplicates == 0:
        return f"✅ 在 {n_images} 张图片中未发现重复或高度相似的图像对。"
    
    perfect = [d for d in duplicates if d['combined_similarity'] > 0.98]
    
    if perfect:
        return (
            f"⚠️ 发现 {len(perfect)} 对近乎完全相同的图片！"
            f"这些图片可能是同一图片的重复使用，强烈建议核查是否为不同实验条件下的独立数据。"
        )
    else:
        return (
            f"⚡ 发现 {n_duplicates} 对高度相似的图片（共扫描 {n_images} 张）。"
            f"可能存在图片复用或篡改，建议人工核查具体图片内容。"
        )


def main():
    parser = argparse.ArgumentParser(
        description='图像重复检测 - 检测论文图片是否存在重复使用或篡改'
    )
    parser.add_argument('--input_dir', '-i', required=True, help='图片目录路径')
    parser.add_argument('--threshold', '-t', type=float, default=0.85,
                       help='相似度阈值（0-1），默认0.85')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.input_dir):
        print(f"错误：目录不存在: {args.input_dir}", file=sys.stderr)
        sys.exit(1)
    
    result = find_duplicates(args.input_dir, args.threshold)
    
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"结果已保存至: {args.output}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
