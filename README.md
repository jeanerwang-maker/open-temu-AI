# Temu 店铺名称与 Logo 批量生成

用于在 Temu 全托管店群模式下快速生成店铺名称和对应 Logo。

## 功能
- 根据类目与数量生成不重复的店铺英文名称（使用生僻英文词）。
- 自动生成对应 Logo，支持多尺寸导出（40x40 / 100x100 / 1024x1024）。
- 输出 CSV，包含店铺名称与各尺寸 Logo 的文件路径。

## 安装依赖
```bash
pip install -r requirements.txt
```

## 使用示例
```bash
python store_generator.py --category "beauty" --count 10 --sizes 40,100,1024
```

默认输出目录为 `output/`，CSV 文件为 `output/store_assets.csv`。

## 参数说明
- `--category`：类目名称。
- `--count`：需要生成的数量。
- `--sizes`：Logo 尺寸列表（用逗号分隔）。
- `--output`：Logo 输出目录。
- `--csv`：CSV 输出路径。
