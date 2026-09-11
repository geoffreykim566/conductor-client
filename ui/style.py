"""App-wide stylesheet, applied once at the QApplication level so every
top-level window (main chat window, popups, minimized bubble, onboarding
dialogs) shares the same look without each needing its own setStyleSheet call."""

MONO = '"Menlo", monospace'

STYLESHEET = f"""
QWidget#setupRoot, QWidget#guideRoot, QWidget#popupRoot {{
    background-color: rgba(28, 28, 30, 0.9);
    border: 1px solid rgba(42, 42, 44, 0.6);
    border-radius: 14px;
}}
QWidget#minimizedRoot {{
    background-color: rgba(28, 28, 30, 0.82);
    border: 1px solid rgba(42, 42, 44, 0.6);
    border-radius: 30px;
}}
QWidget#inputPanel {{
    background: transparent;
    border: none;
}}
QWidget#sessionHeader {{
    border-bottom: 1px solid #222224;
}}
QLabel#title {{
    color: #f2f2f7;
    font-family: {MONO};
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QLabel#subtitle {{
    color: #636366;
    font-family: {MONO};
    font-size: 11px;
}}
QLabel#stepLabel {{
    color: #ebebf5;
    font-size: 13px;
    padding: 2px 0;
}}
QLabel#sessionTitle {{
    color: #636366;
    font-family: {MONO};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}
QLabel#error {{
    color: #ff453a;
    font-family: {MONO};
    font-size: 11px;
}}
QPushButton#headerBtn {{
    background: transparent;
    color: #48484a;
    border: none;
    font-size: 13px;
    font-family: {MONO};
    padding: 0;
}}
QPushButton#headerBtn:hover {{
    color: #ebebf5;
}}
QFrame#userBubble {{
    background-color: rgba(8, 110, 212, 0.78);
    border-radius: 16px;
}}
QFrame#userBubble QLabel {{
    color: #ffffff;
}}
QFrame#assistantBubble {{
    background-color: rgba(28, 28, 30, 0.82);
    border-radius: 16px;
    border: 1px solid #2c2c2e;
}}
QFrame#assistantBubble QLabel {{
    color: #ebebf5;
}}
QTextEdit {{
    background-color: #1c1c1e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 10px;
    padding: 6px 10px;
    font-family: {MONO};
    font-size: 12px;
}}
QTextEdit:focus {{
    border: 1px solid #48484a;
}}
QWidget#inputBubble {{
    background-color: rgba(28, 28, 30, 0.82);
    border: 1px solid rgba(42, 42, 44, 0.6);
    /* Must stay >= half the bubble's actual height (input_bar.py's
       _CONTROL_SIZE + bubble_row's own 4+4 margins) for fully-rounded
       (pill/capsule) ends -- a smaller radius reads as slightly
       rectangular once the control size grows (found live 2026-09-04). */
    border-radius: 23px;
}}
QTextEdit#bareInput {{
    background: transparent;
    border: none;
    padding: 0;
    font-size: 11px;
}}
QLineEdit {{
    background-color: #1c1c1e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 8px;
    padding: 8px 10px;
    font-family: {MONO};
    font-size: 12px;
}}
QLineEdit:focus {{
    border: 1px solid #48484a;
}}
QPushButton {{
    background-color: #2c2c2e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 6px;
    font-family: {MONO};
    font-size: 11px;
}}
QPushButton:hover {{
    background-color: #38383a;
}}
QPushButton:disabled {{
    color: #3a3a3c;
}}
QPushButton#sendBtn {{
    background-color: rgba(10, 132, 255, 0.7);
    color: #ffffff;
    border: none;
    /* Exactly half of input_bar.py's _CONTROL_SIZE (its fixed width/height)
       for a perfect circle -- a smaller radius reads as a rounded square. */
    border-radius: 19px;
    font-size: 15px;
}}
QPushButton#sendBtn:hover {{
    background-color: rgba(64, 156, 255, 0.7);
}}
QPushButton#sendBtn:disabled {{
    background-color: #2c2c2e;
    color: #3a3a3c;
}}
QLabel#remainingLabel {{
    background: transparent;
    color: #636366;
    font-family: {MONO};
    font-size: 10px;
}}
QPushButton#rateBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    font-family: {MONO};
    font-size: 11px;
    padding: 0 6px;
}}
QPushButton#rateBtn:hover {{
    background: #1c1c1e;
    border: 1px solid #2c2c2e;
}}
QPushButton#rateBtn[selected="true"] {{
    background: #2c2c2e;
    border: 1px solid #0a84ff;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    /* Bottom margin keeps the track clear of the backdrop panel's 18px
    bottom-right corner radius (chat_window.py paintEvent) -- at this
    close to the right edge, the track ran almost to the very bottom and
    the handle visibly spilled past the rounded corner's curve when
    scrolled all the way down (found live 2026-09-04). */
    margin: 0 0 8px 0;
}}
QScrollBar::handle:vertical {{
    background: transparent;
    border-radius: 2px;
    min-height: 24px;
}}
QScrollBar[scrolling="true"]::handle:vertical {{
    background: #38383a;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QPushButton#bubble {{
    background-color: rgba(28, 28, 30, 0.82);
    color: white;
    border: 1px solid rgba(42, 42, 44, 0.6);
    border-radius: 30px;
    font-size: 24px;
}}
QPushButton#bubble:hover {{
    background-color: rgba(44, 44, 46, 0.82);
}}
QPushButton#danger {{
    background-color: #2a1515;
    color: #ff453a;
    border: 1px solid #3a2020;
    border-radius: 6px;
    font-family: {MONO};
    font-size: 11px;
    padding: 6px;
}}
QPushButton#danger:hover {{
    background-color: #ff453a;
    color: #ffffff;
    border-color: #ff453a;
}}
QFrame#sessionRow {{
    background: transparent;
    border-radius: 10px;
}}
QFrame#sessionRow:hover {{
    background: #1c1c1e;
}}
QFrame#sessionRowActive {{
    background: #1a2640;
    border-radius: 10px;
}}
QLabel#sessionDate {{
    color: #ebebf5;
    font-family: {MONO};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#sessionPreview {{
    color: #636366;
    font-size: 12px;
}}
QLabel#sessionEmpty {{
    color: #48484a;
    font-family: {MONO};
    font-size: 11px;
    padding: 32px;
}}
QPushButton#showMeBtn {{
    background: transparent;
    border: 1px solid #38383a;
    border-radius: 6px;
    color: #0a84ff;
    font-family: {MONO};
    font-size: 10px;
    font-weight: 600;
    padding: 3px 8px;
}}
QPushButton#showMeBtn:hover {{
    border-color: #0a84ff;
    background: #0f1f3a;
}}
QPushButton#showMeBtn:disabled {{
    color: #48484a;
    border-color: #2c2c2e;
}}
QLabel#chatPlaceholder {{
    color: #3a3a3c;
    font-family: {MONO};
    font-size: 11px;
    padding: 32px;
}}
QPushButton#primary {{
    background-color: rgba(8, 110, 212, 0.78);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 9px;
    font-family: {MONO};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: rgba(64, 156, 255, 0.78); }}
QPushButton#primary:disabled {{ background-color: #2c2c2e; color: #48484a; }}
QPushButton#secondary {{
    background-color: #2c2c2e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 8px;
    padding: 9px;
    font-family: {MONO};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#secondary:hover {{ background-color: #38383a; }}
QPushButton#ghost {{
    background: transparent;
    color: #0a84ff;
    border: none;
    font-family: {MONO};
    font-size: 11px;
    padding: 0;
}}
QPushButton#ghost:hover {{ color: #409cff; }}
QPushButton#chip {{
    background-color: #1c1c1e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 8px;
    padding: 7px 8px;
    font-family: {MONO};
    font-size: 11px;
}}
QPushButton#chip:hover {{ border: 1px solid #48484a; }}
QPushButton#chip[selected="true"] {{
    background-color: #0a84ff;
    border: 1px solid #0a84ff;
    color: white;
}}
"""
