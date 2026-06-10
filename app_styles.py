# app_styles.py

def get_stylesheet(accent_color: str = "#0078D7") -> str:
    return f"""
    #IslandWidget, box, stack, grid {{
        background: transparent;
        background-color: transparent;
        background-image: none;
        border: none;
        box-shadow: none;
    }}
    
    label {{
        color: white;
        font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
    }}
    
    label#TitleLabel {{
        font-size: 14px;
        font-weight: 600;
    }}
    
    label#SubtitleLabel {{
        font-size: 12px;
        color: #A0A0A0;
    }}
    
    label#CurrentDayLabel {{
        font-size: 13px;
        font-weight: bold;
        color: #FF5555;
    }}
    
    label#IconLabel {{
        background-color: transparent;
        font-size: 16px;
    }}
    
    button#MediaButton {{
        background-color: transparent;
        color: white;
        border-radius: 14px;
        border: none;
        min-width: 28px;
        min-height: 28px;
        padding: 2px;
    }}
    
    button#MediaButton:hover {{
        background-color: rgba(255, 255, 255, 0.12);
    }}
    
    button#MediaButton:active {{
        background-color: rgba(255, 255, 255, 0.20);
    }}
    
    label#PerfLabel {{
        font-size: 11px;
        color: #CCCCCC;
        font-weight: 600;
    }}

    button#ActionButton {{
        background-color: rgba(255, 255, 255, 0.06);
        color: white;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.04);
    }}
    
    button#ActionButton:hover {{
        background-color: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.16);
    }}

    button#ActionButton:active {{
        background-color: rgba(255, 255, 255, 0.20);
    }}

    button#ControlBall {{
        background-color: #000000;
        color: white;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.16);
        min-width: 48px;
        min-height: 48px;
        font-size: 20px;
        padding: 0px;
    }}
    
    button#ControlBall:hover {{
        background-color: rgba(40, 40, 40, 1.0);
        border: 1px solid rgba(255, 255, 255, 0.31);
    }}

    button#NavButton {{
        background-color: transparent;
        color: #888;
        border: none;
        font-size: 16px;
        padding: 0px 5px;
    }}
    
    button#NavButton:hover {{
        color: white;
    }}
    
    box#WeatherPanel {{
        background-color: #B5B9B5;
        border-radius: 10px 6px 6px 10px;
    }}
    
    box#CalendarPanel {{
        background-color: #B5B9B5;
        border-radius: 6px 6px 10px 6px;
    }}
    
    label#WeatherTemp {{
        font-size: 42px;
        font-weight: 500;
        color: #111111;
    }}
    
    label#WeatherDesc {{
        font-size: 15px;
        font-weight: 500;
        color: #222222;
    }}
    
    label#WeatherHL {{
        font-size: 12px;
        font-weight: 500;
        color: #444444;
    }}
    
    label#CalendarHeader {{
        font-size: 14px;
        font-weight: 800;
        color: white;
        letter-spacing: 1px;
    }}
    
    label#CalendarYear {{
        font-size: 14px;
        font-weight: 600;
        color: #999999;
    }}
    
    label#CalendarDayName {{
        font-size: 10px;
        font-weight: 700;
        color: #555555;
    }}
    
    label#CalendarDate {{
        font-size: 14px;
        font-weight: 600;
        color: #111111;
    }}
    
    label#ActiveDate {{
        background-color: #111111;
        color: white;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 600;
        padding-left: 6px;
        padding-right: 6px;
    }}
    
    label#EventDot {{
        font-size: 12px;
        color: #777777;
    }}
    
    label#EventTime {{
        font-size: 11px;
        font-weight: 600;
        color: #555555;
    }}
    
    label#EventTitle {{
        font-size: 11px;
        font-weight: 700;
        color: #111111;
        letter-spacing: 0.5px;
    }}
    
    separator#EventSep {{
        background-color: rgba(0, 0, 0, 0.1);
        min-height: 1px;
    }}
    
    /* ─── Settings Panel ─────────────────────────────── */
    label#SettingsHeader {{
        font-size: 17px;
        font-weight: 700;
        color: white;
        letter-spacing: 0.5px;
    }}
    
    label#SettingsLabel {{
        font-size: 13px;
        font-weight: 500;
        color: rgba(255, 255, 255, 0.85);
    }}
    
    label#SettingsSectionLabel {{
        font-size: 10px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.35);
        letter-spacing: 1.2px;
    }}
    
    switch {{
        background-color: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 12px;
        min-width: 40px;
        min-height: 22px;
    }}
    
    switch:checked {{
        background-color: rgba(50, 200, 90, 0.85);
        border-color: rgba(50, 200, 90, 0.5);
    }}
    
    switch slider {{
        background-color: white;
        border-radius: 10px;
        min-width: 18px;
        min-height: 18px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.5);
    }}
    
    separator#SettingsSep {{
        background-color: rgba(255, 255, 255, 0.08);
        min-height: 1px;
        margin-top: 2px;
        margin-bottom: 2px;
    }}
    
    combobox#SettingsCombo button {{
        background-color: rgba(255, 255, 255, 0.10);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        color: white;
        padding: 4px 8px;
    }}
    
    combobox#SettingsCombo button:hover {{
        background-color: rgba(255, 255, 255, 0.18);
    }}
    
    button#SettingsSaveBtn {{
        background-color: rgba(255, 255, 255, 0.90);
        color: #000000;
        border-radius: 8px;
        border: none;
        font-weight: 700;
        font-size: 13px;
        padding: 6px 12px;
        margin-top: 4px;
    }}
    
    button#SettingsSaveBtn:hover {{
        background-color: rgba(255, 255, 255, 1.0);
    }}
    
    button#SettingsSaveBtn:active {{
        background-color: rgba(200, 200, 200, 0.95);
    }}
    
    button#MacTopBtn {{
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        border-radius: 12px;
        border: none;
        padding: 4px 12px;
        font-size: 11px;
        font-weight: 600;
    }}
    button#MacTopBtn:hover {{ background-color: rgba(255, 255, 255, 0.2); }}
    
    label#MacAlbumLabel {{
        font-size: 13px;
        font-weight: 600;
        color: #D0D0D0;
    }}
    
    label#MacArtistLabel {{
        font-size: 12px;
        font-weight: 400;
        color: #888888;
    }}
    
    button#MacNavButton {{
        background-color: transparent;
        color: white;
        border: none;
        font-size: 14px;
        padding: 4px;
    }}
    button#MacNavButton:hover {{ color: #ccc; }}
    
    label#MacMonthLabel {{
        font-size: 24px;
        font-weight: 800;
        color: white;
    }}
    
    label#MacCalDay {{
        font-size: 10px;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.5);
    }}
    label#MacCalDate {{
        font-size: 14px;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.5);
    }}
    
    separator#MacSep {{
        background: rgba(255, 255, 255, 0.1);
    }}
    """
