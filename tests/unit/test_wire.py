from core.automation.wire import _anchor_text, _menu_terminal_expect, wire_to_steps


def test_empty_route():
    assert wire_to_steps([]) == []


def test_unknown_wire_keys_are_dropped():
    assert wire_to_steps([{"teleport": "x"}]) == []


def test_kinds_map_and_last_step_is_final():
    steps = wire_to_steps([{"shortcut": "Cmd+F"}, {"click_text": "Flex"}])
    assert [s["kind"] for s in steps] == ["key", "click_text"]
    assert steps[-1]["final"] is True
    assert "final" not in steps[0]


def test_key_step_expects_next_steps_anchor():
    steps = wire_to_steps([{"shortcut": "Cmd+F"}, {"click_text": ["Off", "Slicing"]}])
    assert steps[0]["expect"] == ["Off", "Slicing"]


def test_menu_route_to_settings_row():
    steps = wire_to_steps([
        {"menu_path": ["Logic Pro", "Settings", "Audio…"]},
        {"click_value_of": "I/O Buffer Size"},
        {"choose": "256", "reopen": [{"menu_path": ["Logic Pro", "Settings", "Audio…"]}]},
    ])
    menu, click, choose = steps
    assert menu["expect"] == ["I/O Buffer Size"]
    assert menu["skip_if_row"] == ["I/O Buffer Size"]
    assert click == {"kind": "click_value_of", "label": "I/O Buffer Size"}
    assert choose["row"] == "I/O Buffer Size"
    assert choose["reopen"] == [{"menu_path": ["Logic Pro", "Settings", "Audio…"]}]
    assert choose["final"] is True


def test_choose_after_click_text_has_no_row():
    steps = wire_to_steps([{"click_text": "Flex Pitch"}, {"choose": "Slicing", "shows": {"Flex Time - Slicing": "Slicing"}}])
    assert steps[1]["row"] is None
    assert steps[1]["shows"] == {"Flex Time - Slicing": "Slicing"}


def test_disclosure_click_expects_following_row():
    steps = wire_to_steps([{"click_text": "Region"}, {"click_value_of": "Mute"}])
    assert steps[0]["expect"] == ["Mute"]


def test_wire_sent_expect_is_kept():
    steps = wire_to_steps([{"menu_path": ["File", "Project Settings", "Audio…"], "expect": ["Sample Rate"]},
                           {"shortcut": "Cmd+S"}])
    assert steps[0]["expect"] == ["Sample Rate"]
    assert steps[0]["skip_if_row"] == ["Sample Rate"]


def test_terminal_menu_step_expects_tab_name_only_for_tabbed_panes():
    tabbed = wire_to_steps([{"menu_path": ["Logic Pro", "Settings", "Recording…"]}])
    assert tabbed[0]["expect"] == ["Recording"]
    command = wire_to_steps([{"menu_path": ["Record", "Low Latency Monitoring Mode"]}])
    assert "expect" not in command[0]


def test_ax_steps_pass_through():
    steps = wire_to_steps([{"ax_open_plugin": "Compressor", "new": True, "track": "Audio 1"},
                           {"ax_set_param": {"plugin": "Compressor", "param": "Ratio", "value": 4}}])
    assert steps[0] == {"kind": "ax_open_plugin", "value": "Compressor", "new": True, "track": "Audio 1"}
    assert steps[1]["value"] == {"plugin": "Compressor", "param": "Ratio", "value": 4}


def test_anchor_text():
    assert _anchor_text({"kind": "click_value_of", "label": "Tempo"}) == ["Tempo"]
    assert _anchor_text({"kind": "click_text", "value": "Flex"}) == ["Flex"]
    assert _anchor_text({"kind": "menu", "path": ["Track", "Show"]}) == ["Track"]
    assert _anchor_text({"kind": "key", "value": "Cmd+F"}) is None
    assert _anchor_text({"kind": "choose", "value": "x"}) is None


def test_menu_terminal_expect_strips_ellipsis():
    assert _menu_terminal_expect(["File", "Project Settings", "Smart Tempo…"]) == ["Smart Tempo"]
    assert _menu_terminal_expect(["Settings"]) is None
