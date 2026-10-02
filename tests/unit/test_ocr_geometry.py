from core.automation.ocr_find import box_center_screen, value_blob_right_of


def w(text, left, top=100, width=40, height=10):
    return {"text": text, "left": left, "top": top, "width": width, "height": height}


def test_box_center_screen_scales_pixels_into_window_points():
    win = {"kCGWindowBounds": {"X": 100, "Y": 50, "Width": 400, "Height": 300}}
    box = {"left": 380, "top": 280, "width": 40, "height": 40}
    assert box_center_screen(box, (800, 600), win) == (100 + 200, 50 + 150)


def test_value_blob_joins_adjacent_words_right_of_label():
    label = w("Buffer:", 0)
    words = [label, w("256", 60), w("Samples", 105), w("far", 400)]
    blob = value_blob_right_of(label, words)
    assert blob["label"] == "256 Samples"
    assert blob["left"] == 60
    assert blob["width"] == 105 + 40 - 60


def test_value_blob_ignores_other_rows_and_left_side():
    label = w("Buffer:", 100)
    words = [label, w("left", 0), w("below", 160, top=140)]
    assert value_blob_right_of(label, words) is None
