#!/usr/bin/env python3
import argparse
import csv
import hashlib
import random
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


DEFAULT_SIZES = [40, 100, 1024]


def load_words(path: Path) -> list[str]:
    words = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [word for word in words if word]


def generate_store_names(category: str, count: int, words: Iterable[str]) -> list[str]:
    random_words = list(words)
    if len(random_words) < count:
        raise ValueError("词库太少，无法生成足够不重复的名称。")

    random.shuffle(random_words)
    names = []
    used = set()
    for word in random_words:
        candidate = f"{word} {category.title()}"
        if candidate in used:
            continue
        used.add(candidate)
        names.append(candidate)
        if len(names) >= count:
            break

    if len(names) < count:
        raise ValueError("无法生成足够不重复的名称，请增加词库或减少数量。")
    return names


def name_seed(name: str) -> int:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def color_from_seed(seed: int, offset: int) -> tuple[int, int, int]:
    rng = random.Random(seed + offset)
    return (rng.randint(20, 220), rng.randint(20, 220), rng.randint(20, 220))


def render_logo(name: str, size: int, output_path: Path) -> None:
    seed = name_seed(name)
    background_color = color_from_seed(seed, 1)
    text_color = color_from_seed(seed, 2)
    accent_color = color_from_seed(seed, 3)
    img = Image.new("RGB", (size, size), color=background_color)
    draw = ImageDraw.Draw(img)

    initials = "".join([part[0] for part in name.split()[:2]]).upper()
    rng = random.Random(seed)

    # Draw name-based geometric accents to make each logo distinct.
    for _ in range(3):
        x0 = rng.randint(0, size // 2)
        y0 = rng.randint(0, size // 2)
        x1 = rng.randint(size // 2, size)
        y1 = rng.randint(size // 2, size)
        draw.ellipse((x0, y0, x1, y1), outline=accent_color, width=max(1, size // 40))

    for _ in range(2):
        x0 = rng.randint(0, size)
        y0 = rng.randint(0, size)
        x1 = rng.randint(0, size)
        y1 = rng.randint(0, size)
        draw.line((x0, y0, x1, y1), fill=accent_color, width=max(1, size // 30))

    font_size = int(size * 0.5)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (size - text_width) / 2
    text_y = (size - text_height) / 2
    draw.text((text_x, text_y), initials, font=font, fill=text_color)

    img.save(output_path, format="PNG")


def generate_assets(category: str, count: int, sizes: list[int], output_dir: Path) -> list[dict[str, str]]:
    words = load_words(Path("data/rare_words.txt"))
    names = generate_store_names(category, count, words)

    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str]] = []

    for name in names:
        record = {"store_name": name}
        for size in sizes:
            filename = f"{name.replace(' ', '_').lower()}_{size}x{size}.png"
            path = output_dir / filename
            render_logo(name, size, path)
            record[f"logo_{size}x{size}"] = str(path)
        records.append(record)

    return records


def write_csv(records: list[dict[str, str]], output_path: Path) -> None:
    if not records:
        return
    fieldnames = list(records[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成 Temu 店铺名称和 Logo")
    parser.add_argument("--category", required=True, help="类目名称")
    parser.add_argument("--count", type=int, required=True, help="生成数量")
    parser.add_argument(
        "--sizes",
        default=",".join(str(size) for size in DEFAULT_SIZES),
        help="Logo 尺寸列表，例如 40,100,1024",
    )
    parser.add_argument("--output", default="output", help="输出目录")
    parser.add_argument("--csv", default="output/store_assets.csv", help="CSV 输出路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sizes = [int(value.strip()) for value in args.sizes.split(",") if value.strip()]
    if not sizes:
        raise SystemExit("请提供至少一个尺寸。")

    records = generate_assets(args.category, args.count, sizes, Path(args.output))
    write_csv(records, Path(args.csv))

    print(f"已生成 {len(records)} 个店铺名称和 Logo。")
    print(f"CSV 已保存至 {args.csv}")


if __name__ == "__main__":
    main()
