import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import requests
from datetime import datetime
from PIL import Image, ImageTk

# Configurazione
SERVER_URL = "http://localhost:5000/f1-data-detailed"
UPDATE_INTERVAL = 5

# Dati
YEARS = [2022, 2023, 2024, 2025]
GRAND_PRIX = ['Bahrain', 'Saudi Arabia', 'Australia', 'Japan', 'China', 'Miami',
              'Monaco', 'Canada', 'Spain', 'Austria', 'Great Britain', 'Hungary',
              'Belgium', 'Netherlands', 'Italy', 'Azerbaijan', 'Singapore',
              'United States', 'Mexico', 'Brazil', 'Las Vegas', 'Qatar', 'Abu Dhabi']
SESSIONS = ['FP1', 'FP2', 'FP3', 'Q', 'SQ', 'S', 'R']

# Colori base
COLORS = {
    'bg': '#0a0a0a',
    'bg_light': '#111111',
    'red': '#e10600',
    'green': '#00cc66',
    'yellow': '#ffcc00',
    'blue': '#0099ff',
    'white': '#ffffff',
    'gray': '#666666'
}

# Colori team F1
TEAM_COLORS = {
    'Red Bull': '#0600EF',  # Blu Red Bull
    'Red Bull Racing': '#0600EF',
    'Ferrari': '#DC0000',  # Rosso Ferrari
    'Mercedes': '#00D2BE',  # Verde acqua Mercedes
    'McLaren': '#FF8700',  # Arancione McLaren
    'Aston Martin': '#006F62',  # Verde Aston Martin
    'Alpine': '#0090FF',  # Blu Alpine
    'Williams': '#005AFF',  # Blu Williams
    'AlphaTauri': '#2B4562',  # Blu scuro AlphaTauri
    'Racing Bulls': '#2B4562',
    'Alfa Romeo': '#900000',  # Rosso scuro Alfa Romeo
    'Kick Sauber': '#900000',
    'Haas': '#FFFFFF',  # Bianco Haas
    'Haas F1 Team': '#FFFFFF',
    'Unknown': '#888888'  # Grigio per team sconosciuti
}

# Colori gomme
TYRE_COLORS = {
    'SOFT': '#FF0000',  # Rosso brillante
    'MEDIUM': '#FFD700',  # Giallo oro
    'HARD': '#FFFFFF',  # Bianco
    'INTER': '#00FF00',  # Verde brillante
    'WET': '#0000FF',  # Blu
    'N/A': '#888888'  # Grigio
}


class F1Tracker:
    def __init__(self, root):
        self.root = root
        self.root.title("🏎️ F1 Live Tracker")
        self.root.geometry("1100x750")
        self.root.configure(bg=COLORS['bg'])

        # Variabili
        self.current_data = None
        self.running = False
        self.tyre_images = self.create_tyre_images()
        self.team_colors_cache = {}  # Cache per colori team

        # Setup GUI
        self.setup_gui()

    def create_tyre_images(self):
        """Crea immagini per le gomme"""
        images = {}

        for compound, color_hex in TYRE_COLORS.items():
            try:
                # Converti hex a RGB
                if compound == 'N/A':
                    color_rgb = (128, 128, 128)
                else:
                    color_hex = color_hex.lstrip('#')
                    color_rgb = tuple(int(color_hex[i:i + 2], 16) for i in (0, 2, 4))

                size = 20
                img = Image.new('RGB', (size, size), color_rgb)
                images[compound] = ImageTk.PhotoImage(img)
            except:
                pass

        return images

    def get_team_color(self, team_name):
        """Restituisce il colore del team"""
        if team_name in self.team_colors_cache:
            return self.team_colors_cache[team_name]

        # Cerca colore esatto
        if team_name in TEAM_COLORS:
            color = TEAM_COLORS[team_name]
        else:
            # Cerca parziale match
            for team_key, color in TEAM_COLORS.items():
                if team_key in team_name or team_name in team_key:
                    self.team_colors_cache[team_name] = color
                    return color
            color = TEAM_COLORS['Unknown']

        self.team_colors_cache[team_name] = color
        return color

    def get_tyre_color(self, compound):
        """Restituisce il colore della gomma"""
        return TYRE_COLORS.get(compound, '#888888')

    def setup_gui(self):
        """Setup interfaccia"""
        # Control Panel
        control_frame = tk.Frame(self.root, bg=COLORS['bg'])
        control_frame.pack(pady=10, padx=10, fill='x')

        # Anno
        tk.Label(control_frame, text="Anno:", fg=COLORS['white'], bg=COLORS['bg']).grid(row=0, column=0, padx=5)
        self.year_var = tk.StringVar(value="2025")
        ttk.Combobox(control_frame, textvariable=self.year_var, values=YEARS, width=6, state='readonly').grid(row=0,
                                                                                                              column=1,
                                                                                                              padx=5)

        # GP
        tk.Label(control_frame, text="GP:", fg=COLORS['white'], bg=COLORS['bg']).grid(row=0, column=2, padx=5)
        self.gp_var = tk.StringVar(value="Qatar")
        ttk.Combobox(control_frame, textvariable=self.gp_var, values=GRAND_PRIX, width=15, state='readonly').grid(row=0,
                                                                                                                  column=3,
                                                                                                                  padx=5)

        # Sessione
        tk.Label(control_frame, text="Sessione:", fg=COLORS['white'], bg=COLORS['bg']).grid(row=0, column=4, padx=5)
        self.session_var = tk.StringVar(value="R")
        ttk.Combobox(control_frame, textvariable=self.session_var, values=SESSIONS, width=5, state='readonly').grid(
            row=0, column=5, padx=5)

        # Pulsanti
        self.load_btn = tk.Button(control_frame, text="▶️ Carica", command=self.start_loading,
                                  bg=COLORS['green'], fg='white', font=('Arial', 10, 'bold'))
        self.load_btn.grid(row=0, column=6, padx=10)

        self.stop_btn = tk.Button(control_frame, text="⏹️ Stop", command=self.stop_loading,
                                  bg=COLORS['red'], fg='white', font=('Arial', 10, 'bold'), state='disabled')
        self.stop_btn.grid(row=0, column=7, padx=5)

        # Info sessione
        info_frame = tk.Frame(self.root, bg=COLORS['bg_light'])
        info_frame.pack(fill='x', padx=10, pady=5)

        self.session_label = tk.Label(info_frame, text="Seleziona una sessione",
                                      font=('Arial', 12, 'bold'), fg=COLORS['white'], bg=COLORS['bg_light'])
        self.session_label.pack(side='left', padx=10, pady=5)

        self.time_label = tk.Label(info_frame, text="", font=('Arial', 10),
                                   fg=COLORS['gray'], bg=COLORS['bg_light'])
        self.time_label.pack(side='right', padx=10, pady=5)

        # Tabella
        self.setup_table()

        # Status bar
        self.status_bar = tk.Label(self.root, text="Pronto", bd=1, relief='sunken',
                                   anchor='w', bg=COLORS['bg_light'], fg=COLORS['white'])
        self.status_bar.pack(side='bottom', fill='x')

        # Stile
        self.setup_styles()

    def setup_styles(self):
        """Configura stili"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Custom.Treeview',
                        background=COLORS['bg_light'],
                        foreground=COLORS['white'],
                        fieldbackground=COLORS['bg_light'],
                        font=('Arial', 10))

        style.configure('Custom.Treeview.Heading',
                        background=COLORS['bg'],
                        foreground=COLORS['white'],
                        font=('Arial', 10, 'bold'))

        style.map('Custom.Treeview',
                  background=[('selected', '#333333')],
                  foreground=[('selected', 'white')])

    def setup_table(self):
        """Setup tabella con colori"""
        table_frame = tk.Frame(self.root)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side='right', fill='y')

        columns = ('pos', 'driver', 'team', 'gap', 'best', 'tyre', 'pit', 'status', 'delta')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                 height=18, yscrollcommand=scrollbar.set, style='Custom.Treeview')

        col_config = [
            ('Pos', 'pos', 50, 'center'),
            ('Pilota', 'driver', 150, 'w'),
            ('Team', 'team', 120, 'w'),
            ('Gap', 'gap', 80, 'center'),
            ('Miglior', 'best', 90, 'center'),
            ('Gomme', 'tyre', 70, 'center'),
            ('Pit', 'pit', 50, 'center'),
            ('Stato', 'status', 70, 'center'),
            ('Delta', 'delta', 80, 'center')
        ]

        for heading, column, width, anchor in col_config:
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor=anchor)

        # Tag per colori speciali
        self.tree.tag_configure('retired', foreground='#ff6666')
        self.tree.tag_configure('leader', foreground=COLORS['yellow'])
        self.tree.tag_configure('fastest', foreground=COLORS['green'])

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.tree.yview)

        self.tree.bind('<Double-1>', self.show_driver_details)

    def start_loading(self):
        """Avvia caricamento"""
        year = self.year_var.get()
        gp = self.gp_var.get()
        session = self.session_var.get()

        if not all([year, gp, session]):
            messagebox.showwarning("Attenzione", "Completa tutti i campi")
            return

        if self.running:
            self.stop_loading()

        self.running = True
        self.load_btn.config(state='disabled', text='⏳ Caricamento...')
        self.stop_btn.config(state='normal')
        self.status_bar.config(text=f"Caricamento {year} {gp} {session}...")

        for item in self.tree.get_children():
            self.tree.delete(item)

        threading.Thread(target=self.update_loop, args=(year, gp, session), daemon=True).start()

    def stop_loading(self):
        """Ferma caricamento"""
        self.running = False
        self.load_btn.config(state='normal', text='▶️ Carica')
        self.stop_btn.config(state='disabled')
        self.status_bar.config(text="Fermato")

    def update_loop(self, year, gp, session):
        """Loop aggiornamento"""
        url = f"{SERVER_URL}?year={year}&gp={gp}&session={session}"

        while self.running:
            try:
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    if data.get('status') == 'success':
                        self.current_data = data
                        self.root.after(0, self.update_display, data)
                    else:
                        self.root.after(0, self.show_error, data.get('error', 'Errore'))
                else:
                    self.root.after(0, self.show_error, f"HTTP {response.status_code}")

                time.sleep(UPDATE_INTERVAL)

            except Exception as e:
                self.root.after(0, self.show_error, str(e))
                time.sleep(UPDATE_INTERVAL)

    def update_display(self, data):
        """Aggiorna display"""
        session_info = data.get('session_info', 'Sessione')
        self.session_label.config(text=session_info)

        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.config(text=f"Aggiornato: {current_time}")

        self.update_table(data.get('drivers', []))

        total = len(data.get('drivers', []))
        self.status_bar.config(text=f"✅ {total} piloti | Aggiornato: {current_time}")

    def update_table(self, drivers):
        """Aggiorna tabella con COLORI"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Trova miglior tempo
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

        # Inserisci piloti con colori
        for driver in sorted(drivers, key=lambda x: x.get('position', 99)):
            pos = driver.get('position', '')
            name = driver.get('driver_name', 'N/A')
            team = driver.get('team', 'N/A')
            gap = driver.get('gap_to_leader', 'N/A')
            best = driver.get('best_lap_time', 'N/A')
            compound = driver.get('compound', 'N/A')
            pit = driver.get('pit_stops', 0)
            status = 'RUNNING'
            delta = driver.get('delta_to_best', 'N/A')

            # Tag speciali
            tags = []
            if gap == 'Leader' or gap == '0' or gap == '+0.000':
                tags.append('leader')
            elif name == fastest_driver:
                tags.append('fastest')

            # Colori personalizzati per team e gomme
            team_color = self.get_team_color(team)
            tyre_color = self.get_tyre_color(compound)

            # Crea tag unico per questa riga
            row_tag = f"row_{pos}"
            self.tree.tag_configure(row_tag, foreground=COLORS['white'])

            # Inserisci con tag
            item_id = self.tree.insert('', 'end',
                                       values=(pos, name, team, gap, best, compound, pit, status, delta),
                                       tags=(row_tag, *tags))

            # Applica colori dopo l'inserimento
            self.apply_cell_colors(item_id, team, compound, team_color, tyre_color)

    def apply_cell_colors(self, item_id, team, compound, team_color, tyre_color):
        """Applica colori alle celle specifiche"""
        try:
            # Colore TEAM (colonna 2)
            self.tree.set(item_id, 'team', team)

            # Usa tag per colorare il team
            team_tag = f"team_{team.replace(' ', '_')}"
            if team_tag not in self.tree.tag_names():
                self.tree.tag_configure(team_tag, foreground=team_color)

            # Aggiungi tag team alla riga
            current_tags = list(self.tree.item(item_id, 'tags'))
            if team_tag not in current_tags:
                self.tree.item(item_id, tags=tuple(current_tags + [team_tag]))

            # Colore GOMME (colonna 5)
            self.tree.set(item_id, 'tyre', compound)

            # Usa tag per colorare le gomme
            tyre_tag = f"tyre_{compound}"
            if tyre_tag not in self.tree.tag_names():
                self.tree.tag_configure(tyre_tag, foreground=tyre_color)

            # Aggiungi tag gomme alla riga
            current_tags = list(self.tree.item(item_id, 'tags'))
            if tyre_tag not in current_tags:
                self.tree.item(item_id, tags=tuple(current_tags + [tyre_tag]))

        except Exception as e:
            print(f"Errore applicazione colori: {e}")

    def show_driver_details(self, event):
        """Mostra popup dettagli pilota"""
        selection = self.tree.selection()
        if not selection or not self.current_data:
            return

        item = selection[0]
        values = self.tree.item(item, 'values')
        if not values:
            return

        driver_name = values[1]

        driver_data = None
        for driver in self.current_data.get('drivers', []):
            if driver.get('driver_name') == driver_name:
                driver_data = driver
                break

        if not driver_data:
            return

        popup = tk.Toplevel(self.root)
        popup.title(f"📊 {driver_data['driver_name']}")
        popup.geometry("500x600")
        popup.configure(bg=COLORS['bg'])
        popup.resizable(False, False)

        popup.transient(self.root)
        popup.grab_set()

        main_frame = tk.Frame(popup, bg=COLORS['bg'])
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        canvas = tk.Canvas(main_frame, bg=COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        content_frame = tk.Frame(canvas, bg=COLORS['bg'])

        content_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        canvas.create_window((0, 0), window=content_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.create_popup_content(content_frame, driver_data)

    def create_popup_content(self, parent, driver_data):
        """Crea contenuto popup con COLORI"""

        # 1. INTESTAZIONE
        header_frame = tk.Frame(parent, bg=COLORS['bg'])
        header_frame.pack(fill='x', pady=(0, 20))

        tk.Label(header_frame,
                 text=f"🏎️ {driver_data['driver_name']}",
                 font=('Arial', 16, 'bold'),
                 bg=COLORS['bg'],
                 fg=COLORS['yellow']).pack()

        # Team con COLORE
        team = driver_data.get('team', 'Unknown')
        team_color = self.get_team_color(team)
        team_label = tk.Label(header_frame,
                              text=f"{driver_data['driver_code']} | {team} | P{driver_data['position']}",
                              font=('Arial', 12),
                              bg=COLORS['bg'],
                              fg=team_color)  # COLORE TEAM
        team_label.pack(pady=5)

        # 2. INFORMAZIONI BASE
        base_frame = tk.LabelFrame(parent, text=" Informazioni Base ",
                                   font=('Arial', 11, 'bold'),
                                   bg=COLORS['bg_light'],
                                   fg=COLORS['white'],
                                   padx=15,
                                   pady=10)
        base_frame.pack(fill='x', pady=5)

        info_data = [
            ("Nome in codice", driver_data['driver_code']),
            ("Numero", driver_data['driver_number']),
            ("Team", driver_data['team']),  # Team - colorato dopo
            ("Posizione", f"P{driver_data['position']}"),
            ("Giro attuale", driver_data.get('lap_number', 'N/A'))
        ]

        for i, (label, value) in enumerate(info_data):
            tk.Label(base_frame, text=label + ":",
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).grid(row=i, column=0, sticky='w', padx=5, pady=2)

            # Colore speciale per TEAM
            if label == "Team":
                team_color = self.get_team_color(str(value))
                value_label = tk.Label(base_frame, text=str(value),
                                       font=('Arial', 10, 'bold'),
                                       bg=COLORS['bg_light'],
                                       fg=team_color)  # COLORE TEAM
            else:
                value_label = tk.Label(base_frame, text=str(value),
                                       font=('Arial', 10, 'bold'),
                                       bg=COLORS['bg_light'],
                                       fg=COLORS['white'])

            value_label.grid(row=i, column=1, sticky='w', padx=5, pady=2)

        # 3. TEMPI E PERFORMANCE
        times_frame = tk.LabelFrame(parent, text=" Tempi e Performance ",
                                    font=('Arial', 11, 'bold'),
                                    bg=COLORS['bg_light'],
                                    fg=COLORS['white'],
                                    padx=15,
                                    pady=10)
        times_frame.pack(fill='x', pady=10)

        # Miglior Giro (in VERDE)
        best_lap = driver_data.get('best_lap_time', 'N/A')
        best_lap_row = tk.Frame(times_frame, bg=COLORS['bg_light'])
        best_lap_row.pack(fill='x', pady=3)

        tk.Label(best_lap_row, text="Miglior Giro:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left', padx=5)

        tk.Label(best_lap_row, text=best_lap,
                 font=('Consolas', 11, 'bold'),
                 bg=COLORS['bg_light'],
                 fg=COLORS['green']).pack(side='left', padx=5)

        if driver_data.get('best_lap_number'):
            tk.Label(best_lap_row, text=f"(Giro {driver_data['best_lap_number']})",
                     font=('Arial', 9),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).pack(side='left', padx=5)

        # Gap dal pilota davanti
        gap_ahead = driver_data.get('gap_to_ahead', 'N/A')
        gap_row = tk.Frame(times_frame, bg=COLORS['bg_light'])
        gap_row.pack(fill='x', pady=3)

        tk.Label(gap_row, text="Gap da Davanti:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left', padx=5)

        tk.Label(gap_row, text=gap_ahead,
                 font=('Consolas', 11, 'bold'),
                 bg=COLORS['bg_light'],
                 fg=COLORS['yellow']).pack(side='left', padx=5)

        # Ultimo giro / Giro corrente
        if driver_data.get('current_lap'):
            lap_type = "Giro Corrente:"
            lap_time = "In corso"
        else:
            lap_type = "Ultimo Giro:"
            lap_time = driver_data.get('last_lap_time', 'N/A')

        current_row = tk.Frame(times_frame, bg=COLORS['bg_light'])
        current_row.pack(fill='x', pady=3)

        tk.Label(current_row, text=lap_type,
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left', padx=5)

        tk.Label(current_row, text=lap_time,
                 font=('Consolas', 11),
                 bg=COLORS['bg_light'],
                 fg=COLORS['blue']).pack(side='left', padx=5)

        # DELTA dal miglior giro
        delta = driver_data.get('delta_to_best', 'N/A')
        delta_row = tk.Frame(times_frame, bg=COLORS['bg_light'])
        delta_row.pack(fill='x', pady=3)

        tk.Label(delta_row, text="Delta dal Migliore:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left', padx=5)

        delta_color = COLORS['red'] if delta != 'N/A' and delta.startswith('+') else COLORS['green']
        tk.Label(delta_row, text=delta,
                 font=('Consolas', 11, 'bold'),
                 bg=COLORS['bg_light'],
                 fg=delta_color).pack(side='left', padx=5)

        if delta != 'N/A':
            if delta.startswith('+'):
                meaning = "(più lento)"
            elif delta.startswith('-'):
                meaning = "(più veloce!)"
            else:
                meaning = "(uguale)"

            tk.Label(delta_row, text=meaning,
                     font=('Arial', 9),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).pack(side='left', padx=5)

        # 4. GOMME E PIT STOP
        tyres_frame = tk.LabelFrame(parent, text=" Gomme e Pit Stop ",
                                    font=('Arial', 11, 'bold'),
                                    bg=COLORS['bg_light'],
                                    fg=COLORS['white'],
                                    padx=15,
                                    pady=10)
        tyres_frame.pack(fill='x', pady=10)

        # Gomma attuale con COLORE
        compound = driver_data.get('compound', 'N/A')
        tyre_life = driver_data.get('tyre_life', 0)
        tyre_color = self.get_tyre_color(compound)

        current_tyre_row = tk.Frame(tyres_frame, bg=COLORS['bg_light'])
        current_tyre_row.pack(fill='x', pady=3)

        tk.Label(current_tyre_row, text="Gomma Attuale:",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left', padx=5)

        # Immagine gomma
        if compound in self.tyre_images:
            tk.Label(current_tyre_row, image=self.tyre_images[compound],
                     bg=COLORS['bg_light']).pack(side='left', padx=5)

        # Testo gomma con COLORE
        tk.Label(current_tyre_row, text=compound,
                 font=('Arial', 10, 'bold'),
                 bg=COLORS['bg_light'],
                 fg=tyre_color).pack(side='left', padx=5)  # COLORE GOMMA

        tk.Label(current_tyre_row, text=f"(Usura: {tyre_life} giri)",
                 font=('Arial', 9),
                 bg=COLORS['bg_light'],
                 fg=COLORS['gray']).pack(side='left', padx=5)

        # Pit stop
        pit_stops = driver_data.get('pit_stops', 0)
        tk.Label(tyres_frame, text=f"Pit Stop effettuati: {pit_stops}",
                 font=('Arial', 10),
                 bg=COLORS['bg_light'],
                 fg=COLORS['white'],
                 anchor='w').pack(fill='x', pady=3)

        # 5. STORIA GOMME con COLORI
        history = driver_data.get('tyre_history', [])
        if history:
            history_frame = tk.LabelFrame(parent, text=" Storia Gomme ",
                                          font=('Arial', 11, 'bold'),
                                          bg=COLORS['bg_light'],
                                          fg=COLORS['white'],
                                          padx=15,
                                          pady=10)
            history_frame.pack(fill='x', pady=10)

            # Frame per storia con scroll
            history_scroll_frame = tk.Frame(history_frame, bg=COLORS['bg_light'])
            history_scroll_frame.pack(fill='both', expand=True)

            history_canvas = tk.Canvas(history_scroll_frame, bg=COLORS['bg_light'], height=80, highlightthickness=0)
            history_scrollbar = ttk.Scrollbar(history_scroll_frame, orient='horizontal', command=history_canvas.xview)
            history_content = tk.Frame(history_canvas, bg=COLORS['bg_light'])

            history_content.bind('<Configure>',
                                 lambda e: history_canvas.configure(scrollregion=history_canvas.bbox('all')))

            history_canvas.create_window((0, 0), window=history_content, anchor='nw')
            history_canvas.configure(xscrollcommand=history_scrollbar.set)

            history_canvas.pack(side='top', fill='x')
            history_scrollbar.pack(side='bottom', fill='x')

            # Mostra storia con colori
            for i, tyre in enumerate(history):
                compound = tyre.get('compound', 'UNKNOWN')
                stint = tyre.get('stint', 1)
                lap_on = tyre.get('lap_on', '?')
                life = tyre.get('tyre_life', 0)
                tyre_color = self.get_tyre_color(compound)

                tyre_frame = tk.Frame(history_content, bg=COLORS['bg_light'])
                tyre_frame.pack(side='left', padx=5)

                # Emoji per compound
                emoji = {
                    'SOFT': '🔴',
                    'MEDIUM': '🟡',
                    'HARD': '⚪',
                    'INTER': '🌧️',
                    'WET': '🌀'
                }.get(compound, '❓')

                tk.Label(tyre_frame, text=f"{emoji}",
                         font=('Arial', 12),
                         bg=COLORS['bg_light']).pack()

                tk.Label(tyre_frame, text=compound,
                         font=('Arial', 9, 'bold'),
                         bg=COLORS['bg_light'],
                         fg=tyre_color).pack()  # COLORE GOMMA

                tk.Label(tyre_frame, text=f"Stint {stint}",
                         font=('Arial', 8),
                         bg=COLORS['bg_light'],
                         fg=COLORS['gray']).pack()

                if life > 0:
                    tk.Label(tyre_frame, text=f"({life} giri)",
                             font=('Arial', 8),
                             bg=COLORS['bg_light'],
                             fg=COLORS['gray']).pack()

                # Freccia tra le gomme (tranche l'ultima)
                if i < len(history) - 1:
                    arrow_frame = tk.Frame(history_content, bg=COLORS['bg_light'])
                    arrow_frame.pack(side='left')
                    tk.Label(arrow_frame, text="→",
                             font=('Arial', 12),
                             bg=COLORS['bg_light'],
                             fg=COLORS['gray']).pack(pady=10)

        else:
            history_frame = tk.LabelFrame(parent, text=" Storia Gomme ",
                                          font=('Arial', 11, 'bold'),
                                          bg=COLORS['bg_light'],
                                          fg=COLORS['white'],
                                          padx=15,
                                          pady=10)
            history_frame.pack(fill='x', pady=10)

            tk.Label(history_frame, text="Nessuna storia gomme disponibile",
                     font=('Arial', 10),
                     bg=COLORS['bg_light'],
                     fg=COLORS['gray']).pack()

        # 6. BOTTONE CHIUDI
        close_btn = tk.Button(parent, text="CHIUDI",
                              command=lambda: parent.winfo_toplevel().destroy(),
                              bg=COLORS['red'],
                              fg='white',
                              font=('Arial', 11, 'bold'),
                              padx=30,
                              pady=5)
        close_btn.pack(pady=20)

    def show_error(self, message):
        """Mostra errore"""
        self.status_bar.config(text=f"❌ Errore: {message}", fg=COLORS['red'])

        if not self.running:
            messagebox.showerror("Errore", message)

    def on_close(self):
        """Gestione chiusura"""
        self.running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = F1Tracker(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()