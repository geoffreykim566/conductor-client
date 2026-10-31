from ui.onboarding.permissions import accessibility_name, active_index, setup_permissions


def test_accessibility_renamed_from_macos_27():
    assert accessibility_name("27.0.1") == "Device Control and Data Access"
    assert accessibility_name("28.0") == "Device Control and Data Access"
    assert accessibility_name("26.4") == "Accessibility"
    assert accessibility_name("") == "Accessibility"


def test_only_first_missing_row_is_live():
    assert active_index([False, False]) == 0
    assert active_index([True, False]) == 1
    assert active_index([False, True]) == 0
    assert active_index([True, True]) is None


def test_asks_accessibility_then_screen_recording_without_input_monitoring():
    perms = setup_permissions()
    assert [p.key for p in perms] == ["accessibility", "screen"]
    assert [p.live for p in perms] == [True, False]
    assert perms[0].settings_url.endswith("Privacy_Accessibility")
