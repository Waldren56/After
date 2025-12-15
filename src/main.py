# main.py (CODICE COMPLETO E AGGIORNATO - FIX CARICAMENTO DATI)

from flask import Flask, render_template, jsonify
import fastf1 as ff1
import pandas as pd
import numpy as np 
import os 
from fastf1 import plotting 

plotting.setup_mpl() 

app = Flask(__name__)

YEAR = 2024
ROUND = 9 
RACE_SESSION = 'R' 

# Impostazione della cache per FastF1
CACHE_PATH = './fastf1_cache'
if not os.path.exists(CACHE_PATH):
    os.makedirs(CACHE_PATH)
ff1.Cache.enable_cache(CACHE_PATH)


# --- Variabile Globale per la Sessione ---
race_session_data = None

@app.before_request
def load_session():
    """Carica la sessione una sola volta all'avvio del server."""
    global race_session_data
    if race_session_data is None:
        try:
            session = ff1.get_session(YEAR, ROUND, RACE_SESSION)
            
            # *** FIX CRITICO: Caricamento completo dei dati dei giri e del timing ***
            session.load(laps=True, telemetry=True, weather=False) 
            # **********************************************************************
            
            race_session_data = session
            print(f"Server: Sessione {session.event.get('EventName')} (Tutti i dati) caricata con successo.")
        except Exception as e:
            print(f"Server ERRORE: Impossibile caricare la sessione FastF1: {e}")
            race_session_data = None
        
# --- Funzione per formattare il tempo ---
def format_time(td):
    if pd.isna(td):
        return "N/A"
    try:
        total_seconds = td.total_seconds() 
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds - int(total_seconds)) * 1000)
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    except AttributeError:
        return str(td)
    except Exception:
        return "N/A"


# --- ROUTE 1: HomePage (Tabella Risultati) ---
@app.route('/')
def home():
    if not race_session_data:
        return render_template('error.html', message="Dati FastF1 non disponibili. Controlla la console del server.")

    session = race_session_data
    results = session.results
    
    race_name = session.event.get('EventName', 'Gara Sconosciuta')
    
    circuit_name = session.event.get('CircuitName')
    if not circuit_name:
        circuit_name = session.event.get('Circuit', {}).get('Name', 'Circuito Sconosciuto')

    data_for_template = []
    
    for driver_id, row in results.iterrows():
        time_str = row['Status']
        if pd.notna(row['Time']):
            time_str = format_time(row['Time'])
        
        data_for_template.append({
            'DriverId': str(driver_id), 
            'Pos': row['Position'],
            'Pilota': row['BroadcastName'],
            'Scuderia': row['TeamName'],
            'Giri': row['Laps'],
            'Tempo/Status': time_str, 
            'Punti': int(row['Points']) if pd.notna(row['Points']) else 0
        })

    return render_template(
        'race_results.html',
        year=YEAR,
        race_name=race_name,
        circuit_name=circuit_name,
        results=data_for_template
    )

# --- ROUTE 2: Endpoint Dettagli Pilota (API) ---
@app.route('/api/details/<driver_id>')
def get_driver_details(driver_id):
    if not race_session_data: 
        return jsonify({'error': 'Sessione non caricata'}), 500
    
    session = race_session_data 
    
    # FIX CHIAVE: Prova prima intero, poi stringa
    try:
        driver_id_key = int(driver_id)
        results = session.results.loc[driver_id_key] 
    except KeyError:
        try:
            driver_id_key = str(driver_id)
            results = session.results.loc[driver_id_key]
        except KeyError:
            return jsonify({'error': f'Pilota ID {driver_id} non trovato nel DataFrame risultati.'}), 404
    except ValueError:
        return jsonify({'error': f'ID pilota non valido: {driver_id}'}), 400
    
    try:
        laps = session.laps.pick_driver(driver_id) 
        
        # --- GESTIONE ROBUSTA DEI TEMPI ---
        fastest_lap_time = np.nan
        last_lap_time = np.nan
        delta_time = np.nan
        
        if not laps.empty:
            fastest_lap = laps.pick_fastest()
            last_lap = laps.loc[laps['LapNumber'].idxmax()]
            
            if fastest_lap is not None and pd.notna(fastest_lap['LapTime']):
                fastest_lap_time = fastest_lap['LapTime']
            
            if last_lap is not None and pd.notna(last_lap['LapTime']):
                last_lap_time = last_lap['LapTime']

            if pd.notna(fastest_lap_time) and pd.notna(last_lap_time):
                delta_time = last_lap_time - fastest_lap_time
        # --- FINE GESTIONE ROBUSTA DEI TEMPI ---

        team_color = plotting.get_team_color(results['TeamName'], session=session)
        
        # --- FIX: Gestione robusta degli Stint/Gomme ---
        tyre_history = []
        if not laps.empty and 'TyreCompound' in laps.columns:
            try:
                stints = laps[['Stint', 'TyreCompound', 'LapNumber']].copy()
                if not stints.empty:
                    stint_groups = stints.groupby('Stint').agg(
                        start_lap=('LapNumber', 'min'),
                        end_lap=('LapNumber', 'max'),
                        tyre_compound=('TyreCompound', 'first')
                    ).reset_index()
                    stint_groups['giri'] = stint_groups['end_lap'] - stint_groups['start_lap'] + 1
                    
                    tyre_history = stint_groups[['tyre_compound', 'giri']].to_dict('records')
            except KeyError as e:
                print(f"Avviso: Colonna non trovata negli stint per {driver_id}: {e}")
                tyre_history = []
        else:
            # Nessun dato gomme disponibile
            tyre_history = []
        # --- FINE FIX STINT ---

        # Calcola il numero di pit stop (numero di stint - 1)
        if not laps.empty and 'Stint' in laps.columns:
            pit_stops_count = max(laps['Stint']) - 1 if max(laps['Stint']) > 1 else 0
        else:
            pit_stops_count = 0
        
        details = {
            'fullName': results['FullName'],
            'teamName': results['TeamName'],
            'teamColor': f"#{team_color}" if team_color else "#000000",
            'fastestLap': format_time(fastest_lap_time),
            'lastLap': format_time(last_lap_time),
            'delta': format_time(delta_time),
            'pitStopsCount': pit_stops_count, 
            'tyreHistory': tyre_history
        }
        
        return jsonify(details)
    
    except Exception as e:
        print(f"Errore CRITICO nel recupero dati per {driver_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Errore nel recupero dati dettagliati: {str(e)}'}), 500

# --- ROUTE 3: Endpoint Telemetria Pilota (API) ---
@app.route('/api/telemetry/<driver_id>')
def get_driver_telemetry(driver_id):
    if not race_session_data: return jsonify({'error': 'Sessione non caricata'}), 500
    session = race_session_data
    
    try:
        laps = session.laps.pick_driver(driver_id) 
        fastest_lap = laps.pick_fastest()
        
        if fastest_lap is None or fastest_lap.empty:
            return jsonify({'error': f"Nessun giro veloce trovato per il pilota {driver_id}"}), 404

        telemetry = fastest_lap.get_telemetry()
        
        all_laps_telemetry = session.laps.pick_drivers(driver_id).get_telemetry()
        all_laps_speed = all_laps_telemetry['Speed'].mean()

        N = 20 
        telemetry_data = {
            'Distance': telemetry['Distance'].iloc[::N].tolist(),
            'Speed': telemetry['Speed'].iloc[::N].tolist(),
            'Throttle': telemetry['Throttle'].iloc[::N].tolist(),
            'Brake': telemetry['Brake'].iloc[::N].tolist(),
        }
        
        avg_rpm = telemetry['RPM'].mean()

        return jsonify({
            'driverId': driver_id,
            'avgRaceSpeed': float(all_laps_speed) if pd.notna(all_laps_speed) else 0.0,
            'avgRpm': float(avg_rpm) if pd.notna(avg_rpm) else 0.0,
            'fastestLapTelemetry': telemetry_data
        })
        
    except KeyError:
        return jsonify({'error': f'Telemetria non disponibile per il pilota {driver_id}'}), 404
    except Exception as e:
        print(f"Errore nell'endpoint telemetria: {e}")
        return jsonify({'error': f'Errore nel recupero telemetria: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        load_session()
        
    app.run(debug=True)