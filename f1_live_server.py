import fastf1 as ff1
import fastf1.plotting
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
from flask import Flask, jsonify, request
from typing import Dict, List, Any, Optional
import warnings

warnings.filterwarnings('ignore')

# Abilita cache per performance
ff1.Cache.enable_cache('./f1_cache', ignore_version=False)

app = Flask(__name__)

# Dizionario per cache sessioni
_session_cache = {}
_CACHE_DURATION = 300  # 5 minuti


def safe_get(series, key, default=None):
    """Get sicuro da pandas Series"""
    try:
        val = series.get(key, default)
        return default if pd.isna(val) else val
    except:
        return default


def format_laptime(td):
    """Formatta Timedelta in MM:SS.sss"""
    if pd.isna(td) or td is None:
        return None

    try:
        total_seconds = td.total_seconds()
        if total_seconds <= 0 or total_seconds > 300:
            return None

        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds - int(total_seconds)) * 1000)

        return f"{minutes}:{seconds:02d}.{milliseconds:03d}"
    except:
        return None


def laptime_to_seconds(laptime_str):
    """Converte stringa tempo in secondi"""
    if laptime_str is None:
        return float('inf')

    try:
        if ':' in laptime_str:
            parts = laptime_str.split(':')
            if len(parts) == 2:
                minutes, rest = parts
                seconds, ms = rest.split('.')
                return int(minutes) * 60 + int(seconds) + float(f"0.{ms}")
        return float('inf')
    except:
        return float('inf')


def get_driver_details(session, driver_number):
    """Ottieni dettagli completi pilota"""
    try:
        driver = session.get_driver(driver_number)
        return {
            'full_name': driver.get('FullName', f"Driver {driver_number}"),
            'abbreviation': driver.get('Abbreviation', driver_number),
            'team': driver.get('TeamName', 'Unknown'),
            'driver_number': driver_number,
            'country': driver.get('Country', 'Unknown')
        }
    except:
        return {
            'full_name': f"Driver {driver_number}",
            'abbreviation': driver_number,
            'team': 'Unknown',
            'driver_number': driver_number,
            'country': 'Unknown'
        }


def get_tyre_history(laps, driver_code):
    """Ottieni cronologia completa gomme"""
    if laps.empty or 'Driver' not in laps.columns:
        return []

    driver_laps = laps[laps['Driver'] == driver_code].copy()
    if driver_laps.empty:
        return []

    # Ordina per giro
    driver_laps = driver_laps.sort_values('LapNumber')

    # Prendi solo giri con compound validi
    tyre_changes = driver_laps[driver_laps['Compound'].notna()].copy()
    if tyre_changes.empty:
        return []

    # Trova cambi gomme (cambio stint o compound)
    history = []
    last_compound = None
    last_stint = None

    for idx, lap in tyre_changes.iterrows():
        compound = str(lap['Compound']).upper().strip()
        stint = lap.get('Stint', 1)

        # Standardizza nomi compound
        if 'SOFT' in compound:
            compound_display = 'SOFT'
            emoji = '🔴'
        elif 'MEDIUM' in compound:
            compound_display = 'MEDIUM'
            emoji = '🟡'
        elif 'HARD' in compound:
            compound_display = 'HARD'
            emoji = '⚪'
        elif 'INTERMEDIATE' in compound:
            compound_display = 'INTER'
            emoji = '🌧️'
        elif 'WET' in compound:
            compound_display = 'WET'
            emoji = '🌀'
        else:
            compound_display = compound
            emoji = '❓'

        # Aggiungi solo se è un cambio
        if compound_display != last_compound or stint != last_stint:
            tyre_life = int(safe_get(lap, 'TyreLife', 0))
            history.append({
                'compound': compound_display,
                'emoji': emoji,
                'stint': stint,
                'lap_on': int(lap['LapNumber']),
                'tyre_life': tyre_life,
                'color': get_tyre_color(compound_display)
            })
            last_compound = compound_display
            last_stint = stint

    return history


def get_tyre_color(compound):
    """Colore per ogni tipo di gomma"""
    colors = {
        'SOFT': '#FF0000',  # Rosso
        'MEDIUM': '#FFD700',  # Giallo oro
        'HARD': '#FFFFFF',  # Bianco
        'INTER': '#00FF00',  # Verde
        'WET': '#0000FF'  # Blu
    }
    return colors.get(compound, '#808080')  # Grigio default


def calculate_driver_metrics(session, laps, driver_code, session_status):
    """Calcola tutte le metriche per un pilota"""
    metrics = {
        'delta_to_ahead': None,
        'current_lap_time': None,
        'delta_to_best': None,
        'lap_progress': None,
        'sector_times': [],
        'gap_to_leader_laptime': None,
        'gap_to_ahead_laptime': None
    }

    if laps.empty:
        return metrics

    # Filtra giri del pilota
    driver_laps = laps[laps['Driver'] == driver_code].copy()
    if driver_laps.empty:
        return metrics

    # Ordina per giro
    driver_laps = driver_laps.sort_values('LapNumber')
    last_lap = driver_laps.iloc[-1] if not driver_laps.empty else None

    # 1. MIGLIOR GIRO
    valid_laps = driver_laps[driver_laps['LapTime'].notna()].copy()
    if not valid_laps.empty:
        best_lap_idx = valid_laps['LapTime'].idxmin()
        best_lap = valid_laps.loc[best_lap_idx]
        metrics['best_lap_time'] = format_laptime(best_lap['LapTime'])
        metrics['best_lap_number'] = int(best_lap['LapNumber'])
        metrics['best_lap_seconds'] = best_lap['LapTime'].total_seconds()
    else:
        metrics['best_lap_time'] = None
        metrics['best_lap_seconds'] = None

    # 2. ULTIMO GIRO COMPLETATO
    completed_laps = driver_laps[driver_laps['LapTime'].notna()]
    if not completed_laps.empty:
        last_completed = completed_laps.iloc[-1]
        metrics['last_lap_time'] = format_laptime(last_completed['LapTime'])
        metrics['last_lap_seconds'] = last_completed['LapTime'].total_seconds()
        metrics['last_lap_number'] = int(last_completed['LapNumber'])

        # Delta dal miglior giro - USANDO NUOVA FUNZIONE
        metrics['delta_to_best'] = calculate_delta_to_best(driver_laps)
    else:
        metrics['last_lap_time'] = None
        metrics['last_lap_seconds'] = None

    # 3. GIRO IN CORSO (se sessione live)
    if session_status == 'live' and last_lap is not None:
        current_lap_num = int(last_lap['LapNumber'])

        # Cerca tempi settore per giro corrente
        sector_cols = [col for col in driver_laps.columns if 'Sector' in col]
        current_sectors = []

        for sector in ['Sector1Time', 'Sector2Time', 'Sector3Time']:
            if sector in driver_laps.columns and not pd.isna(last_lap.get(sector)):
                sector_time = format_laptime(last_lap[sector])
                current_sectors.append(sector_time)

        metrics['current_lap'] = current_lap_num
        metrics['sector_times'] = current_sectors

        # Se ci sono tutti e 3 i settori, calcola tempo giro
        if len(current_sectors) == 3:
            try:
                s1 = laptime_to_seconds(current_sectors[0])
                s2 = laptime_to_seconds(current_sectors[1])
                s3 = laptime_to_seconds(current_sectors[2])
                if all(t != float('inf') for t in [s1, s2, s3]):
                    total = s1 + s2 + s3
                    metrics['current_lap_time'] = format_laptime(
                        pd.Timedelta(seconds=total)
                    )
            except:
                pass

    # 4. CALCOLA GAP TRA PILOTI - VERSIONE SEMPLIFICATA MA FUNZIONANTE
    try:
        if session_status in ['R', 'S', 'Q', 'SQ', 'FP1', 'FP2', 'FP3']:
            # Usa funzione separata per calcolare tutti i gap
            all_gaps = calculate_gaps_for_all(laps, session_status)

            if driver_code in all_gaps:
                driver_gaps = all_gaps[driver_code]
                metrics['gap_to_leader'] = driver_gaps.get('gap_to_leader', 'N/A')  # NOME CORRETTO
                metrics['gap_to_ahead'] = driver_gaps.get('gap_to_ahead', 'N/A')

                # Aggiorna anche i vecchi nomi per compatibilità
                metrics['gap_to_leader_laptime'] = driver_gaps.get('gap_to_leader', 'N/A')
                metrics['gap_to_ahead_laptime'] = driver_gaps.get('gap_to_ahead', 'N/A')
    except Exception as e:
        print(f"Errore calcolo gap: {e}")

    return metrics


def calculate_gaps_for_all(laps, session_type):
    """Calcola gap leader e gap ahead per TUTTE le sessioni - VERSIONE FIXED"""
    gaps = {}

    if laps.empty or 'Driver' not in laps.columns:
        return gaps

    # Per QUALIFICHE e PROVE: usa miglior tempo
    if session_type in ['Q', 'SQ', 'FP1', 'FP2', 'FP3']:
        best_times = {}

        for driver in laps['Driver'].unique():
            driver_laps = laps[laps['Driver'] == driver]
            valid_laps = driver_laps[driver_laps['LapTime'].notna()]

            if not valid_laps.empty:
                best_time = valid_laps['LapTime'].min().total_seconds()
                best_times[driver] = best_time

        if best_times:
            # Ordina per tempo (dal più veloce)
            sorted_times = sorted(best_times.items(), key=lambda x: x[1])

            for i, (driver, time_sec) in enumerate(sorted_times):
                if i == 0:
                    gaps[driver] = {
                        'gap_to_leader': "Leader",
                        'gap_to_ahead': "Leader",  # Il leader non ha nessuno davanti
                        'position': i + 1
                    }
                else:
                    gap_to_leader = time_sec - sorted_times[0][1]
                    gap_ahead = time_sec - sorted_times[i - 1][1]  # Differenza col pilota PRIMA

                    gaps[driver] = {
                        'gap_to_leader': f"+{gap_to_leader:.3f}",
                        'gap_to_ahead': f"+{gap_ahead:.3f}",  # Questo è gap_to_ahead
                        'position': i + 1
                    }

    # Per GARE e SPRINT
    elif session_type in ['R', 'S']:
        try:
            # Prendi l'ultimo giro di ogni pilota
            latest_laps = laps.sort_values('LapNumber').groupby('Driver').last().reset_index()

            # Usa la colonna Position se disponibile
            if 'Position' in latest_laps.columns:
                latest_laps = latest_laps[latest_laps['Position'].notna()].copy()

                # Converti a numerico
                latest_laps['Position'] = pd.to_numeric(latest_laps['Position'], errors='coerce')
                latest_laps = latest_laps[latest_laps['Position'].notna()]
                latest_laps['Position'] = latest_laps['Position'].astype(int)

                # Ordina per posizione
                latest_laps = latest_laps.sort_values('Position')

                for i, row in latest_laps.iterrows():
                    driver = row['Driver']
                    pos = int(row['Position'])

                    if pos == 1:
                        gaps[driver] = {
                            'gap_to_leader': "Leader",
                            'gap_to_ahead': "Leader",  # Il leader non ha nessuno davanti
                            'position': pos
                        }
                    else:
                        # Per gara, calcola gap ahead se abbiamo Time
                        if 'Time' in row and pd.notna(row['Time']):
                            # Trova tempo del pilota davanti (posizione - 1)
                            ahead_pos = pos - 1
                            ahead_row = latest_laps[latest_laps['Position'] == ahead_pos]

                            if not ahead_row.empty:
                                ahead_time = ahead_row.iloc[0]['Time'].total_seconds()
                                driver_time = row['Time'].total_seconds()
                                gap_ahead = driver_time - ahead_time

                                # Trova tempo del leader (posizione 1)
                                leader_row = latest_laps[latest_laps['Position'] == 1]
                                if not leader_row.empty:
                                    leader_time = leader_row.iloc[0]['Time'].total_seconds()
                                    gap_to_leader = driver_time - leader_time

                                    gaps[driver] = {
                                        'gap_to_leader': f"+{gap_to_leader:.3f}",
                                        'gap_to_ahead': f"+{gap_ahead:.3f}",  # Gap dal pilota immediatamente davanti
                                        'position': pos
                                    }
                                else:
                                    gaps[driver] = {
                                        'gap_to_leader': f"P+{pos - 1}",
                                        'gap_to_ahead': f"+{gap_ahead:.3f}",
                                        'position': pos
                                    }
                            else:
                                # Non trovato pilota davanti, mostra solo gap leader
                                gaps[driver] = {
                                    'gap_to_leader': f"P+{pos - 1}",
                                    'gap_to_ahead': "N/A",  # Non calcolabile
                                    'position': pos
                                }
                        else:
                            # Fallback: mostra posizioni dietro
                            gaps[driver] = {
                                'gap_to_leader': f"P+{pos - 1}",
                                'gap_to_ahead': "N/A",  # Non calcolabile senza tempo
                                'position': pos
                            }

            # Fallback se non c'è Position ma c'è Time
            elif 'Time' in latest_laps.columns:
                latest_laps = latest_laps[latest_laps['Time'].notna()].copy()
                latest_laps['TotalTimeSec'] = latest_laps['Time'].dt.total_seconds()
                latest_laps = latest_laps.sort_values('TotalTimeSec')

                for i, row in latest_laps.iterrows():
                    driver = row['Driver']

                    if i == 0:
                        gaps[driver] = {
                            'gap_to_leader': "Leader",
                            'gap_to_ahead': "Leader",  # Il leader non ha nessuno davanti
                            'position': i + 1
                        }
                    else:
                        gap_to_leader = row['TotalTimeSec'] - latest_laps.iloc[0]['TotalTimeSec']
                        gap_ahead = row['TotalTimeSec'] - latest_laps.iloc[i - 1][
                            'TotalTimeSec']  # Differenza col pilota PRIMA

                        gaps[driver] = {
                            'gap_to_leader': f"+{gap_to_leader:.3f}",
                            'gap_to_ahead': f"+{gap_ahead:.3f}",  # Questo è gap_to_ahead
                            'position': i + 1
                        }

        except Exception as e:
            print(f"Errore calcolo gap gara: {e}")
            # Fallback semplice
            if 'Driver' in laps.columns:
                drivers = laps['Driver'].unique()
                for i, driver in enumerate(drivers):
                    if i == 0:
                        gaps[driver] = {
                            'gap_to_leader': "Leader",
                            'gap_to_ahead': "Leader",  # Il leader non ha nessuno davanti
                            'position': 1
                        }
                    else:
                        gaps[driver] = {
                            'gap_to_leader': f"P+{i}",
                            'gap_to_ahead': "N/A",  # Non calcolabile senza dati
                            'position': i + 1
                        }

    return gaps


def calculate_delta_to_best(driver_laps):
    """Calcola delta tra ultimo giro e miglior giro del pilota"""
    if driver_laps.empty:
        return "N/A"

    # Filtra giri validi
    valid_laps = driver_laps[driver_laps['LapTime'].notna()].copy()
    if len(valid_laps) < 2:  # Almeno 2 giri per confronto
        return "N/A"

    # Ordina per giro
    valid_laps = valid_laps.sort_values('LapNumber')

    # Trova miglior giro
    best_lap_idx = valid_laps['LapTime'].idxmin()
    best_lap = valid_laps.loc[best_lap_idx]
    best_time = best_lap['LapTime'].total_seconds()

    # Prendi ultimo giro (escluso il miglior se è l'ultimo)
    last_lap = valid_laps.iloc[-1]
    last_time = last_lap['LapTime'].total_seconds()

    # Calcola delta
    delta = last_time - best_time

    # Formatta: + per più lento, - per più veloce, ±0.000 per uguale
    if delta > 0:
        return f"+{delta:.3f}"
    elif delta < 0:
        return f"{delta:.3f}"  # negativo mostra già il -
    else:
        return "±0.000"

def get_session_status(session):
    """Ottieni stato sessione"""
    status = {
        'flag': 'UNKNOWN',
        'session_status': 'Unknown',
        'total_laps': None,
        'current_lap': None,
        'is_live': False,
        'is_finished': False
    }

    try:
        # Controlla se sessione è finita
        if hasattr(session, 'session_status'):
            if not session.session_status.empty:
                last_status = session.session_status.iloc[-1]
                status_code = str(last_status.get('Status', ''))

                flag_map = {
                    '1': 'GREEN', '2': 'YELLOW', '3': 'DOUBLE_YELLOW',
                    '4': 'GREEN', '5': 'RED', '6': 'CHEQUERED'
                }

                status['flag'] = flag_map.get(status_code, 'UNKNOWN')
                status['session_status'] = last_status.get('Message', 'Unknown')

                if status_code == '6':
                    status['is_finished'] = True

        # Ottieni numero giri
        if hasattr(session, 'total_laps') and session.total_laps:
            status['total_laps'] = int(session.total_laps)
        elif hasattr(session, 'laps') and not session.laps.empty:
            status['total_laps'] = int(session.laps['LapNumber'].max())

        # Determina se è live (semplificato)
        status['is_live'] = not status['is_finished']

    except Exception as e:
        print(f"Errore stato sessione: {e}")

    return status


@app.route('/f1-data-detailed')
def f1_data_detailed():
    """Endpoint per dati dettagliati"""
    try:
        year = request.args.get('year', '2025')
        gp = request.args.get('gp', 'Qatar')
        session_type = request.args.get('session', 'R')

        cache_key = f"{year}_{gp}_{session_type}"
        current_time = time.time()

        # Controlla cache
        if cache_key in _session_cache:
            cached_data, timestamp = _session_cache[cache_key]
            if current_time - timestamp < _CACHE_DURATION:
                print(f"Usando cache per {cache_key}")
                return jsonify(cached_data)

        print(f"Caricamento sessione: {year} {gp} {session_type}")

        # Carica sessione FastF1
        session = ff1.get_session(int(year), gp, session_type)

        # Carica dati necessari
        if session_type in ['R', 'S']:
            session.load(laps=True, telemetry=False, weather=False, messages=True)
        else:
            session.load(laps=True, telemetry=False, weather=False, messages=False)

        # Prepara dati sessione
        laps_data = session.laps.copy()
        session_status = get_session_status(session)

        # Assicurati colonna Driver
        if 'Driver' not in laps_data.columns and 'DriverNumber' in laps_data.columns:
            driver_map = {}
            for drv_num in session.drivers:
                try:
                    drv_info = session.get_driver(str(drv_num))
                    abbrev = drv_info.get('Abbreviation', str(drv_num))
                    driver_map[str(drv_num)] = abbrev
                except:
                    driver_map[str(drv_num)] = str(drv_num)
            laps_data['Driver'] = laps_data['DriverNumber'].astype(str).map(driver_map)

        # Raccogli dati piloti
        drivers_info = []
        driver_codes = laps_data['Driver'].unique() if not laps_data.empty else []

        for driver_code in driver_codes:
            try:
                # Ottieni ultimo giro del pilota
                driver_laps = laps_data[laps_data['Driver'] == driver_code]
                if driver_laps.empty:
                    continue

                last_lap = driver_laps.sort_values('LapNumber').iloc[-1]
                driver_number = str(safe_get(last_lap, 'DriverNumber', ''))

                # Dettagli pilota
                driver_details = get_driver_details(session, driver_number)

                # Calcola metriche
                metrics = calculate_driver_metrics(
                    session, laps_data, driver_code, session_type
                )

                # Storia gomme
                tyre_history = get_tyre_history(laps_data, driver_code)
                current_compound = str(safe_get(last_lap, 'Compound', 'N/A')).upper()
                current_tyre_life = int(safe_get(last_lap, 'TyreLife', 0))

                # Posizione
                position = int(safe_get(last_lap, 'Position', 99))

                # Controlla se ritirato
                is_retired = False
                try:
                    if hasattr(session, 'results'):
                        results = session.results
                        driver_result = results[results['DriverNumber'] == driver_number]
                        if not driver_result.empty:
                            status = str(driver_result.iloc[0].get('Status', '')).upper()
                            if 'RETIRED' in status or 'DNF' in status or 'DNS' in status:
                                is_retired = True
                except:
                    pass

                # Dati completi pilota
                driver_data = {
                    # Identificazione
                    'driver_name': driver_details['full_name'],
                    'driver_code': driver_details['abbreviation'],
                    'driver_number': driver_number,
                    'team': driver_details['team'],
                    'country': driver_details['country'],

                    # Posizione e stato
                    'position': position,
                    'status': 'RETIRED' if is_retired else 'RUNNING',

                    # Tempi
                    'best_lap_time': metrics['best_lap_time'],
                    'best_lap_number': metrics.get('best_lap_number'),
                    'last_lap_time': metrics.get('last_lap_time'),
                    'last_lap_number': metrics.get('last_lap_number'),

                    # Gap
                    'gap_to_leader': metrics.get('gap_to_leader_laptime'),
                    'gap_to_ahead': metrics.get('gap_to_ahead_laptime'),

                    # Delta
                    'delta_to_best': metrics.get('delta_to_best'),

                    # Giro corrente (se live)
                    'current_lap': metrics.get('current_lap'),
                    'current_lap_time': metrics.get('current_lap_time'),
                    'sector_times': metrics.get('sector_times', []),

                    # Gomme
                    'compound': current_compound,
                    'compound_emoji': get_tyre_color(current_compound),
                    'tyre_life': current_tyre_life,
                    'pit_stops': max(0, int(safe_get(last_lap, 'Stint', 1)) - 1),
                    'tyre_history': tyre_history,

                    # Altro
                    'lap_number': int(safe_get(last_lap, 'LapNumber', 0)),
                    'points': float(safe_get(last_lap, 'Points', 0))
                }

                drivers_info.append(driver_data)

            except Exception as e:
                print(f"Errore elaborazione pilota {driver_code}: {e}")
                continue

        # Ordina per posizione
        drivers_info.sort(key=lambda x: (
            0 if x['status'] == 'RUNNING' else 1,
            x['position']
        ))

        # Ri-assigna posizioni dopo ordinamento
        running_pos = 1
        retired_pos = len([d for d in drivers_info if d['status'] == 'RUNNING']) + 1

        for driver in drivers_info:
            if driver['status'] == 'RUNNING':
                driver['position'] = running_pos
                running_pos += 1
            else:
                driver['position'] = retired_pos
                retired_pos += 1

        # Risposta finale
        response_data = {
            'status': 'success',
            'session_info': f"{year} {gp} - {session_type}",
            'session_type': session_type,
            'session_status': session_status,
            'drivers': drivers_info,
            'timestamp': datetime.now().isoformat(),
            'total_drivers': len(drivers_info),
            'retired_drivers': len([d for d in drivers_info if d['status'] == 'RETIRED'])
        }

        # Aggiorna cache
        _session_cache[cache_key] = (response_data, current_time)

        return jsonify(response_data)

    except Exception as e:
        error_msg = f"Errore: {str(e)}"
        print(error_msg)
        return jsonify({
            'status': 'error',
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/clear-cache')
def clear_cache():
    """Pulisci cache"""
    _session_cache.clear()
    return jsonify({
        'status': 'success',
        'message': 'Cache pulita',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/')
def home():
    """Homepage"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🏎️ F1 Live Data Server</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #111;
                color: white;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: #222;
                padding: 30px;
                border-radius: 10px;
                border: 2px solid #e10600;
            }
            h1 {
                color: #e10600;
                text-align: center;
            }
            .endpoint {
                background: #333;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                border-left: 4px solid #00d2be;
            }
            code {
                background: #444;
                padding: 2px 5px;
                border-radius: 3px;
                color: #ffcc00;
            }
            .note {
                background: #2a2a2a;
                padding: 10px;
                border-radius: 5px;
                margin: 20px 0;
                border-left: 4px solid #ffcc00;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏎️ F1 Live Data Server</h1>

            <div class="note">
                <strong>⚠️ ATTENZIONE:</strong> Il server utilizza FastF1. Alcune sessioni potrebbero non avere dati completi.
            </div>

            <h2>Endpoints Disponibili</h2>

            <div class="endpoint">
                <h3>📊 Dati Dettagliati Sessione</h3>
                <p><code>GET /f1-data-detailed?year=2025&gp=Qatar&session=R</code></p>
                <p>Parametri:</p>
                <ul>
                    <li><code>year</code>: 2022, 2023, 2024, 2025</li>
                    <li><code>gp</code>: Nome Gran Premio (es: "Monaco", "Qatar")</li>
                    <li><code>session</code>: FP1, FP2, FP3, Q, SQ, S, R</li>
                </ul>
            </div>

            <div class="endpoint">
                <h3>🗑️ Pulisci Cache</h3>
                <p><code>GET /clear-cache</code></p>
                <p>Forza il ricaricamento dei dati da FastF1</p>
            </div>

            <h2>Dati Inclusi</h2>
            <ul>
                <li>Posizione e gap in tempo reale</li>
                <li>Tempo miglior giro (in verde)</li>
                <li>Delta dal miglior giro</li>
                <li>Tempi settore</li>
                <li>Cronologia gomme con immagini</li>
                <li>Usura gomme attuali</li>
                <li>Stato pilota (RUNNING/RETIRED)</li>
                <li>Numero pit stop</li>
            </ul>

            <div class="note">
                <strong>💡 SUGGERIMENTO:</strong> Usa la cache per sessioni storiche. Per dati live, forza ricaricamento con /clear-cache.
            </div>
        </div>
    </body>
    </html>
    '''


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 F1 LIVE DATA SERVER - AVVIATO")
    print("=" * 60)
    print("📡 Server in esecuzione su: http://localhost:5000")
    print("")
    print("Esempi endpoint:")
    print("  • http://localhost:5000/f1-data-detailed?year=2025&gp=Qatar&session=R")
    print("  • http://localhost:5000/f1-data-detailed?year=2024&gp=Monaco&session=Q")
    print("  • http://localhost:5000/clear-cache")
    print("")
    print("⚠️  Prima esecuzione: il download dati potrebbe richiedere qualche minuto")
    print("=" * 60)

    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)