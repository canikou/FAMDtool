from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets"
PNG_PATH = ASSET_DIR / "FAMDTool.png"
ICO_PATH = ASSET_DIR / "FAMDTool.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def rounded_rectangle(draw: ImageDraw.ImageDraw, xy, radius: int, fill) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def make_icon(size: int) -> Image.Image:
    scale = size / 1024
    canvas_size = size
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def s(value: int) -> int:
        return round(value * scale)

    rounded_rectangle(
        draw,
        (s(80), s(80), s(944), s(944)),
        s(180),
        (18, 71, 88, 255),
    )
    rounded_rectangle(
        draw,
        (s(122), s(122), s(902), s(902)),
        s(150),
        (25, 115, 132, 255),
    )

    # Clipboard sheet.
    rounded_rectangle(
        draw,
        (s(270), s(190), s(754), s(830)),
        s(76),
        (247, 252, 250, 255),
    )
    rounded_rectangle(
        draw,
        (s(324), s(150), s(700), s(268)),
        s(58),
        (218, 239, 235, 255),
    )
    rounded_rectangle(
        draw,
        (s(405), s(118), s(619), s(204)),
        s(43),
        (238, 78, 85, 255),
    )

    # Medical cross.
    cross = (238, 78, 85, 255)
    rounded_rectangle(draw, (s(462), s(350), s(562), s(665)), s(28), cross)
    rounded_rectangle(draw, (s(354), s(458), s(670), s(558)), s(28), cross)

    # Attendance/check mark accent.
    accent = (241, 192, 76, 255)
    draw.line(
        [(s(357), s(692)), (s(444), s(767)), (s(666), s(612))],
        fill=accent,
        width=s(54),
        joint="curve",
    )
    draw.line(
        [(s(357), s(692)), (s(444), s(767)), (s(666), s(612))],
        fill=(255, 220, 112, 255),
        width=s(26),
        joint="curve",
    )

    return image


def main() -> None:
    ASSET_DIR.mkdir(exist_ok=True)
    large = make_icon(1024)
    large.save(PNG_PATH)
    frames = [make_icon(size) for size in SIZES]
    frames[-1].save(ICO_PATH, sizes=[(size, size) for size in SIZES], append_images=frames[:-1])
    print(f"Wrote {PNG_PATH}")
    print(f"Wrote {ICO_PATH}")


if __name__ == "__main__":
    main()
