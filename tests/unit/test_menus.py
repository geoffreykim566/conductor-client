from core.automation import menus


def _record_click(monkeypatch):
    clicks = []
    monkeypatch.setattr(menus, "check_stop", lambda stop_event: None)
    monkeypatch.setattr(menus, "menu_window_count", lambda: 0)
    monkeypatch.setattr(menus, "wait_menu_count", lambda n: True)
    monkeypatch.setattr(menus, "click_at", lambda x, y, stop_event: clicks.append((x, y)))
    return clicks


def test_menubar_title_clicked_at_its_ax_point(monkeypatch):
    clicks = _record_click(monkeypatch)
    monkeypatch.setattr(menus, "title_point_ax", lambda title: (83.5, 15.0))
    monkeypatch.setattr(menus, "title_point_ocr", lambda title: (_ for _ in ()).throw(AssertionError("OCR ran")))
    menus.open_menubar_menu("Logic Pro")
    assert clicks == [(83.5, 15.0)]


def test_menubar_title_falls_back_to_ocr_without_ax(monkeypatch):
    clicks = _record_click(monkeypatch)
    monkeypatch.setattr(menus, "title_point_ax", lambda title: None)
    monkeypatch.setattr(menus, "title_point_ocr", lambda title: (90.0, 14.0))
    menus.open_menubar_menu("Logic Pro")
    assert clicks == [(90.0, 14.0)]
