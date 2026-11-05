import io

import numpy as np
from PIL import Image

from app.diff_engine import compute_diff


def _make_png(
    size: tuple[int, int] = (200, 150),
    color: tuple[int, int, int] = (100, 100, 100),
) -> bytes:
    """Create a solid-color PNG image as bytes."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_png_with_rect(
    size: tuple[int, int] = (200, 150),
    bg_color: tuple[int, int, int] = (100, 100, 100),
    rect: tuple[int, int, int, int] = (50, 40, 100, 90),
    rect_color: tuple[int, int, int] = (255, 0, 0),
) -> bytes:
    """Create a PNG image with a colored rectangle drawn on it."""
    img = Image.new("RGB", size, bg_color)
    arr = np.array(img)
    x1, y1, x2, y2 = rect
    arr[y1:y2, x1:x2] = rect_color
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_identical_images_no_diff():
    """Identical images should produce no diff regions."""
    img = _make_png()
    regions = compute_diff(img, img)
    assert regions == []


def test_single_modified_region():
    """One modified rectangle should produce one DiffRegion."""
    template = _make_png()
    test = _make_png_with_rect(rect=(50, 40, 100, 90), rect_color=(255, 0, 0))
    regions = compute_diff(template, test, threshold=20, min_area=50)
    assert len(regions) == 1
    box = regions[0].bounding_box
    # The bounding box should encompass the modified region (with padding)
    assert box.x_min <= 50
    assert box.y_min <= 40
    assert box.x_max >= 100
    assert box.y_max >= 90


def test_multiple_separate_modifications():
    """Two separate modified rectangles should produce two DiffRegions."""
    template = _make_png(size=(300, 200))
    # Create test image with two separate rectangles
    img = Image.new("RGB", (300, 200), (100, 100, 100))
    arr = np.array(img)
    arr[10:40, 10:40] = (255, 0, 0)     # Top-left
    arr[150:180, 250:280] = (0, 255, 0)  # Bottom-right
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    test = buf.getvalue()

    regions = compute_diff(template, test, threshold=20, min_area=50)
    assert len(regions) == 2


def test_tiny_noise_filtered():
    """Very small diff regions should be filtered out by min_area."""
    template = _make_png(size=(200, 150))
    # Create a tiny 3x3 pixel modification
    img = Image.new("RGB", (200, 150), (100, 100, 100))
    arr = np.array(img)
    arr[75:78, 100:103] = (255, 255, 255)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    test = buf.getvalue()

    # With min_area=100, a 3x3 region (9 pixels) should be filtered
    regions = compute_diff(template, test, threshold=20, min_area=100)
    assert len(regions) == 0


def test_nearby_modifications_merged():
    """Overlapping or nearby modifications should be merged into one region."""
    template = _make_png(size=(200, 150))
    # Create two adjacent rectangles that should merge after padding
    img = Image.new("RGB", (200, 150), (100, 100, 100))
    arr = np.array(img)
    arr[50:70, 50:70] = (255, 0, 0)
    arr[50:70, 75:95] = (0, 255, 0)  # 5px gap, should merge with 20px padding
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    test = buf.getvalue()

    regions = compute_diff(template, test, threshold=20, min_area=50, padding=20)
    assert len(regions) == 1


def test_crop_is_valid_png():
    """Both raw and highlighted crops should be valid PNG images."""
    template = _make_png()
    test = _make_png_with_rect(rect=(50, 40, 100, 90), rect_color=(255, 0, 0))
    regions = compute_diff(template, test, threshold=20, min_area=50)
    assert len(regions) >= 1
    raw_img = Image.open(io.BytesIO(regions[0].crop_raw))
    assert raw_img.format == "PNG"
    highlighted_img = Image.open(io.BytesIO(regions[0].crop_highlighted))
    assert highlighted_img.format == "PNG"


def test_bounds_within_image():
    """All bounding boxes should be within the image dimensions."""
    size = (200, 150)
    template = _make_png(size=size)
    # Modification near edge
    test = _make_png_with_rect(size=size, rect=(180, 130, 200, 150), rect_color=(255, 0, 0))
    regions = compute_diff(template, test, threshold=20, min_area=50)
    for region in regions:
        box = region.bounding_box
        assert box.x_min >= 0
        assert box.y_min >= 0
        assert box.x_max <= size[0]
        assert box.y_max <= size[1]


def test_dimension_mismatch_raises():
    """Images with different dimensions should raise ValueError."""
    img1 = _make_png(size=(200, 150))
    img2 = _make_png(size=(300, 200))
    try:
        compute_diff(img1, img2)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "dimensions must match" in str(e)
