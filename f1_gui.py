import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import requests
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw
import random
import json
import fastf1 as ff1
import pandas as pd
import numpy as np

# Configurazione
SERVER_URL_PAST = "http://localhost:5000/f1-data-detailed"
UPDATE_INTERVAL_PAST = 5
UPDATE_INTERVAL_LIVE = 2

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
        self.live_simulation_data = None
        self.live_update_thread = None
        self.simulation_running = False
        self.current_schedule = []  # Calendario attuale
        self.active_session_info = None  # Sessione attiva per LIVE
        self.fastf1_loaded = False  # Flag per FastF1

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

        # Aggiorna lista GP in base all'anno selezionato - USA after PER ASPETTARE
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
        self.root.after(100, self.update_gp_list)  # 100ms delay per sicurezza

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

            # Aggiorna lo stato SOLO se status_bar esiste già
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

        self.past_tree.bind('<Double-1>', self.show_driver_details)

    def setup_live_section(self):
        """Setup sezione LIVE"""
        self.live_frame = tk.Frame(self.control_frame, bg=COLORS['bg_light'])

        row1 = tk.Frame(self.live_frame, bg=COLORS['bg_light'])
        row1.pack(fill='x', pady=5)

        # Informazioni GP attuale
        self.live_gp_info = tk.Label(row1, text="📡 Caricamento calendario...",
                                     font=('Arial', 12, 'bold'),
                                     fg=COLORS['white'], bg=COLORS['bg_light'])
        self.live_gp_info.pack(side='left', padx=10, fill='x', expand=True)

        # Pulsanti live
        self.live_start_btn = tk.Button(row1, text="🔴 Avvia Live",
                                        command=self.start_live,
                                        bg=COLORS['red'], fg='white',
                                        font=('Arial', 10, 'bold'),
                                        state='disabled')
        self.live_start_btn.pack(side='right', padx=5)

        self.live_stop_btn = tk.Button(row1, text="⏹️ Ferma Live",
                                       command=self.stop_live,
                                       bg=COLORS['gray'], fg='white',
                                       font=('Arial', 10, 'bold'), state='disabled')
        self.live_stop_btn.pack(side='right', padx=5)

        # Pulsante refresh
        self.refresh_btn = tk.Button(row1, text="🔄 Aggiorna",
                                     command=self.refresh_schedule,
                                     bg=COLORS['yellow'], fg='black',
                                     font=('Arial', 9, 'bold'))
        self.refresh_btn.pack(side='right', padx=5)

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
        # Gestisci diversi formati di nomi GP
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
            if team_tag not in self.past_tree.tag_names():
                self.past_tree.tag_configure(team_tag, foreground=team_color)

            tyre_color = self.get_tyre_color(compound)
            tyre_tag = f"tyre_{compound}"
            if tyre_tag not in self.past_tree.tag_names():
                self.past_tree.tag_configure(tyre_tag, foreground=tyre_color)

            current_tags = list(self.past_tree.item(item_id, 'tags'))
            if team_tag not in current_tags:
                current_tags.append(team_tag)
            if tyre_tag not in current_tags:
                current_tags.append(tyre_tag)

            self.past_tree.item(item_id, tags=tuple(current_tags))

        except Exception as e:
            print(f"Errore applicazione colori: {e}")

    def start_live(self):
        """Avvia modalità LIVE"""
        if not self.active_session_info:
            messagebox.showinfo("Info", "Nessuna sessione selezionata.")
            return

        session = self.active_session_info['session']
        gp = self.active_session_info['gp']

        print(f"Avvio LIVE per: {gp['gp_name']} - {session['name']}")

        # Avvisa se è una sessione futura
        if session['status'] != 'in_progress':
            response = messagebox.askyesno(
                "Sessione Futura",
                f"La sessione {session['name']} inizierà tra {session.get('countdown', '?')}.\n"
                f"Avviare la simulazione live comunque?"
            )
            if not response:
                return

        self.status_bar.config(text=f"Avvio LIVE: {gp['gp_name']} - {session['name']}")

        # Carica dati simulati per la sessione
        self.live_simulation_data = self.prepare_simulation_data(gp, session)

        self.simulation_running = True
        self.running = True
        self.live_start_btn.config(state='disabled')
        self.live_stop_btn.config(state='normal')
        self.status_bar.config(text=f"LIVE attivo: {gp['gp_name']} - Simulazione in corso")

        # Carica mappa circuito
        gp_name_short = gp['gp_name'].replace('Grand Prix', '').strip()
        self.load_track_map(gp_name_short)

        # Aggiorna info
        self.live_session_label.config(text=f"LIVE: {session['name']}")
        self.flag_label.config(text="🟢")

        # Imposta numero giri in base al tipo di sessione
        if session['code'] == 'R':
            self.lap_label.config(text="1/57")
        elif session['code'] == 'S':
            self.lap_label.config(text="1/24")
        else:
            self.lap_label.config(text="Session")

        self.weather_label.config(text="Sereno")
        self.track_label.config(text=f"Circuito: {gp['location']}")

        # Avvia thread simulazione
        self.live_update_thread = threading.Thread(target=self.live_simulation_loop,
                                                   daemon=True)
        self.live_update_thread.start()

    def prepare_simulation_data(self, gp_info, session_info):
        """Prepara dati per simulazione live"""
        # Crea piloti fittizi per la simulazione
        drivers = []
        sample_drivers = [
            {'driver_name': 'Max Verstappen', 'team': 'Red Bull', 'driver_code': 'VER'},
            {'driver_name': 'Charles Leclerc', 'team': 'Ferrari', 'driver_code': 'LEC'},
            {'driver_name': 'Lewis Hamilton', 'team': 'Mercedes', 'driver_code': 'HAM'},
            {'driver_name': 'George Russell', 'team': 'Mercedes', 'driver_code': 'RUS'},
            {'driver_name': 'Carlos Sainz', 'team': 'Ferrari', 'driver_code': 'SAI'},
            {'driver_name': 'Lando Norris', 'team': 'McLaren', 'driver_code': 'NOR'},
            {'driver_name': 'Oscar Piastri', 'team': 'McLaren', 'driver_code': 'PIA'},
            {'driver_name': 'Fernando Alonso', 'team': 'Aston Martin', 'driver_code': 'ALO'},
            {'driver_name': 'Lance Stroll', 'team': 'Aston Martin', 'driver_code': 'STR'},
            {'driver_name': 'Pierre Gasly', 'team': 'Alpine', 'driver_code': 'GAS'},
            {'driver_name': 'Esteban Ocon', 'team': 'Alpine', 'driver_code': 'OCO'},
            {'driver_name': 'Alexander Albon', 'team': 'Williams', 'driver_code': 'ALB'},
            {'driver_name': 'Logan Sargeant', 'team': 'Williams', 'driver_code': 'SAR'},
            {'driver_name': 'Daniel Ricciardo', 'team': 'Racing Bulls', 'driver_code': 'RIC'},
            {'driver_name': 'Yuki Tsunoda', 'team': 'Racing Bulls', 'driver_code': 'TSU'},
            {'driver_name': 'Valtteri Bottas', 'team': 'Kick Sauber', 'driver_code': 'BOT'},
            {'driver_name': 'Zhou Guanyu', 'team': 'Kick Sauber', 'driver_code': 'ZHO'},
            {'driver_name': 'Kevin Magnussen', 'team': 'Haas', 'driver_code': 'MAG'},
            {'driver_name': 'Nico Hülkenberg', 'team': 'Haas', 'driver_code': 'HUL'},
            {'driver_name': 'Oliver Bearman', 'team': 'Haas', 'driver_code': 'BEA'}
        ]

        for i, driver in enumerate(sample_drivers):
            driver_data = {
                **driver,
                'position': i + 1,
                'sim_status': 'RUNNING',
                'current_lap': 1,
                'current_sector': random.randint(1, 3),
                'last_lap_time': f"1:{random.randint(30, 40):02d}.{random.randint(0, 999):03d}",
                'gap_to_leader_sim': f"+{random.uniform(0.5, 30.0):.3f}" if i > 0 else 'Leader',
                'compound': random.choice(['SOFT', 'MEDIUM', 'HARD']),
                'tyre_wear': random.randint(1, 30),
                'pit_stops': 0,
                'driver_number': str(44 + i) if i != 0 else '1'
            }
            drivers.append(driver_data)

        # Determina numero giri in base al tipo di sessione
        if session_info['code'] == 'R':
            total_laps = 57
        elif session_info['code'] == 'S':
            total_laps = 24
        else:
            total_laps = 1  # Sessioni di qualifica/prove

        return {
            'drivers': drivers,
            'gp_info': gp_info,
            'session_info': session_info,
            'current_lap': 1,
            'total_laps': total_laps,
            'elapsed_time': 0,
            'flag': 'GREEN',
            'weather': 'Sereno',
            'safety_car': 'No',
            'session_start': datetime.now()
        }

    def live_simulation_loop(self):
        """Loop di simulazione dati live"""
        lap_count = 1

        while self.simulation_running and self.current_mode == "live":
            try:
                if self.live_simulation_data:
                    # Incrementa tempo
                    elapsed = datetime.now() - self.live_simulation_data['session_start']
                    self.live_simulation_data['elapsed_time'] = elapsed.total_seconds()

                    # Aggiorna piloti
                    for i, driver in enumerate(self.live_simulation_data['drivers']):
                        if driver['sim_status'] == 'RUNNING':
                            # Avanza settore
                            driver['current_sector'] += 1
                            if driver['current_sector'] > 3:
                                driver['current_sector'] = 1
                                driver['current_lap'] += 1

                                # Nuovo tempo giro
                                base_time = random.uniform(85.0, 95.0)
                                variation = random.uniform(-0.5, 0.5)
                                lap_time_sec = base_time + variation

                                minutes = int(lap_time_sec // 60)
                                seconds = lap_time_sec % 60
                                driver['last_lap_time'] = f"{minutes}:{seconds:06.3f}"

                                # Aggiorna gap
                                if i == 0:
                                    driver['gap_to_leader_sim'] = 'Leader'
                                else:
                                    gap = random.uniform(0.5, 15.0)
                                    driver['gap_to_leader_sim'] = f"+{gap:.3f}"

                                # Usura gomme
                                driver['tyre_wear'] += random.randint(1, 5)

                                # Pit stop casuale
                                if driver['tyre_wear'] > 50 and random.random() < 0.1:
                                    driver['pit_stops'] = driver.get('pit_stops', 0) + 1
                                    driver['tyre_wear'] = 1
                                    compounds = ['SOFT', 'MEDIUM', 'HARD']
                                    current = driver['compound']
                                    new_compounds = [c for c in compounds if c != current]
                                    driver['compound'] = random.choice(new_compounds) if new_compounds else current

                    # Cambio bandiera occasionale
                    if random.random() < 0.05:
                        flags = ['GREEN', 'YELLOW', 'RED', 'CHEQUERED']
                        self.live_simulation_data['flag'] = random.choice(flags)

                    # Aggiorna giro
                    self.live_simulation_data['current_lap'] = lap_count
                    lap_count += 1
                    if lap_count > self.live_simulation_data['total_laps']:
                        lap_count = 1

                    # Aggiorna GUI
                    self.root.after(0, self.update_live_display)

                time.sleep(UPDATE_INTERVAL_LIVE)

            except Exception as e:
                print(f"Errore simulazione live: {e}")
                time.sleep(UPDATE_INTERVAL_LIVE)

    def update_live_display(self):
        """Aggiorna display live"""
        if not self.live_simulation_data:
            return

        current_time = datetime.now().strftime("%H:%M:%S")
        self.live_time_label.config(text=f"Aggiornato: {current_time}")

        # Aggiorna info panel
        elapsed = self.live_simulation_data['elapsed_time']
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.elapsed_time_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        self.lap_label.config(
            text=f"{self.live_simulation_data['current_lap']}/{self.live_simulation_data['total_laps']}")
        self.flag_label.config(text=FLAGS.get(self.live_simulation_data['flag'], '⚫'))

        # Aggiorna mappa
        self.update_track_map(self.live_simulation_data['drivers'])

        # Aggiorna status bar
        gp_name = self.live_simulation_data['gp_info']['gp_name']
        session_name = self.live_simulation_data['session_info']['name']
        self.status_bar.config(
            text=f"LIVE: {gp_name} - {session_name} | Giro {self.live_simulation_data['current_lap']}/{self.live_simulation_data['total_laps']}")

    def load_track_map(self, gp):
        """Carica o genera mappa del circuito"""
        try:
            self.track_label.config(text=f"Circuito: {gp}")
            self.create_placeholder_track(gp.lower())
        except Exception as e:
            print(f"Errore caricamento mappa: {e}")
            self.track_label.config(text=f"Circuito: {gp} (mappa non disponibile)")

    def create_placeholder_track(self, circuit_name):
        """Crea mappa placeholder per il circuito"""
        canvas_width = self.track_canvas.winfo_width() or 600
        canvas_height = self.track_canvas.winfo_height() or 400

        if canvas_width < 100 or canvas_height < 100:
            canvas_width, canvas_height = 600, 400

        img = Image.new('RGB', (canvas_width, canvas_height), color=(20, 20, 20))
        draw = ImageDraw.Draw(img)

        margin = 40
        track_width = 25
        points = []

        if 'monaco' in circuit_name:
            points = [
                (margin, canvas_height // 2),
                (canvas_width // 4, margin),
                (canvas_width // 2, margin),
                (3 * canvas_width // 4, margin),
                (canvas_width - margin, canvas_height // 3),
                (canvas_width - margin, 2 * canvas_height // 3),
                (3 * canvas_width // 4, canvas_height - margin),
                (canvas_width // 2, canvas_height - margin),
                (canvas_width // 4, canvas_height - margin),
                (margin, 2 * canvas_height // 3),
                (margin, canvas_height // 2)
            ]
        elif 'spa' in circuit_name or 'belgium' in circuit_name:
            points = [
                (margin, margin),
                (canvas_width - margin, margin),
                (canvas_width - 50, canvas_height // 2),
                (canvas_width - margin, canvas_height - margin),
                (canvas_width // 2, canvas_height - 50),
                (margin, canvas_height - margin),
                (50, canvas_height // 2),
                (margin, margin)
            ]
        elif 'abu dhabi' in circuit_name.lower() or 'yas marina' in circuit_name.lower():
            # Circuito Abu Dhabi/Yas Marina
            points = [
                (margin, margin),
                (canvas_width - margin, margin),
                (canvas_width - margin, canvas_height // 3),
                (2 * canvas_width // 3, canvas_height // 2),
                (canvas_width - margin, 2 * canvas_height // 3),
                (canvas_width - margin, canvas_height - margin),
                (canvas_width // 2, canvas_height - margin),
                (margin, canvas_height // 2),
                (margin, margin)
            ]
        else:
            points = [
                (margin, margin),
                (canvas_width - margin, margin),
                (canvas_width - margin, canvas_height - margin),
                (margin, canvas_height - margin),
                (margin, margin)
            ]

        if len(points) > 1:
            for i in range(len(points) - 1):
                draw.line([points[i], points[i + 1]], fill=(60, 60, 60), width=track_width)
            draw.line([points[-1], points[0]], fill=(60, 60, 60), width=track_width)

        start_x = margin + 50
        for i in range(10):
            y = margin + 30 + (i * 15)
            draw.line([start_x, y, start_x + 30, y], fill=(200, 200, 200), width=2)

        if len(points) > 2:
            for i, point in enumerate(points):
                if i % 3 == 0:
                    draw.ellipse([point[0] - 15, point[1] - 15, point[0] + 15, point[1] + 15],
                                 outline=(100, 200, 100), width=3)

        self.track_image = ImageTk.PhotoImage(img)
        self.track_canvas.delete("all")
        self.track_canvas.create_image(0, 0, anchor='nw', image=self.track_image)
        self.track_points = points

    def update_track_map(self, drivers):
        """Aggiorna posizioni piloti sulla mappa"""
        if not hasattr(self, 'track_points') or not self.track_points:
            return

        self.track_canvas.delete("driver")
        visible_drivers = [d for d in drivers if d.get('sim_status') == 'RUNNING']
        num_drivers = len(visible_drivers)

        if num_drivers > 0 and len(self.track_points) > 0:
            step = max(1, len(self.track_points) // num_drivers)

            for i, driver in enumerate(visible_drivers[:min(num_drivers, len(self.track_points))]):
                point_idx = (i * step) % len(self.track_points)
                point = self.track_points[point_idx]

                team_color = self.get_team_color(driver.get('team', 'Unknown'))

                try:
                    hex_color = team_color.lstrip('#')
                    rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                except:
                    rgb = (128, 128, 128)

                x, y = point
                pos = driver.get('position', i + 1)

                self.track_canvas.create_oval(x - 12, y - 12, x + 12, y + 12,
                                              fill=f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}",
                                              outline='white', width=2,
                                              tags="driver")

                self.track_canvas.create_text(x, y,
                                              text=str(pos),
                                              fill='white',
                                              font=('Arial', 9, 'bold'),
                                              tags="driver")

                driver_code = driver.get('driver_code', f"D{pos}")
                self.track_canvas.create_text(x, y - 20,
                                              text=driver_code,
                                              fill='white',
                                              font=('Arial', 8, 'bold'),
                                              anchor='s',
                                              tags="driver")

    def stop_live(self):
        """Ferma modalità LIVE"""
        self.simulation_running = False
        self.running = False

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

    def show_driver_details(self, event):
        """Mostra dettagli pilota - POPUP FIXED"""
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
        """Mostra popup dettagli pilota - VERSIONE COMPLETA"""
        popup = tk.Toplevel(self.root)
        popup.title(f"📊 {driver_data['driver_name']}")
        popup.geometry("500x600")
        popup.configure(bg=COLORS['bg'])
        popup.resizable(False, False)

        popup.transient(self.root)
        popup.grab_set()

        # Contenuto principale con scroll
        main_frame = tk.Frame(popup, bg=COLORS['bg'])
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Frame per contenuto (senza canvas per semplicità)
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

        # Modalità
        tk.Label(header_frame,
                 text=f"Modalità: {'LIVE' if mode == 'live' else 'PASSATO'}",
                 font=('Arial', 10),
                 bg=COLORS['bg'],
                 fg=COLORS['gray_light']).pack()

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
            ("Stato", driver_data.get('status', driver_data.get('sim_status', 'N/A')))
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

        # Ultimo giro (solo per live)
        if mode == 'live' and driver_data.get('last_lap_time'):
            last_row = tk.Frame(times_frame, bg=COLORS['bg_light'])
            last_row.pack(fill='x', pady=3)

            tk.Label(last_row, text="Ultimo Giro:",
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).pack(side='left')

            tk.Label(last_row, text=driver_data['last_lap_time'],
                     font=('Consolas', 11),
                     bg=COLORS['bg_light'],
                     fg=COLORS['blue']).pack(side='left', padx=10)

        # Gap
        gap = driver_data.get('gap_to_leader', driver_data.get('gap_to_leader_sim', 'N/A'))
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
        tyre_life = driver_data.get('tyre_life', driver_data.get('tyre_wear', 0))
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
                tk.Label(current_tyre_row, text=f"(Usura: {tyre_life})",
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

        # Bottone chiudi
        close_btn = tk.Button(content_frame, text="CHIUDI",
                              command=popup.destroy,
                              bg=COLORS['red'],
                              fg='white',
                              font=('Arial', 11, 'bold'),
                              padx=30,
                              pady=10)
        close_btn.pack(pady=20)

    def show_error(self, message):
        """Mostra errore"""
        self.status_bar.config(text=f"❌ Errore: {message}")

        if not self.running:
            messagebox.showerror("Errore", message)

    def on_close(self):
        """Gestione chiusura"""
        self.running = False
        self.simulation_running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = F1MainApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
