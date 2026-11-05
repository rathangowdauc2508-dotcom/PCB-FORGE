from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def draw_template(path: Path) -> None:
    img = Image.new("RGB", (512, 512), "#0f141a")
    draw = ImageDraw.Draw(img)

    # Parallel traces.
    draw.line((80, 200, 430, 200), fill="#c2d3de", width=20)
    draw.line((80, 280, 430, 280), fill="#c2d3de", width=20)

    # Background guide markings.
    draw.rectangle((60, 160, 450, 320), outline="#2f3b46", width=2)
    img.save(path)


def draw_tested(path: Path) -> None:
    img = Image.new("RGB", (512, 512), "#0f141a")
    draw = ImageDraw.Draw(img)

    draw.line((80, 200, 430, 200), fill="#c2d3de", width=20)
    draw.line((80, 280, 430, 280), fill="#c2d3de", width=20)
    draw.rectangle((60, 160, 450, 320), outline="#2f3b46", width=2)

    # Defect bridge (micro-short candidate)
    draw.ellipse((238, 205, 278, 275), fill="#a78a5b")
    draw.line((250, 218, 266, 258), fill="#9e6f3f", width=8)

    # Visual defect hint for humans.
    draw.rectangle((220, 185, 292, 295), outline="#ff6b6b", width=2)
    img.save(path)


def main() -> None:
    assets_dir = Path(__file__).resolve().parents[1] / "data" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    draw_template(assets_dir / "template_board.png")
    draw_tested(assets_dir / "tested_board.png")
    print(f"Generated demo assets in {assets_dir}")


if __name__ == "__main__":
    main()
