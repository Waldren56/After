import tkinter as tk
from tkinter import ttk, messagebox, font
import threading
import time
from datetime import datetime, timedelta
from collections import deque
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import json
import pandas as pd
import websockets
import asyncio
from threading import Thread
import queue
import requests
import math
import os
import sys
import tempfile
import uuid
import random

# Import per i grafici
import matplotlib

matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ============ SETUP CACHE FASTF1 ============
def setup_fastf1_cache():
    """Configura la cache per FastF1"""
    print("🔧 Setting up FastF1 cache...")

    cache_path = './f1_cache'

    try:
        if not os.path.exists(cache_path):
            os.makedirs(cache_path, exist_ok=True)
            print(f"✅ Created cache directory: {cache_path}")

        import fastf1 as ff1
        ff1.Cache.enable_cache(cache_path, ignore_version=False)
        print(f"✅ Cache enabled at: {cache_path}")

        return ff1

    except Exception as e:
        print(f"⚠️ Cache error: {e}")
        try:
            import fastf1 as ff1
            return ff1
        except ImportError:
            print("❌ FastF1 not installed")
            return None


# Setup FastF1
ff1 = setup_fastf1_cache()

# ============ CONFIGURAZIONE MODERNA ============
OPENF1_API_URL = "https://api.openf1.org/v1"
WEBSOCKET_URL = "wss://api.openf1.org/v1"
UPDATE_INTERVAL_REAL_TIME = 3
HISTORY_LENGTH = 50

# TEMA MODERNO NERO/VIOLA
COLORS = {
    'bg': '#0a0a12',
    'bg_light': '#1a1a24',
    'bg_dark': '#05050a',
    'bg_card': '#151520',
    'accent': '#7c4dff',  # Viola moderno
    'accent_light': '#9a7dff',
    'accent_dark': '#5c3db8',
    'red': '#ff5252',
    'green': '#4caf50',
    'yellow': '#ffc107',
    'blue': '#2196f3',
    'cyan': '#00e5ff',
    'orange': '#ff9800',
    'purple': '#9c27b0',
    'white': '#e0e0e0',
    'gray': '#757575',
    'gray_light': '#b0b0b0',
    'gray_dark': '#424242',
    'success': '#00c853',
    'warning': '#ff9800',
    'error': '#f44336',
    'info': '#2196f3'
}

# Font moderni
FONTS = {
    'h1': ('Segoe UI', 24, 'bold'),
    'h2': ('Segoe UI', 18, 'bold'),
    'h3': ('Segoe UI', 14, 'bold'),
    'body': ('Segoe UI', 11),
    'small': ('Segoe UI', 9),
    'code': ('Consolas', 10),
    'bold': ('Segoe UI', 11, 'bold')
}


# ============ COMPONENTI UI MODERNI ============
class RoundedButton(tk.Canvas):
    """Pulsante moderno con bordi arrotondati"""

    def __init__(self, parent, text, command, width=120, height=40,
                 radius=10, bg_color=COLORS['accent'], fg_color=COLORS['white'],
                 hover_color=None, active_color=None, font=FONTS['bold']):

        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bg=COLORS['bg'])

        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_color = hover_color or self._lighten_color(bg_color, 20)
        self.active_color = active_color or self._darken_color(bg_color, 20)
        self.radius = radius
        self.font = font

        # Draw button
        self.draw_button(bg_color)
        self.create_text(width // 2, height // 2, text=text,
                         fill=fg_color, font=font)

        # Bind events
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)

    def _lighten_color(self, color, percent):
        """Schiarisci un colore"""
        if isinstance(color, str) and color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = min(255, r + int((255 - r) * percent / 100))
            g = min(255, g + int((255 - g) * percent / 100))
            b = min(255, b + int((255 - b) * percent / 100))
            return f'#{r:02x}{g:02x}{b:02x}'
        return color

    def _darken_color(self, color, percent):
        """Scurisci un colore"""
        if isinstance(color, str) and color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = max(0, r - int(r * percent / 100))
            g = max(0, g - int(g * percent / 100))
            b = max(0, b - int(b * percent / 100))
            return f'#{r:02x}{g:02x}{b:02x}'
        return color

    def draw_button(self, color):
        """Disegna il pulsante arrotondato"""
        self.delete("all")
        width = int(self.cget('width'))
        height = int(self.cget('height'))

        # Crea forma arrotondata
        self.create_rounded_rect(0, 0, width, height, self.radius,
                                 fill=color, outline=color)

    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Crea rettangolo con bordi arrotondati"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]

        return self.create_polygon(points, smooth=True, **kwargs)

    def on_enter(self, e):
        self.draw_button(self.hover_color)

    def on_leave(self, e):
        self.draw_button(self.bg_color)

    def on_click(self, e):
        self.draw_button(self.active_color)

    def on_release(self, e):
        self.draw_button(self.hover_color)
        self.command()


class ModernCard(tk.Frame):
    """Card moderna con ombre e bordi arrotondati"""

    def __init__(self, parent, title="", **kwargs):
        bg = kwargs.pop('bg', COLORS['bg_card'])
        super().__init__(parent, bg=COLORS['bg'], **kwargs)

        # Frame interno con padding
        inner_frame = tk.Frame(self, bg=bg, relief='flat')
        inner_frame.pack(fill='both', expand=True, padx=1, pady=1)

        # Titolo
        if title:
            title_frame = tk.Frame(inner_frame, bg=bg)
            title_frame.pack(fill='x', padx=15, pady=(10, 5))

            tk.Label(title_frame, text=title,
                     font=FONTS['h3'],
                     bg=bg,
                     fg=COLORS['accent']).pack(anchor='w')

            # Separatore
            tk.Frame(inner_frame, height=1, bg=COLORS['gray_dark']).pack(fill='x', padx=15, pady=(0, 10))

        self.content_frame = tk.Frame(inner_frame, bg=bg)
        self.content_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def get_content_frame(self):
        return self.content_frame


class MetricCard(tk.Frame):
    """Card per metriche KPI"""

    def __init__(self, parent, title, value, unit="", color=COLORS['white'], **kwargs):
        super().__init__(parent, bg=COLORS['bg_card'], relief='flat', **kwargs)

        # Titolo
        tk.Label(self, text=title,
                 font=FONTS['small'],
                 bg=COLORS['bg_card'],
                 fg=COLORS['gray_light']).pack(pady=(10, 5))

        # Valore
        self.value_label = tk.Label(self, text="",
                                    font=FONTS['h2'],
                                    bg=COLORS['bg_card'],
                                    fg=color)
        self.value_label.pack()

        # Unità
        if unit:
            tk.Label(self, text=unit,
                     font=FONTS['small'],
                     bg=COLORS['bg_card'],
                     fg=COLORS['gray']).pack(pady=(0, 10))

        # Aggiorna valore iniziale
        self.update_value(value)

    def update_value(self, value):
        self.value_label.config(text=str(value))


# ============ LIVE DATA MANAGER MIGLIORATO ============
class LiveDataManager:
    """Gestore per dati F1 in tempo reale con gestione sessione migliorata"""

    def __init__(self, app):
        self.app = app
        self.running = False
        self.session_key = None
        self.session_data = {}
        self.drivers = {}
        self.positions = {}
        self.laps = {}
        self.intervals = {}
        self.weather = {}
        self.next_session = None
        self.current_lap = 1
        self.data_mode = "DEMO"

    def start(self):
        """Avvia acquisizione dati"""
        self.running = True
        self.app.update_status("🔍 Ricerca sessioni F1...", COLORS['info'])

        # Cerca sessioni
        threading.Thread(target=self.find_sessions, daemon=True).start()

    def find_sessions(self):
        """Trova sessioni attive e future"""
        try:
            now = datetime.now()
            now_iso = now.isoformat() + 'Z'

            # 1. Cerca sessioni attive ORA
            url = f"{OPENF1_API_URL}/sessions"
            params = {
                'date_start__lte': now_iso,
                'date_end__gte': now_iso,
                'order': '-date_start'
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                active_sessions = response.json()
                if active_sessions:
                    session = active_sessions[0]
                    self.session_key = session['session_key']
                    self.session_data = session
                    self.data_mode = "LIVE"

                    # Aggiorna GUI
                    self.app.root.after(0, self.app.show_session_info, {
                        'type': 'active',
                        'name': session['session_name'],
                        'circuit': session.get('location', 'Unknown'),
                        'start': session.get('date_start'),
                        'end': session.get('date_end')
                    })

                    self.app.update_status(f"✅ Sessione live trovata!", COLORS['success'])

                    # Carica dati
                    self.load_initial_data()
                    threading.Thread(target=self.polling_loop, daemon=True).start()
                    return

            # 2. Se nessuna sessione attiva, cerca prossima
            params = {
                'date_start__gte': now_iso,
                'order': 'date_start',
                'limit': 5
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                future_sessions = response.json()
                if future_sessions:
                    # Trova la prossima sessione
                    next_session = None
                    min_diff = float('inf')

                    for session in future_sessions:
                        start_str = session.get('date_start')
                        if start_str:
                            try:
                                start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                                diff = (start_time - now).total_seconds()

                                if 0 < diff < min_diff:
                                    min_diff = diff
                                    next_session = session
                            except:
                                continue

                    if next_session:
                        self.next_session = next_session
                        start_time = datetime.fromisoformat(next_session['date_start'].replace('Z', '+00:00'))

                        self.app.root.after(0, self.app.show_session_info, {
                            'type': 'upcoming',
                            'name': next_session['session_name'],
                            'circuit': next_session.get('location', 'Unknown'),
                            'start': next_session['date_start'],
                            'countdown': self.format_countdown(start_time - now)
                        })

                        self.app.update_status("⏰ Nessuna sessione live - Modalità demo", COLORS['warning'])
                        self.data_mode = "DEMO (Prossima: " + self.format_countdown(start_time - now) + ")"

                        # Avvia demo
                        self.start_demo_mode()
                        return

            # 3. Nessuna sessione trovata
            self.app.root.after(0, self.app.show_session_info, {
                'type': 'none',
                'message': "Nessuna sessione F1 programmata nelle prossime 24h"
            })

            self.app.update_status("📊 Nessuna sessione trovata - Modalità demo", COLORS['warning'])
            self.data_mode = "DEMO"
            self.start_demo_mode()

        except Exception as e:
            print(f"❌ Errore ricerca sessioni: {e}")
            self.app.update_status(f"❌ Errore connessione: {e}", COLORS['error'])
            self.data_mode = "DEMO (Errore)"
            self.start_demo_mode()

    def format_countdown(self, time_diff):
        """Formatta countdown"""
        if time_diff.total_seconds() <= 0:
            return "IN CORSO"

        days = time_diff.days
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def load_initial_data(self):
        """Carica dati iniziali"""
        try:
            if not self.session_key:
                return

            # Carica piloti
            self.load_drivers()

            # Carica altre info
            self.load_positions()
            self.load_laps()
            self.load_intervals()

            print(f"✅ Dati caricati: {len(self.drivers)} piloti")

        except Exception as e:
            print(f"Errore caricamento dati: {e}")

    def load_drivers(self):
        """Carica piloti"""
        try:
            url = f"{OPENF1_API_URL}/drivers"
            params = {'session_key': self.session_key}

            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                drivers_list = response.json()
                for driver in drivers_list:
                    num = driver.get('driver_number')
                    if num:
                        self.drivers[num] = {
                            'code': driver.get('name_acronym', f'D{num}'),
                            'name': driver.get('full_name', f'Driver {num}'),
                            'team': driver.get('team_name', 'Unknown'),
                            'country': driver.get('country_code', ''),
                        }

        except Exception as e:
            print(f"Errore piloti: {e}")

    def load_positions(self):
        """Carica posizioni"""
        try:
            url = f"{OPENF1_API_URL}/position"
            params = {'session_key': self.session_key, 'order': '-date'}

            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                positions = response.json()
                for pos in positions:
                    num = pos.get('driver_number')
                    if num:
                        self.positions[num] = {
                            'position': pos.get('position', 20),
                            'date': pos.get('date'),
                        }

        except Exception as e:
            print(f"Errore posizioni: {e}")

    def load_laps(self):
        """Carica giri"""
        try:
            url = f"{OPENF1_API_URL}/laps"
            params = {'session_key': self.session_key, 'order': '-lap_number', 'limit': 50}

            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                laps_list = response.json()
                for lap in laps_list:
                    num = lap.get('driver_number')
                    if num:
                        self.laps[num] = {
                            'lap_number': lap.get('lap_number', 1),
                            'duration': lap.get('lap_duration'),
                            'date': lap.get('date'),
                        }

                        # Aggiorna giro corrente
                        lap_num = lap.get('lap_number', 1)
                        if lap_num > self.current_lap:
                            self.current_lap = lap_num

        except Exception as e:
            print(f"Errore giri: {e}")

    def load_intervals(self):
        """Carica intervalli"""
        try:
            url = f"{OPENF1_API_URL}/intervals"
            params = {'session_key': self.session_key, 'order': '-date'}

            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                intervals = response.json()
                for interval in intervals[:20]:
                    num = interval.get('driver_number')
                    if num:
                        self.intervals[num] = {
                            'interval': interval.get('interval'),
                            'date': interval.get('date'),
                        }

        except Exception as e:
            print(f"Errore intervalli: {e}")

    def polling_loop(self):
        """Loop per aggiornamento dati"""
        while self.running:
            try:
                self.load_positions()
                self.load_laps()

                # Prepara dati per dashboard
                data = self.prepare_dashboard_data()
                self.app.root.after(0, self.app.dashboard.update_dashboard, data)

                time.sleep(UPDATE_INTERVAL_REAL_TIME)

            except Exception as e:
                print(f"Polling error: {e}")
                time.sleep(5)

    def prepare_dashboard_data(self):
        """Prepara dati per dashboard"""
        # Classifica
        classification = self.get_classification()

        # Leader info
        leader_info = self.get_leader_info()

        return {
            'current_lap': self.current_lap,
            'total_laps': 57,
            'leader': leader_info['code'],
            'gap_to_second': leader_info['gap'],
            'flag': '🟢',
            'weather': {
                'conditions': 'Sereno',
                'air_temp': '24°C',
                'track_temp': '32°C',
                'humidity': '45%'
            },
            'drs': {
                'zone1': 'ATTIVO',
                'zone2': 'ATTIVO',
                'zone3': 'N/A'
            },
            'safety_car': 'NESSUNO',
            'classification': classification,
            'gap_data': self.get_gap_data(),
            'session_live': True if self.session_key else False,
            'data_mode': self.data_mode,
            'session_info': {
                'name': self.session_data.get('session_name', 'Demo Session'),
                'circuit': self.session_data.get('location', 'Circuito Demo'),
                'type': self.session_data.get('session_type', 'Race')
            }
        }

    def get_classification(self):
        """Genera classifica"""
        classification = []

        if not self.positions:
            return self.get_demo_classification()

        # Ordina per posizione
        sorted_drivers = sorted(self.positions.items(),
                                key=lambda x: x[1].get('position', 99))

        for idx, (num, pos_info) in enumerate(sorted_drivers[:20]):
            driver = self.drivers.get(num, {})
            interval = self.intervals.get(num, {})

            gap = "Leader" if idx == 0 else f"+{interval.get('interval', idx * 2.5):.3f}"

            classification.append({
                'position': pos_info.get('position', idx + 1),
                'driver': driver.get('code', f'D{num}'),
                'team': driver.get('team', 'Unknown'),
                'gap': gap,
                'last_lap': '1:30.000',
                'tyre': ['SOFT', 'MEDIUM', 'HARD'][num % 3],
                'pit_stops': num % 2
            })

        return classification

    def get_leader_info(self):
        """Ottieni info leader"""
        if self.positions:
            for num, pos_info in self.positions.items():
                if pos_info.get('position') == 1:
                    driver = self.drivers.get(num, {})

                    # Trova gap al secondo
                    gap = 1.234
                    for other_num, other_pos in self.positions.items():
                        if other_pos.get('position') == 2:
                            interval = self.intervals.get(other_num, {})
                            gap = interval.get('interval', 1.234)
                            break

                    return {'code': driver.get('code', 'VER'), 'gap': gap}

        return {'code': 'VER', 'gap': 1.234}

    def get_gap_data(self):
        """Dati per grafico gap"""
        return {'VER': 0, 'LEC': 2.5, 'HAM': 5.0, 'NOR': 7.5}

    def get_demo_classification(self):
        """Classifica demo"""
        drivers = [
            {'code': 'VER', 'team': 'Red Bull'},
            {'code': 'LEC', 'team': 'Ferrari'},
            {'code': 'HAM', 'team': 'Mercedes'},
            {'code': 'NOR', 'team': 'McLaren'},
            {'code': 'SAI', 'team': 'Ferrari'},
            {'code': 'RUS', 'team': 'Mercedes'},
            {'code': 'PIA', 'team': 'McLaren'},
            {'code': 'ALO', 'team': 'Aston Martin'},
            {'code': 'STR', 'team': 'Aston Martin'},
            {'code': 'GAS', 'team': 'Alpine'},
        ]

        classification = []
        for i, driver in enumerate(drivers):
            classification.append({
                'position': i + 1,
                'driver': driver['code'],
                'team': driver['team'],
                'gap': 'Leader' if i == 0 else f"+{i * 2.345:.3f}",
                'last_lap': f"1:{30 + i % 10}.{i:03d}",
                'tyre': ['SOFT', 'MEDIUM', 'HARD'][i % 3],
                'pit_stops': i % 2
            })

        return classification

    def start_demo_mode(self):
        """Avvia modalità demo"""
        # Genera dati demo
        self.generate_demo_data()

        # Avvia loop demo
        threading.Thread(target=self.demo_loop, daemon=True).start()

    def generate_demo_data(self):
        """Genera dati demo"""
        # Pilot demo
        driver_data = {
            1: {'code': 'VER', 'name': 'Max Verstappen', 'team': 'Red Bull'},
            16: {'code': 'LEC', 'name': 'Charles Leclerc', 'team': 'Ferrari'},
            44: {'code': 'HAM', 'name': 'Lewis Hamilton', 'team': 'Mercedes'},
            4: {'code': 'NOR', 'name': 'Lando Norris', 'team': 'McLaren'},
            55: {'code': 'SAI', 'name': 'Carlos Sainz', 'team': 'Ferrari'},
        }

        for num, data in driver_data.items():
            self.drivers[num] = {
                'code': data['code'],
                'name': data['name'],
                'team': data['team'],
                'country': 'NED' if num == 1 else 'MON' if num == 16 else 'GBR'
            }

        # Posizioni demo
        drivers = list(self.drivers.keys())
        random.shuffle(drivers)

        for i, num in enumerate(drivers):
            self.positions[num] = {
                'position': i + 1,
                'date': datetime.now().isoformat()
            }

        # Giri demo
        self.current_lap = random.randint(10, 30)

        for num in self.drivers.keys():
            self.laps[num] = {
                'lap_number': self.current_lap,
                'duration': 90.0 + random.random() * 2,
                'date': datetime.now().isoformat()
            }

    def demo_loop(self):
        """Loop demo con variazioni"""
        while self.running:
            try:
                # Simula variazioni
                if random.random() < 0.1:  # 10% chance di avanzare giro
                    self.current_lap = min(self.current_lap + 1, 57)

                # Occasionalmente cambia posizioni
                if random.random() < 0.05:  # 5% chance
                    drivers = list(self.positions.keys())
                    random.shuffle(drivers)

                    for i, num in enumerate(drivers[:5]):
                        self.positions[num]['position'] = i + 1

                # Aggiorna dashboard
                data = self.prepare_dashboard_data()
                self.app.root.after(0, self.app.dashboard.update_dashboard, data)

                time.sleep(UPDATE_INTERVAL_REAL_TIME)

            except Exception as e:
                print(f"Demo error: {e}")
                time.sleep(1)

    def stop(self):
        """Ferma acquisizione"""
        self.running = False


# ============ DASHBOARD MODERNA ============
class ModernDashboard:
    """Dashboard moderna con design nero/viola"""

    def __init__(self, parent):
        self.parent = parent
        self.data_history = deque(maxlen=HISTORY_LENGTH)

    def create_dashboard(self, container):
        """Crea la dashboard"""
        self.container = container

        # Notebook con stile moderno
        style = ttk.Style()
        style.theme_use('clam')

        # Configura notebook
        style.configure('TNotebook', background=COLORS['bg'], borderwidth=0)
        style.configure('TNotebook.Tab',
                        background=COLORS['bg_light'],
                        foreground=COLORS['white'],
                        padding=[15, 5],
                        font=FONTS['bold'])
        style.map('TNotebook.Tab',
                  background=[('selected', COLORS['accent_dark'])],
                  foreground=[('selected', COLORS['white'])])

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab Panoramica
        self.overview_tab = tk.Frame(self.notebook, bg=COLORS['bg'])
        self.notebook.add(self.overview_tab, text="🏁 LIVE")
        self.create_overview_tab()

        # Tab Dettagli
        self.details_tab = tk.Frame(self.notebook, bg=COLORS['bg'])
        self.notebook.add(self.details_tab, text="📊 ANALISI")
        self.create_details_tab()

        # Tab Info
        self.info_tab = tk.Frame(self.notebook, bg=COLORS['bg'])
        self.notebook.add(self.info_tab, text="ℹ️ INFO")
        self.create_info_tab()

    def create_overview_tab(self):
        """Crea tab panoramica"""
        # Frame principale con scroll
        main_frame = tk.Frame(self.overview_tab, bg=COLORS['bg'])
        main_frame.pack(fill='both', expand=True)

        canvas = tk.Canvas(main_frame, bg=COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS['bg'])

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 1. HEADER con info sessione
        self.session_header = ModernCard(scrollable_frame, title="STATO SESSIONE")
        self.session_header.pack(fill='x', padx=20, pady=(20, 10))

        content = self.session_header.get_content_frame()

        self.session_status = tk.Label(content,
                                       text="🔍 Ricerca sessioni in corso...",
                                       font=FONTS['h3'],
                                       bg=COLORS['bg_card'],
                                       fg=COLORS['white'])
        self.session_status.pack(anchor='w', pady=(0, 5))

        self.session_details = tk.Label(content,
                                        text="",
                                        font=FONTS['body'],
                                        bg=COLORS['bg_card'],
                                        fg=COLORS['gray_light'],
                                        wraplength=800,
                                        justify='left')
        self.session_details.pack(anchor='w')

        # 2. KPI CARDS in griglia
        kpi_frame = tk.Frame(scrollable_frame, bg=COLORS['bg'])
        kpi_frame.pack(fill='x', padx=20, pady=(0, 20))

        # Prima riga KPI
        row1 = tk.Frame(kpi_frame, bg=COLORS['bg'])
        row1.pack(fill='x', pady=(0, 10))

        self.kpi_cards = {}
        kpis_row1 = [
            ('GIRO', 'current_lap', '1/57', COLORS['cyan']),
            ('LEADER', 'leader', 'VER', COLORS['yellow']),
            ('GAP', 'gap_to_second', '+1.234s', COLORS['green']),
            ('BANDIERA', 'flag', '🟢', COLORS['accent_light'])
        ]

        for title, key, value, color in kpis_row1:
            card = MetricCard(row1, title, value, color=color, width=180, height=100)
            card.pack(side='left', padx=5)
            self.kpi_cards[key] = card

        # Seconda riga KPI
        row2 = tk.Frame(kpi_frame, bg=COLORS['bg'])
        row2.pack(fill='x')

        kpis_row2 = [
            ('METEO', 'weather_cond', 'Sereno', COLORS['blue']),
            ('PISTA', 'track_temp', '32°C', COLORS['orange']),
            ('DRS', 'drs_status', 'ATTIVO', COLORS['purple']),
            ('S.CAR', 'safety_car', 'NO', COLORS['gray_light'])
        ]

        for title, key, value, color in kpis_row2:
            card = MetricCard(row2, title, value, color=color, width=180, height=100)
            card.pack(side='left', padx=5)
            self.kpi_cards[key] = card

        # 3. CLASSIFICA LIVE
        class_card = ModernCard(scrollable_frame, title="🏆 CLASSIFICA LIVE")
        class_card.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        class_content = class_card.get_content_frame()

        # Treeview per classifica
        columns = ('Pos', 'Pilota', 'Team', 'Gap', 'Ultimo Giro', 'Gomme', 'Pit')
        self.class_tree = ttk.Treeview(class_content,
                                       columns=columns,
                                       show='headings',
                                       height=12)

        # Configura colonne
        col_config = [
            ('Pos', 50, 'center'),
            ('Pilota', 100, 'center'),
            ('Team', 120, 'center'),
            ('Gap', 80, 'center'),
            ('Ultimo Giro', 100, 'center'),
            ('Gomme', 80, 'center'),
            ('Pit', 50, 'center')
        ]

        for heading, width, anchor in col_config:
            self.class_tree.heading(heading, text=heading)
            self.class_tree.column(heading, width=width, anchor=anchor)

        # Stile Treeview
        style = ttk.Style()
        style.configure("Treeview",
                        background=COLORS['bg_card'],
                        foreground=COLORS['white'],
                        fieldbackground=COLORS['bg_card'],
                        font=FONTS['small'])
        style.configure("Treeview.Heading",
                        background=COLORS['bg_dark'],
                        foreground=COLORS['accent_light'],
                        font=FONTS['bold'],
                        relief='flat')
        style.map("Treeview.Heading",
                  background=[('active', COLORS['accent_dark'])])

        # Scrollbar
        scrollbar_tree = ttk.Scrollbar(class_content, orient='vertical', command=self.class_tree.yview)
        self.class_tree.configure(yscrollcommand=scrollbar_tree.set)

        self.class_tree.pack(side='left', fill='both', expand=True)
        scrollbar_tree.pack(side='right', fill='y')

        # 4. INFO AGGIUNTIVE
        info_card = ModernCard(scrollable_frame, title="📡 INFO LIVE")
        info_card.pack(fill='x', padx=20, pady=(0, 20))

        info_content = info_card.get_content_frame()

        # Griglia info
        info_grid = tk.Frame(info_content, bg=COLORS['bg_card'])
        info_grid.pack(fill='x')

        self.info_labels = {}
        info_items = [
            ('Ultimo aggiornamento:', 'last_update', '--:--:--', COLORS['gray_light']),
            ('Modo dati:', 'data_mode', 'DEMO', COLORS['warning']),
            ('Connessione:', 'connection', '🔴 OFFLINE', COLORS['error']),
            ('Frequenza:', 'update_freq', f'{UPDATE_INTERVAL_REAL_TIME}s', COLORS['info'])
        ]

        for i, (label, key, value, color) in enumerate(info_items):
            if i % 2 == 0:
                row = tk.Frame(info_grid, bg=COLORS['bg_card'])
                row.pack(fill='x', pady=5)

            frame = tk.Frame(row, bg=COLORS['bg_card'])
            frame.pack(side='left', padx=20)

            tk.Label(frame, text=label,
                     font=FONTS['small'],
                     bg=COLORS['bg_card'],
                     fg=COLORS['gray']).pack(side='left', padx=(0, 5))

            self.info_labels[key] = tk.Label(frame, text=value,
                                             font=FONTS['small'],
                                             bg=COLORS['bg_card'],
                                             fg=color)
            self.info_labels[key].pack(side='left')

    def create_details_tab(self):
        """Crea tab dettagli"""
        main_frame = tk.Frame(self.details_tab, bg=COLORS['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Titolo
        tk.Label(main_frame, text="📊 ANALISI AVANZATA",
                 font=FONTS['h1'],
                 bg=COLORS['bg'],
                 fg=COLORS['white']).pack(pady=(0, 20))

        # Sezione grafici
        graphs_card = ModernCard(main_frame, title="GRAFICI LIVE")
        graphs_card.pack(fill='both', expand=True)

        graphs_content = graphs_card.get_content_frame()

        # Frame per grafici
        graphs_frame = tk.Frame(graphs_content, bg=COLORS['bg_card'])
        graphs_frame.pack(fill='both', expand=True)

        # Grafico 1: Gap tra piloti
        fig1 = Figure(figsize=(6, 4), dpi=80, facecolor=COLORS['bg_card'])
        ax1 = fig1.add_subplot(111)
        ax1.set_facecolor(COLORS['bg_card'])
        ax1.set_title('Gap dal Leader', color=COLORS['white'])
        ax1.set_xlabel('Piloti', color=COLORS['gray_light'])
        ax1.set_ylabel('Gap (s)', color=COLORS['gray_light'])
        ax1.tick_params(colors=COLORS['gray_light'])

        # Dati iniziali
        drivers = ['VER', 'LEC', 'HAM', 'NOR', 'SAI']
        gaps = [0, 2.5, 5.0, 7.5, 10.0]
        bars = ax1.bar(drivers, gaps, color=COLORS['accent'])

        # Applica stile al grafico
        for spine in ax1.spines.values():
            spine.set_color(COLORS['gray_dark'])

        # Canvas per grafico
        canvas1 = FigureCanvasTkAgg(fig1, graphs_frame)
        canvas1.draw()
        canvas1.get_tk_widget().pack(side='left', fill='both', expand=True, padx=10)

        # Grafico 2: Velocità media
        fig2 = Figure(figsize=(6, 4), dpi=80, facecolor=COLORS['bg_card'])
        ax2 = fig2.add_subplot(111)
        ax2.set_facecolor(COLORS['bg_card'])
        ax2.set_title('Velocità Media per Pilota', color=COLORS['white'])
        ax2.set_xlabel('Piloti', color=COLORS['gray_light'])
        ax2.set_ylabel('Velocità (km/h)', color=COLORS['gray_light'])
        ax2.tick_params(colors=COLORS['gray_light'])

        speeds = [285, 283, 281, 279, 277]
        bars2 = ax2.bar(drivers, speeds, color=COLORS['cyan'])

        for spine in ax2.spines.values():
            spine.set_color(COLORS['gray_dark'])

        canvas2 = FigureCanvasTkAgg(fig2, graphs_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(side='left', fill='both', expand=True, padx=10)

        self.fig1 = fig1
        self.ax1 = ax1
        self.fig2 = fig2
        self.ax2 = ax2

        # Info dettagliate
        info_card = ModernCard(main_frame, title="INFORMAZIONI DETTAGLIATE")
        info_card.pack(fill='x', pady=(20, 0))

        info_content = info_card.get_content_frame()

        # Dati tecnici
        tech_frame = tk.Frame(info_content, bg=COLORS['bg_card'])
        tech_frame.pack(fill='x', pady=10)

        tech_items = [
            ('DRS Zone Attive:', 'drs_zones', '2/3', COLORS['green']),
            ('Tempo Safety Car:', 'sc_time', '0:00', COLORS['yellow']),
            ('Incidenti:', 'incidents', '0', COLORS['red']),
            ('Tempo Rosso:', 'red_flag', '0:00', COLORS['red'])
        ]

        for i, (label, key, value, color) in enumerate(tech_items):
            if i % 2 == 0:
                row = tk.Frame(tech_frame, bg=COLORS['bg_card'])
                row.pack(fill='x', pady=5)

            frame = tk.Frame(row, bg=COLORS['bg_card'])
            frame.pack(side='left', padx=20)

            tk.Label(frame, text=label,
                     font=FONTS['small'],
                     bg=COLORS['bg_card'],
                     fg=COLORS['gray_light']).pack(side='left', padx=(0, 10))

            tk.Label(frame, text=value,
                     font=FONTS['bold'],
                     bg=COLORS['bg_card'],
                     fg=color).pack(side='left')

    def create_info_tab(self):
        """Crea tab informazioni"""
        main_frame = tk.Frame(self.info_tab, bg=COLORS['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Titolo
        tk.Label(main_frame, text="ℹ️ INFORMAZIONI SISTEMA",
                 font=FONTS['h1'],
                 bg=COLORS['bg'],
                 fg=COLORS['white']).pack(pady=(0, 20))

        # Card informazioni
        info_card = ModernCard(main_frame, title="INFORMAZIONI SESSIONE")
        info_card.pack(fill='x')

        info_content = info_card.get_content_frame()

        # Dettagli sessione
        self.session_info_labels = {}
        session_items = [
            ('Nome Sessione:', 'session_name', 'Demo Session'),
            ('Circuito:', 'circuit_name', 'Circuito Demo'),
            ('Tipo Sessione:', 'session_type', 'Race'),
            ('Stato:', 'session_status', 'In Attesa'),
        ]

        for label, key, default in session_items:
            item_frame = tk.Frame(info_content, bg=COLORS['bg_card'])
            item_frame.pack(fill='x', pady=5)

            tk.Label(item_frame, text=label,
                     font=FONTS['bold'],
                     bg=COLORS['bg_card'],
                     fg=COLORS['gray_light'],
                     width=20, anchor='w').pack(side='left')

            self.session_info_labels[key] = tk.Label(item_frame, text=default,
                                                     font=FONTS['body'],
                                                     bg=COLORS['bg_card'],
                                                     fg=COLORS['white'],
                                                     anchor='w')
            self.session_info_labels[key].pack(side='left', fill='x', expand=True)

        # Card API info
        api_card = ModernCard(main_frame, title="CONNESSIONE API")
        api_card.pack(fill='x', pady=(20, 0))

        api_content = api_card.get_content_frame()

        # Stato API
        api_frame = tk.Frame(api_content, bg=COLORS['bg_card'])
        api_frame.pack(fill='x', pady=10)

        api_items = [
            ('API OpenF1:', 'api_openf1', '🟢 ONLINE', COLORS['green']),
            ('WebSocket:', 'websocket', '🔴 OFFLINE', COLORS['red']),
            ('Ultima risposta:', 'last_response', '--:--:--', COLORS['gray_light']),
            ('Pacchetti ricevuti:', 'packets_received', '0', COLORS['info'])
        ]

        for i, (label, key, value, color) in enumerate(api_items):
            if i % 2 == 0:
                row = tk.Frame(api_frame, bg=COLORS['bg_card'])
                row.pack(fill='x', pady=5)

            frame = tk.Frame(row, bg=COLORS['bg_card'])
            frame.pack(side='left', padx=20)

            tk.Label(frame, text=label,
                     font=FONTS['small'],
                     bg=COLORS['bg_card'],
                     fg=COLORS['gray_light']).pack(side='left', padx=(0, 10))

            tk.Label(frame, text=value,
                     font=FONTS['bold'],
                     bg=COLORS['bg_card'],
                     fg=color).pack(side='left')

        # Card note
        note_card = ModernCard(main_frame, title="NOTE")
        note_card.pack(fill='x', pady=(20, 0))

        note_content = note_card.get_content_frame()

        tk.Label(note_content, text="• Il sistema utilizza OpenF1 API per dati real-time",
                 font=FONTS['small'],
                 bg=COLORS['bg_card'],
                 fg=COLORS['gray_light'],
                 justify='left').pack(anchor='w', pady=2)

        tk.Label(note_content, text="• Modalità demo attiva quando nessuna sessione è live",
                 font=FONTS['small'],
                 bg=COLORS['bg_card'],
                 fg=COLORS['gray_light'],
                 justify='left').pack(anchor='w', pady=2)

        tk.Label(note_content, text="• I dati si aggiornano automaticamente ogni 3 secondi",
                 font=FONTS['small'],
                 bg=COLORS['bg_card'],
                 fg=COLORS['gray_light'],
                 justify='left').pack(anchor='w', pady=2)

    def update_dashboard(self, data):
        """Aggiorna la dashboard con nuovi dati"""
        try:
            # Aggiorna KPI
            self.kpi_cards['current_lap'].update_value(f"{data['current_lap']}/{data['total_laps']}")
            self.kpi_cards['leader'].update_value(data['leader'])
            self.kpi_cards['gap_to_second'].update_value(f"+{data['gap_to_second']:.3f}s")
            self.kpi_cards['flag'].update_value(data['flag'])

            # Aggiorna meteo e DRS
            self.kpi_cards['weather_cond'].update_value(data['weather']['conditions'])
            self.kpi_cards['track_temp'].update_value(data['weather']['track_temp'])
            self.kpi_cards['drs_status'].update_value(data['drs']['zone1'])
            self.kpi_cards['safety_car'].update_value(data['safety_car'])

            # Aggiorna classifica
            self.update_classification(data['classification'])

            # Aggiorna info live
            update_time = datetime.now().strftime("%H:%M:%S")
            self.info_labels['last_update'].config(text=update_time)
            self.info_labels['data_mode'].config(text=data.get('data_mode', 'DEMO'))

            # Aggiorna connessione
            conn_text = "🟢 LIVE" if data.get('session_live') else "🟡 DEMO"
            conn_color = COLORS['success'] if data.get('session_live') else COLORS['warning']
            self.info_labels['connection'].config(text=conn_text, fg=conn_color)

            # Aggiorna grafici
            if hasattr(self, 'ax1'):
                self.update_charts(data)

            # Aggiorna info sessione
            session_info = data.get('session_info', {})
            for key in self.session_info_labels:
                if key in session_info:
                    self.session_info_labels[key].config(text=session_info[key])

        except Exception as e:
            print(f"Errore aggiornamento dashboard: {e}")

    def update_classification(self, classification):
        """Aggiorna la classifica"""
        # Cancella dati precedenti
        for item in self.class_tree.get_children():
            self.class_tree.delete(item)

        # Inserisci nuovi dati
        for driver in classification[:20]:
            self.class_tree.insert('', 'end', values=(
                driver['position'],
                driver['driver'],
                driver['team'],
                driver['gap'],
                driver['last_lap'],
                driver['tyre'],
                driver['pit_stops']
            ))

    def update_charts(self, data):
        """Aggiorna i grafici"""
        try:
            # Aggiorna grafico gap
            self.ax1.clear()
            gap_data = data.get('gap_data', {'VER': 0, 'LEC': 2.5, 'HAM': 5.0, 'NOR': 7.5})

            drivers = list(gap_data.keys())[:5]
            gaps = list(gap_data.values())[:5]

            bars = self.ax1.bar(drivers, gaps, color=COLORS['accent'])
            self.ax1.set_title('Gap dal Leader', color=COLORS['white'])
            self.ax1.set_xlabel('Piloti', color=COLORS['gray_light'])
            self.ax1.set_ylabel('Gap (s)', color=COLORS['gray_light'])
            self.ax1.tick_params(colors=COLORS['gray_light'])

            for spine in self.ax1.spines.values():
                spine.set_color(COLORS['gray_dark'])

            # Aggiorna grafico velocità
            self.ax2.clear()
            speeds = [285 + random.uniform(-5, 5) for _ in range(5)]
            bars2 = self.ax2.bar(drivers, speeds, color=COLORS['cyan'])
            self.ax2.set_title('Velocità Media per Pilota', color=COLORS['white'])
            self.ax2.set_xlabel('Piloti', color=COLORS['gray_light'])
            self.ax2.set_ylabel('Velocità (km/h)', color=COLORS['gray_light'])
            self.ax2.tick_params(colors=COLORS['gray_light'])

            for spine in self.ax2.spines.values():
                spine.set_color(COLORS['gray_dark'])

            # Ridisegna
            self.fig1.canvas.draw()
            self.fig2.canvas.draw()

        except Exception as e:
            print(f"Errore aggiornamento grafici: {e}")


# ============ APPLICAZIONE PRINCIPALE ============
class F1RealTimeApp:
    """Applicazione principale con design moderno"""

    def __init__(self, root):
        self.root = root
        self.root.title("🏎️ F1 LIVE TRACKER - DASHBOARD MODERNA")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS['bg'])

        # Variabili
        self.realtime_mode = False
        self.live_manager = LiveDataManager(self)
        self.dashboard = ModernDashboard(self)

        # Setup GUI
        self.setup_gui()

        # Inizializza
        self.initialize()

    def setup_gui(self):
        """Setup interfaccia moderna"""
        # TOP BAR
        top_frame = tk.Frame(self.root, bg=COLORS['bg_dark'], height=70)
        top_frame.pack(fill='x', pady=(0, 5))
        top_frame.pack_propagate(False)

        # Logo e titolo
        title_frame = tk.Frame(top_frame, bg=COLORS['bg_dark'])
        title_frame.pack(side='left', padx=20)

        tk.Label(title_frame, text="🏎️",
                 font=('Segoe UI', 24),
                 bg=COLORS['bg_dark'],
                 fg=COLORS['accent']).pack(side='left')

        tk.Label(title_frame, text="F1 LIVE TRACKER",
                 font=FONTS['h1'],
                 bg=COLORS['bg_dark'],
                 fg=COLORS['white']).pack(side='left', padx=10)

        # Status indicator
        status_frame = tk.Frame(top_frame, bg=COLORS['bg_dark'])
        status_frame.pack(side='right', padx=20)

        self.status_indicator = tk.Label(status_frame, text="● OFFLINE",
                                         font=FONTS['bold'],
                                         bg=COLORS['bg_dark'],
                                         fg=COLORS['red'])
        self.status_indicator.pack(side='right', padx=(10, 0))

        self.session_timer = tk.Label(status_frame, text="00:00:00",
                                      font=FONTS['body'],
                                      bg=COLORS['bg_dark'],
                                      fg=COLORS['gray_light'])
        self.session_timer.pack(side='right', padx=10)

        # CONTROLLI con pulsanti arrotondati
        control_frame = tk.Frame(self.root, bg=COLORS['bg'])
        control_frame.pack(fill='x', padx=20, pady=10)

        # Pulsanti in una riga
        buttons_frame = tk.Frame(control_frame, bg=COLORS['bg'])
        buttons_frame.pack()

        # Pulsante AVVIA LIVE
        self.start_btn = RoundedButton(buttons_frame,
                                       text="▶️ AVVIA LIVE",
                                       command=self.start_realtime,
                                       width=150, height=45,
                                       bg_color=COLORS['accent'])
        self.start_btn.pack(side='left', padx=5)

        # Pulsante FERMA
        self.stop_btn = RoundedButton(buttons_frame,
                                      text="⏹️ FERMA",
                                      command=self.stop_realtime,
                                      width=120, height=45,
                                      bg_color=COLORS['gray_dark'],
                                      fg_color=COLORS['gray_light'])
        self.stop_btn.pack(side='left', padx=5)

        # Pulsante AGGIORNA
        self.refresh_btn = RoundedButton(buttons_frame,
                                         text="🔄 AGGIORNA",
                                         command=self.refresh_connection,
                                         width=150, height=45,
                                         bg_color=COLORS['blue'])
        self.refresh_btn.pack(side='left', padx=5)

        # Pulsante TEST
        self.test_btn = RoundedButton(buttons_frame,
                                      text="🌐 TEST API",
                                      command=self.test_connection,
                                      width=140, height=45,
                                      bg_color=COLORS['cyan'],
                                      fg_color=COLORS['bg_dark'])
        self.test_btn.pack(side='left', padx=5)

        # Info sessione
        self.session_info = tk.Label(control_frame,
                                     text="Pronto per connessione...",
                                     font=FONTS['body'],
                                     bg=COLORS['bg'],
                                     fg=COLORS['gray_light'])
        self.session_info.pack(pady=(10, 0))

        # DASHBOARD
        self.dashboard_frame = tk.Frame(self.root, bg=COLORS['bg'])
        self.dashboard_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.dashboard.create_dashboard(self.dashboard_frame)

        # STATUS BAR
        self.status_bar = tk.Label(self.root,
                                   text="Sistema pronto - In attesa di comandi",
                                   bd=1, relief='flat',
                                   anchor='w',
                                   bg=COLORS['bg_dark'],
                                   fg=COLORS['gray_light'],
                                   font=FONTS['small'])
        self.status_bar.pack(side='bottom', fill='x', padx=1, pady=1)

    def initialize(self):
        """Inizializza l'applicazione"""
        self.update_status("🚀 Sistema inizializzato", COLORS['info'])
        self.start_time = datetime.now()
        self.update_timer()

        # Cerca automaticamente sessioni
        self.start_realtime()

    def start_realtime(self):
        """Avvia modalità live"""
        self.realtime_mode = True
        self.status_indicator.config(text="● LIVE", fg=COLORS['success'])

        self.update_status("Avvio acquisizione dati live...", COLORS['info'])

        # Avvia live manager
        self.live_manager.start()

        # Aggiorna timer sessione
        self.session_start_time = datetime.now()

    def stop_realtime(self):
        """Ferma modalità live"""
        self.realtime_mode = False
        self.status_indicator.config(text="● OFFLINE", fg=COLORS['error'])

        self.update_status("Modalità live fermata", COLORS['warning'])

        # Ferma live manager
        self.live_manager.stop()

    def refresh_connection(self):
        """Ricarica connessione"""
        self.update_status("Ricarico connessione...", COLORS['info'])

        if self.realtime_mode:
            self.live_manager.stop()
            time.sleep(1)
            self.live_manager.start()
        else:
            self.update_status("Avvia prima la modalità live", COLORS['warning'])

    def test_connection(self):
        """Test connessione API"""
        self.update_status("Test connessione API...", COLORS['info'])

        def test():
            try:
                response = requests.get(OPENF1_API_URL, timeout=5)

                if response.status_code == 200:
                    message = f"✅ API OpenF1 raggiungibile!\n"
                    message += f"Status: {response.status_code}\n\n"

                    # Test sessioni
                    sessions_response = requests.get(f"{OPENF1_API_URL}/sessions",
                                                     params={'limit': 3},
                                                     timeout=5)

                    if sessions_response.status_code == 200:
                        sessions = sessions_response.json()
                        message += f"Sessioni disponibili: {len(sessions)}\n"

                        if sessions:
                            message += "\nProssime sessioni:\n"
                            for i, session in enumerate(sessions[:3]):
                                session_time = session.get('date_start', '')
                                if session_time:
                                    try:
                                        dt = datetime.fromisoformat(session_time.replace('Z', '+00:00'))
                                        time_str = dt.strftime("%d/%m %H:%M")
                                    except:
                                        time_str = session_time
                                else:
                                    time_str = "N/A"

                                message += f"{i + 1}. {session.get('session_name')} - {session.get('location')} ({time_str})\n"
                    else:
                        message += f"⚠️ Errore sessioni: {sessions_response.status_code}"
                else:
                    message = f"❌ API non raggiungibile: {response.status_code}"

            except Exception as e:
                message = f"❌ Errore connessione: {e}"

            self.root.after(0, lambda: messagebox.showinfo("Test Connessione", message))
            self.root.after(0, lambda: self.update_status("Test completato", COLORS['success']))

        threading.Thread(target=test, daemon=True).start()

    def update_timer(self):
        """Aggiorna timer"""
        if hasattr(self, 'start_time'):
            elapsed = datetime.now() - self.start_time
            hours = elapsed.seconds // 3600
            minutes = (elapsed.seconds % 3600) // 60
            seconds = elapsed.seconds % 60
            timer_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            self.session_timer.config(text=timer_text)

            # Richiama ogni secondo
            self.root.after(1000, self.update_timer)

    def update_status(self, message, color=COLORS['white']):
        """Aggiorna status bar"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_bar.config(text=f"[{timestamp}] {message}", fg=color)
        print(f"[{timestamp}] {message}")

    def show_session_info(self, info):
        """Mostra informazioni sulla sessione"""
        if info['type'] == 'active':
            start_time = datetime.fromisoformat(info['start'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(info['end'].replace('Z', '+00:00'))

            self.session_info.config(
                text=f"🏁 SESSIONE LIVE: {info['name']} @ {info['circuit']}",
                fg=COLORS['success']
            )

            self.dashboard.session_status.config(
                text=f"✅ SESSIONE LIVE: {info['name']}",
                fg=COLORS['success']
            )

            self.dashboard.session_details.config(
                text=f"📍 {info['circuit']}\n"
                     f"🕐 {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n"
                     f"📊 Dati in tempo reale",
                fg=COLORS['gray_light']
            )

        elif info['type'] == 'upcoming':
            self.session_info.config(
                text=f"⏰ PROSSIMA SESSIONE: {info['name']} tra {info['countdown']}",
                fg=COLORS['warning']
            )

            self.dashboard.session_status.config(
                text=f"⏰ PROSSIMA SESSIONE: {info['name']}",
                fg=COLORS['warning']
            )

            self.dashboard.session_details.config(
                text=f"📍 {info['circuit']}\n"
                     f"⏰ Inizio tra: {info['countdown']}\n"
                     f"📊 Modalità demo attiva",
                fg=COLORS['gray_light']
            )

        elif info['type'] == 'none':
            self.session_info.config(
                text="📭 Nessuna sessione F1 nelle prossime 24h",
                fg=COLORS['gray']
            )

            self.dashboard.session_status.config(
                text="📭 NESSUNA SESSIONE DISPONIBILE",
                fg=COLORS['gray']
            )

            self.dashboard.session_details.config(
                text=info['message'] + "\n📊 Modalità demo attiva",
                fg=COLORS['gray_light']
            )


# ============ MAIN ============
def main():
    root = tk.Tk()

    # Imposta icona (se disponibile)
    try:
        root.iconbitmap('f1_icon.ico')
    except:
        pass

    app = F1RealTimeApp(root)

    def on_closing():
        app.realtime_mode = False
        if hasattr(app, 'live_manager'):
            app.live_manager.stop()
        print("👋 Closing F1 Live Tracker...")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
