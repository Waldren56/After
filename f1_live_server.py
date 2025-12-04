import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import json
import fastf1 as ff1
import pandas as pd
import websockets
import asyncio
from threading import Thread
import queue
import requests
import math

# Import per i grafici
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Configurazione
SERVER_URL_PAST = "http://localhost:5000/f1-data-detailed"
UPDATE_INTERVAL_PAST = 5
UPDATE_INTERVAL_LIVE = 2

WEBSOCKET_URL = "wss://api.openf1.org/v1"
OPENF1_API_URL = "https://api.openf1.org/v1"

# Abilita cache FastF1
ff1.Cache.enable_cache('./f1_cache', ignore_version=False)

# Colori
COLORS = {
    'bg': '#0a0a0a',
    'bg_light': '#111111',
    'bg_dark': '#050505',
    'red': '#e10600',
    'green': '#00cc66',
    'yellow': '#ffcc00',
    'blue': '#0099ff',
    'white': '#ffffff',
    'gray': '#666666',
    'gray_light': '#999999'
}

# Colori team F1
TEAM_COLORS = {
    'Red Bull': '#0600EF',
    'Red Bull Racing': '#0600EF',
    'Ferrari': '#DC0000',
    'Mercedes': '#00D2BE',
    'McLaren': '#FF8700',
    'Aston Martin': '#006F62',
    'Alpine': '#0090FF',
    'Williams': '#005AFF',
    'AlphaTauri': '#2B4562',
    'Racing Bulls': '#2B4562',
    'Alfa Romeo': '#900000',
    'Kick Sauber': '#900000',
    'Haas': '#FFFFFF',
    'Haas F1 Team': '#FFFFFF',
    'Unknown': '#888888'
}

# Colori gomme
TYRE_COLORS = {
    'SOFT': '#FF0000',
    'MEDIUM': '#FFD700',
    'HARD': '#FFFFFF',
    'INTER': '#00FF00',
    'WET': '#0000FF',
    'N/A': '#888888'
}

# Bandiere
FLAGS = {
    'GREEN': '🟢',
    'YELLOW': '🟡',
    'DOUBLE_YELLOW': '🟡🟡',
    'RED': '🔴',
    'CHEQUERED': '🏁',
    'UNKNOWN': '⚫'
}

# Nomi sessioni per display
SESSION_NAMES = {
    'FP1': 'Free Practice 1',
    'FP2': 'Free Practice 2',
    'FP3': 'Free Practice 3',
    'Q': 'Qualifying',
    'SQ': 'Sprint Qualifying',
    'S': 'Sprint Race',
    'R': 'Race'
}


class F1MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🏎️ F1 TRACKER - PASSATO & LIVE")
        self.root.geometry("1400x850")
        self.root.configure(bg=COLORS['bg'])

        # Variabili
        self.current_mode = "past"  # "past" o "live"
        self.current_data = None
        self.running = False
        self.tyre_images = {}
        self.team_colors_cache = {}
        self.track_image = None
        self.current_schedule = []  # Calendario attuale
        self.active_session_info = None  # Sessione attiva per LIVE
        self.fastf1_loaded = False  # Flag per FastF1
        self.live_data_manager = LiveDataManager(self)
        self.websocket_connected = False
        self.real_data_active = False
        self.open_driver_windows = {}  # Dizionario per tenere traccia delle finestre aperte

        # Setup GUI
        self.create_tyre_images()
        self.setup_gui()

        # Carica subito il calendario da FastF1
        threading.Thread(target=self.load_schedule_from_fastf1, daemon=True).start()

    def create_tyre_images(self):
        """Crea immagini per le gomme"""
        for compound, color_hex in TYRE_COLORS.items():
            try:
                if compound == 'N/A':
                    color_rgb = (128, 128, 128)
                else:
                    color_hex = color_hex.lstrip('#')
                    color_rgb = tuple(int(color_hex[i:i + 2], 16) for i in (0, 2, 4))

                size = 24
                img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)

                draw.ellipse([2, 2, size - 2, size - 2], fill=color_rgb, outline='#333333', width=1)
                self.tyre_images[compound] = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Errore creazione immagine gomma {compound}: {e}")
                img = Image.new('RGB', (20, 20), (128, 128, 128))
                self.tyre_images[compound] = ImageTk.PhotoImage(img)

    def get_team_color(self, team_name):
        """Restituisce il colore del team"""
        if team_name in self.team_colors_cache:
            return self.team_colors_cache[team_name]

        if team_name in TEAM_COLORS:
            color = TEAM_COLORS[team_name]
        else:
            for team_key, color in TEAM_COLORS.items():
                if team_key in team_name or team_name in team_key:
                    self.team_colors_cache[team_name] = color
                    return color
            color = TEAM_COLORS['Unknown']

        self.team_colors_cache[team_name] = color
        return color

    def get_tyre_color(self, compound):
        """Restituisce il colore della gomma"""
        return TYRE_COLORS.get(compound.upper(), '#888888')

    def load_schedule_from_fastf1(self):
        """Carica il calendario delle gare usando FastF1"""
        try:
            self.root.after(0, lambda: self.status_bar.config(
                text="📡 Caricamento calendario da FastF1..."
            ))

            # Prova a ottenere il calendario per l'anno corrente
            current_year = datetime.now().year
            print(f"Tentativo di caricare calendario per l'anno {current_year}...")

            try:
                schedule = ff1.get_event_schedule(current_year)
                self.fastf1_loaded = True
                print("Calendario FastF1 caricato con successo")
                print(f"Numero di eventi: {len(schedule)}")

                self.process_fastf1_schedule(schedule)

            except Exception as e:
                print(f"Errore FastF1 primario: {e}")
                # Prova con l'anno precedente
                try:
                    schedule = ff1.get_event_schedule(current_year - 1)
                    self.fastf1_loaded = True
                    print("Calendario FastF1 (anno precedente) caricato con successo")
                    self.process_fastf1_schedule(schedule)
                except Exception as e2:
                    print(f"Errore FastF1 secondario: {e2}")
                    self.create_fallback_schedule()
                    self.fastf1_loaded = False

        except Exception as e:
            print(f"Errore critico caricamento calendario: {e}")
            self.create_fallback_schedule()
            self.fastf1_loaded = False

    def process_fastf1_schedule(self, schedule_df):
        """Processa il dataframe del calendario da FastF1"""
        try:
            self.current_schedule = []

            for _, event in schedule_df.iterrows():
                gp_info = {
                    'gp_name': event['EventName'],
                    'location': event['Location'],
                    'country': event['Country'],
                    'year': event['EventDate'].year,
                    'round': int(event['RoundNumber']),
                    'sessions': []
                }

                # Ottieni le sessioni per questo evento
                try:
                    sessions = ff1.get_event(event['Year'], event['RoundNumber'])

                    # Definisci tutti i tipi di sessione possibili
                    session_types = [
                        ('FP1', 'Free Practice 1'),
                        ('FP2', 'Free Practice 2'),
                        ('FP3', 'Free Practice 3'),
                        ('Q', 'Qualifying'),
                        ('S', 'Sprint'),
                        ('SQ', 'Sprint Qualifying'),
                        ('R', 'Race')
                    ]

                    for session_code, session_name in session_types:
                        try:
                            session_time = getattr(sessions, f'get_{session_code.lower()}', None)
                            if session_time:
                                session_date = session_time()
                                if pd.notna(session_date):
                                    session_info = {
                                        'code': session_code,
                                        'name': session_name,
                                        'time': session_date.to_pydatetime(),
                                        'status': self.get_session_status(session_date.to_pydatetime()),
                                        'countdown': self.get_countdown(session_date.to_pydatetime())
                                    }
                                    gp_info['sessions'].append(session_info)
                        except:
                            continue

                except Exception as e:
                    print(f"Errore caricamento sessioni per {event['EventName']}: {e}")
                    # Sessioni di default
                    event_date = event['EventDate'].to_pydatetime()
                    default_sessions = [
                        {'code': 'FP1', 'name': 'Free Practice 1', 'time': event_date - timedelta(days=2, hours=2)},
                        {'code': 'FP2', 'name': 'Free Practice 2', 'time': event_date - timedelta(days=2)},
                        {'code': 'FP3', 'name': 'Free Practice 3', 'time': event_date - timedelta(days=1, hours=3)},
                        {'code': 'Q', 'name': 'Qualifying', 'time': event_date - timedelta(days=1)},
                        {'code': 'R', 'name': 'Race', 'time': event_date}
                    ]

                    for session in default_sessions:
                        session_info = {
                            'code': session['code'],
                            'name': session['name'],
                            'time': session['time'],
                            'status': self.get_session_status(session['time']),
                            'countdown': self.get_countdown(session['time'])
                        }
                        gp_info['sessions'].append(session_info)

                # Aggiungi prossima sessione
                gp_info['next_session'] = self.get_next_session(gp_info['sessions'])
                self.current_schedule.append(gp_info)

            # Ordina per round
            self.current_schedule.sort(key=lambda x: x['round'])

            print(f"Processati {len(self.current_schedule)} eventi")

            # Aggiorna GUI
            self.root.after(0, lambda: self.status_bar.config(
                text=f"✅ Calendario FastF1 caricato: {len(self.current_schedule)} GP"
            ))
            self.root.after(0, self.update_schedule_display)

        except Exception as e:
            print(f"Errore processamento calendario: {e}")
            self.create_fallback_schedule()

    def create_fallback_schedule(self):
        """Crea un calendario di fallback"""
        now = datetime.now()
        schedule = []

        # Crea alcuni GP di esempio
        sample_gps = [
            {
                'gp_name': 'Australian Grand Prix',
                'location': 'Albert Park Circuit, Melbourne',
                'country': 'Australia',
                'year': 2024,
                'round': 3,
                'sessions': [
                    {'code': 'FP1', 'name': 'Free Practice 1', 'time': now - timedelta(days=30, hours=2)},
                    {'code': 'FP2', 'name': 'Free Practice 2', 'time': now - timedelta(days=30)},
                    {'code': 'FP3', 'name': 'Free Practice 3', 'time': now - timedelta(days=29, hours=23)},
                    {'code': 'Q', 'name': 'Qualifying', 'time': now - timedelta(days=29, hours=20)},
                    {'code': 'R', 'name': 'Race', 'time': now - timedelta(days=29, hours=3)}
                ]
            },
            {
                'gp_name': 'Japanese Grand Prix',
                'location': 'Suzuka Circuit',
                'country': 'Japan',
                'year': 2024,
                'round': 4,
                'sessions': [
                    {'code': 'FP1', 'name': 'Free Practice 1', 'time': now - timedelta(days=7, hours=5)},
                    {'code': 'FP2', 'name': 'Free Practice 2', 'time': now - timedelta(days=7, hours=1)},
                    {'code': 'FP3', 'name': 'Free Practice 3', 'time': now - timedelta(days=6, hours=22)},
                    {'code': 'Q', 'name': 'Qualifying', 'time': now - timedelta(days=6, hours=19)},
                    {'code': 'R', 'name': 'Race', 'time': now - timedelta(days=6, hours=2)}
                ]
            },
            {
                'gp_name': 'Abu Dhabi Grand Prix',
                'location': 'Yas Marina Circuit',
                'country': 'UAE',
                'year': 2024,
                'round': 24,
                'sessions': [
                    {'code': 'FP1', 'name': 'Free Practice 1', 'time': now + timedelta(days=60, hours=10)},
                    {'code': 'FP2', 'name': 'Free Practice 2', 'time': now + timedelta(days=60, hours=14)},
                    {'code': 'FP3', 'name': 'Free Practice 3', 'time': now + timedelta(days=61, hours=10)},
                    {'code': 'Q', 'name': 'Qualifying', 'time': now + timedelta(days=61, hours=14)},
                    {'code': 'R', 'name': 'Race', 'time': now + timedelta(days=62, hours=13)}
                ]
            }
        ]

        for gp in sample_gps:
            sessions_info = []
            for session in gp['sessions']:
                status = self.get_session_status(session['time'])
                sessions_info.append({
                    'code': session['code'],
                    'name': session['name'],
                    'time': session['time'],
                    'status': status,
                    'countdown': self.get_countdown(session['time']) if status == 'upcoming' else None
                })

            gp['sessions'] = sessions_info
            gp['next_session'] = self.get_next_session(sessions_info)
            schedule.append(gp)

        self.current_schedule = schedule
        self.fastf1_loaded = False
        print("Calendario di fallback creato")

        self.root.after(0, lambda: self.status_bar.config(
            text="✅ Calendario di esempio caricato"
        ))
        self.root.after(0, self.update_schedule_display)

    def get_session_status(self, session_time):
        """Determina lo stato della sessione"""
        now = datetime.now()
        time_diff = session_time - now

        if time_diff.total_seconds() > 3600:  # Più di 1 ora nel futuro
            return 'upcoming'
        elif time_diff.total_seconds() > 0:  # Tra 0 e 1 ora
            return 'starting_soon'
        elif abs(time_diff.total_seconds()) < 10800:  # Entro 3 ore dal passato
            return 'in_progress'
        else:
            return 'completed'

    def get_countdown(self, session_time):
        """Calcola il countdown alla sessione"""
        now = datetime.now()
        time_diff = session_time - now

        if time_diff.total_seconds() <= 0:
            return "STARTED"

        days = time_diff.days
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def get_next_session(self, sessions):
        """Trova la prossima sessione"""
        now = datetime.now()
        upcoming_sessions = [s for s in sessions if s['status'] in ['upcoming', 'starting_soon', 'in_progress']]

        if not upcoming_sessions:
            return None

        # Trova la sessione più vicina
        upcoming_sessions.sort(key=lambda x: x['time'])
        return upcoming_sessions[0]

    def setup_gui(self):
        """Setup interfaccia principale"""
        # TOP BAR - Selezione modalità
        top_frame = tk.Frame(self.root, bg=COLORS['bg_dark'], height=50)
        top_frame.pack(fill='x', pady=(0, 5))
        top_frame.pack_propagate(False)

        tk.Label(top_frame, text="🏎️ F1 TRACKER",
                 font=('Arial', 16, 'bold'),
                 bg=COLORS['bg_dark'],
                 fg=COLORS['yellow']).pack(side='left', padx=20)

        mode_frame = tk.Frame(top_frame, bg=COLORS['bg_dark'])
        mode_frame.pack(side='left', padx=50)

        self.past_btn = tk.Button(mode_frame, text="📜 PASSATO",
                                  command=lambda: self.switch_mode("past"),
                                  bg=COLORS['blue'], fg='white',
                                  font=('Arial', 11, 'bold'),
                                  padx=20, pady=5)
        self.past_btn.pack(side='left', padx=5)

        self.live_btn = tk.Button(mode_frame, text="🔴 LIVE",
                                  command=lambda: self.switch_mode("live"),
                                  bg=COLORS['gray'], fg='white',
                                  font=('Arial', 11, 'bold'),
                                  padx=20, pady=5)
        self.live_btn.pack(side='left', padx=5)

        self.control_frame = tk.Frame(self.root, bg=COLORS['bg_light'])
        self.control_frame.pack(fill='x', padx=10, pady=5)

        self.setup_past_section()
        self.setup_live_section()

        self.show_section("past")

        self.status_bar = tk.Label(self.root, text="Pronto - Seleziona una sessione",
                                   bd=1, relief='sunken',
                                   anchor='w', bg=COLORS['bg_dark'], fg=COLORS['white'])
        self.status_bar.pack(side='bottom', fill='x')

    def setup_live_section(self):
        """Setup sezione LIVE"""
        self.live_frame = tk.Frame(self.control_frame, bg=COLORS['bg_light'])

        # Crea row1 per live section
        live_row1 = tk.Frame(self.live_frame, bg=COLORS['bg_light'])
        live_row1.pack(fill='x', pady=5)

        # Informazioni GP attuale
        self.live_gp_info = tk.Label(live_row1, text="📡 Caricamento calendario...",
                                     font=('Arial', 12, 'bold'),
                                     fg=COLORS['white'], bg=COLORS['bg_light'])
        self.live_gp_info.pack(side='left', padx=10, fill='x', expand=True)

        # Pulsanti live
        self.live_start_btn = tk.Button(live_row1, text="🔴 Avvia Live",
                                        command=self.start_live,
                                        bg=COLORS['red'], fg='white',
                                        font=('Arial', 10, 'bold'),
                                        state='disabled')
        self.live_start_btn.pack(side='right', padx=5)

        self.live_stop_btn = tk.Button(live_row1, text="⏹️ Ferma Live",
                                       command=self.stop_live,
                                       bg=COLORS['gray'], fg='white',
                                       font=('Arial', 10, 'bold'), state='disabled')
        self.live_stop_btn.pack(side='right', padx=5)

        # Pulsante refresh
        self.refresh_btn = tk.Button(live_row1, text="🔄 Aggiorna",
                                     command=self.refresh_schedule,
                                     bg=COLORS['yellow'], fg='black',
                                     font=('Arial', 9, 'bold'))
        self.refresh_btn.pack(side='right', padx=5)

        # Pulsante test connessione
        self.test_connection_btn = tk.Button(live_row1, text="🧪 Test OpenF1",
                                             command=self.test_openf1_connection,
                                             bg='#FFD700', fg='black',
                                             font=('Arial', 9, 'bold'))
        self.test_connection_btn.pack(side='right', padx=5)

        self.live_info_frame = tk.Frame(self.live_frame, bg=COLORS['bg_light'])
        self.live_info_frame.pack(fill='x', pady=5)

        self.live_session_label = tk.Label(self.live_info_frame, text="Modalità Live - Pronto",
                                           font=('Arial', 12, 'bold'),
                                           fg=COLORS['red'], bg=COLORS['bg_light'])
        self.live_session_label.pack(side='left', padx=10)

        self.live_time_label = tk.Label(self.live_info_frame, text="",
                                        font=('Arial', 10),
                                        fg=COLORS['gray'], bg=COLORS['bg_light'])
        self.live_time_label.pack(side='right', padx=10)

        self.live_main_container = tk.Frame(self.root, bg=COLORS['bg'])
        self.live_main_container.pack(fill='both', expand=True, padx=10, pady=5)

        self.setup_live_split_view()

    def setup_past_section(self):
        """Setup sezione PASSATO"""
        self.past_frame = tk.Frame(self.control_frame, bg=COLORS['bg_light'])

        row1 = tk.Frame(self.past_frame, bg=COLORS['bg_light'])
        row1.pack(fill='x', pady=5)

        tk.Label(row1, text="Anno:", fg=COLORS['white'], bg=COLORS['bg_light']).pack(side='left', padx=5)
        self.year_var = tk.StringVar(value=str(datetime.now().year))

        # Crea anni dal 2018 ad oggi
        current_year = datetime.now().year
        years = [str(y) for y in range(2018, current_year + 1)]

        year_combo = ttk.Combobox(row1, textvariable=self.year_var,
                                  values=years,
                                  width=6, state='readonly')
        year_combo.pack(side='left', padx=5)

        tk.Label(row1, text="GP:", fg=COLORS['white'], bg=COLORS['bg_light']).pack(side='left', padx=5)
        self.gp_var = tk.StringVar()
        self.gp_combobox = ttk.Combobox(row1, textvariable=self.gp_var, width=20, state='readonly')
        self.gp_combobox.pack(side='left', padx=5)

        tk.Label(row1, text="Sessione:", fg=COLORS['white'], bg=COLORS['bg_light']).pack(side='left', padx=5)
        self.session_var = tk.StringVar(value="R")
        ttk.Combobox(row1, textvariable=self.session_var,
                     values=['FP1', 'FP2', 'FP3', 'Q', 'SQ', 'S', 'R'],
                     width=5, state='readonly').pack(side='left', padx=5)

        self.past_load_btn = tk.Button(row1, text="▶️ Carica Sessione",
                                       command=self.start_past_loading,
                                       bg=COLORS['green'], fg='white',
                                       font=('Arial', 10, 'bold'))
        self.past_load_btn.pack(side='left', padx=20)

        self.past_stop_btn = tk.Button(row1, text="⏹️ Stop",
                                       command=self.stop_loading,
                                       bg=COLORS['red'], fg='white',
                                       font=('Arial', 10, 'bold'), state='disabled')
        self.past_stop_btn.pack(side='left', padx=5)

        # Aggiorna lista GP in base all'anno selezionato
        self.year_var.trace('w', lambda *args: self.update_gp_list())

        self.past_info_frame = tk.Frame(self.past_frame, bg=COLORS['bg_light'])
        self.past_info_frame.pack(fill='x', pady=5)

        self.past_session_label = tk.Label(self.past_info_frame, text="Nessuna sessione caricata",
                                           font=('Arial', 12, 'bold'),
                                           fg=COLORS['white'], bg=COLORS['bg_light'])
        self.past_session_label.pack(side='left', padx=10)

        self.past_time_label = tk.Label(self.past_info_frame, text="",
                                        font=('Arial', 10),
                                        fg=COLORS['gray'], bg=COLORS['bg_light'])
        self.past_time_label.pack(side='right', padx=10)

        self.setup_past_table()

        # Aggiorna la lista GP DOPO che tutto è stato configurato
        self.root.after(100, self.update_gp_list)

    def load_circuit_from_fastf1(self, year, circuit_name):
        """Carica dati reali del circuito da FastF1"""
        try:
            # Trova l'evento
            schedule = ff1.get_event_schedule(year)
            event = None
            for _, ev in schedule.iterrows():
                if circuit_name.lower() in ev['EventName'].lower():
                    event = ev
                    break

            if event:
                # Carica la sessione (usiamo FP1 come riferimento)
                session = ff1.get_session(year, event['RoundNumber'], 'FP1')
                session.load()

                # Ottieni dati del tracciato
                if hasattr(session, 'track') and session.track is not None:
                    # Crea immagine del tracciato
                    canvas_width = self.track_canvas.winfo_width() or 600
                    canvas_height = self.track_canvas.winfo_height() or 400

                    img = Image.new('RGB', (canvas_width, canvas_height), color=(10, 10, 20))
                    draw = ImageDraw.Draw(img)

                    # Normalizza le coordinate del tracciato
                    # (Qui dovresti processare i dati reali di session.track)
                    # Per ora usiamo un placeholder

                    return ImageTk.PhotoImage(img)

        except Exception as e:
            print(f"Errore caricamento circuito FastF1: {e}")

        return None

    def on_year_selected(self):
        """Gestisce la selezione dell'anno"""
        try:
            year = self.year_var.get()
            print(f"Anno selezionato: {year}")
            self.update_gp_list()
        except Exception as e:
            print(f"Errore selezione anno: {e}")

    def update_gp_list(self, *args):
        """Aggiorna la lista dei GP in base all'anno selezionato"""
        try:
            year = int(self.year_var.get())

            # Prova a usare FastF1 per ottenere la lista GP per quell'anno
            gp_names = []

            try:
                # Prima prova con FastF1
                schedule = ff1.get_event_schedule(year)
                gp_names = [event['EventName'] for _, event in schedule.iterrows()]
                print(f"GP trovati via FastF1 per {year}: {len(gp_names)}")
            except Exception as e1:
                print(f"FastF1 non disponibile per {year}: {e1}")
                # Se FastF1 fallisce, usa la lista statica
                gp_lists = {
                    2025: ['Bahrain Grand Prix', 'Saudi Arabian Grand Prix', 'Australian Grand Prix',
                           'Japanese Grand Prix', 'Chinese Grand Prix', 'Miami Grand Prix',
                           'Emilia Romagna Grand Prix', 'Monaco Grand Prix', 'Canadian Grand Prix',
                           'Spanish Grand Prix', 'Austrian Grand Prix', 'British Grand Prix',
                           'Hungarian Grand Prix', 'Belgian Grand Prix', 'Dutch Grand Prix',
                           'Italian Grand Prix', 'Azerbaijan Grand Prix', 'Singapore Grand Prix',
                           'United States Grand Prix', 'Mexico City Grand Prix', 'São Paulo Grand Prix',
                           'Las Vegas Grand Prix', 'Qatar Grand Prix', 'Abu Dhabi Grand Prix'],
                    2024: ['Bahrain Grand Prix', 'Saudi Arabian Grand Prix', 'Australian Grand Prix',
                           'Japanese Grand Prix', 'Chinese Grand Prix', 'Miami Grand Prix',
                           'Emilia Romagna Grand Prix', 'Monaco Grand Prix', 'Canadian Grand Prix',
                           'Spanish Grand Prix', 'Austrian Grand Prix', 'British Grand Prix',
                           'Hungarian Grand Prix', 'Belgian Grand Prix', 'Dutch Grand Prix',
                           'Italian Grand Prix', 'Azerbaijan Grand Prix', 'Singapore Grand Prix',
                           'United States Grand Prix', 'Mexico City Grand Prix', 'São Paulo Grand Prix',
                           'Las Vegas Grand Prix', 'Qatar Grand Prix', 'Abu Dhabi Grand Prix'],
                    2023: ['Bahrain Grand Prix', 'Saudi Arabian Grand Prix', 'Australian Grand Prix',
                           'Azerbaijan Grand Prix', 'Miami Grand Prix', 'Monaco Grand Prix',
                           'Spanish Grand Prix', 'Canadian Grand Prix', 'Austrian Grand Prix',
                           'British Grand Prix', 'Hungarian Grand Prix', 'Belgian Grand Prix',
                           'Dutch Grand Prix', 'Italian Grand Prix', 'Singapore Grand Prix',
                           'Japanese Grand Prix', 'Qatar Grand Prix', 'United States Grand Prix',
                           'Mexico City Grand Prix', 'São Paulo Grand Prix', 'Las Vegas Grand Prix',
                           'Abu Dhabi Grand Prix'],
                    2022: ['Bahrain Grand Prix', 'Saudi Arabian Grand Prix', 'Australian Grand Prix',
                           'Emilia Romagna Grand Prix', 'Miami Grand Prix', 'Spanish Grand Prix',
                           'Monaco Grand Prix', 'Azerbaijan Grand Prix', 'Canadian Grand Prix',
                           'British Grand Prix', 'Austrian Grand Prix', 'French Grand Prix',
                           'Hungarian Grand Prix', 'Belgian Grand Prix', 'Dutch Grand Prix',
                           'Italian Grand Prix', 'Singapore Grand Prix', 'Japanese Grand Prix',
                           'United States Grand Prix', 'Mexico City Grand Prix', 'São Paulo Grand Prix',
                           'Abu Dhabi Grand Prix'],
                    2021: ['Bahrain Grand Prix', 'Emilia Romagna Grand Prix', 'Portuguese Grand Prix',
                           'Spanish Grand Prix', 'Monaco Grand Prix', 'Azerbaijan Grand Prix',
                           'French Grand Prix', 'Styrian Grand Prix', 'Austrian Grand Prix',
                           'British Grand Prix', 'Hungarian Grand Prix', 'Belgian Grand Prix',
                           'Dutch Grand Prix', 'Italian Grand Prix', 'Russian Grand Prix',
                           'Turkish Grand Prix', 'United States Grand Prix', 'Mexico City Grand Prix',
                           'São Paulo Grand Prix', 'Qatar Grand Prix', 'Saudi Arabian Grand Prix',
                           'Abu Dhabi Grand Prix'],
                    2020: ['Austrian Grand Prix', 'Styrian Grand Prix', 'Hungarian Grand Prix',
                           'British Grand Prix', '70th Anniversary Grand Prix', 'Spanish Grand Prix',
                           'Belgian Grand Prix', 'Italian Grand Prix', 'Tuscan Grand Prix',
                           'Russian Grand Prix', 'Eifel Grand Prix', 'Portuguese Grand Prix',
                           'Emilia Romagna Grand Prix', 'Turkish Grand Prix', 'Bahrain Grand Prix',
                           'Sakhir Grand Prix', 'Abu Dhabi Grand Prix'],
                    2019: ['Australian Grand Prix', 'Bahrain Grand Prix', 'Chinese Grand Prix',
                           'Azerbaijan Grand Prix', 'Spanish Grand Prix', 'Monaco Grand Prix',
                           'Canadian Grand Prix', 'French Grand Prix', 'Austrian Grand Prix',
                           'British Grand Prix', 'German Grand Prix', 'Hungarian Grand Prix',
                           'Belgian Grand Prix', 'Italian Grand Prix', 'Singapore Grand Prix',
                           'Russian Grand Prix', 'Japanese Grand Prix', 'Mexican Grand Prix',
                           'United States Grand Prix', 'Brazilian Grand Prix', 'Abu Dhabi Grand Prix'],
                    2018: ['Australian Grand Prix', 'Bahrain Grand Prix', 'Chinese Grand Prix',
                           'Azerbaijan Grand Prix', 'Spanish Grand Prix', 'Monaco Grand Prix',
                           'Canadian Grand Prix', 'French Grand Prix', 'Austrian Grand Prix',
                           'British Grand Prix', 'German Grand Prix', 'Hungarian Grand Prix',
                           'Belgian Grand Prix', 'Italian Grand Prix', 'Singapore Grand Prix',
                           'Russian Grand Prix', 'Japanese Grand Prix', 'United States Grand Prix',
                           'Mexican Grand Prix', 'Brazilian Grand Prix', 'Abu Dhabi Grand Prix']
                }

                if year in gp_lists:
                    gp_names = gp_lists[year]
                    print(f"GP trovati nella lista statica per {year}: {len(gp_names)}")
                else:
                    # Se l'anno non è nella lista, prova con FastF1 per anni più vecchi
                    try:
                        schedule = ff1.get_event_schedule(year)
                        gp_names = [event['EventName'] for _, event in schedule.iterrows()]
                        print(f"GP trovati via FastF1 per {year} (anni più vecchi): {len(gp_names)}")
                    except:
                        gp_names = [f"Grand Prix {year} - {i + 1}" for i in range(10)]
                        print(f"GP generici creati per {year}: {len(gp_names)}")

            # Aggiorna la combobox
            self.gp_combobox['values'] = gp_names

            # Imposta il primo GP come valore predefinito
            if gp_names:
                self.gp_var.set(gp_names[0])
            else:
                self.gp_var.set("")

            # Aggiorna lo stato
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text=f"Anno {year}: {len(gp_names)} GP disponibili")

        except ValueError:
            # Se l'anno non è un numero valido
            self.gp_combobox['values'] = []
            self.gp_var.set("")
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text="Anno non valido")
        except Exception as e:
            print(f"Errore aggiornamento lista GP: {e}")
            self.gp_combobox['values'] = []
            self.gp_var.set("")
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text=f"Errore: {str(e)[:50]}...")

    def setup_past_table(self):
        """Setup tabella per dati passati"""
        table_container = tk.Frame(self.root, bg=COLORS['bg'])
        table_container.pack(fill='both', expand=True, padx=10, pady=5)
        self.past_table_container = table_container

        scrollbar = ttk.Scrollbar(table_container)
        scrollbar.pack(side='right', fill='y')

        columns = ('pos', 'driver', 'team', 'gap', 'best', 'tyre', 'pit', 'status', 'delta')
        self.past_tree = ttk.Treeview(table_container, columns=columns, show='headings',
                                      height=20, yscrollcommand=scrollbar.set)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview",
                        background=COLORS['bg_light'],
                        foreground=COLORS['white'],
                        fieldbackground=COLORS['bg_light'],
                        font=('Arial', 9))
        style.configure("Treeview.Heading",
                        background=COLORS['bg'],
                        foreground=COLORS['white'],
                        font=('Arial', 9, 'bold'))

        col_config = [
            ('Pos', 'pos', 50, 'center'),
            ('Pilota', 'driver', 120, 'w'),
            ('Team', 'team', 120, 'w'),
            ('Gap', 'gap', 80, 'center'),
            ('Miglior', 'best', 90, 'center'),
            ('Gomme', 'tyre', 70, 'center'),
            ('Pit', 'pit', 50, 'center'),
            ('Stato', 'status', 70, 'center'),
            ('Delta', 'delta', 80, 'center')
        ]

        for heading, column, width, anchor in col_config:
            self.past_tree.heading(column, text=heading)
            self.past_tree.column(column, width=width, anchor=anchor)

        self.past_tree.tag_configure('retired', foreground='#ff6666')
        self.past_tree.tag_configure('leader', foreground=COLORS['yellow'])
        self.past_tree.tag_configure('fastest', foreground=COLORS['green'])

        self.past_tree.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.past_tree.yview)

        # Aggiungi doppio click per dettagli e tasto destro per telemetria
        self.past_tree.bind('<Double-1>', self.show_driver_details)
        self.past_tree.bind('<Button-3>', self.show_telemetry_context_menu)

    def show_telemetry_context_menu(self, event):
        """Mostra menu contestuale per aprire telemetria"""
        selection = self.past_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.past_tree.item(item, 'values')
        if not values:
            return

        driver_name = values[1]

        # Cerca i dati del pilota
        driver_data = None
        if self.current_data:
            for driver in self.current_data.get('drivers', []):
                if driver.get('driver_name') == driver_name:
                    driver_data = driver
                    break

        if driver_data:
            # Crea menu contestuale
            menu = tk.Menu(self.root, tearoff=0)

            # PRIMA finestra telemetria
            menu.add_command(label=f"📊 Apri Telemetria {driver_name}",
                             command=lambda d=driver_data: self.show_telemetry_popup(d, "past"))

            # SECONDA finestra telemetria (sempre possibile)
            menu.add_command(label=f"📊 Apri Altra Telemetria {driver_name}",
                             command=lambda d=driver_data: self.show_telemetry_popup(d, "past"))

            menu.add_separator()

            menu.add_command(label=f"👤 Dettagli Pilota",
                             command=lambda d=driver_data: self.show_driver_popup(d, "past"))

            # Mostra menu alla posizione del click
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

    def show_telemetry_popup_single(self, driver_data, window_number):
        """Apre una specifica finestra di telemetria"""
        # Crea ID unico per questa finestra
        window_id = f"{driver_data['driver_name']}_window_{window_number}"

        # Crea nuova finestra
        popup = tk.Toplevel(self.root)
        popup.title(f"📊 Telemetria {window_number} - {driver_data['driver_name']}")
        popup.geometry("1000x700")
        popup.configure(bg=COLORS['bg'])

        # Salva riferimento
        self.open_driver_windows[window_id] = popup

        # ... resto del codice per creare la finestra ...

        print(f"✅ Aperta finestra {window_number} per {driver_data['driver_name']}")

    def open_multiple_telemetry_windows(self, driver_data):
        """Apre 3 finestre di telemetria contemporaneamente"""
        for i in range(1, 4):
            self.root.after(i * 100, lambda idx=i: self.show_telemetry_popup_single(driver_data, idx))

    def test_openf1_connection(self):
        """Test immediato della connessione OpenF1"""
        print("\n" + "=" * 60)
        print("🧪 TEST CONNESSIONE OPENF1 API")
        print("=" * 60)

        try:
            # Test 1: API base
            print("1. Test API base...")
            response = requests.get("https://api.openf1.org/v1", timeout=5)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:100]}...")

            # Test 2: Sessioni
            print("\n2. Test endpoint sessioni...")
            sessions_url = "https://api.openf1.org/v1/sessions"
            response = requests.get(sessions_url, timeout=5)

            if response.status_code == 200:
                sessions = response.json()
                print(f"   Trovate {len(sessions)} sessioni")

                if sessions:
                    print("\n   Ultime 3 sessioni:")
                    for i, session in enumerate(sessions[:3]):
                        print(f"   {i + 1}. {session.get('session_name', 'Unknown')} "
                              f"a {session.get('location', 'Unknown')} "
                              f"(key: {session.get('session_key')})")

            # Test 3: Driver
            print("\n3. Test endpoint piloti...")
            drivers_url = "https://api.openf1.org/v1/drivers"
            response = requests.get(drivers_url, params={'limit': 5}, timeout=5)

            if response.status_code == 200:
                drivers = response.json()
                print(f"   Trovati {len(drivers)} piloti")

                for driver in drivers[:3]:
                    print(f"   - {driver.get('full_name', 'Unknown')} "
                          f"(#{driver.get('driver_number')})")

            print("\n✅ Test completato!")

        except Exception as e:
            print(f"\n❌ Errore test: {e}")

        print("=" * 60)

    def setup_live_split_view(self):
        """Setup vista divisa per live: mappa a sinistra, calendario a destra"""
        # Frame sinistro per mappa (50%)
        left_frame = tk.Frame(self.live_main_container, bg=COLORS['bg_dark'])
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

        tk.Label(left_frame, text="🏁 MAPPA PISTA LIVE",
                 font=('Arial', 14, 'bold'),
                 bg=COLORS['bg_dark'],
                 fg=COLORS['white']).pack(pady=10)

        self.track_canvas = tk.Canvas(left_frame, bg=COLORS['bg_dark'],
                                      highlightthickness=0, relief='flat')
        self.track_canvas.pack(fill='both', expand=True, padx=10, pady=10)

        self.track_label = tk.Label(left_frame, text="Circuito: --",
                                    font=('Arial', 11),
                                    bg=COLORS['bg_dark'],
                                    fg=COLORS['gray_light'])
        self.track_label.pack(pady=5)

        # Frame destro per calendario (50%)
        right_frame = tk.Frame(self.live_main_container, bg=COLORS['bg'])
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

        # Calendario sessioni
        self.setup_schedule_panel(right_frame)

        # Info aggiuntive live
        self.setup_live_info_panel(right_frame)

    def setup_schedule_panel(self, parent):
        """Setup pannello calendario sessioni"""
        tk.Label(parent, text="📅 CALENDARIO SESSIONI LIVE",
                 font=('Arial', 14, 'bold'),
                 bg=COLORS['bg'],
                 fg=COLORS['white']).pack(pady=(0, 10))

        # Container per calendario con scroll
        schedule_container = tk.Frame(parent, bg=COLORS['bg'])
        schedule_container.pack(fill='both', expand=True, pady=5)

        scrollbar = ttk.Scrollbar(schedule_container)
        scrollbar.pack(side='right', fill='y')

        # Canvas per calendario
        self.schedule_canvas = tk.Canvas(schedule_container, bg=COLORS['bg'],
                                         highlightthickness=0,
                                         yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.schedule_canvas.yview)

        self.schedule_canvas.pack(side='left', fill='both', expand=True)

        # Frame interno per contenuto
        self.schedule_content = tk.Frame(self.schedule_canvas, bg=COLORS['bg'])
        self.schedule_canvas.create_window((0, 0), window=self.schedule_content, anchor='nw')

        # Messaggio di caricamento iniziale
        self.schedule_loading_label = tk.Label(self.schedule_content,
                                               text="Caricamento calendario da FastF1...",
                                               font=('Arial', 11),
                                               bg=COLORS['bg'],
                                               fg=COLORS['gray'])
        self.schedule_loading_label.pack(pady=20)

    def update_schedule_display(self):
        """Aggiorna la visualizzazione del calendario"""
        # Rimuovi messaggio di caricamento
        if hasattr(self, 'schedule_loading_label') and self.schedule_loading_label.winfo_exists():
            self.schedule_loading_label.destroy()

        # Pulisci contenuto precedente
        for widget in self.schedule_content.winfo_children():
            widget.destroy()

        if not self.current_schedule or len(self.current_schedule) == 0:
            tk.Label(self.schedule_content, text="Nessuna gara programmata",
                     font=('Arial', 11),
                     bg=COLORS['bg'],
                     fg=COLORS['gray']).pack(pady=20)
            self.live_start_btn.config(state='disabled')
            return

        # Reset della sessione attiva
        self.active_session_info = None

        # Mostra ogni GP
        for gp_info in self.current_schedule:
            gp_frame = tk.Frame(self.schedule_content, bg=COLORS['bg_light'], relief='ridge', bd=1)
            gp_frame.pack(fill='x', pady=10, padx=5)

            # Intestazione GP
            header_frame = tk.Frame(gp_frame, bg=COLORS['bg'])
            header_frame.pack(fill='x', padx=10, pady=10)

            # Nome GP e round
            round_num = gp_info.get('round', '?')
            gp_title = f"Round {round_num}: {gp_info['gp_name']}"
            tk.Label(header_frame, text=gp_title,
                     font=('Arial', 12, 'bold'),
                     bg=COLORS['bg'],
                     fg=COLORS['yellow']).pack(side='left')

            # Anno
            tk.Label(header_frame, text=f"Season {gp_info.get('year', '?')}",
                     font=('Arial', 10),
                     bg=COLORS['bg'],
                     fg=COLORS['gray']).pack(side='right')

            # Location e paese
            location_text = f"{gp_info['location']}"
            if gp_info.get('country'):
                location_text += f", {gp_info['country']}"

            tk.Label(gp_frame, text=location_text,
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray_light']).pack(anchor='w', padx=10, pady=(0, 10))

            # Sessioni
            for session in gp_info['sessions']:
                session_frame = tk.Frame(gp_frame, bg=COLORS['bg_light'])
                session_frame.pack(fill='x', padx=15, pady=5)

                # Nome sessione
                tk.Label(session_frame, text=session['name'],
                         font=('Arial', 10, 'bold'),
                         bg=COLORS['bg_light'],
                         fg=self.get_session_color(session['status']),
                         width=20,
                         anchor='w').pack(side='left')

                # Orario
                time_str = session['time'].strftime('%d/%m %H:%M')

                # Stato/Countdown
                if session['status'] == 'upcoming' and session['countdown']:
                    tk.Label(session_frame, text=f"{time_str} - ⏰ {session['countdown']}",
                             font=('Arial', 10),
                             bg=COLORS['bg_light'],
                             fg=COLORS['blue'],
                             width=25).pack(side='left', padx=10)
                    tk.Label(session_frame, text="Prossimamente",
                             font=('Arial', 9, 'bold'),
                             bg=COLORS['bg_light'],
                             fg=COLORS['blue']).pack(side='right')
                elif session['status'] == 'starting_soon':
                    tk.Label(session_frame, text=f"{time_str} - A BREVE",
                             font=('Arial', 10),
                             bg=COLORS['bg_light'],
                             fg=COLORS['white'],
                             width=25).pack(side='left', padx=10)
                    tk.Label(session_frame, text="🚦 STARTING SOON",
                             font=('Arial', 9, 'bold'),
                             bg=COLORS['bg_light'],
                             fg=COLORS['green']).pack(side='right')
                elif session['status'] == 'in_progress':
                    tk.Label(session_frame, text=f"{time_str} - IN CORSO",
                             font=('Arial', 10),
                             bg=COLORS['bg_light'],
                             fg=COLORS['white'],
                             width=25).pack(side='left', padx=10)
                    tk.Label(session_frame, text="🔴 LIVE NOW",
                             font=('Arial', 9, 'bold'),
                             bg=COLORS['bg_light'],
                             fg=COLORS['red']).pack(side='right')
                    # Salva info sessione attiva
                    self.active_session_info = {
                        'gp': gp_info,
                        'session': session
                    }
                    print(f"Sessione attiva trovata: {gp_info['gp_name']} - {session['name']}")
                elif session['status'] == 'completed':
                    tk.Label(session_frame, text=f"{time_str} - TERMINATA",
                             font=('Arial', 10),
                             bg=COLORS['bg_light'],
                             fg=COLORS['gray'],
                             width=25).pack(side='left', padx=10)
                    tk.Label(session_frame, text="✅ COMPLETED",
                             font=('Arial', 9),
                             bg=COLORS['bg_light'],
                             fg=COLORS['gray']).pack(side='right')

            # Separatore
            tk.Frame(gp_frame, height=1, bg=COLORS['gray']).pack(fill='x', pady=5)

        # Aggiorna dimensione canvas
        self.schedule_content.update_idletasks()
        self.schedule_canvas.config(scrollregion=self.schedule_canvas.bbox('all'))

        # Aggiorna info GP attuale
        self.update_current_gp_info()

    def get_session_color(self, status):
        """Restituisce il colore in base allo stato della sessione"""
        colors = {
            'upcoming': COLORS['white'],
            'starting_soon': COLORS['yellow'],
            'in_progress': COLORS['red'],
            'completed': COLORS['gray']
        }
        return colors.get(status, COLORS['white'])

    def setup_live_info_panel(self, parent):
        """Setup pannello info aggiuntive live"""
        info_frame = tk.LabelFrame(parent, text=" 📡 INFO LIVE ",
                                   font=('Arial', 11, 'bold'),
                                   bg=COLORS['bg_light'],
                                   fg=COLORS['white'],
                                   padx=10,
                                   pady=10)
        info_frame.pack(fill='x', pady=10)

        # Bandiera
        flag_frame = tk.Frame(info_frame, bg=COLORS['bg_light'])
        flag_frame.pack(fill='x', pady=3)

        tk.Label(flag_frame, text="Bandiera:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left')

        self.flag_label = tk.Label(flag_frame, text="--",
                                   font=('Arial', 10, 'bold'),
                                   bg=COLORS['bg_light'],
                                   fg=COLORS['green'])
        self.flag_label.pack(side='left', padx=10)

        # Giro attuale
        lap_frame = tk.Frame(info_frame, bg=COLORS['bg_light'])
        lap_frame.pack(fill='x', pady=3)

        tk.Label(lap_frame, text="Giro:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left')

        self.lap_label = tk.Label(lap_frame, text="--/--",
                                  font=('Arial', 10, 'bold'),
                                  bg=COLORS['bg_light'],
                                  fg=COLORS['blue'])
        self.lap_label.pack(side='left', padx=10)

        # SC/VSC
        sc_frame = tk.Frame(info_frame, bg=COLORS['bg_light'])
        sc_frame.pack(fill='x', pady=3)

        tk.Label(sc_frame, text="Sicurezza:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left')

        self.sc_label = tk.Label(sc_frame, text="No",
                                 font=('Arial', 10, 'bold'),
                                 bg=COLORS['bg_light'],
                                 fg=COLORS['white'])
        self.sc_label.pack(side='left', padx=10)

        # Meteo
        weather_frame = tk.Frame(info_frame, bg=COLORS['bg_light'])
        weather_frame.pack(fill='x', pady=3)

        tk.Label(weather_frame, text="Meteo:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left')

        self.weather_label = tk.Label(weather_frame, text="Sereno",
                                      font=('Arial', 10, 'bold'),
                                      bg=COLORS['bg_light'],
                                      fg=COLORS['white'])
        self.weather_label.pack(side='left', padx=10)

        # Tempo trascorso
        time_frame = tk.Frame(info_frame, bg=COLORS['bg_light'])
        time_frame.pack(fill='x', pady=3)

        tk.Label(time_frame, text="Tempo:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left')

        self.elapsed_time_label = tk.Label(time_frame, text="00:00:00",
                                           font=('Arial', 10, 'bold'),
                                           bg=COLORS['bg_light'],
                                           fg=COLORS['yellow'])
        self.elapsed_time_label.pack(side='left', padx=10)

    def switch_mode(self, mode):
        """Cambia modalità tra PASSATO e LIVE"""
        if self.running:
            if mode == "past" and self.current_mode == "live":
                self.stop_live()
            elif mode == "live" and self.current_mode == "past":
                self.stop_loading()

        self.current_mode = mode

        if mode == "past":
            self.past_btn.config(bg=COLORS['blue'])
            self.live_btn.config(bg=COLORS['gray'])
            self.show_section("past")
            self.status_bar.config(text="Modalità PASSATO - Carica una sessione storica")
        else:
            self.past_btn.config(bg=COLORS['gray'])
            self.live_btn.config(bg=COLORS['red'])
            self.show_section("live")
            self.status_bar.config(text="Modalità LIVE - Visualizzazione calendario")

            # Aggiorna informazioni GP attuale
            self.update_current_gp_info()

    def update_current_gp_info(self):
        """Aggiorna le informazioni del GP attuale"""
        if not self.current_schedule or len(self.current_schedule) == 0:
            self.live_gp_info.config(text="Nessuna gara programmata")
            self.live_start_btn.config(state='disabled')
            return

        # Cerca prossima sessione
        next_session_info = None
        next_session_gp = None
        min_time_diff = float('inf')

        for gp in self.current_schedule:
            for session in gp['sessions']:
                if session['status'] in ['upcoming', 'starting_soon', 'in_progress']:
                    time_diff = (session['time'] - datetime.now()).total_seconds()
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        next_session_info = session
                        next_session_gp = gp

        if next_session_info:
            # Calcola countdown
            now = datetime.now()
            time_diff = next_session_info['time'] - now

            if time_diff.total_seconds() <= 0:
                countdown_str = "ORA!"
                status_text = "🔴 LIVE"
            else:
                days = time_diff.days
                hours = time_diff.seconds // 3600
                minutes = (time_diff.seconds % 3600) // 60

                if days > 0:
                    countdown_str = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    countdown_str = f"{hours}h {minutes}m"
                else:
                    countdown_str = f"{minutes}m"
                status_text = "⏰"

            # Mostra informazioni
            session_status = next_session_info['status']
            if session_status == 'in_progress':
                self.live_gp_info.config(
                    text=f"🔴 LIVE: {next_session_gp['gp_name']} - {next_session_info['name']}")
                self.live_session_label.config(text=f"LIVE: {next_session_info['name']}")
            else:
                self.live_gp_info.config(
                    text=f"{status_text} {next_session_gp['gp_name']} - {next_session_info['name']} tra {countdown_str}")
                self.live_session_label.config(text=f"Prossimo: {next_session_info['name']}")

            self.live_start_btn.config(state='normal')
            # Salva info sessione attiva
            self.active_session_info = {
                'gp': next_session_gp,
                'session': next_session_info
            }
            print(f"Sessione attiva impostata: {next_session_gp['gp_name']} - {next_session_info['name']}")
        else:
            # Nessuna sessione trovata
            self.live_gp_info.config(text="Nessuna sessione programmata")
            self.live_start_btn.config(state='disabled')
            self.live_session_label.config(text="Modalità Live - Pronto")

    def show_section(self, section):
        """Mostra/nascondi sezioni"""
        self.past_frame.pack_forget()
        self.past_table_container.pack_forget()
        self.live_frame.pack_forget()
        self.live_main_container.pack_forget()

        if section == "past":
            self.past_frame.pack(fill='x', padx=10, pady=5)
            self.past_table_container.pack(fill='both', expand=True, padx=10, pady=5)
        else:
            self.live_frame.pack(fill='x', padx=10, pady=5)
            self.live_main_container.pack(fill='both', expand=True, padx=10, pady=5)

            if self.current_schedule:
                self.update_schedule_display()

    def start_live(self):
        """Avvia modalità LIVE con dati REALI"""
        print("\n" + "=" * 60)
        print("🚀 AVVIO MODALITÀ LIVE REALI")
        print("=" * 60)

        # Cerca sessione attiva in tempo reale
        live_session = self.live_data_manager.get_live_session_info()

        if live_session:
            print(f"✅ SESSIONE LIVE TROVATA:")
            print(f"   GP: {live_session['gp_name']}")
            print(f"   Sessione: {live_session['session_name']}")
            print(f"   Session Key: {live_session['session_key']}")
            print(f"   Stato: {live_session['status']}")

            # Imposta la sessione attiva
            self.active_session_info = {
                'gp': {
                    'gp_name': live_session['gp_name'],
                    'location': live_session['gp_name'],
                    'circuit_key': live_session.get('circuit_key')
                },
                'session': {
                    'name': live_session['session_name'],
                    'code': 'R' if 'race' in live_session['session_name'].lower() else 'Q',
                    'session_key': live_session['session_key']
                },
                'is_real': True
            }

            session_key = live_session['session_key']

        else:
            print("⚠️ Nessuna sessione live trovata")
            messagebox.showinfo("Nessuna sessione live",
                                "Non ci sono sessioni F1 attive in questo momento.\n"
                                "Le sessioni reali sono disponibili durante i weekend di gara.")
            return False

        # Carica mappa circuito
        gp_name = live_session['gp_name']
        print(f"\n🗺️ Caricamento mappa per: {gp_name}")
        self.load_track_map(gp_name)

        # Avvia connessione WebSocket REALI
        self.real_data_active = True
        self.running = True
        self.live_start_btn.config(state='disabled')
        self.live_stop_btn.config(state='normal')

        print(f"\n🔗 Connessione WebSocket a OpenF1...")

        # Avvia thread per dati reali
        real_data_thread = threading.Thread(
            target=self._start_real_data_connection,
            args=(session_key, live_session),
            daemon=True
        )
        real_data_thread.start()

        # Aggiorna GUI
        self.live_session_label.config(
            text=f"🔴 LIVE: {live_session['session_name']}",
            fg=COLORS['red']
        )
        self.status_bar.config(
            text=f"📡 Connessione a {gp_name}...",
            fg=COLORS['yellow']
        )

        # Timer per timeout
        self.root.after(10000, self._check_connection_timeout)

        return True

    def _start_real_data_connection(self, session_key, live_session):
        """Avvia connessione a dati reali in thread separato"""
        try:
            print(f"🌐 Connessione con session_key: {session_key}")

            # Carica dati iniziali
            self._load_initial_driver_data(session_key)

            # Avvia WebSocket
            self.live_data_manager.start_live_data(session_key)

            # Aggiorna status
            self.root.after(0, lambda: self.status_bar.config(
                text=f"✅ CONNESSO LIVE: {live_session['gp_name']}",
                fg=COLORS['green']
            ))

        except Exception as e:
            print(f"❌ Errore connessione dati reali: {e}")
            self.root.after(0, lambda: messagebox.showerror(
                "Errore connessione",
                f"Impossibile connettersi ai dati in tempo reale:\n{str(e)}"
            ))

    def _load_initial_driver_data(self, session_key):
        """Carica dati iniziali piloti dalla REST API"""
        try:
            print(f"👥 Caricamento piloti per sessione {session_key}...")

            # Ottieni piloti della sessione
            drivers_url = "https://api.openf1.org/v1/drivers"
            params = {'session_key': session_key}

            response = requests.get(drivers_url, params=params, timeout=10)

            if response.status_code == 200:
                drivers = response.json()
                print(f"✅ Caricati {len(drivers)} piloti")

                # Processa dati piloti
                for driver in drivers:
                    driver_number = driver.get('driver_number')
                    name = driver.get('full_name', 'Unknown')
                    team = driver.get('team_name', 'Unknown')

                    if driver_number:
                        print(f"   #{driver_number}: {name} - {team}")

            else:
                print(f"❌ Errore API piloti: {response.status_code}")

        except Exception as e:
            print(f"❌ Errore caricamento piloti: {e}")

    def _check_connection_timeout(self):
        """Controlla timeout connessione"""
        if not self.live_data_manager.websocket_connected:
            print("⏱️ Timeout connessione WebSocket")
            self.status_bar.config(
                text="⚠️ Timeout connessione",
                fg=COLORS['yellow']
            )

    def load_track_map(self, gp):
        """Carica o genera mappa del circuito - VERSIONE ROBUSTA"""
        try:
            print(f"\n" + "=" * 60)
            print(f"🗺️ CARICAMENTO MAPPA per: {gp}")
            print("=" * 60)

            # Pulisci canvas
            if hasattr(self, 'track_canvas'):
                self.track_canvas.delete("all")

            # Genera mappa
            print(f"🎨 Generazione mappa schematica...")
            self.track_image = self.create_circuit_map(gp)

            if self.track_image:
                if hasattr(self, 'track_canvas'):
                    self.track_canvas.create_image(0, 0, anchor='nw', image=self.track_image)
                    self.track_label.config(text=f"Circuito: {gp}")
                    print(f"✅ Mappa generata e visualizzata")

                    # Assicurati track_points esistano
                    if not hasattr(self, 'track_points') or not self.track_points:
                        print("⚠️ Generando punti tracciato di default...")
                        # Crea punti circolari di default
                        center_x = self.track_canvas.winfo_width() // 2 or 300
                        center_y = self.track_canvas.winfo_height() // 2 or 200
                        radius = min(center_x, center_y) * 0.6

                        self.track_points = []
                        for angle in range(0, 360, 36):  # 10 punti
                            rad = angle * 3.14159 / 180
                            x = center_x + radius * math.cos(rad)
                            y = center_y + radius * math.sin(rad)
                            self.track_points.append((int(x), int(y)))

                        print(f"✅ Generati {len(self.track_points)} punti tracciato")
                else:
                    print("⚠️ Canvas non disponibile")
            else:
                print("❌ Errore generazione immagine")
                self.track_label.config(text=f"Circuito: {gp} (errore generazione)")

        except Exception as e:
            print(f"❌ Errore caricamento mappa: {e}")
            import traceback
            traceback.print_exc()
            self.track_label.config(text=f"Circuito: {gp} (errore)")

    def create_circuit_map(self, circuit_name):
        """Crea una mappa schematica del circuito - VERSIONE CORRETTA"""
        canvas_width = self.track_canvas.winfo_width() or 600
        canvas_height = self.track_canvas.winfo_height() or 400

        if canvas_width < 100 or canvas_height < 100:
            canvas_width, canvas_height = 600, 400

        img = Image.new('RGB', (canvas_width, canvas_height), color=(15, 15, 25))
        draw = ImageDraw.Draw(img)

        # Mappe per circuiti famosi - VERSIONE MIGLIORATA
        circuit_name_lower = circuit_name.lower()

        print(f"🔍 Creazione mappa per: {circuit_name}")
        print(f"🔍 Nome lowercase: {circuit_name_lower}")

        # Yas Marina Circuit (Abu Dhabi) - FORMA MIGLIORATA
        if 'abu dhabi' in circuit_name_lower or 'yas marina' in circuit_name_lower or 'abu' in circuit_name_lower:
            print("✅ Riconosciuto: Yas Marina Circuit")

            # Punti caratteristici Yas Marina
            points = [
                # Start/Finish straight
                (canvas_width // 4, 3 * canvas_height // 4),
                (canvas_width // 2, 3 * canvas_height // 4),
                (3 * canvas_width // 4, 3 * canvas_height // 4),
                # Curva 1-2
                (4 * canvas_width // 5, 2 * canvas_height // 3),
                # Hotel section (curve stretta)
                (4 * canvas_width // 5, canvas_height // 3),
                # Back straight
                (3 * canvas_width // 4, canvas_height // 4),
                (canvas_width // 2, canvas_height // 4),
                # Chicane
                (canvas_width // 4, canvas_height // 3),
                # Curva finale
                (canvas_width // 8, canvas_height // 2),
                # Ritorno a start
                (canvas_width // 4, 3 * canvas_height // 4)
            ]

            circuit_type = "Yas Marina Circuit"
            color = (255, 200, 50)  # Oro deserto

            # Disegna hotel caratteristico
            hotel_x = 4 * canvas_width // 5 - 50
            hotel_y = canvas_height // 3 - 50
            draw.rectangle([hotel_x, hotel_y, hotel_x + 100, hotel_y + 100],
                           fill=(255, 150, 50), outline=(255, 200, 100), width=3)

            # Testo "Hotel"
            from PIL import ImageFont
            try:
                font = ImageFont.truetype("arial.ttf", 12)
                draw.text((hotel_x + 10, hotel_y + 40), "HOTEL", fill=(255, 255, 200), font=font)
            except:
                pass

        # Bahrain International Circuit
        elif 'bahrain' in circuit_name_lower:
            print("✅ Riconosciuto: Bahrain International Circuit")
            points = [
                (canvas_width // 4, canvas_height // 2),
                (canvas_width // 2, canvas_height // 4),
                (3 * canvas_width // 4, canvas_height // 3),
                (3 * canvas_width // 4, 2 * canvas_height // 3),
                (canvas_width // 2, 3 * canvas_height // 4),
                (canvas_width // 4, 3 * canvas_height // 4),
                (canvas_width // 8, 2 * canvas_height // 3),
                (canvas_width // 8, canvas_height // 3),
                (canvas_width // 4, canvas_height // 2)
            ]
            circuit_type = "Bahrain International Circuit"
            color = (100, 200, 255)  # Blu deserto

        # Albert Park (Australia)
        elif 'australia' in circuit_name_lower or 'albert' in circuit_name_lower:
            print("✅ Riconosciuto: Albert Park Circuit")
            points = [
                (canvas_width // 4, canvas_height // 2),
                (canvas_width // 2, canvas_height // 4),
                (3 * canvas_width // 4, canvas_height // 3),
                (3 * canvas_width // 4, 2 * canvas_height // 3),
                (canvas_width // 2, 3 * canvas_height // 4),
                (canvas_width // 4, 3 * canvas_height // 4),
                (canvas_width // 8, canvas_height // 2),
                (canvas_width // 4, canvas_height // 2)
            ]
            circuit_type = "Albert Park Circuit"
            color = (50, 200, 100)  # Verde parco

        # Suzuka (Giappone)
        elif 'japan' in circuit_name_lower or 'suzuka' in circuit_name_lower:
            print("✅ Riconosciuto: Suzuka Circuit")
            points = [
                (canvas_width // 2, canvas_height // 4),
                (3 * canvas_width // 4, canvas_height // 3),
                (3 * canvas_width // 4, 2 * canvas_height // 3),
                (canvas_width // 2, 3 * canvas_height // 4),
                (canvas_width // 4, 2 * canvas_height // 3),
                (canvas_width // 4, canvas_height // 3),
                (canvas_width // 2, canvas_height // 4)
            ]
            circuit_type = "Suzuka Circuit"
            color = (255, 100, 100)  # Rosso giapponese

        # Monaco
        elif 'monaco' in circuit_name_lower:
            print("✅ Riconosciuto: Circuit de Monaco")
            points = [
                (canvas_width // 4, canvas_height // 2),
                (canvas_width // 3, canvas_height // 4),
                (canvas_width // 2, canvas_height // 3),
                (2 * canvas_width // 3, canvas_height // 4),
                (3 * canvas_width // 4, canvas_height // 3),
                (4 * canvas_width // 5, 2 * canvas_height // 3),
                (2 * canvas_width // 3, 3 * canvas_height // 4),
                (canvas_width // 2, 2 * canvas_height // 3),
                (canvas_width // 3, 3 * canvas_height // 4),
                (canvas_width // 4, canvas_height // 2)
            ]
            circuit_type = "Circuit de Monaco"
            color = (100, 150, 255)  # Blu mediterraneo

        # Circuito generico
        else:
            print(f"⚠️ Circuito non riconosciuto: {circuit_name}")
            margin = 40
            points = [
                (margin, margin),
                (canvas_width - margin, margin),
                (canvas_width - margin, canvas_height - margin),
                (margin, canvas_height - margin),
                (margin, margin)
            ]
            circuit_type = f"Circuito: {circuit_name}"
            color = (150, 150, 255)  # Blu generico

        # Disegna il tracciato
        if len(points) > 1:
            for i in range(len(points) - 1):
                draw.line([points[i], points[i + 1]], fill=color, width=4)
            # Linea di start/finish più spessa e di colore diverso
            draw.line([points[0], points[1]], fill=(255, 255, 0), width=6)

            # Salva punti per visualizzazione auto
            self.track_points = points

        # Aggiungi punti di controllo (curve)
        for i, point in enumerate(points):
            if i == 0:  # Start/Finish
                draw.ellipse([point[0] - 10, point[1] - 10, point[0] + 10, point[1] + 10],
                             fill=(255, 50, 50), outline='white', width=2)
                # Testo "S/F"
                draw.text((point[0] - 8, point[1] - 5), "S/F", fill='white')
            else:  # Altre curve
                draw.ellipse([point[0] - 6, point[1] - 6, point[0] + 6, point[1] + 6],
                             fill=(50, 255, 50), outline='white', width=1)

        # Aggiungi griglia di partenza (solo su Start/Finish)
        if len(points) > 0:
            start_x, start_y = points[0]
            for i in range(10):
                offset = i * 8 - 36
                draw.line([start_x + offset, start_y - 25, start_x + offset, start_y + 25],
                          fill=(220, 220, 220), width=2)

        # Aggiungi testo circuito
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()

        # Nome circuito in alto
        draw.text((10, 10), circuit_type, fill=(255, 255, 255), font=font)

        # Aggiungi indicatori specifici per Yas Marina
        if 'abu dhabi' in circuit_name_lower or 'yas marina' in circuit_name_lower:
            # Punto hotel
            hotel_point = points[4]  # Il punto hotel
            draw.text((hotel_point[0] - 20, hotel_point[1] + 20), "🏨", fill=(255, 200, 100))

            # Marina
            marina_x = canvas_width // 8 + 50
            marina_y = canvas_height // 2 + 50
            draw.rectangle([marina_x - 60, marina_y - 20, marina_x + 60, marina_y + 20],
                           fill=(30, 60, 120), outline=(100, 150, 200))
            draw.text((marina_x - 25, marina_y - 10), "MARINA", fill=(200, 200, 255))

        return ImageTk.PhotoImage(img)

    def start_past_loading(self):
        """Avvia caricamento dati passati"""
        year = self.year_var.get()
        gp = self.gp_var.get()
        session = self.session_var.get()

        if not all([year, gp, session]):
            messagebox.showwarning("Attenzione", "Completa tutti i campi: Anno, GP e Sessione")
            return

        # Mostra cosa sta cercando
        print(f"Caricamento: Anno={year}, GP={gp}, Sessione={session}")

        # Estrai solo il nome principale del GP
        gp_short = gp
        if 'Grand Prix' in gp:
            gp_short = gp.replace('Grand Prix', '').strip()

        self.running = True
        self.past_load_btn.config(state='disabled', text='⏳ Caricamento...')
        self.past_stop_btn.config(state='normal')
        self.status_bar.config(text=f"Caricamento {year} {gp_short} {session}...")

        # Pulisci la tabella
        for item in self.past_tree.get_children():
            self.past_tree.delete(item)

        # Aggiorna etichetta sessione
        self.past_session_label.config(text=f"{year} - {gp} - {session}")

        threading.Thread(target=self.past_update_loop,
                         args=(year, gp_short, session),
                         daemon=True).start()

    def past_update_loop(self, year, gp, session):
        """Loop aggiornamento dati passati"""
        url = f"{SERVER_URL_PAST}?year={year}&gp={gp}&session={session}"

        while self.running and self.current_mode == "past":
            try:
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    if data.get('status') == 'success':
                        self.current_data = data
                        self.root.after(0, self.update_past_display, data)
                    else:
                        self.root.after(0, self.show_error, data.get('error', 'Errore'))
                else:
                    self.root.after(0, self.show_error, f"HTTP {response.status_code}")

                time.sleep(UPDATE_INTERVAL_PAST)

            except Exception as e:
                self.root.after(0, self.show_error, str(e))
                time.sleep(UPDATE_INTERVAL_PAST)

    def update_past_display(self, data):
        """Aggiorna display dati passati"""
        session_info = data.get('session_info', 'Sessione')
        self.past_session_label.config(text=session_info)

        current_time = datetime.now().strftime("%H:%M:%S")
        self.past_time_label.config(text=f"Aggiornato: {current_time}")

        self.update_past_table(data.get('drivers', []))

        total = len(data.get('drivers', []))
        self.status_bar.config(text=f"✅ {total} piloti | Aggiornato: {current_time}")

    def update_past_table(self, drivers):
        """Aggiorna tabella dati passati"""
        for item in self.past_tree.get_children():
            self.past_tree.delete(item)

        best_times = []
        for driver in drivers:
            best_lap = driver.get('best_lap_time')
            if best_lap and best_lap != 'N/A':
                try:
                    parts = best_lap.split(':')
                    if len(parts) == 2:
                        mins, rest = parts
                        secs, ms = rest.split('.')
                        total_sec = int(mins) * 60 + int(secs) + float(f"0.{ms}")
                        best_times.append((driver['driver_name'], total_sec))
                except:
                    pass

        fastest_driver = None
        if best_times:
            fastest_driver = min(best_times, key=lambda x: x[1])[0]

        for driver in sorted(drivers, key=lambda x: x.get('position', 99)):
            pos = driver.get('position', '')
            name = driver.get('driver_name', 'N/A')
            team = driver.get('team', 'N/A')
            gap = driver.get('gap_to_leader', 'N/A')
            best = driver.get('best_lap_time', 'N/A')
            compound = driver.get('compound', 'N/A')
            pit = driver.get('pit_stops', 0)
            status = driver.get('status', 'RUNNING')
            delta = driver.get('delta_to_best', 'N/A')

            tags = []
            if gap == 'Leader' or gap == '0' or gap == '+0.000':
                tags.append('leader')
            elif name == fastest_driver:
                tags.append('fastest')
            elif status == 'RETIRED':
                tags.append('retired')

            if not tags:
                tags.append('')

            item_id = self.past_tree.insert('', 'end',
                                            values=(pos, name, team, gap, best, compound, pit, status, delta),
                                            tags=tags)

            self.apply_cell_colors_past(item_id, team, compound)

    def apply_cell_colors_past(self, item_id, team, compound):
        """Applica colori alle celle tabella passato"""
        try:
            team_color = self.get_team_color(team)
            team_tag = f"team_{team.replace(' ', '_')}"

            # Verifica se il tag esiste già - USA tag_names() CON PARENTESI
            existing_tags = self.past_tree.tag_names()  # <-- Aggiungi parentesi qui!

            if team_tag not in existing_tags:
                self.past_tree.tag_configure(team_tag, foreground=team_color)

            tyre_color = self.get_tyre_color(compound)
            tyre_tag = f"tyre_{compound}"
            if tyre_tag not in existing_tags:
                self.past_tree.tag_configure(tyre_tag, foreground=tyre_color)

            current_tags = list(self.past_tree.item(item_id, 'tags'))
            if team_tag not in current_tags:
                current_tags.append(team_tag)
            if tyre_tag not in current_tags:
                current_tags.append(tyre_tag)

            self.past_tree.item(item_id, tags=tuple(current_tags))

        except Exception as e:
            print(f"Errore applicazione colori: {e}")

    def show_telemetry_popup(self, driver_data, mode="past"):
        """Mostra popup di telemetria per un pilota - MULTIPLE FINESTRE"""
        driver_name = driver_data.get('driver_name', 'Unknown')
        driver_code = driver_data.get('driver_code', 'Unknown')

        # Crea nuova finestra SEMPRE
        popup = tk.Toplevel(self.root)
        popup.title(f"📊 Telemetria - {driver_name} ({driver_code})")
        popup.geometry("1000x700")
        popup.configure(bg=COLORS['bg'])

        # Genera un ID unico per questa finestra
        import time
        window_id = f"{driver_name}_{int(time.time() * 1000)}"

        # Memorizza la finestra (lista per supportare multiple)
        if driver_name not in self.open_driver_windows:
            self.open_driver_windows[driver_name] = []
        self.open_driver_windows[driver_name].append({
            'id': window_id,
            'window': popup
        })

        popup.transient(self.root)

        # Frame principale con scroll
        main_frame = tk.Frame(popup, bg=COLORS['bg'])
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Canvas per scroll
        canvas = tk.Canvas(main_frame, bg=COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS['bg'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Header
        header_frame = tk.Frame(scrollable_frame, bg=COLORS['bg'])
        header_frame.pack(fill='x', pady=(0, 20))

        tk.Label(header_frame,
                 text=f"🏎️ TELEMETRIA - {driver_name}",
                 font=('Arial', 18, 'bold'),
                 bg=COLORS['bg'],
                 fg=COLORS['yellow']).pack()

        # Info pilota
        team = driver_data.get('team', 'Unknown')
        team_color = self.get_team_color(team)

        info_frame = tk.Frame(scrollable_frame, bg=COLORS['bg_light'], relief='ridge', bd=2)
        info_frame.pack(fill='x', pady=10, padx=5)

        tk.Label(info_frame,
                 text=f"{driver_code} | {team} | P{driver_data.get('position', 'N/A')}",
                 font=('Arial', 14, 'bold'),
                 bg=COLORS['bg_light'],
                 fg=team_color).pack(pady=10)

        # Sezione grafici telemetria
        self.create_telemetry_charts(scrollable_frame, driver_data, team_color)

        # Bottone chiudi con gestione corretta - SOLO 3 PARAMETRI!
        close_btn = tk.Button(scrollable_frame, text="CHIUDI TELEMETRIA",
                              command=lambda d=driver_name, w_id=window_id, p=popup:
                              self._close_telemetry_window(d, w_id, p),  # SOLO 3 PARAMETRI
                              bg=COLORS['red'],
                              fg='white',
                              font=('Arial', 12, 'bold'),
                              padx=30,
                              pady=10)
        close_btn.pack(pady=20)

        # Imposta gestione chiusura della finestra - SOLO 3 PARAMETRI!
        popup.protocol("WM_DELETE_WINDOW",
                       lambda d=driver_name, w_id=window_id, p=popup:
                       self._close_telemetry_window(d, w_id, p))  # SOLO 3 PARAMETRI

        # Imposta focus
        popup.focus_force()
        print(f"✅ Aperta finestra telemetria per {driver_name} (ID: {window_id})")

        return popup

    def _close_telemetry_window(self, driver_name, window_id, window):
        """Gestisce la chiusura della finestra di telemetria"""
        try:
            print(f"🔒 Tentativo chiusura finestra per {driver_name} (ID: {window_id})")

            if driver_name in self.open_driver_windows:
                # Rimuovi questa finestra dalla lista
                self.open_driver_windows[driver_name] = [
                    w for w in self.open_driver_windows[driver_name]
                    if w['id'] != window_id
                ]

                # Se la lista è vuota, rimuovi l'entry
                if not self.open_driver_windows[driver_name]:
                    del self.open_driver_windows[driver_name]

            window.destroy()
            print(f"✅ Finestra chiusa per {driver_name}")

        except Exception as e:
            print(f"Errore chiusura finestra: {e}")
            try:
                window.destroy()
            except:
                pass

    def create_telemetry_charts(self, parent, driver_data, team_color):
        """Crea i grafici di telemetria per il pilota"""
        # Converti colore team per matplotlib
        hex_color = team_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        mpl_color = (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

        # 1. GRAFICO TEMPI GIRO
        times_frame = tk.LabelFrame(parent, text=" ⏱️ TEMPI GIRO ",
                                    font=('Arial', 12, 'bold'),
                                    bg=COLORS['bg_light'],
                                    fg=COLORS['white'],
                                    padx=10,
                                    pady=10)
        times_frame.pack(fill='x', pady=10, padx=5)

        fig1 = Figure(figsize=(10, 4), dpi=80, facecolor=(0.05, 0.05, 0.05))
        ax1 = fig1.add_subplot(111)

        # Simula dati tempi giro
        laps = list(range(1, 21))
        lap_times = [95 + np.random.randn() * 2 for _ in range(20)]

        ax1.plot(laps, lap_times, color=mpl_color, linewidth=2, marker='o', markersize=4)
        ax1.set_xlabel('Numero Giro', color='white', fontsize=10)
        ax1.set_ylabel('Tempo (secondi)', color='white', fontsize=10)
        ax1.set_title('Andamento Tempi Giro', color='white', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.set_facecolor((0.1, 0.1, 0.1))
        ax1.tick_params(colors='white')

        # Evidenzia miglior tempo
        best_lap_idx = np.argmin(lap_times)
        ax1.plot(laps[best_lap_idx], lap_times[best_lap_idx], 'o',
                 color='gold', markersize=8, label='Miglior tempo')

        # Aggiungi linea media
        avg_time = np.mean(lap_times)
        ax1.axhline(y=avg_time, color='gray', linestyle='--', alpha=0.5, label=f'Media: {avg_time:.2f}s')

        ax1.legend(facecolor=(0.1, 0.1, 0.1), edgecolor='white', labelcolor='white')

        canvas1 = FigureCanvasTkAgg(fig1, times_frame)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill='x', padx=5, pady=5)

        # 2. GRAFICO VELOCITÀ SETTORI
        speed_frame = tk.LabelFrame(parent, text=" 🚀 VELOCITÀ SETTORI ",
                                    font=('Arial', 12, 'bold'),
                                    bg=COLORS['bg_light'],
                                    fg=COLORS['white'],
                                    padx=10,
                                    pady=10)
        speed_frame.pack(fill='x', pady=10, padx=5)

        fig2 = Figure(figsize=(10, 4), dpi=80, facecolor=(0.05, 0.05, 0.05))
        ax2 = fig2.add_subplot(111)

        sectors = ['S1', 'S2', 'S3']
        sector_speeds = [
            np.random.uniform(280, 320),
            np.random.uniform(270, 310),
            np.random.uniform(290, 330)
        ]

        bars = ax2.bar(sectors, sector_speeds, color=mpl_color, edgecolor='white', linewidth=1.5)
        ax2.set_xlabel('Settore', color='white', fontsize=10)
        ax2.set_ylabel('Velocità (km/h)', color='white', fontsize=10)
        ax2.set_title('Velocità Media per Settore', color='white', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax2.set_facecolor((0.1, 0.1, 0.1))
        ax2.tick_params(colors='white')

        # Aggiungi valori sulle barre
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2., height + 1,
                     f'{height:.0f} km/h',
                     ha='center', va='bottom', color='white', fontweight='bold')

        canvas2 = FigureCanvasTkAgg(fig2, speed_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill='x', padx=5, pady=5)

        # 3. GRAFICO USURA GOMME
        tyre_frame = tk.LabelFrame(parent, text=" 🛞 USURA GOMME ",
                                   font=('Arial', 12, 'bold'),
                                   bg=COLORS['bg_light'],
                                   fg=COLORS['white'],
                                   padx=10,
                                   pady=10)
        tyre_frame.pack(fill='x', pady=10, padx=5)

        fig3 = Figure(figsize=(10, 4), dpi=80, facecolor=(0.05, 0.05, 0.05))
        ax3 = fig3.add_subplot(111)

        compound = driver_data.get('compound', 'SOFT')
        tyre_color = self.get_tyre_color(compound)
        hex_tyre = tyre_color.lstrip('#')
        rgb_tyre = tuple(int(hex_tyre[i:i + 2], 16) for i in (0, 2, 4))
        mpl_tyre_color = (rgb_tyre[0] / 255, rgb_tyre[1] / 255, rgb_tyre[2] / 255)

        tyre_laps = list(range(1, 31))
        tyre_wear = [100 - (i * 3.2) + np.random.randn() * 2 for i in range(30)]

        ax3.plot(tyre_laps, tyre_wear, color=mpl_tyre_color, linewidth=3, marker='o', markersize=4)
        ax3.fill_between(tyre_laps, tyre_wear, 0, alpha=0.3, color=mpl_tyre_color)
        ax3.set_xlabel('Giri', color='white', fontsize=10)
        ax3.set_ylabel('Vita Gomma (%)', color='white', fontsize=10)
        ax3.set_title(f'Usura Gomme - {compound}', color='white', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3, linestyle='--')
        ax3.set_facecolor((0.1, 0.1, 0.1))
        ax3.tick_params(colors='white')

        # Aggiungi linee di riferimento
        ax3.axhline(y=50, color='yellow', linestyle='--', alpha=0.5, label='Consiglio pit (50%)')
        ax3.axhline(y=30, color='red', linestyle='--', alpha=0.5, label='Pericolo (30%)')

        ax3.legend(facecolor=(0.1, 0.1, 0.1), edgecolor='white', labelcolor='white')

        canvas3 = FigureCanvasTkAgg(fig3, tyre_frame)
        canvas3.draw()
        canvas3.get_tk_widget().pack(fill='x', padx=5, pady=5)

        # 4. GRAFICO DISTRIBUZIONE TEMPI
        dist_frame = tk.LabelFrame(parent, text=" 📊 DISTRIBUZIONE TEMPI ",
                                   font=('Arial', 12, 'bold'),
                                   bg=COLORS['bg_light'],
                                   fg=COLORS['white'],
                                   padx=10,
                                   pady=10)
        dist_frame.pack(fill='x', pady=10, padx=5)

        fig4 = Figure(figsize=(10, 4), dpi=80, facecolor=(0.05, 0.05, 0.05))
        ax4 = fig4.add_subplot(111)

        # Genera distribuzione normale di tempi
        mean_time = np.mean(lap_times)
        std_time = np.std(lap_times)
        distribution = np.random.normal(mean_time, std_time, 1000)

        n, bins, patches = ax4.hist(distribution, bins=30, color=mpl_color,
                                    edgecolor='white', alpha=0.7, density=True)
        ax4.set_xlabel('Tempo Giro (secondi)', color='white', fontsize=10)
        ax4.set_ylabel('Densità', color='white', fontsize=10)
        ax4.set_title('Distribuzione Tempi Giro', color='white', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3, linestyle='--')
        ax4.set_facecolor((0.1, 0.1, 0.1))
        ax4.tick_params(colors='white')

        # Aggiungi linee per media e deviazione standard
        ax4.axvline(x=mean_time, color='yellow', linestyle='-', linewidth=2, label=f'Media: {mean_time:.2f}s')
        ax4.axvline(x=mean_time - std_time, color='gray', linestyle='--', alpha=0.5, label=f'±1σ')
        ax4.axvline(x=mean_time + std_time, color='gray', linestyle='--', alpha=0.5)

        ax4.legend(facecolor=(0.1, 0.1, 0.1), edgecolor='white', labelcolor='white')

        canvas4 = FigureCanvasTkAgg(fig4, dist_frame)
        canvas4.draw()
        canvas4.get_tk_widget().pack(fill='x', padx=5, pady=5)

    def show_driver_details(self, event):
        """Mostra dettagli pilota"""
        if self.current_mode != "past" or not self.current_data:
            return

        selection = self.past_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.past_tree.item(item, 'values')
        if not values:
            return

        driver_name = values[1]

        driver_data = None
        for driver in self.current_data.get('drivers', []):
            if driver.get('driver_name') == driver_name:
                driver_data = driver
                break

        if driver_data:
            self.show_driver_popup(driver_data, "past")

    def show_driver_popup(self, driver_data, mode):
        """Mostra popup dettagli pilota"""
        popup = tk.Toplevel(self.root)
        popup.title(f"📊 {driver_data['driver_name']}")
        popup.geometry("500x600")
        popup.configure(bg=COLORS['bg'])
        popup.resizable(False, False)

        popup.transient(self.root)
        popup.grab_set()

        # Contenuto principale
        main_frame = tk.Frame(popup, bg=COLORS['bg'])
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        content_frame = tk.Frame(main_frame, bg=COLORS['bg'])
        content_frame.pack(fill='both', expand=True)

        # Intestazione
        header_frame = tk.Frame(content_frame, bg=COLORS['bg'])
        header_frame.pack(fill='x', pady=(0, 20))

        tk.Label(header_frame,
                 text=f"🏎️ {driver_data['driver_name']}",
                 font=('Arial', 16, 'bold'),
                 bg=COLORS['bg'],
                 fg=COLORS['yellow']).pack()

        # Team con colore
        team = driver_data.get('team', 'Unknown')
        team_color = self.get_team_color(team)
        tk.Label(header_frame,
                 text=f"{driver_data.get('driver_code', '')} | {team} | P{driver_data.get('position', '')}",
                 font=('Arial', 12),
                 bg=COLORS['bg'],
                 fg=team_color).pack(pady=5)

        # Informazioni base
        base_frame = tk.LabelFrame(content_frame, text=" Informazioni Base ",
                                   font=('Arial', 11, 'bold'),
                                   bg=COLORS['bg_light'],
                                   fg=COLORS['white'],
                                   padx=15,
                                   pady=10)
        base_frame.pack(fill='x', pady=5)

        info_data = [
            ("Codice", driver_data.get('driver_code', 'N/A')),
            ("Numero", driver_data.get('driver_number', 'N/A')),
            ("Team", team),
            ("Posizione", f"P{driver_data.get('position', 'N/A')}"),
            ("Stato", driver_data.get('status', 'N/A'))
        ]

        for i, (label, value) in enumerate(info_data):
            row = tk.Frame(base_frame, bg=COLORS['bg_light'])
            row.pack(fill='x', pady=2)

            tk.Label(row, text=label + ":",
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray'],
                     width=12,
                     anchor='w').pack(side='left')

            # Colore speciale per Team
            if label == "Team":
                tk.Label(row, text=value,
                         font=('Arial', 10, 'bold'),
                         bg=COLORS['bg_light'],
                         fg=team_color,
                         anchor='w').pack(side='left', fill='x', expand=True)
            else:
                tk.Label(row, text=value,
                         font=('Arial', 10, 'bold'),
                         bg=COLORS['bg_light'],
                         fg=COLORS['white'],
                         anchor='w').pack(side='left', fill='x', expand=True)

        # Tempi
        times_frame = tk.LabelFrame(content_frame, text=" Tempi ",
                                    font=('Arial', 11, 'bold'),
                                    bg=COLORS['bg_light'],
                                    fg=COLORS['white'],
                                    padx=15,
                                    pady=10)
        times_frame.pack(fill='x', pady=10)

        # Miglior giro
        if driver_data.get('best_lap_time'):
            best_row = tk.Frame(times_frame, bg=COLORS['bg_light'])
            best_row.pack(fill='x', pady=3)

            tk.Label(best_row, text="Miglior Giro:",
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).pack(side='left')

            tk.Label(best_row, text=driver_data['best_lap_time'],
                     font=('Consolas', 11, 'bold'),
                     bg=COLORS['bg_light'],
                     fg=COLORS['green']).pack(side='left', padx=10)

        # Gap
        gap = driver_data.get('gap_to_leader', 'N/A')
        if gap and gap != 'N/A':
            gap_row = tk.Frame(times_frame, bg=COLORS['bg_light'])
            gap_row.pack(fill='x', pady=3)

            tk.Label(gap_row, text="Gap dal Leader:",
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).pack(side='left')

            tk.Label(gap_row, text=gap,
                     font=('Consolas', 11, 'bold'),
                     bg=COLORS['bg_light'],
                     fg=COLORS['yellow'] if gap != 'Leader' else COLORS['green']).pack(side='left', padx=10)

        # Gomme
        tyres_frame = tk.LabelFrame(content_frame, text=" Gomme ",
                                    font=('Arial', 11, 'bold'),
                                    bg=COLORS['bg_light'],
                                    fg=COLORS['white'],
                                    padx=15,
                                    pady=10)
        tyres_frame.pack(fill='x', pady=10)

        compound = driver_data.get('compound', 'N/A')
        tyre_life = driver_data.get('tyre_life', 0)
        pit_stops = driver_data.get('pit_stops', 0)

        # Gomma attuale
        if compound != 'N/A':
            current_tyre_row = tk.Frame(tyres_frame, bg=COLORS['bg_light'])
            current_tyre_row.pack(fill='x', pady=3)

            tk.Label(current_tyre_row, text="Gomma Attuale:",
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).pack(side='left')

            # Immagine gomma
            if compound in self.tyre_images:
                tk.Label(current_tyre_row, image=self.tyre_images[compound],
                         bg=COLORS['bg_light']).pack(side='left', padx=5)

            # Testo gomma
            tk.Label(current_tyre_row, text=compound,
                     font=('Arial', 10, 'bold'),
                     bg=COLORS['bg_light'],
                     fg=self.get_tyre_color(compound)).pack(side='left', padx=5)

            if tyre_life > 0:
                tk.Label(current_tyre_row, text=f"(Vita: {tyre_life} giri)",
                         font=('Arial', 9),
                         bg=COLORS['bg_light'],
                         fg=COLORS['gray']).pack(side='left', padx=5)

        # Pit stop
        pit_row = tk.Frame(tyres_frame, bg=COLORS['bg_light'])
        pit_row.pack(fill='x', pady=3)

        tk.Label(pit_row, text="Pit Stop:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left')

        tk.Label(pit_row, text=str(pit_stops),
                 font=('Arial', 10, 'bold'),
                 bg=COLORS['bg_light'],
                 fg=COLORS['white']).pack(side='left', padx=10)

        # Bottone per telemetria
        telemetry_btn = tk.Button(content_frame, text="📊 APRI TELEMETRIA",
                                  command=lambda: self.show_telemetry_popup(driver_data, mode),
                                  bg=COLORS['blue'],
                                  fg='white',
                                  font=('Arial', 11, 'bold'),
                                  padx=20,
                                  pady=10)
        telemetry_btn.pack(pady=10)

        # Bottone chiudi
        close_btn = tk.Button(content_frame, text="CHIUDI",
                              command=popup.destroy,
                              bg=COLORS['red'],
                              fg='white',
                              font=('Arial', 11, 'bold'),
                              padx=30,
                              pady=10)
        close_btn.pack(pady=20)

    def stop_live(self):
        """Ferma modalità LIVE"""
        self.real_data_active = False
        self.running = False

        # Ferma dati reali
        self.live_data_manager.stop_live_data()

        self.live_start_btn.config(state='normal')
        self.live_stop_btn.config(state='disabled')
        self.status_bar.config(text="Modalità LIVE fermata")
        self.update_current_gp_info()

    def refresh_schedule(self):
        """Ricarica il calendario"""
        self.status_bar.config(text="🔄 Ricaricamento calendario...")
        self.live_gp_info.config(text="📡 Aggiornamento in corso...")
        threading.Thread(target=self.load_schedule_from_fastf1, daemon=True).start()

    def stop_loading(self):
        """Ferma caricamento dati"""
        self.running = False

        if self.current_mode == "past":
            self.past_load_btn.config(state='normal', text='▶️ Carica Sessione')
            self.past_stop_btn.config(state='disabled')
        else:
            self.live_start_btn.config(state='normal')
            self.live_stop_btn.config(state='disabled')

        self.status_bar.config(text="Caricamento fermato")

    def show_error(self, message):
        """Mostra errore"""
        self.status_bar.config(text=f"❌ Errore: {message}")

        if not self.running:
            messagebox.showerror("Errore", message)

    def on_close(self):
        """Gestione chiusura"""
        self.running = False
        self.real_data_active = False
        self.root.destroy()


class LiveDataManager:
    """Gestisce i dati live REALI da OpenF1 API"""

    def __init__(self, app):
        self.app = app
        self.websocket_connected = False
        self.websocket_task = None
        self.data_queue = queue.Queue()
        self.current_session_key = None
        self.driver_positions = {}
        self.session_data = {}
        self.lap_times = {}
        self.stints = {}
        self.loop = None
        self.current_lap = 1
        self.session_started = False

    def start_live_data(self, session_key=None):
        """Avvia connessione ai dati live REALI"""
        print(f"🚀 AVVIO DATI LIVE con session_key: {session_key}")

        if session_key:
            self.current_session_key = session_key

        # Prima carica dati iniziali dalla REST API
        self.load_initial_data()

        # Poi avvia WebSocket per aggiornamenti in tempo reale
        self.websocket_thread = Thread(target=self._run_websocket, daemon=True)
        self.websocket_thread.start()

        # Consumer per processare dati
        self.consumer_thread = Thread(target=self._process_data_queue, daemon=True)
        self.consumer_thread.start()

    def load_initial_data(self):
        """Carica dati iniziali dalla REST API di OpenF1"""
        try:
            # Carica sessioni attive
            sessions_url = f"{OPENF1_API_URL}/sessions"
            response = requests.get(sessions_url, timeout=5)

            if response.status_code == 200:
                sessions = response.json()
                print(f"Sessioni disponibili: {len(sessions)}")

                # Carica piloti per la sessione corrente
                if self.current_session_key:
                    drivers_url = f"{OPENF1_API_URL}/drivers"
                    params = {'session_key': self.current_session_key}
                    drivers_response = requests.get(drivers_url, params=params, timeout=5)

                    if drivers_response.status_code == 200:
                        drivers = drivers_response.json()
                        print(f"Piloti caricati: {len(drivers)}")

                        # Inizializza strutture dati
                        for driver in drivers:
                            driver_number = driver.get('driver_number', '')
                            if driver_number:
                                self.driver_positions[driver_number] = 1
                                self.lap_times[driver_number] = []
                                self.stints[driver_number] = []

            print("✅ Dati iniziali caricati")

        except Exception as e:
            print(f"❌ Errore caricamento dati iniziali: {e}")

    def _run_websocket(self):
        """Esegue loop WebSocket in thread separato"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._websocket_loop())
        except Exception as e:
            print(f"Errore WebSocket loop: {e}")

    async def _websocket_loop(self):
        """Loop WebSocket robusto con riconnessione"""
        reconnect_attempts = 0
        max_reconnect_attempts = 3

        while self.app.real_data_active and reconnect_attempts < max_reconnect_attempts:
            try:
                print(f"🔗 Tentativo connessione WebSocket ({reconnect_attempts + 1}/{max_reconnect_attempts})...")

                async with websockets.connect(
                        WEBSOCKET_URL,
                        ping_interval=20,
                        ping_timeout=10,
                        close_timeout=5
                ) as websocket:

                    self.websocket_connected = True
                    reconnect_attempts = 0

                    print("✅ Connesso a OpenF1 WebSocket")

                    # Subscribe ai dati
                    subscribe_messages = []

                    if self.current_session_key:
                        # Sottoscrivi a specifica sessione
                        streams = ['position', 'lap', 'session', 'car_data', 'weather']
                        for stream in streams:
                            msg = {
                                "type": "subscribe",
                                "stream": stream,
                                "session_key": str(self.current_session_key)
                            }
                            subscribe_messages.append(msg)
                    else:
                        # Sottoscrivi a tutte le sessioni
                        msg = {
                            "type": "subscribe",
                            "stream": "position"
                        }
                        subscribe_messages.append(msg)

                    # Invia sottoscrizioni
                    for msg in subscribe_messages:
                        try:
                            await websocket.send(json.dumps(msg))
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            print(f"Errore invio sottoscrizione: {e}")

                    print("✅ Sottoscrizioni inviate")

                    # Loop ricezione dati
                    while self.app.real_data_active and self.websocket_connected:
                        try:
                            # Timeout per ricezione
                            data = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=30.0
                            )

                            # Processa dati
                            self.data_queue.put(data)

                            # Log ricezione
                            try:
                                parsed = json.loads(data)
                                if 'type' in parsed:
                                    stream_type = parsed['type']
                                    data_count = len(parsed.get('data', []))
                                    print(f"📥 Ricevuti {data_count} dati da {stream_type}")
                            except:
                                pass

                        except asyncio.TimeoutError:
                            print("⏱️ Timeout ricezione, invio ping...")
                            try:
                                await websocket.ping()
                            except:
                                break
                        except Exception as e:
                            print(f"❌ Errore ricezione: {e}")
                            break

            except Exception as e:
                print(f"❌ Errore connessione WebSocket: {e}")
                reconnect_attempts += 1

                if reconnect_attempts < max_reconnect_attempts:
                    print(f"🔄 Tentativo riconnessione in 5 secondi...")
                    await asyncio.sleep(5)

        self.websocket_connected = False
        print("🔌 Connessione WebSocket chiusa")

    def _process_data_queue(self):
        """Processa i dati dalla coda"""
        while self.app.real_data_active:
            try:
                if not self.data_queue.empty():
                    data = self.data_queue.get_nowait()
                    self._process_websocket_data(data)
                else:
                    time.sleep(0.1)
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                print(f"Errore processamento coda: {e}")

    def _process_websocket_data(self, raw_data):
        """Processa dati WebSocket REALI"""
        try:
            data = json.loads(raw_data)

            # Debug: mostra struttura dati
            if 'type' in data:
                stream_type = data['type']

                if stream_type == 'position':
                    self._process_position_data(data)
                elif stream_type == 'lap':
                    self._process_lap_data(data)
                elif stream_type == 'session':
                    self._process_session_data(data)
                elif stream_type == 'car_data':
                    self._process_car_data(data)

        except Exception as e:
            print(f"Errore processamento dati: {e}")

    def _process_position_data(self, data):
        """Processa dati di posizione REALI"""
        try:
            if 'data' in data:
                for pos_data in data['data']:
                    driver_number = str(pos_data.get('driver_number', ''))
                    position = pos_data.get('position', 1)
                    date = pos_data.get('date', datetime.now().isoformat())

                    if driver_number and position:
                        self.driver_positions[driver_number] = position

                        # Salva timestamp
                        self.session_data[f'pos_{driver_number}_time'] = date

                        print(f"📍 Posizione: Driver {driver_number} -> P{position}")

        except Exception as e:
            print(f"Errore processamento posizioni: {e}")

    def _process_lap_data(self, data):
        """Processa dati giro REALI"""
        try:
            if 'data' in data:
                for lap_data in data['data']:
                    driver_number = str(lap_data.get('driver_number', ''))
                    lap_number = lap_data.get('lap_number', 1)
                    lap_duration = lap_data.get('lap_duration', 0)

                    if driver_number and lap_duration:
                        # Aggiorna giro corrente
                        self.current_lap = max(self.current_lap, lap_number)

                        # Salva tempo giro
                        if driver_number not in self.lap_times:
                            self.lap_times[driver_number] = []

                        lap_info = {
                            'lap': lap_number,
                            'time': lap_duration,
                            'timestamp': datetime.now().isoformat()
                        }
                        self.lap_times[driver_number].append(lap_info)

                        # Mantieni solo ultimi 10 giri
                        if len(self.lap_times[driver_number]) > 10:
                            self.lap_times[driver_number] = self.lap_times[driver_number][-10:]

                        print(f"⏱️  Giro {lap_number}: Driver {driver_number} -> {lap_duration}s")

        except Exception as e:
            print(f"Errore processamento giri: {e}")

    def _process_session_data(self, data):
        """Processa dati sessione REALI"""
        try:
            if 'data' in data:
                for session_data in data['data']:
                    # Aggiorna dati sessione
                    self.session_data.update(session_data)

                    # Controlla se sessione è iniziata
                    session_status = session_data.get('session_status', '')
                    if session_status and not self.session_started:
                        self.session_started = True
                        print(f"🏁 Sessione iniziata: {session_status}")

        except Exception as e:
            print(f"Errore processamento sessione: {e}")

    def _process_car_data(self, data):
        """Processa dati auto REALI"""
        try:
            if 'data' in data:
                for car_data in data['data']:
                    driver_number = str(car_data.get('driver_number', ''))

                    if driver_number:
                        # Salva stint info
                        if driver_number not in self.stints:
                            self.stints[driver_number] = []

                        stint_info = {
                            'timestamp': datetime.now().isoformat(),
                            'data': car_data
                        }
                        self.stints[driver_number].append(stint_info)

                        # Mantieni solo ultimi 5 stint
                        if len(self.stints[driver_number]) > 5:
                            self.stints[driver_number] = self.stints[driver_number][-5:]

        except Exception as e:
            print(f"Errore processamento dati auto: {e}")

    def get_live_session_info(self):
        """Ottiene informazioni sessione live - VERSIONE ROBUSTA"""
        try:
            print("🔍 Ricerca sessioni LIVE attive...")

            # Metodo 1: Cerca sessioni attive con query più specifica
            base_url = "https://api.openf1.org/v1/sessions"

            # Prova diversi approcci
            search_methods = [
                # Cerca sessioni di gara
                lambda: requests.get(base_url, params={'session_name': 'Race'}, timeout=5),
                # Cerca sessioni recenti (oggi)
                lambda: requests.get(base_url, params={
                    'date_start': datetime.now().strftime('%Y-%m-%d'),
                    'date_end': datetime.now().strftime('%Y-%m-%d')
                }, timeout=5),
                # Cerca tutte le sessioni
                lambda: requests.get(base_url, timeout=5)
            ]

            for i, method in enumerate(search_methods):
                try:
                    response = method()
                    if response.status_code == 200:
                        sessions = response.json()
                        now = datetime.now()

                        print(f"✅ Trovate {len(sessions)} sessioni (metodo {i + 1})")

                        if sessions:
                            for session in sessions:
                                # Debug: mostra tutte le info della sessione
                                print(f"\n📋 Sessione trovata:")
                                for key, value in session.items():
                                    print(f"   {key}: {value}")

                                session_key = session.get('session_key')
                                session_name = session.get('session_name', 'Unknown')
                                location = session.get('location', 'Unknown')
                                circuit_key = session.get('circuit_key')

                                # Controlla se è attiva
                                session_start = session.get('session_start')
                                if session_start:
                                    try:
                                        start_time = datetime.fromisoformat(
                                            session_start.replace('Z', '+00:00')
                                        )
                                        time_diff = (now - start_time).total_seconds()

                                        # Sessione attiva se iniziata meno di 4 ore fa
                                        if 0 <= time_diff <= 14400:  # 4 ore
                                            print(f"\n🎯 SESSIONE ATTIVA TROVATA:")
                                            print(f"   Nome: {session_name}")
                                            print(f"   Location: {location}")
                                            print(f"   Key: {session_key}")
                                            print(f"   Iniziata: {time_diff:.0f} secondi fa")

                                            return {
                                                'session_key': session_key,
                                                'gp_name': location,
                                                'session_name': session_name,
                                                'circuit_key': circuit_key,
                                                'start_time': start_time,
                                                'status': 'live'
                                            }
                                    except Exception as e:
                                        print(f"Errore parsing tempo: {e}")
                                        continue

                        # Se non trovata in questo metodo, prova il prossimo
                        continue

                except Exception as e:
                    print(f"Errore metodo {i + 1}: {e}")
                    continue

            print("❌ Nessuna sessione attiva trovata")
            return None

        except Exception as e:
            print(f"❌ Errore generale ricerca sessioni: {e}")
            return None

    def stop_live_data(self):
        """Ferma connessione dati live"""
        print("🛑 Fermando dati live...")
        self.websocket_connected = False
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        print("✅ Dati live fermati")


def main():
    root = tk.Tk()
    app = F1MainApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
