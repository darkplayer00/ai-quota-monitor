import os
import sys
import json
import threading
import time
import subprocess
import ctypes
from ctypes import wintypes
import winsound
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageDraw
import pystray
from quota_service import QuotaService
from usage_tracker import UsageTracker

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

# Soporte dual: Modo Portable (si existe portable.txt) o Instalado (%APPDATA%)
PORTABLE_MARKER = os.path.join(APP_DIR, "portable.txt")
if os.path.exists(PORTABLE_MARKER):
    APPDATA_DIR = os.path.join(APP_DIR, "data")
    os.makedirs(APPDATA_DIR, exist_ok=True)
    CONFIG_FILE = os.path.join(APPDATA_DIR, "widget_config.json")
else:
    APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AIQuotaWidget")
    os.makedirs(APPDATA_DIR, exist_ok=True)
    CONFIG_FILE = os.path.join(APPDATA_DIR, "widget_config.json")

STARTUP_PATH = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup", "AI_Quota_Widget.vbs")

ICON_PATH = os.path.join(BUNDLE_DIR, "icon.ico")
if not os.path.exists(ICON_PATH):
    ICON_PATH = os.path.join(APP_DIR, "icon.ico")

THEMES = {
    "bento_dark": {
        "name": "Bento Modern Dark",
        "appearance": "dark",
        "bg_root": "#121418",
        "bg_card": "#181A20",
        "border": "#282C37",
        "bento_bg": "#1F232B",
        "bento_border": "#2A303C",
        "switch_bg": "#13151A",
        "switch_border": "#252932",
        "text_primary": "#F1F3F4",
        "text_secondary": "#9AA0A6",
        "text_muted": "#6E7681",
        "progress_bg": "#2D333F",
        "accent": "#3B82F6",
        "active_tab": "#1A73E8"
    },
    "bento_light": {
        "name": "Bento Clean Light (Claro)",
        "appearance": "light",
        "bg_root": "#EEF2F6",
        "bg_card": "#FFFFFF",
        "border": "#D1D5DB",
        "bento_bg": "#F3F4F6",
        "bento_border": "#E5E7EB",
        "switch_bg": "#E5E7EB",
        "switch_border": "#D1D5DB",
        "text_primary": "#111827",
        "text_secondary": "#4B5563",
        "text_muted": "#6B7280",
        "progress_bg": "#E5E7EB",
        "accent": "#1A73E8",
        "active_tab": "#1A73E8"
    },
    "oled_black": {
        "name": "OLED Pure Black",
        "appearance": "dark",
        "bg_root": "#000000",
        "bg_card": "#0A0A0A",
        "border": "#202020",
        "bento_bg": "#121212",
        "bento_border": "#252525",
        "switch_bg": "#000000",
        "switch_border": "#222222",
        "text_primary": "#FFFFFF",
        "text_secondary": "#888888",
        "text_muted": "#555555",
        "progress_bg": "#1C1C1C",
        "accent": "#64B5F6",
        "active_tab": "#2563EB"
    },
    "cyber_neon": {
        "name": "Cyberpunk Neon",
        "appearance": "dark",
        "bg_root": "#070B12",
        "bg_card": "#0D121D",
        "border": "#00E5FF",
        "bento_bg": "#141C2B",
        "bento_border": "#1E2B3E",
        "switch_bg": "#090D15",
        "switch_border": "#00E5FF",
        "text_primary": "#E0F7FA",
        "text_secondary": "#4DD0E1",
        "text_muted": "#26C6DA",
        "progress_bg": "#1B273A",
        "accent": "#00E5FF",
        "active_tab": "#00B0FF"
    }
}

def load_config():
    default_config = {
        "x": 1000,
        "y": 350,
        "width": 295,
        "height": 300,
        "always_on_top": False,
        "selected_model": "Gemini",
        "show_exact_date": True,
        "dynamic_opacity": False,
        "notifications_enabled": True,
        "sound_enabled": True,
        "theme": "bento_dark",
        "refresh_interval_sec": 60,
        "show_stats": False,
        "stats_mode": "weekly",
        "mini_mode": False
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("width", 295) > 360 or saved.get("width", 295) < 290:
                    saved["width"] = 295
                if not saved.get("show_stats", False) and (saved.get("height", 300) > 330 or saved.get("height", 300) < 290):
                    saved["height"] = 300
                elif saved.get("show_stats", False) and (saved.get("height", 560) > 600 or saved.get("height", 560) < 540):
                    saved["height"] = 560
                if saved.get("theme") == "google_dark":
                    saved["theme"] = "bento_dark"
                default_config.update(saved)
        except Exception:
            pass
    return default_config

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def ensure_visible_coordinates(x, y, w, h):
    try:
        user32 = ctypes.windll.user32
        # Medidas de la pantalla virtual completa (soporte para 1, 2 o más monitores con coords negativas)
        virt_x = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        virt_y = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        virt_w = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        virt_h = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN

        if virt_w <= 0 or virt_h <= 0:
            virt_x, virt_y = 0, 0
            virt_w = user32.GetSystemMetrics(0)
            virt_h = user32.GetSystemMetrics(1)

        # Si el widget está completamente fuera del área virtual de todos los monitores, recentrar al primario
        if x < (virt_x - 50) or x > (virt_x + virt_w - 50) or y < (virt_y - 50) or y > (virt_y + virt_h - 50):
            safe_x = max(20, user32.GetSystemMetrics(0) - w - 25)
            safe_y = max(20, user32.GetSystemMetrics(1) - h - 75)
            return safe_x, safe_y
        return x, y
    except Exception:
        return 900, 300

def apply_screen_snapping(x, y, w, h):
    try:
        user32 = ctypes.windll.user32
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong),
                        ("rcMonitor", RECT),
                        ("rcWork", RECT),
                        ("dwFlags", ctypes.c_ulong)]

        pt = POINT(x + w // 2, y + h // 2)
        h_monitor = user32.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST
        if h_monitor:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi)):
                work = mi.rcWork
                SNAP_DISTANCE = 20
                if abs(x - work.left) < SNAP_DISTANCE:
                    x = work.left + 8
                if abs((x + w) - work.right) < SNAP_DISTANCE:
                    x = work.right - w - 8
                if abs(y - work.top) < SNAP_DISTANCE:
                    y = work.top + 8
                if abs((y + h) - work.bottom) < SNAP_DISTANCE:
                    y = work.bottom - h - 8
                return x, y
        return x, y
    except Exception:
        return x, y

def get_color_for_fraction(fraction):
    if fraction is None:
        return "#70757A"
    if fraction >= 0.60:
        return "#34A853"  # Verde
    elif fraction >= 0.35:
        return "#FBBC04"  # Amarillo
    elif fraction >= 0.15:
        return "#FA7B17"  # Naranja
    else:
        return "#EA4335"  # Rojo

def create_tray_icon_image(color="#70757A"):
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([4, 4, 60, 60], fill="#181A20", outline="#2A2E39", width=4)
    draw.ellipse([18, 18, 46, 46], fill=color)
    return image

def send_windows_notification(title, message, play_sound=True):
    try:
        if play_sound:
            try:
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                pass
        ps_code = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $toastXml = [xml]$template.GetXml()
        $textNodes = $toastXml.GetElementsByTagName('text')
        $textNodes.Item(0).AppendChild($toastXml.CreateTextNode('{title}')) > $null
        $textNodes.Item(1).AppendChild($toastXml.CreateTextNode('{message}')) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($toastXml)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AI Quota Monitor')
        $notifier.Show($toast)
        """
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_code],
            capture_output=True,
            check=False,
            creationflags=CREATE_NO_WINDOW
        )
    except Exception:
        pass

def clean_ghost_icons():
    """Fuerza al Explorador de Windows a purgar inmediatamente iconos fantasma de la bandeja del sistema."""
    try:
        user32 = ctypes.windll.user32
        h_tray = user32.FindWindowW('Shell_TrayWnd', None)
        h_tray_notify = user32.FindWindowExW(h_tray, 0, 'TrayNotifyWnd', None)
        h_sys_pager = user32.FindWindowExW(h_tray_notify, 0, 'SysPager', None)
        h_toolbar = user32.FindWindowExW(h_sys_pager, 0, 'ToolbarWindow32', None)
        if not h_toolbar:
            h_toolbar = user32.FindWindowExW(h_tray_notify, 0, 'ToolbarWindow32', None)

        h_overflow = user32.FindWindowW('NotifyIconOverflowWindow', None)
        h_overflow_toolbar = user32.FindWindowExW(h_overflow, 0, 'ToolbarWindow32', None)

        WM_MOUSEMOVE = 0x0200
        for h in [h_toolbar, h_overflow_toolbar]:
            if h:
                rect = wintypes.RECT()
                user32.GetClientRect(h, ctypes.byref(rect))
                for x in range(0, rect.right, 4):
                    for y in range(0, rect.bottom, 4):
                        user32.PostMessageW(h, WM_MOUSEMOVE, 0, (y << 16) | x)
                user32.InvalidateRect(h, None, True)
                user32.UpdateWindow(h)
    except Exception:
        pass


class PureQuotaWidget(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.quota_service = QuotaService()
        self.usage_tracker = UsageTracker(APPDATA_DIR)
        self.config = load_config()
        self.is_fetching = False
        self.last_quota_data = None
        self.previous_fractions = {}
        self._is_in_foreground = True
        self._hotkey_thread_id = None
        
        self.current_theme_key = self.config.get("theme", "bento_dark")
        self.current_theme = THEMES.get(self.current_theme_key, THEMES["bento_dark"])
        
        self.selected_model = self.config.get("selected_model", "Gemini")
        self.show_exact_date = self.config.get("show_exact_date", True)
        self.dynamic_opacity = self.config.get("dynamic_opacity", False)
        self.notifications_enabled = self.config.get("notifications_enabled", True)
        self.sound_enabled = self.config.get("sound_enabled", True)
        self.refresh_interval_sec = self.config.get("refresh_interval_sec", 60)
        self.show_stats = self.config.get("show_stats", False)
        self.stats_mode = self.config.get("stats_mode", "weekly")
        self.stats_view_mode = "projects"
        self.mini_mode = self.config.get("mini_mode", False)
        self._fetch_event = threading.Event()
        
        # Limpiar cualquier icono fantasma previo en la bandeja de Windows
        clean_ghost_icons()

        # Window setup
        self.title("AI Quota Widget")
        ctk.set_appearance_mode(self.current_theme.get("appearance", "dark"))
        self.configure(fg_color=self.current_theme["bg_root"])
        self.overrideredirect(True)
        
        if os.path.exists(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception:
                pass
        
        # Proporciones Bento Card SaaS
        self.card_w = 295
        self.card_h = 560 if self.show_stats else 300
        
        raw_x = self.config.get("x", 1000)
        raw_y = self.config.get("y", 350)
        init_x, init_y = ensure_visible_coordinates(raw_x, raw_y, self.card_w, self.card_h)
        
        self.geometry(f"{self.card_w}x{self.card_h}+{init_x}+{init_y}")
        self.attributes("-topmost", self.config.get("always_on_top", False))
        
        if self.dynamic_opacity:
            self.attributes("-alpha", 0.88)
        else:
            self.attributes("-alpha", 1.0)
            
        self.after(20, self._hide_from_taskbar)
        
        # Dragging & Resizing
        self.is_dragging = False
        self.drag_mouse_start_x = 0
        self.drag_mouse_start_y = 0
        self.drag_win_start_x = 0
        self.drag_win_start_y = 0
        
        self.is_resizing = False
        self.resize_mouse_start_x = 0
        self.resize_mouse_start_y = 0
        self.resize_win_start_w = 0
        self.resize_win_start_h = 0
        self.resize_win_fixed_x = 0
        self.resize_win_fixed_y = 0
        
        # Main Bento Container
        self.container = ctk.CTkFrame(
            self, 
            fg_color=self.current_theme["bg_card"], 
            corner_radius=16, 
            border_width=1, 
            border_color=self.current_theme["border"]
        )
        self.container.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Layout Modular Bento Box
        self._build_top_bar()
        self._build_bottom_controls()
        self._build_stats_section()
        self._build_buckets_container()
        self._build_resize_grip()
        self._build_mini_bar()
        self._build_context_menu()
        
        self._bind_events_recursive(self.container)

        if self.mini_mode:
            self.container.pack_forget()
            self.configure(fg_color=self.current_theme["bg_root"])
            self.mini_frame.configure(
                fg_color=self.current_theme["bg_card"],
                border_color=self.current_theme["border"]
            )
            self.mini_frame.pack(fill="both", expand=True, padx=2, pady=2)
            self.geometry(f"280x34+{init_x}+{init_y}")
        
        # System Tray & Hotkey
        self.tray_icon = None
        self._setup_system_tray()
        self._setup_global_hotkey()
        
        self.running = True
        self._start_fetch_thread()
        self._start_countdown_timer()
        
        self.deiconify()
        self.lift()

    def _hide_from_taskbar(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def _setup_global_hotkey(self):
        def listener():
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._hotkey_thread_id = kernel32.GetCurrentThreadId()
            
            MOD_ALT = 0x0001
            MOD_CONTROL = 0x0002
            VK_Q = 0x51
            HOTKEY_ID = 1001

            if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_Q):
                return
                
            msg = wintypes.MSG()
            while self.running:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res == 0 or res == -1:
                    break
                if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                    self.after(0, self._handle_tray_click)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            user32.UnregisterHotKey(None, HOTKEY_ID)

        threading.Thread(target=listener, daemon=True).start()

    def _setup_system_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("📊 Traer al Frente / Enviar al Fondo", self._tray_toggle_or_bring_front, default=True),
            pystray.MenuItem("⇄ Cambiar a Gemini / Claude", self._switch_model),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📍 Reposicionar en Pantalla Principal", self._reset_position_to_primary),
            pystray.MenuItem("🔄 Actualizar Cuota Ahora", self._trigger_manual_refresh),
            pystray.MenuItem("🚀 Iniciar con Windows", self._toggle_autostart, checked=lambda item: os.path.exists(STARTUP_PATH)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✕ Ocultar a la Bandeja", self.withdraw),
            pystray.MenuItem("⛔ Salir del Programa", self._request_close)
        )
        
        self.tray_icon = pystray.Icon(
            "AIQuotaMonitor",
            create_tray_icon_image("#70757A"),
            "AI Quota: Conectando...",
            menu
        )
        self.tray_icon.run_detached()

    def _tray_toggle_or_bring_front(self, icon=None, item=None):
        self.after(0, self._handle_tray_click)

    def _handle_tray_click(self):
        try:
            is_viewable = self.winfo_viewable()
            if not is_viewable:
                self._bring_to_front()
                self._is_in_foreground = True
            elif self._is_in_foreground:
                self._send_to_back()
                self._is_in_foreground = False
            else:
                self._bring_to_front()
                self._is_in_foreground = True
        except Exception:
            self._bring_to_front()

    def _bring_to_front(self):
        self.deiconify()
        self._hide_from_taskbar()
        
        w = self.card_w
        h = self.card_h
        cur_x = self.winfo_x()
        cur_y = self.winfo_y()
        safe_x, safe_y = ensure_visible_coordinates(cur_x, cur_y, w, h)
        if (safe_x, safe_y) != (cur_x, cur_y):
            self.geometry(f"{w}x{h}+{safe_x}+{safe_y}")
            self.config["x"] = safe_x
            self.config["y"] = safe_y
            save_config(self.config)
            
        is_pin = self.config.get("always_on_top", False)
        self.attributes("-topmost", is_pin)
        self.lift()
        self.focus_force()
        
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            z_order = -1 if is_pin else 0
            ctypes.windll.user32.SetWindowPos(hwnd, z_order, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            
            if not is_pin:
                ctypes.windll.user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        except Exception:
            pass

    def _send_to_back(self):
        try:
            self.attributes("-topmost", False)
            self.lower()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            ctypes.windll.user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        except Exception:
            self.lower()

    def _reset_position_to_primary(self, icon=None, item=None):
        try:
            user32 = ctypes.windll.user32
            primary_w = user32.GetSystemMetrics(0)
            primary_h = user32.GetSystemMetrics(1)
            w = self.card_w
            h = self.card_h
            safe_x = max(20, primary_w - w - 25)
            safe_y = max(20, primary_h - h - 75)
            
            self.after(0, lambda: (
                self.geometry(f"{w}x{h}+{safe_x}+{safe_y}"),
                self._bring_to_front()
            ))
            self.config["x"] = safe_x
            self.config["y"] = safe_y
            save_config(self.config)
        except Exception:
            pass

    # =========================================================================
    # PROPUESTA 2: TOP BAR CON SEGMENTED CONTROL TIPO SWITCH
    # =========================================================================
    def _build_top_bar(self):
        self.top_bar = ctk.CTkFrame(self.container, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=10, pady=(8, 4))

        # 1. Segmented Control Switcher (Gemini | Claude)
        self.switch_frame = ctk.CTkFrame(
            self.top_bar, 
            fg_color=self.current_theme["switch_bg"],
            corner_radius=8, 
            border_width=1, 
            border_color=self.current_theme["switch_border"]
        )
        self.switch_frame.pack(side="left")

        self.btn_tab_gemini = ctk.CTkButton(
            self.switch_frame, 
            text="Gemini", 
            width=58, 
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.current_theme["active_tab"] if self.selected_model == "Gemini" else "transparent",
            text_color="#FFFFFF" if self.selected_model == "Gemini" else self.current_theme["text_muted"],
            hover_color=self.current_theme["accent"],
            corner_radius=6,
            command=lambda: self._set_model("Gemini")
        )
        self.btn_tab_gemini.pack(side="left", padx=2, pady=2)

        self.btn_tab_claude = ctk.CTkButton(
            self.switch_frame, 
            text="Claude", 
            width=58, 
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.current_theme["active_tab"] if self.selected_model == "Claude" else "transparent",
            text_color="#FFFFFF" if self.selected_model == "Claude" else self.current_theme["text_muted"],
            hover_color=self.current_theme["accent"],
            corner_radius=6,
            command=lambda: self._set_model("Claude")
        )
        self.btn_tab_claude.pack(side="left", padx=2, pady=2)

        # 2. Right Side: Status Badge & Hover Controls
        self.right_header_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.right_header_frame.pack(side="right")

        # Status Pill
        self.status_pill = ctk.CTkFrame(self.right_header_frame, fg_color=self.current_theme["switch_bg"], corner_radius=6)
        self.status_pill.pack(side="right", padx=(4, 0))

        self.status_dot = ctk.CTkLabel(self.status_pill, text="●", font=ctk.CTkFont(size=9), text_color="#70757A")
        self.status_dot.pack(side="left", padx=(5, 2))

        self.status_label = ctk.CTkLabel(
            self.status_pill, 
            text="En línea", 
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=self.current_theme["text_muted"]
        )
        self.status_label.pack(side="left", padx=(0, 6), pady=2)

        # Hover Action Buttons
        self.controls_frame = ctk.CTkFrame(self.right_header_frame, fg_color="transparent")
        btn_base = {
            "width": 20, "height": 20, "fg_color": "transparent",
            "text_color": self.current_theme["text_secondary"], "corner_radius": 4, "font": ctk.CTkFont(size=11)
        }
        
        self.btn_close = ctk.CTkButton(self.controls_frame, text="✕", hover_color="#EA4335", command=self.withdraw, **btn_base)
        self.btn_close.pack(side="right", padx=1)
        
        pin_char = "📌" if self.config.get("always_on_top", False) else "📍"
        self.btn_pin = ctk.CTkButton(self.controls_frame, text=pin_char, hover_color=self.current_theme["bento_bg"], command=self._toggle_always_on_top, **btn_base)
        self.btn_pin.pack(side="right", padx=1)
        
        self.btn_refresh = ctk.CTkButton(self.controls_frame, text="🔄", hover_color=self.current_theme["bento_bg"], command=self._trigger_manual_refresh, **btn_base)
        self.btn_refresh.pack(side="right", padx=1)

        self.btn_mini = ctk.CTkButton(self.controls_frame, text="—", hover_color=self.current_theme["bento_bg"], command=self._toggle_mini_mode, **btn_base)
        self.btn_mini.pack(side="right", padx=1)

        self.btn_info = ctk.CTkButton(self.controls_frame, text="ℹ", hover_color=self.current_theme["bento_bg"], command=self._show_about_dialog, **btn_base)
        self.btn_info.pack(side="right", padx=1)

    # =========================================================================
    # PROPUESTA 2: BOTÓN INFERIOR ANCLADO Y MINI-PILL DE ESTADÍSTICAS
    # =========================================================================
    def _build_bottom_controls(self):
        self.bottom_bar = ctk.CTkFrame(self.container, fg_color="transparent")
        self.bottom_bar.pack(side="bottom", fill="x", padx=8, pady=(2, 4))

        # Crédito y acceso rápido a la Guía
        self.lbl_author = ctk.CTkLabel(
            self.bottom_bar,
            text="⚡ Desarrollado por Darkplayer00",
            font=ctk.CTkFont(family="Segoe UI", size=8),
            text_color=self.current_theme["text_muted"],
            cursor="hand2"
        )
        self.lbl_author.pack(side="bottom", pady=(2, 0))
        self.lbl_author.bind("<Button-1>", lambda e: self._show_about_dialog())

        # 1. Botón Plegable / Desplegable Anclado al Fondo
        self.btn_toggle_stats = ctk.CTkButton(
            self.bottom_bar,
            text="▲ Ocultar Estadísticas" if self.show_stats else "📊 Ver Estadísticas y Proyectos ▼",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.current_theme["bento_bg"],
            hover_color=self.current_theme["bento_border"],
            text_color=self.current_theme["accent"],
            height=26,
            corner_radius=8,
            border_width=1,
            border_color=self.current_theme["bento_border"],
            command=self._toggle_stats
        )
        self.btn_toggle_stats.pack(side="bottom", fill="x", pady=(2, 0))

        # 2. Bento Pill de Resumen Rápido (Siempre visible)
        self.summary_pill = ctk.CTkFrame(
            self.bottom_bar, 
            fg_color=self.current_theme["switch_bg"],
            corner_radius=8, 
            border_width=1, 
            border_color=self.current_theme["switch_border"]
        )
        self.summary_pill.pack(side="bottom", fill="x", pady=(2, 2), ipadx=4, ipady=3)

        self.lbl_pill_proj = ctk.CTkLabel(
            self.summary_pill, 
            text="📁 ● widgets", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#34A853"
        )
        self.lbl_pill_proj.pack(side="left", padx=6)

        self.lbl_pill_spend = ctk.CTkLabel(
            self.summary_pill, 
            text="Hoy: 0.0%  |  Mes: 0.0%", 
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=self.current_theme["text_secondary"]
        )
        self.lbl_pill_spend.pack(side="right", padx=6)

    # =========================================================================
    # PROPUESTA 2: SECCIÓN EXPANDIBLE DE ESTADÍSTICAS BENTO
    # =========================================================================
    def _build_stats_section(self):
        self.stats_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        
        # Switch entre Cupo Semanal y Ventana 5 Horas
        self.stats_switch_frame = ctk.CTkFrame(
            self.stats_frame,
            fg_color=self.current_theme["switch_bg"],
            corner_radius=8,
            border_width=1,
            border_color=self.current_theme["switch_border"]
        )
        self.stats_switch_frame.pack(fill="x", padx=8, pady=(0, 4))

        self.btn_stats_weekly = ctk.CTkButton(
            self.stats_switch_frame,
            text="📅 Cupo Semanal",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.current_theme["active_tab"] if self.stats_mode == "weekly" else "transparent",
            text_color="#FFFFFF" if self.stats_mode == "weekly" else self.current_theme["text_muted"],
            height=22,
            corner_radius=6,
            command=lambda: self._set_stats_mode("weekly")
        )
        self.btn_stats_weekly.pack(side="left", fill="x", expand=True, padx=2, pady=2)

        self.btn_stats_5h = ctk.CTkButton(
            self.stats_switch_frame,
            text="⏱️ Ventana 5h",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.current_theme["active_tab"] if self.stats_mode == "5h" else "transparent",
            text_color="#FFFFFF" if self.stats_mode == "5h" else self.current_theme["text_muted"],
            height=22,
            corner_radius=6,
            command=lambda: self._set_stats_mode("5h")
        )
        self.btn_stats_5h.pack(side="right", fill="x", expand=True, padx=2, pady=2)

        # Grid 2x2 Métricas Temporales
        self.grid_frame = ctk.CTkFrame(
            self.stats_frame, 
            fg_color=self.current_theme["bento_bg"], 
            corner_radius=10,
            border_width=1,
            border_color=self.current_theme["bento_border"]
        )
        self.grid_frame.pack(fill="x", padx=8, pady=(0, 4), ipadx=4, ipady=4)

        row1 = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
        row1.pack(fill="x", padx=6, pady=2)
        
        self.lbl_stat_last = ctk.CTkLabel(
            row1, text="🔻 Último: 0.0%", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), 
            text_color=self.current_theme["text_primary"], anchor="w"
        )
        self.lbl_stat_last.pack(side="left", fill="x", expand=True)

        self.lbl_stat_today = ctk.CTkLabel(
            row1, text="☀️ Hoy: 0.0%", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), 
            text_color="#FBBC04", anchor="e"
        )
        self.lbl_stat_today.pack(side="right")

        row2 = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
        row2.pack(fill="x", padx=6, pady=2)

        self.lbl_stat_week = ctk.CTkLabel(
            row2, text="📆 Semana: 0.0%", 
            font=ctk.CTkFont(family="Segoe UI", size=10), 
            text_color=self.current_theme["text_secondary"], anchor="w"
        )
        self.lbl_stat_week.pack(side="left", fill="x", expand=True)

        self.lbl_stat_month = ctk.CTkLabel(
            row2, text="🗓️ Mes: 0.0%", 
            font=ctk.CTkFont(family="Segoe UI", size=10), 
            text_color=self.current_theme["accent"], anchor="e"
        )
        self.lbl_stat_month.pack(side="right")

        # Encabezado con selector entre Proyectos y Consultas Recientes + Indicador de Ritmo
        self.proj_header = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        self.proj_header.pack(fill="x", padx=8, pady=(2, 2))

        self.btn_view_proj = ctk.CTkButton(
            self.proj_header,
            text="📁 Proyectos",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color=self.current_theme["active_tab"] if self.stats_view_mode == "projects" else "transparent",
            text_color="#FFFFFF" if self.stats_view_mode == "projects" else self.current_theme["text_muted"],
            height=20,
            width=75,
            corner_radius=5,
            command=lambda: self._set_stats_view_mode("projects")
        )
        self.btn_view_proj.pack(side="left", padx=1)

        self.btn_view_recent = ctk.CTkButton(
            self.proj_header,
            text="⏱️ Recientes",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color=self.current_theme["active_tab"] if self.stats_view_mode == "recent" else "transparent",
            text_color="#FFFFFF" if self.stats_view_mode == "recent" else self.current_theme["text_muted"],
            height=20,
            width=75,
            corner_radius=5,
            command=lambda: self._set_stats_view_mode("recent")
        )
        self.btn_view_recent.pack(side="left", padx=2)

        # Indicador de ritmo (Burn rate)
        self.lbl_burn_rate = ctk.CTkLabel(
            self.proj_header,
            text="🟢 Ritmo normal",
            font=ctk.CTkFont(family="Segoe UI", size=8, weight="bold"),
            text_color="#34A853"
        )
        self.lbl_burn_rate.pack(side="right", padx=2)

        self.projects_container = ctk.CTkFrame(
            self.stats_frame, 
            fg_color=self.current_theme["bento_bg"], 
            corner_radius=10,
            border_width=1,
            border_color=self.current_theme["bento_border"]
        )
        self.projects_container.pack(fill="both", expand=True, padx=8, pady=(0, 4), ipadx=4, ipady=3)

        self.lbl_no_proj = ctk.CTkLabel(
            self.projects_container, text="Registrando consumo en tiempo real...",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=self.current_theme["text_secondary"]
        )
        self.lbl_no_proj.pack(pady=4)

        if self.show_stats:
            self.stats_frame.pack(side="bottom", fill="both", expand=True, pady=(0, 2))

    def _set_stats_mode(self, mode):
        self.stats_mode = mode
        self.config["stats_mode"] = mode
        save_config(self.config)
        self._update_stats_mode_tabs()
        self._update_stats_display()

    def _update_stats_mode_tabs(self):
        is_weekly = (self.stats_mode == "weekly")
        self.btn_stats_weekly.configure(
            fg_color=self.current_theme["active_tab"] if is_weekly else "transparent",
            text_color="#FFFFFF" if is_weekly else self.current_theme["text_muted"]
        )
        self.btn_stats_5h.configure(
            fg_color=self.current_theme["active_tab"] if not is_weekly else "transparent",
            text_color="#FFFFFF" if not is_weekly else self.current_theme["text_muted"]
        )

    def _toggle_stats(self):
        self.show_stats = not self.show_stats
        self.config["show_stats"] = self.show_stats
        save_config(self.config)

        cur_x = self.winfo_x()
        cur_y = self.winfo_y()

        if self.show_stats:
            self.stats_frame.pack(side="bottom", fill="x", padx=0, pady=(0, 2))
            self.btn_toggle_stats.configure(text="▲ Ocultar Estadísticas")
            self.card_h = 560
            self.geometry(f"{self.card_w}x{self.card_h}+{cur_x}+{cur_y}")
        else:
            self.stats_frame.pack_forget()
            self.btn_toggle_stats.configure(text="📊 Ver Estadísticas y Proyectos ▼")
            self.card_h = 300
            self.geometry(f"{self.card_w}x{self.card_h}+{cur_x}+{cur_y}")

        self._update_stats_display()

    def _set_stats_view_mode(self, mode):
        self.stats_view_mode = mode
        is_p = (mode == "projects")
        self.btn_view_proj.configure(
            fg_color=self.current_theme["active_tab"] if is_p else "transparent",
            text_color="#FFFFFF" if is_p else self.current_theme["text_muted"]
        )
        self.btn_view_recent.configure(
            fg_color=self.current_theme["active_tab"] if not is_p else "transparent",
            text_color="#FFFFFF" if not is_p else self.current_theme["text_muted"]
        )
        self._update_stats_display()

    def _build_mini_bar(self):
        self.mini_frame = ctk.CTkFrame(
            self,
            fg_color=self.current_theme["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=self.current_theme["border"]
        )
        self.mini_dot = ctk.CTkLabel(self.mini_frame, text="●", font=ctk.CTkFont(size=9), text_color="#34A853")
        self.mini_dot.pack(side="left", padx=(7, 2))

        self.lbl_mini_model = ctk.CTkLabel(
            self.mini_frame, text=self.selected_model, font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=self.current_theme["accent"]
        )
        self.lbl_mini_model.pack(side="left", padx=(0, 4))

        self.lbl_mini_weekly = ctk.CTkLabel(
            self.mini_frame, text="Sem: --%", font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=self.current_theme["text_primary"]
        )
        self.lbl_mini_weekly.pack(side="left", padx=2)

        self.lbl_mini_sep = ctk.CTkLabel(self.mini_frame, text="|", font=ctk.CTkFont(size=9), text_color=self.current_theme["text_muted"])
        self.lbl_mini_sep.pack(side="left", padx=2)

        self.lbl_mini_5h = ctk.CTkLabel(
            self.mini_frame, text="5h: --%", font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=self.current_theme["text_secondary"]
        )
        self.lbl_mini_5h.pack(side="left", padx=2)

        self.lbl_mini_sep2 = ctk.CTkLabel(self.mini_frame, text="|", font=ctk.CTkFont(size=9), text_color=self.current_theme["text_muted"])
        self.lbl_mini_sep2.pack(side="left", padx=2)

        self.lbl_mini_proj = ctk.CTkLabel(
            self.mini_frame, text="📁 ...", font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#34A853"
        )
        self.lbl_mini_proj.pack(side="left", padx=(2, 6))

        self.btn_mini_expand = ctk.CTkLabel(
            self.mini_frame, text="⤢", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.current_theme["text_secondary"], cursor="hand2"
        )
        self.btn_mini_expand.pack(side="right", padx=(0, 7))
        self.btn_mini_expand.bind("<Button-1>", lambda e: self._toggle_mini_mode())

        for w in [self.mini_frame, self.mini_dot, self.lbl_mini_model, self.lbl_mini_weekly, self.lbl_mini_sep, self.lbl_mini_5h, self.lbl_mini_sep2, self.lbl_mini_proj]:
            w.bind("<Double-Button-1>", lambda e: self._toggle_mini_mode())
            w.bind("<ButtonPress-1>", self._start_drag, add="+")
            w.bind("<B1-Motion>", self._on_drag, add="+")
            w.bind("<ButtonRelease-1>", self._end_drag, add="+")
            w.bind("<Button-3>", self._show_context_menu, add="+")

    def _toggle_mini_mode(self):
        self.mini_mode = not self.mini_mode
        self.config["mini_mode"] = self.mini_mode
        save_config(self.config)

        cur_x = self.winfo_x()
        cur_y = self.winfo_y()

        self.configure(fg_color=self.current_theme["bg_root"])

        if self.mini_mode:
            self.container.pack_forget()
            self.mini_frame.configure(
                fg_color=self.current_theme["bg_card"],
                border_color=self.current_theme["border"]
            )
            self.lbl_mini_model.configure(text=self.selected_model, text_color=self.current_theme["accent"])
            self.lbl_mini_sep.configure(text_color=self.current_theme["text_muted"])
            self.lbl_mini_sep2.configure(text_color=self.current_theme["text_muted"])
            self.btn_mini_expand.configure(text_color=self.current_theme["text_secondary"])
            self.mini_frame.pack(fill="both", expand=True, padx=2, pady=2)
            self.geometry(f"280x34+{cur_x}+{cur_y}")
            self._update_display()
        else:
            self.mini_frame.pack_forget()
            self.container.configure(
                fg_color=self.current_theme["bg_card"],
                border_color=self.current_theme["border"]
            )
            self.container.pack(fill="both", expand=True, padx=2, pady=2)
            target_h = 560 if self.show_stats else 300
            self.geometry(f"{self.card_w}x{target_h}+{cur_x}+{cur_y}")
            self._update_stats_display()

    # =========================================================================
    # PROPUESTA 2: CONTENEDOR DE TARJETAS BENTO MODULARES
    # =========================================================================
    def _build_buckets_container(self):
        self.buckets_container = ctk.CTkFrame(self.container, fg_color="transparent")
        self.buckets_container.pack(side="top", fill="x", padx=8, pady=(2, 2))
        
        self.msg_banner = ctk.CTkLabel(
            self.buckets_container, 
            text="Conectando con Antigravity...", 
            font=ctk.CTkFont(family="Segoe UI", size=11), 
            text_color=self.current_theme["text_secondary"]
        )
        self.msg_banner.pack(pady=20)
        
        self.bucket_widgets = {}

    def _build_resize_grip(self):
        self.resize_grip = ctk.CTkLabel(
            self.container,
            text="◢",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#555B66",
            cursor="size_nw_se",
            width=16,
            height=16
        )
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se", x=-3, y=-3)
        
        self.resize_grip.bind("<ButtonPress-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._on_resize)
        self.resize_grip.bind("<ButtonRelease-1>", self._end_resize)
        self.resize_grip.bind("<Enter>", lambda e: self.resize_grip.configure(text_color=self.current_theme["accent"]))
        self.resize_grip.bind("<Leave>", lambda e: self.resize_grip.configure(text_color="#555B66"))

    def _build_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0, bg="#181A20", fg="#E3E3E3", activebackground="#1A73E8", activeforeground="#FFFFFF", bd=1)

    def _show_context_menu(self, event):
        self.context_menu.delete(0, "end")
        
        model_switch_text = "⇄ Cambiar a Claude & GPT" if self.selected_model == "Gemini" else "⇄ Cambiar a Gemini Models"
        self.context_menu.add_command(label=model_switch_text, command=self._switch_model)
        bg_c = self.current_theme["bg_card"]
        fg_c = self.current_theme["text_primary"]
        self.context_menu.configure(bg=bg_c, fg=fg_c, activebackground="#1A73E8", activeforeground="#FFFFFF")

        theme_menu = tk.Menu(self.context_menu, tearoff=0, bg=bg_c, fg=fg_c, activebackground="#1A73E8", activeforeground="#FFFFFF")
        themes_list = [
            ("bento_dark", "Bento Modern Dark (Oscuro)"),
            ("bento_light", "Bento Clean Light (Claro)"),
            ("oled_black", "OLED Pure Black"),
            ("cyber_neon", "Cyberpunk Neon")
        ]
        for key, name in themes_list:
            prefix = "● " if self.current_theme_key == key else "○ "
            theme_menu.add_command(label=f"{prefix}{name}", command=lambda k=key: self._set_theme(k))
        self.context_menu.add_cascade(label="🎨 Tema Visual", menu=theme_menu)
        
        interval_menu = tk.Menu(self.context_menu, tearoff=0, bg=bg_c, fg=fg_c, activebackground="#1A73E8", activeforeground="#FFFFFF")
        intervals = [(30, "30 segundos"), (60, "1 minuto (Recomendado)"), (120, "2 minutos"), (300, "5 minutos")]
        for sec, label_text in intervals:
            prefix = "● " if self.refresh_interval_sec == sec else "○ "
            interval_menu.add_command(label=f"{prefix}{label_text}", command=lambda s=sec: self._set_refresh_interval(s))
        self.context_menu.add_cascade(label="⏱️ Intervalo de Actualización", menu=interval_menu)
        
        self.context_menu.add_command(label="📍 Reposicionar en Pantalla Principal", command=self._reset_position_to_primary)
        self.context_menu.add_command(label="⬇️ Enviar al Fondo del Escritorio", command=self._send_to_back)
        self.context_menu.add_separator()
        
        self.context_menu.add_command(
            label=f"{'✔' if self.show_stats else '◻'}  Ver Panel de Estadísticas y Proyectos",
            command=self._toggle_stats
        )
        self.context_menu.add_command(
            label=f"{'✔' if self.show_exact_date else '◻'}  Mostrar Fecha Exacta de Reset",
            command=self._toggle_exact_date
        )
        self.context_menu.add_command(
            label=f"{'✔' if self.dynamic_opacity else '◻'}  Transparencia Dinámica (88% ➔ 100%)",
            command=self._toggle_dynamic_opacity
        )
        self.context_menu.add_command(
            label=f"{'✔' if self.notifications_enabled else '◻'}  Notificaciones de Windows (100% / <15%)",
            command=self._toggle_notifications
        )
        self.context_menu.add_command(
            label=f"{'✔' if self.sound_enabled else '◻'}  Sonido al Restablecer Cuota (100%)",
            command=self._toggle_sound
        )
        is_pinned = self.config.get("always_on_top", False)
        self.context_menu.add_command(
            label=f"{'✔' if is_pinned else '◻'}  Fijar Siempre al Frente (Always on Top)",
            command=self._toggle_always_on_top
        )
        is_autostart = os.path.exists(STARTUP_PATH)
        self.context_menu.add_command(
            label=f"{'✔' if is_autostart else '◻'}  Iniciar Automáticamente con Windows",
            command=self._toggle_autostart
        )
        self.context_menu.add_command(
            label=f"{'✔' if self.mini_mode else '◻'}  Modo Píldora Flotante (Ultra Compacto)",
            command=self._toggle_mini_mode
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📋  Copiar Resumen de Gastos", command=self._copy_summary_report)
        self.context_menu.add_command(label="📑  Exportar Historial a CSV (Excel)", command=self._export_csv_report)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="ℹ️  Acerca de & Guía de Uso", command=self._show_about_dialog)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔄  Actualizar Cuota Ahora", command=self._trigger_manual_refresh)
        self.context_menu.add_command(label="✕  Ocultar a la Bandeja (Minimizar)", command=self.withdraw)
        self.context_menu.add_command(label="⛔  Salir del Programa", command=self._request_close)
        
        self.context_menu.post(event.x_root, event.y_root)

    def _copy_summary_report(self):
        try:
            text = self.usage_tracker.generate_summary_text()
            self.clipboard_clear()
            self.clipboard_append(text)
            send_windows_notification("AI Quota Monitor", "📋 Reporte copiado al portapapeles exitosamente.", play_sound=False)
        except Exception:
            pass

    def _export_csv_report(self):
        try:
            csv_path = self.usage_tracker.export_to_csv()
            if csv_path:
                send_windows_notification("AI Quota Monitor", f"📑 Historial exportado al Escritorio:\n{os.path.basename(csv_path)}", play_sound=False)
                try:
                    os.startfile(os.path.dirname(csv_path))
                except Exception:
                    pass
        except Exception:
            pass

    def _show_about_dialog(self):
        """Muestra una ventana modal moderna con los créditos de Darkplayer00 y la guía de uso."""
        if hasattr(self, "_about_win") and self._about_win and self._about_win.winfo_exists():
            self._about_win.lift()
            self._about_win.attributes("-topmost", True)
            self._about_win.focus_force()
            return

        mw, mh = 400, 520
        cur_x = self.winfo_x()
        cur_y = self.winfo_y()

        # Calcular posición óptima adyacente para que NUNCA quede detrás ni tapada por el widget
        target_x = cur_x - mw - 12
        target_y = cur_y
        try:
            user32 = ctypes.windll.user32
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_ulong),
                            ("rcMonitor", RECT),
                            ("rcWork", RECT),
                            ("dwFlags", ctypes.c_ulong)]

            pt = POINT(cur_x + self.card_w // 2, cur_y + self.card_h // 2)
            h_mon = user32.MonitorFromPoint(pt, 2)
            if h_mon:
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(h_mon, ctypes.byref(mi)):
                    w_left = mi.rcWork.left
                    w_right = mi.rcWork.right
                    w_top = mi.rcWork.top
                    w_bot = mi.rcWork.bottom
                    
                    if (cur_x - mw - 12) >= w_left:
                        target_x = cur_x - mw - 12
                    elif (cur_x + self.card_w + 12 + mw) <= w_right:
                        target_x = cur_x + self.card_w + 12
                    else:
                        target_x = w_left + max(20, (w_right - w_left - mw) // 2)

                    target_y = max(w_top + 10, min(cur_y, w_bot - mh - 10))
        except Exception:
            target_x = max(20, cur_x - mw - 12)
            target_y = cur_y

        self._about_win = ctk.CTkToplevel(self)
        self._about_win.title("Acerca de AI Quota Monitor")
        self._about_win.geometry(f"{mw}x{mh}+{target_x}+{target_y}")
        self._about_win.resizable(False, False)
        self._about_win.transient(self)
        self._about_win.attributes("-topmost", True)
        self._about_win.configure(fg_color=self.current_theme["bg_root"])

        card = ctk.CTkFrame(
            self._about_win,
            fg_color=self.current_theme["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=self.current_theme["border"]
        )
        card.pack(fill="both", expand=True, padx=10, pady=10)

        lbl_title = ctk.CTkLabel(
            card, text="🤖 AI Quota Monitor v2.5",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.current_theme["text_primary"]
        )
        lbl_title.pack(pady=(12, 1))

        lbl_dev = ctk.CTkLabel(
            card, text="⚡ Desarrollado por Darkplayer00",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=self.current_theme["accent"]
        )
        lbl_dev.pack(pady=(0, 8))

        guide_box = ctk.CTkScrollableFrame(
            card,
            fg_color=self.current_theme["bento_bg"],
            corner_radius=10,
            border_width=1,
            border_color=self.current_theme["bento_border"]
        )
        guide_box.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        tips = [
            ("🖱️ Arrastre Magnético Multi-Monitor", "Mueve el widget haciendo clic en cualquier parte. Se imanta con suavidad a los bordes de tu pantalla primaria o secundaria."),
            ("💊 Modo Píldora Flotante", "Presiona el botón '—' en la barra superior o haz doble clic para reducir el widget a una barrita de 34px."),
            ("📊 Estadísticas y Proyectos", "Despliega el panel inferior para ver el acumulado mensual por proyecto y el gasto por día o semana."),
            ("⏱️ Consultas en Vivo (Recientes)", "En la pestaña 'Recientes' verás el desglose inmediato de tus últimos prompts con hora y % consumido."),
            ("🟢 Indicador de Ritmo (Burn Rate)", "Monitorea tu velocidad de consumo y te avisa si el cupo se agotará antes del reset semanal."),
            ("⌨️ Atajo Global (Ctrl + Alt + Q)", "Trae el widget al frente o envíalo al fondo al instante desde cualquier aplicación o juego."),
            ("📑 Exportar a Excel (CSV)", "Haz clic derecho y selecciona 'Exportar a CSV' para guardar el historial completo en tu Escritorio.")
        ]

        for title, desc in tips:
            item = ctk.CTkFrame(guide_box, fg_color="transparent")
            item.pack(fill="x", pady=4, padx=2)

            t_lbl = ctk.CTkLabel(
                item, text=title,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=self.current_theme["accent"], anchor="w"
            )
            t_lbl.pack(fill="x")

            d_lbl = ctk.CTkLabel(
                item, text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=self.current_theme["text_secondary"],
                wraplength=310, justify="left", anchor="w"
            )
            d_lbl.pack(fill="x")

        btn_close = ctk.CTkButton(
            card, text="Entendido",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=self.current_theme["accent"],
            hover_color=self.current_theme.get("active_tab", "#1A73E8"),
            text_color="#FFFFFF",
            height=28,
            corner_radius=8,
            command=self._about_win.destroy
        )
        btn_close.pack(pady=(0, 8))

        self._about_win.lift()
        self._about_win.focus_force()
        self._about_win.after(30, lambda: (self._about_win.lift(), self._about_win.focus_force()))

    def _set_refresh_interval(self, sec):
        self.refresh_interval_sec = sec
        self.config["refresh_interval_sec"] = sec
        save_config(self.config)
        self._fetch_event.set()

    def _set_theme(self, theme_key):
        if theme_key in THEMES:
            self.current_theme_key = theme_key
            self.current_theme = THEMES[theme_key]
            self.config["theme"] = theme_key
            save_config(self.config)
            
            appearance = self.current_theme.get("appearance", "dark")
            ctk.set_appearance_mode(appearance)

            self.configure(fg_color=self.current_theme["bg_root"])
            self.container.configure(
                fg_color=self.current_theme["bg_card"],
                border_color=self.current_theme["border"]
            )
            self.switch_frame.configure(
                fg_color=self.current_theme["switch_bg"],
                border_color=self.current_theme["switch_border"]
            )
            self.status_pill.configure(
                fg_color=self.current_theme["switch_bg"]
            )
            self.status_label.configure(
                text_color=self.current_theme["text_muted"]
            )
            self.btn_close.configure(
                text_color=self.current_theme["text_secondary"]
            )
            self.btn_pin.configure(
                text_color=self.current_theme["text_secondary"],
                hover_color=self.current_theme["bento_bg"]
            )
            self.btn_refresh.configure(
                text_color=self.current_theme["text_secondary"],
                hover_color=self.current_theme["bento_bg"]
            )
            if hasattr(self, "btn_info"):
                self.btn_info.configure(
                    text_color=self.current_theme["text_secondary"],
                    hover_color=self.current_theme["bento_bg"]
                )
            if hasattr(self, "lbl_author"):
                self.lbl_author.configure(
                    text_color=self.current_theme["text_muted"]
                )

            if hasattr(self, "summary_pill"):
                self.summary_pill.configure(
                    fg_color=self.current_theme["switch_bg"],
                    border_color=self.current_theme["switch_border"]
                )
                self.lbl_pill_spend.configure(
                    text_color=self.current_theme["text_secondary"]
                )
            if hasattr(self, "btn_toggle_stats"):
                self.btn_toggle_stats.configure(
                    fg_color=self.current_theme["bento_bg"],
                    hover_color=self.current_theme["bento_border"],
                    border_color=self.current_theme["bento_border"],
                    text_color=self.current_theme["accent"]
                )
            if hasattr(self, "stats_switch_frame"):
                self.stats_switch_frame.configure(
                    fg_color=self.current_theme["switch_bg"],
                    border_color=self.current_theme["switch_border"]
                )
            if hasattr(self, "grid_frame"):
                self.grid_frame.configure(
                    fg_color=self.current_theme["bento_bg"],
                    border_color=self.current_theme["bento_border"]
                )
                self.lbl_stat_last.configure(text_color=self.current_theme["text_primary"])
                self.lbl_stat_week.configure(text_color=self.current_theme["text_secondary"])
                self.lbl_stat_month.configure(text_color=self.current_theme["accent"])
            if hasattr(self, "lbl_proj_title"):
                self.lbl_proj_title.configure(text_color=self.current_theme["text_muted"])
            if hasattr(self, "projects_container"):
                self.projects_container.configure(
                    fg_color=self.current_theme["bento_bg"],
                    border_color=self.current_theme["bento_border"]
                )

            if hasattr(self, "mini_frame"):
                self.mini_frame.configure(
                    fg_color=self.current_theme["bg_card"],
                    border_color=self.current_theme["border"]
                )
                self.lbl_mini_model.configure(text_color=self.current_theme["accent"])
                self.lbl_mini_weekly.configure(text_color=self.current_theme["text_primary"])
                self.lbl_mini_sep.configure(text_color=self.current_theme["text_muted"])
                self.lbl_mini_5h.configure(text_color=self.current_theme["text_secondary"])
                self.lbl_mini_sep2.configure(text_color=self.current_theme["text_muted"])
                self.btn_mini_expand.configure(text_color=self.current_theme["text_secondary"])

            # Destruir y reconstruir las tarjetas bento para que tomen los colores del nuevo tema
            for b_id, view in list(self.bucket_widgets.items()):
                try:
                    view["row"].destroy()
                except Exception:
                    pass
            self.bucket_widgets.clear()

            self._update_model_tabs()
            self._update_stats_mode_tabs()
            self._update_display()

    def _toggle_dynamic_opacity(self):
        self.dynamic_opacity = not self.dynamic_opacity
        self.config["dynamic_opacity"] = self.dynamic_opacity
        save_config(self.config)
        self.attributes("-alpha", 0.88 if self.dynamic_opacity else 1.0)

    def _toggle_notifications(self):
        self.notifications_enabled = not self.notifications_enabled
        self.config["notifications_enabled"] = self.notifications_enabled
        save_config(self.config)

    def _toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.config["sound_enabled"] = self.sound_enabled
        save_config(self.config)

    def _toggle_autostart(self, icon=None, item=None):
        try:
            if os.path.exists(STARTUP_PATH):
                os.remove(STARTUP_PATH)
            else:
                startup_dir = os.path.dirname(STARTUP_PATH)
                if not os.path.exists(startup_dir):
                    os.makedirs(startup_dir, exist_ok=True)
                
                if getattr(sys, "frozen", False):
                    target_exe = sys.executable
                    with open(STARTUP_PATH, "w", encoding="utf-8") as f:
                        f.write(f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{target_exe}""", 0, False\n')
                else:
                    this_vbs = os.path.join(APP_DIR, "iniciar_widget_silencioso.vbs")
                    if os.path.exists(this_vbs):
                        with open(STARTUP_PATH, "w", encoding="utf-8") as f:
                            f.write(f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{this_vbs}""", 0, False\n')
        except Exception:
            pass

    def _switch_model(self, icon=None, item=None):
        new_model = "Claude" if self.selected_model == "Gemini" else "Gemini"
        self._set_model(new_model)

    def _set_model(self, model_name):
        self.selected_model = model_name
        self.config["selected_model"] = model_name
        save_config(self.config)
        self._update_model_tabs()
        self._update_display()
        self._update_stats_display()

    def _update_model_tabs(self):
        is_gemini = (self.selected_model == "Gemini")
        self.btn_tab_gemini.configure(
            fg_color=self.current_theme["active_tab"] if is_gemini else "transparent",
            text_color="#FFFFFF" if is_gemini else self.current_theme["text_muted"]
        )
        self.btn_tab_claude.configure(
            fg_color=self.current_theme["active_tab"] if not is_gemini else "transparent",
            text_color="#FFFFFF" if not is_gemini else self.current_theme["text_muted"]
        )

    def _toggle_exact_date(self):
        self.show_exact_date = not self.show_exact_date
        self.config["show_exact_date"] = self.show_exact_date
        save_config(self.config)
        self._update_display()

    def _check_and_notify_quota(self, target_group):
        if not self.notifications_enabled or not target_group:
            return
            
        name = target_group.get("displayName", "AI Model")
        for b in target_group.get("buckets", []):
            b_id = b.get("bucketId", b.get("displayName"))
            frac = float(b.get("remainingFraction", 1.0))
            disp_name = b.get("displayName", "Límite")
            
            prev_frac = self.previous_fractions.get(b_id)
            self.previous_fractions[b_id] = frac
            
            if prev_frac is not None:
                if prev_frac < 0.95 and frac >= 0.99:
                    send_windows_notification(
                        "🎉 ¡Límite Restablecido!",
                        f"Tu {disp_name} en {name} ha vuelto al 100%.",
                        play_sound=self.sound_enabled
                    )
                elif prev_frac >= 0.15 and frac < 0.15:
                    send_windows_notification(
                        "⚠️ Cuota Baja",
                        f"Te queda sólo {round(frac*100)}% en {disp_name} ({name}).",
                        play_sound=self.sound_enabled
                    )

    def _update_display(self):
        if not self.last_quota_data:
            return
            
        groups = self.last_quota_data.get("groups", [])
        
        self.usage_tracker.record_quota_update(groups)
        self._update_stats_display()

        target_group = None
        for g in groups:
            name = g.get("displayName", "")
            if self.selected_model == "Gemini" and "Gemini" in name:
                target_group = g
                break
            elif self.selected_model == "Claude" and ("Claude" in name or "GPT" in name):
                target_group = g
                break
                
        if not target_group and groups:
            target_group = groups[0]
            
        if target_group:
            title_text = target_group.get("displayName", "AI Models")
            self.msg_banner.pack_forget()
            self._check_and_notify_quota(target_group)
            
            buckets = target_group.get("buckets", [])
            model_short = "Gemini" if "Gemini" in title_text else "Claude"
            tray_lines = [f"{model_short}:"]
            
            min_frac = 1.0
            for b in buckets:
                b_id = b.get("bucketId", b.get("displayName"))
                frac = float(b.get("remainingFraction", 1.0))
                min_frac = min(min_frac, frac)
                pct = round(frac * 100)
                reset_time = b.get("resetTime")
                time_left = self.quota_service.calculate_time_remaining(reset_time)
                exact_reset = self.quota_service.format_exact_reset_time(reset_time)
                display_name = b.get("displayName", "Límite")
                
                is_weekly = "Weekly" in display_name
                tag = "Sem" if is_weekly else "5h"
                
                tray_lines.append(f"{tag}: {pct}% ({time_left}) • {exact_reset}")
                
                if "Weekly" in display_name:
                    short_name = "Cupo Semanal"
                elif "Five Hour" in display_name or "5-Hour" in display_name:
                    short_name = "Ventana de 5 Horas"
                else:
                    short_name = display_name

                color = get_color_for_fraction(frac)

                # Tarjeta Bento Modular
                if b_id not in self.bucket_widgets:
                    bento_card = ctk.CTkFrame(
                        self.buckets_container, 
                        fg_color=self.current_theme["bento_bg"], 
                        corner_radius=10, 
                        border_width=1, 
                        border_color=self.current_theme["bento_border"]
                    )
                    bento_card.pack(fill="x", pady=3, ipadx=4, ipady=4)
                    
                    line1 = ctk.CTkFrame(bento_card, fg_color="transparent")
                    line1.pack(fill="x", padx=8, pady=(3, 1))
                    
                    lbl_name = ctk.CTkLabel(
                        line1, 
                        text=short_name, 
                        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                        text_color=self.current_theme["text_primary"]
                    )
                    lbl_name.pack(side="left")
                    
                    lbl_pct = ctk.CTkLabel(
                        line1, 
                        text=f"{pct}%", 
                        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                        text_color=color
                    )
                    lbl_pct.pack(side="right")
                    
                    progress = ctk.CTkProgressBar(
                        bento_card, 
                        height=7, 
                        corner_radius=4,
                        fg_color=self.current_theme["progress_bg"],
                        progress_color=color
                    )
                    progress.set(frac)
                    progress.pack(fill="x", padx=8, pady=3)
                    
                    line2 = ctk.CTkFrame(bento_card, fg_color="transparent")
                    line2.pack(fill="x", padx=8, pady=(1, 3))
                    
                    lbl_timer = ctk.CTkLabel(
                        line2, 
                        text=f"⏳ {time_left} restantes", 
                        font=ctk.CTkFont(family="Segoe UI", size=9),
                        text_color=self.current_theme["text_secondary"],
                        anchor="w"
                    )
                    lbl_timer.pack(side="left")
                    
                    lbl_exact = ctk.CTkLabel(
                        line2, 
                        text=f"Reset: {exact_reset}", 
                        font=ctk.CTkFont(family="Segoe UI", size=9),
                        text_color=self.current_theme["text_muted"],
                        anchor="e"
                    )
                    if self.show_exact_date:
                        lbl_exact.pack(side="right")
                    
                    self.bucket_widgets[b_id] = {
                        "row": bento_card,
                        "lbl_name": lbl_name,
                        "lbl_pct": lbl_pct,
                        "progress": progress,
                        "lbl_timer": lbl_timer,
                        "lbl_exact": lbl_exact,
                        "reset_time": reset_time
                    }
                    self._bind_events_recursive(bento_card)
                else:
                    view = self.bucket_widgets[b_id]
                    view["row"].pack(fill="x", pady=3, ipadx=4, ipady=4)
                    view["lbl_name"].configure(text=short_name)
                    view["reset_time"] = reset_time
                    view["lbl_pct"].configure(text=f"{pct}%", text_color=color)
                    view["progress"].configure(progress_color=color)
                    view["progress"].set(frac)
                    view["lbl_timer"].configure(text=f"⏳ {time_left} restantes")
                    view["lbl_exact"].configure(text=f"Reset: {exact_reset}")
                    
                    if self.show_exact_date and not view["lbl_exact"].winfo_ismapped():
                        view["lbl_exact"].pack(side="right")
                    elif not self.show_exact_date and view["lbl_exact"].winfo_ismapped():
                        view["lbl_exact"].pack_forget()

            current_b_ids = [b.get("bucketId", b.get("displayName")) for b in buckets]
            for b_id, view in self.bucket_widgets.items():
                if b_id not in current_b_ids:
                    view["row"].pack_forget()
                    
            active_color = get_color_for_fraction(min_frac)
            self.status_dot.configure(text_color="#34A853")
            self.status_label.configure(text="En línea", text_color=self.current_theme["text_muted"])
            
            if hasattr(self, "lbl_mini_weekly"):
                self.lbl_mini_model.configure(text=self.selected_model, text_color=self.current_theme["accent"])
                self.mini_frame.configure(fg_color=self.current_theme["bg_card"], border_color=self.current_theme["border"])
                cur_p = self.usage_tracker.detect_active_project()
                self.lbl_mini_proj.configure(text=f"📁 {cur_p}")
                for b in buckets:
                    bid = b.get("bucketId", "").lower()
                    frac = float(b.get("remainingFraction", 1.0))
                    pct = int(frac * 100)
                    if "weekly" in bid:
                        self.lbl_mini_weekly.configure(text=f"Sem: {pct}%", text_color=get_color_for_fraction(frac))
                    elif "5h" in bid or "five" in bid:
                        self.lbl_mini_5h.configure(text=f"5h: {pct}%", text_color=get_color_for_fraction(frac))

            if self.tray_icon:
                try:
                    tray_text = "\n".join(tray_lines)[:125]
                    self.tray_icon.title = tray_text
                    self.tray_icon.icon = create_tray_icon_image(active_color)
                except Exception:
                    pass

    def _update_stats_display(self):
        if not hasattr(self, "stats_frame"):
            return

        stats = self.usage_tracker.get_statistics(filter_group=self.selected_model, bucket_type=self.stats_mode)
        tag = "sem" if self.stats_mode == "weekly" else "5h"
        
        last_pct = stats.get("last_spend_pct", 0.0)
        last_time = stats.get("last_spend_time_str", "Ninguno")
        if last_pct > 0:
            self.lbl_stat_last.configure(text=f"🔻 Último: -{last_pct}% ({last_time})")
        else:
            self.lbl_stat_last.configure(text=f"🔻 Último: 0.0%")

        today_spend = stats.get("today_spend_pct", 0.0)
        week_spend = stats.get("week_spend_pct", 0.0)
        month_spend = stats.get("month_spend_pct", 0.0)
        
        self.lbl_stat_today.configure(text=f"☀️ Hoy: -{today_spend}%")
        self.lbl_stat_week.configure(text=f"📆 Sem: -{week_spend}%")
        self.lbl_stat_month.configure(text=f"🗓️ Mes: -{month_spend}%")

        cur_proj = stats.get("current_project", "General")
        self.lbl_pill_proj.configure(text=f"📁 ● {cur_proj}")

        # En la píldora inferior mostramos siempre el consumo del Cupo Semanal (el principal)
        weekly_stats = self.usage_tracker.get_statistics(filter_group=self.selected_model, bucket_type="weekly")
        w_today = weekly_stats.get("today_spend_pct", 0.0)
        w_month = weekly_stats.get("month_spend_pct", 0.0)
        self.lbl_pill_spend.configure(text=f"Hoy: -{w_today}% sem  |  Mes: -{w_month}% sem")

        # 1. Indicador de Ritmo Inteligente (Burn Rate)
        weekly_frac = 1.0
        weekly_reset = None
        if self.last_quota_data:
            for g in self.last_quota_data.get("groups", []):
                if (self.selected_model == "Gemini" and "Gemini" in g.get("displayName", "")) or \
                   (self.selected_model == "Claude" and ("Claude" in g.get("displayName", "") or "GPT" in g.get("displayName", ""))):
                    for b in g.get("buckets", []):
                        if "weekly" in b.get("bucketId", "").lower():
                            weekly_frac = float(b.get("remainingFraction", 1.0))
                            weekly_reset = b.get("resetTime")
        burn = self.usage_tracker.calculate_burn_rate(weekly_frac, weekly_reset)
        if hasattr(self, "lbl_burn_rate"):
            burn_color = "#FBBC04" if burn.get("status") == "warning" else "#34A853"
            self.lbl_burn_rate.configure(text=burn.get("text", "🟢 Ritmo normal"), text_color=burn_color)

        # 2. Desglose según Pestaña Activa: Proyectos vs Consultas Recientes
        for widget in self.projects_container.winfo_children():
            widget.destroy()

        if self.stats_view_mode == "recent":
            recent_events = self.usage_tracker.get_recent_history(
                filter_group=self.selected_model, bucket_type=self.stats_mode, limit=4
            )
            if not recent_events:
                lbl = ctk.CTkLabel(
                    self.projects_container, 
                    text="Esperando nuevas consultas para registrar...",
                    font=ctk.CTkFont(family="Segoe UI", size=9),
                    text_color=self.current_theme["text_muted"]
                )
                lbl.pack(pady=4)
            else:
                for item in recent_events:
                    p_row = ctk.CTkFrame(self.projects_container, fg_color="transparent")
                    p_row.pack(fill="x", padx=4, pady=1)

                    lbl_time = ctk.CTkLabel(
                        p_row, text=f"{item['time']} · 📁 {item['project']}",
                        font=ctk.CTkFont(family="Segoe UI", size=9),
                        text_color=self.current_theme["text_primary"], anchor="w"
                    )
                    lbl_time.pack(side="left")

                    lbl_spend = ctk.CTkLabel(
                        p_row, text=item["spend_str"],
                        font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                        text_color="#FA7B17", anchor="e"
                    )
                    lbl_spend.pack(side="right")
        else:
            projects = stats.get("projects", [])
            if not projects:
                lbl = ctk.CTkLabel(
                    self.projects_container, 
                    text=f"● Proyecto activo: {cur_proj}\nRegistrando consumo del cupo {tag}...",
                    font=ctk.CTkFont(family="Segoe UI", size=9),
                    text_color=self.current_theme["text_muted"]
                )
                lbl.pack(pady=4)
            else:
                for p in projects[:4]:
                    p_row = ctk.CTkFrame(self.projects_container, fg_color="transparent")
                    p_row.pack(fill="x", padx=4, pady=1)

                    p_name = p.get("name", "General")
                    p_spend = p.get("spend_pct", 0.0)
                    
                    is_active = (p_name == cur_proj)
                    color = "#34A853" if is_active else self.current_theme["text_primary"]
                    prefix = "📁 ● " if is_active else "📁 "

                    lbl_pname = ctk.CTkLabel(
                        p_row, text=f"{prefix}{p_name}",
                        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold" if is_active else "normal"),
                        text_color=color, anchor="w"
                    )
                    lbl_pname.pack(side="left")

                    lbl_pspend = ctk.CTkLabel(
                        p_row, text=f"-{p_spend}% {tag}",
                        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                        text_color="#FA7B17", anchor="e"
                    )
                    lbl_pspend.pack(side="right")

    def _bind_events_recursive(self, widget):
        widget.bind("<Enter>", self._on_mouse_enter, add="+")
        widget.bind("<Leave>", self._on_mouse_leave, add="+")
        widget.bind("<Button-3>", self._show_context_menu, add="+")
        
        if widget != self.resize_grip and not isinstance(widget, (ctk.CTkButton, tk.Menu)):
            widget.bind("<ButtonPress-1>", self._start_drag, add="+")
            widget.bind("<B1-Motion>", self._on_drag, add="+")
            widget.bind("<ButtonRelease-1>", self._end_drag, add="+")
            
        for child in widget.winfo_children():
            if child != self.resize_grip:
                self._bind_events_recursive(child)

    def _on_mouse_enter(self, event=None):
        if self.dynamic_opacity:
            self.attributes("-alpha", 1.0)
        self.status_pill.pack_forget()
        self.controls_frame.pack(side="right")
        self.resize_grip.configure(text_color=self.current_theme["accent"])

    def _on_mouse_leave(self, event=None):
        if self.is_resizing or self.is_dragging:
            return
        x, y = self.winfo_pointerxy()
        wx = self.winfo_rootx()
        wy = self.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        
        if not (wx <= x <= wx + w and wy <= y <= wy + h):
            if self.dynamic_opacity:
                self.attributes("-alpha", 0.88)
            self.controls_frame.pack_forget()
            self.status_pill.pack(side="right", padx=(4, 0))
            self.resize_grip.configure(text_color="#555B66")

    # --- DRAGGING & MAGNETIC SNAPPING ---
    def _start_drag(self, event):
        if self.is_resizing:
            return
        self.is_dragging = True
        self.drag_mouse_start_x = event.x_root
        self.drag_mouse_start_y = event.y_root
        self.drag_win_start_x = self.winfo_x()
        self.drag_win_start_y = self.winfo_y()

    def _on_drag(self, event):
        if not self.is_dragging or self.is_resizing:
            return
        delta_x = event.x_root - self.drag_mouse_start_x
        delta_y = event.y_root - self.drag_mouse_start_y
        new_x = self.drag_win_start_x + delta_x
        new_y = self.drag_win_start_y + delta_y
        self.geometry(f"+{new_x}+{new_y}")

    def _end_drag(self, event):
        self.is_dragging = False
        cur_x = self.winfo_x()
        cur_y = self.winfo_y()
        snapped_x, snapped_y = apply_screen_snapping(cur_x, cur_y, self.card_w, self.card_h)
        if (snapped_x, snapped_y) != (cur_x, cur_y):
            self.geometry(f"+{snapped_x}+{snapped_y}")
            
        self.config["x"] = snapped_x
        self.config["y"] = snapped_y
        save_config(self.config)

    # --- RESIZING ---
    def _start_resize(self, event):
        self.is_resizing = True
        self.resize_mouse_start_x = event.x_root
        self.resize_mouse_start_y = event.y_root
        self.resize_win_start_w = self.card_w
        self.resize_win_start_h = self.card_h
        self.resize_win_fixed_x = self.winfo_x()
        self.resize_win_fixed_y = self.winfo_y()

    def _on_resize(self, event):
        if not self.is_resizing:
            return
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        delta_w = int((event.x_root - self.resize_mouse_start_x) / scale)
        delta_h = int((event.y_root - self.resize_mouse_start_y) / scale)
        new_w = max(240, self.resize_win_start_w + delta_w)
        new_h = max(280, self.resize_win_start_h + delta_h)
        self.card_w = new_w
        self.card_h = new_h
        self.geometry(f"{new_w}x{new_h}+{self.resize_win_fixed_x}+{self.resize_win_fixed_y}")

    def _end_resize(self, event):
        self.is_resizing = False
        self.config["width"] = self.card_w
        self.config["height"] = self.card_h
        save_config(self.config)

    def _toggle_always_on_top(self):
        curr = self.config.get("always_on_top", False)
        new_state = not curr
        self.config["always_on_top"] = new_state
        self.attributes("-topmost", new_state)
        
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            z_order = -1 if new_state else -2
            ctypes.windll.user32.SetWindowPos(hwnd, z_order, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        except Exception:
            pass
            
        self.btn_pin.configure(text="📌" if new_state else "📍")
        save_config(self.config)

    def _trigger_manual_refresh(self, icon=None, item=None):
        if not self.is_fetching:
            self.btn_refresh.configure(state="disabled")
            threading.Thread(target=self._fetch_quota_worker, daemon=True).start()

    def _fetch_quota_worker(self):
        self.is_fetching = True
        res = self.quota_service.fetch_quota()
        self.is_fetching = False
        self.after(0, lambda: self._apply_quota_update(res))

    def _apply_quota_update(self, res):
        self.btn_refresh.configure(state="normal")
        if res.get("success"):
            data = res.get("data", {})
            self.last_quota_data = data
            self._update_display()
        else:
            err = res.get("error", "Desconectado")
            self.status_dot.configure(text_color="#70757A")
            self.status_label.configure(text="Desconectado", text_color="#EA4335")
            if self.tray_icon:
                try:
                    self.tray_icon.title = f"AI Quota: {err}"[:120]
                    self.tray_icon.icon = create_tray_icon_image("#70757A")
                except Exception:
                    pass
            self.msg_banner.configure(text=f"⚠️ {err}\nReintentando en segundo plano...")
            self.msg_banner.pack(pady=20)

    def _start_fetch_thread(self):
        def loop():
            self._fetch_quota_worker()
            while self.running:
                interval = self.config.get("refresh_interval_sec", 60)
                self._fetch_event.wait(timeout=interval)
                self._fetch_event.clear()
                if not self.running:
                    break
                if not self.is_fetching:
                    self._fetch_quota_worker()
        threading.Thread(target=loop, daemon=True).start()

    def _start_countdown_timer(self):
        def tick():
            if self.running:
                try:
                    for b_id, view in self.bucket_widgets.items():
                        if view["row"].winfo_ismapped():
                            reset_time = view.get("reset_time")
                            if reset_time:
                                time_left = self.quota_service.calculate_time_remaining(reset_time)
                                view["lbl_timer"].configure(text=f"⏳ {time_left} restantes")
                except Exception:
                    pass
                if self.running:
                    self.after(1000, tick)
        self.after(1000, tick)

    def _request_close(self, icon=None, item=None):
        """Programa el cierre en el hilo principal de Tkinter para que el menú de la bandeja se libere."""
        self.after(10, self._on_close)

    def _on_close(self):
        self.running = False
        self._fetch_event.set()
        
        # 1. Liberar hotkey global
        if self._hotkey_thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(self._hotkey_thread_id, 0x0012, 0, 0)
            except Exception:
                pass

        # 2. Ocultar y remover icono de la bandeja de forma síncrona
        if self.tray_icon:
            try:
                self.tray_icon.visible = False
                if hasattr(self.tray_icon, "_hide"):
                    self.tray_icon._hide()
                self.tray_icon.stop()
            except Exception:
                pass

        # 3. Forzar a Windows Explorer a purgar cualquier icono fantasma inmediatamente
        clean_ghost_icons()
        time.sleep(0.08)

        # 4. Destruir ventana y salir limpiamente
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

if __name__ == "__main__":
    app = PureQuotaWidget()
    app.mainloop()
