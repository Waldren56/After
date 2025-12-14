# FILE: start.py (CODICE AGGIORNATO: Correzione ID Video Stream)
import fastf1
import pandas as pd
import asyncio
import httpx 
import pytz 
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# ===============================================
# CONFIGURAZIONE E INIZIALIZZAZIONE
# ===============================================

# Abilita cache FastF1
fastf1.Cache.enable_cache("f1_cache")

# Anno della stagione corrente
SEASON_YEAR = datetime.now().year 

# Variabili di stato condivise per i dati live
live_data_f1 = {"laps": [], "last_update": None, "session_info": "", "active_session": None} 
connections_f1 = [] 

# Analisi e Odds
championship_odds = {"pilots": [], "remaining_races": 0}

# Calcio (API Placeholder)
CALCIO_API_URL = "http://api.football.com/v1/seriea/fixtures" 
CALCIO_DATA = {"status": "In attesa di API reale...", "matches": []}
connections_calcio = [] 

# Configurazione FastAPI
templates = Jinja2Templates(directory="templates")


# ===============================================
# HELPER: Funzioni di Formattazione e Stato
# ===============================================

def format_timedelta(td):
    """Converte un oggetto pandas Timedelta in una stringa di tempo leggibile (M:SS.mmm)."""
    if pd.isna(td):
        return "-"
    try:
        if td is None or (isinstance(td, (int, float)) and td == 0):
             return "-"
        
        if not isinstance(td, pd.Timedelta):
             td = pd.to_timedelta(td)
             
        total_seconds = td.total_seconds()
        
        # Gestisce i gap (che sono solo secondi o millisecondi, senza minuti)
        if total_seconds < 60 and total_seconds > -60: 
             return f"{total_seconds:+.3f}s"
             
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:06.3f}"
    except (AttributeError, TypeError, ValueError):
        return str(td)

def get_session_status(session_date):
    """Restituisce lo stato attuale della sessione in base alla data/ora UTC."""
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    session_start_utc = session_date.tz_convert(pytz.utc)
    
    if utc_now >= session_start_utc and utc_now < session_start_utc + timedelta(hours=2, minutes=30):
        return "LIVE"
    elif utc_now < session_start_utc:
        return "UPCOMING"
    else:
        return "COMPLETED"

def get_available_seasons(start_year=2018):
    """Restituisce una lista degli anni disponibili (FastF1 supporta dal 2018)."""
    current_year = datetime.now().year
    return list(range(start_year, current_year + 1))[::-1] 


# ===============================================
# FUNZIONE PRINCIPALE: Calcolo Dettagli Pilota (ROBUSTA)
# ===============================================

def _calculate_driver_details(session, driver_abbr):
    """Funzione helper per calcolare i dettagli del pilota data una sessione FastF1 caricata."""
    
    driver_abbr = driver_abbr.upper()

    # 1. Filtra i giri del pilota
    laps = session.laps.pick_drivers(driver_abbr)
    
    lap_data_available = not laps.empty
    
    best_lap_time = "Non Disponibile"
    last_lap_time = "Non Disponibile"
    delta_last_best = "Non Disponibile"
    
    # Variabile per memorizzare il Timedelta del Best Lap per il calcolo del delta
    best_lap_timedata = pd.NaT 

    if lap_data_available:
        # 2. Best Lap
        best_lap = laps.pick_fastest()
        
        # FIX: Accesso al Best Lap Timedelta in modo sicuro usando .index (per Series/Lap object)
        if not best_lap.empty and 'LapTime' in best_lap.index: 
            try:
                # Estrae il valore Timedelta scalare
                best_lap_timedata = best_lap['LapTime']
                best_lap_time = format_timedelta(best_lap_timedata)
            except Exception:
                 best_lap_time = "Dati Best Lap Mancanti"
                 best_lap_timedata = pd.NaT
            
        else:
             best_lap_time = "Dati Best Lap Mancanti"
             best_lap_timedata = pd.NaT


        # 3. Last Lap (o ultimo giro completato)
        if not laps.empty and 'LapNumber' in laps.columns and laps['LapNumber'].max() > 0:
            last_lap_index = laps['LapNumber'].idxmax()
            last_lap = laps.loc[last_lap_index]
            last_lap_time_data = last_lap.get('LapTime', pd.NaT)
            last_lap_time = format_timedelta(last_lap_time_data) if pd.notna(last_lap_time_data) else "Dati Last Lap Mancanti"

            # 4. Delta Last Lap vs Best Lap
            if pd.notna(last_lap_time_data) and pd.notna(best_lap_timedata):
                delta_time = last_lap_time_data - best_lap_timedata
                delta_last_best = format_timedelta(delta_time)
            else:
                delta_last_best = "N/A (Dati mancanti)"
        
    
    # 5. Gap e Informazioni Pilota dai risultati attuali
    results = session.results
    
    driver_result_rows = results[results['Abbreviation'] == driver_abbr]
    
    if driver_result_rows.empty:
        raise HTTPException(
            status_code=404, 
            detail=f"Pilota {driver_abbr} non trovato nei risultati correnti ({session.event['EventName']} - {session.session_info['Type']}). L'abbreviazione potrebbe essere errata o il pilota non ha preso parte alla sessione."
        )
        
    driver_result = driver_result_rows.iloc[0] 

    # 6. Gap to Leader & Gap to Ahead
    gap_to_leader = driver_result.get('GapToLeader')
    gap_to_ahead = driver_result.get('GapToAhead')
    
    final_time = driver_result.get('Time')
    if pd.notna(final_time) and final_time != 0 and session.session_info['Type'] == 'Race':
          gap_to_leader_str = format_timedelta(final_time)
    elif pd.notna(gap_to_leader):
          gap_to_leader_str = format_timedelta(gap_to_leader)
    elif driver_result.get('Position') == 1:
          gap_to_leader_str = "Leader"
    else:
          gap_to_leader_str = "-"
          
    gap_to_ahead_str = format_timedelta(gap_to_ahead) if pd.notna(gap_to_ahead) else "---" if driver_result.get('Position') == 1 else "-"


    # 7. Info Pilota
    driver_info = {
        "DriverCode": driver_abbr,
        "DriverName": driver_result.get('FullName', driver_result.get('Driver', driver_abbr)),
        "TeamName": driver_result.get('TeamName', '-'),
        "DriverNumber": int(driver_result.get('DriverNumber')) if pd.notna(driver_result.get('DriverNumber')) else "-",
        "CurrentPosition": int(driver_result.get('Position')) if pd.notna(driver_result.get('Position')) else "-",
    }

    return {
        "DriverInfo": driver_info,
        "LapMetrics": {
            "BestLapTime": best_lap_time,
            "LastLapTime": last_lap_time,
            "DeltaLastToBest": delta_last_best,
            "LapDataAvailable": lap_data_available
        },
        "RaceMetrics": {
            "GapToLeader": gap_to_leader_str,
            "GapToAhead": gap_to_ahead_str,
        }
    }


# ===============================================
# LOOP 1: Aggiornamento Dati F1 LIVE (WebSocket)
# ===============================================

async def update_f1_data():
    """Loop asincrono per l'aggiornamento dei dati live F1 tramite FastF1."""
    global live_data_f1
    
    while True:
        try:
            current_time = datetime.utcnow().strftime("%H:%M:%S")
            schedule = fastf1.get_event_schedule(SEASON_YEAR)
            
            live_session = None
            live_session_type = None
            next_session_details = None
            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)

            for _, event in schedule.iterrows():
                possible_sessions = ["FP1", "FP2", "FP3", "Q", "SprintQ", "R"]
                
                for ses in possible_sessions:
                    if ses in event and pd.notna(event[f'{ses}Date']):
                        session_date = event[f'{ses}Date']
                        status = get_session_status(session_date)
                        
                        if status == "LIVE":
                            live_session = fastf1.get_session(event.loc['EventDate'].year, event.loc['RoundNumber'], ses)
                            live_session_type = ses
                            break 
                        
                        elif status == "UPCOMING":
                            if not next_session_details or session_date < next_session_details['time_utc']:
                                next_session_details = {
                                    'time_utc': session_date.tz_convert(pytz.utc),
                                    'grand_prix': event["EventName"], 
                                    'session_name': ses,
                                    'location': event['Location'],
                                    'location_tz': event['CountryTimezone'], 
                                }
                
                if live_session:
                    break 
            
            
            if live_session:
                # --- LOGICA SESSIONE LIVE ---
                try:
                    live_session.load(allow_cached=False, telemetry=False, weather=False) 
                    
                    live_data_f1["active_session"] = live_session
                    
                    laps = live_session.laps.copy()
                    
                    if live_session_type in ["FP1", "FP2", "FP3", "Q", "SprintQ"]:
                        best_laps = laps.pick_fastest().sort_values('LapTime')
                    else: 
                        if 'Position' in live_session.results.columns:
                            best_laps = live_session.results.sort_values(by='Position', ascending=True)
                        else:
                            laps['TotalLapTime'] = laps.groupby('Driver')['LapTime'].cumsum()
                            last_lap = laps.groupby('Driver').last()
                            best_laps = last_lap.sort_values(['LapNumber', 'TotalLapTime'], ascending=[False, True])
                            best_laps = best_laps.reset_index().assign(Position=lambda x: x.index + 1)


                    laps_data = []
                    for index, lap in best_laps.iterrows():
                        position = lap['Position'] if 'Position' in lap and pd.notna(lap['Position']) else index + 1
                        
                        laps_data.append({
                            "Position": int(position),
                            "Driver": lap['Abbreviation'] if 'Abbreviation' in lap else lap['Driver'],
                            "LapNumber": lap.get('LapNumber', '-') if pd.notna(lap.get('LapNumber')) else '-',
                            "LapTime": format_timedelta(lap.get('LapTime')),
                            "Sector1Time": format_timedelta(lap.get('Sector1Time')),
                            "Sector2Time": format_timedelta(lap.get('Sector2Time')),
                            "Sector3Time": format_timedelta(lap.get('Sector3Time')),
                        })

                    live_data_f1["laps"] = laps_data
                    live_data_f1["session_info"] = f"LIVE: {live_session.event['EventName']} - {live_session_type}"
                    live_data_f1["last_update"] = current_time

                except Exception as e:
                    live_data_f1["session_info"] = f"ERRORE CARICAMENTO LIVE: {live_session.event['EventName']} ({live_session_type}). Riprova: {e}"
                    live_data_f1["last_update"] = current_time + " (Errore Caricamento Dati)"
                    live_data_f1["active_session"] = None
                    
            else:
                # --- LOGICA PROSSIMA SESSIONE / STAGIONE FINITA ---
                live_data_f1["laps"] = []
                live_data_f1["active_session"] = None 
                
                if next_session_details:
                    time_remaining = next_session_details['time_utc'] - now_utc
                    days = time_remaining.days
                    hours = time_remaining.seconds // 3600
                    minutes = (time_remaining.seconds % 3600) // 60
                    
                    remaining_str = f"{days}g {hours}h {minutes}m"
                    
                    live_data_f1["session_info"] = (
                        f"Nessuna sessione live. Prossima sessione in **{remaining_str}**: "
                        f"**{next_session_details['session_name']}** "
                        f"del **{next_session_details['grand_prix']}**."
                    )
                else:
                    live_data_f1["session_info"] = f"Stagione F1 {SEASON_YEAR} terminata o schedule non disponibile."

            if connections_f1:
                data_to_send = json.dumps(live_data_f1)
                await asyncio.gather(*[ws.send_text(data_to_send) for ws in connections_f1], return_exceptions=True)


        except Exception as e:
            error_msg = f"Errore generale in update_f1_data: {e}"
            print(error_msg)
            live_data_f1["session_info"] = error_msg
            live_data_f1["last_update"] = current_time + " (ERRORE)"
            live_data_f1["active_session"] = None
        
        await asyncio.sleep(5) 


# ===============================================
# LOOP 3: Aggiornamento ODDS E CLASSIFICA MONDIALE 
# ===============================================

async def calculate_championship_odds():
    """Calcola le quote di vittoria del campionato basate sui punti e le gare rimanenti."""
    global championship_odds
    
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Calcolo probabilità mondiale...")
            
            schedule = fastf1.get_event_schedule(SEASON_YEAR)
            utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
            
            if schedule['EventDate'].dt.tz is None:
                schedule['EventDate'] = schedule['EventDate'].dt.tz_localize(pytz.utc)
            
            remaining_rounds = schedule[schedule['EventDate'] > utc_now].shape[0]
            completed_events = schedule[schedule['EventDate'] < utc_now]
            
            current_standings = []
            standings_table = pd.DataFrame()
            
            if not completed_events.empty:
                last_round_num = completed_events.iloc[-1]['RoundNumber']
                
                try:
                    last_session = fastf1.get_session(SEASON_YEAR, round(last_round_num), 'R')
                    last_session.load(telemetry=False, weather=False) 
                    standings_table = last_session.load_table('DriverStandings')
                    
                except Exception as e:
                    print(f"Errore nel caricamento della classifica F1: {e}. Saltando il calcolo Odds.")
                
                
                if not standings_table.empty:
                    for index, row in standings_table.iterrows():
                        driver_ref = row['DriverId'] 
                        abbreviation = row.get('Abbreviation', driver_ref.upper()[:3]) 
                        
                        current_standings.append({
                            "Position": int(row['Position']),
                            "Driver": abbreviation,
                            "Points": int(row['Points'])
                        })
                
                # Logica di Predizione Semplificata (invariata)
                max_race_points = 26 
                total_max_points_remaining = remaining_rounds * max_race_points 
                
                if current_standings and total_max_points_remaining > 0:
                    leader_points = current_standings[0]['Points']
                    
                    for pilot in current_standings:
                        gap = leader_points - pilot['Points']
                        
                        if pilot['Points'] + total_max_points_remaining < leader_points:
                            pilot['Odds'] = "0.0%" 
                        else:
                            if total_max_points_remaining > 0:
                                normalized_score = (pilot['Points'] + total_max_points_remaining - gap) / (2 * total_max_points_remaining)
                                final_odds = min(99.9, max(0.1, normalized_score * 100 * 1.5))
                                
                                if pilot['Position'] == 1:
                                    final_odds = max(final_odds, 55.0) 
                                    
                                pilot['Odds'] = f"{final_odds:.1f}%"
                            else:
                                pilot['Odds'] = "100.0%" if pilot['Position'] == 1 else "0.0%"
                            
            
            championship_odds["pilots"] = current_standings
            championship_odds["remaining_races"] = remaining_rounds
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Probabilità calcolate con successo.")
            
        except Exception as e:
            print(f"Errore nel calcolo delle probabilità: {e}")
            championship_odds["pilots"] = []
            championship_odds["remaining_races"] = 0
        
        await asyncio.sleep(3600) 


# ===============================================
# LOOP 2: Aggiornamento Dati Calcio (Placeholder)
# ===============================================
# ... (Logica di update_calcio_data invariata)
async def update_calcio_data():
    """Loop per aggiornare i dati Calcio. DEVI SOSTITUIRE CON UN'API REALE."""
    global CALCIO_DATA
    
    while True:
        current_time = datetime.utcnow().strftime("%H:%M:%S")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # PLACEHOLDER: La linea sotto fallirà se non cambi l'URL
                response = await client.get(CALCIO_API_URL) 
                response.raise_for_status() 

            data = response.json()
            CALCIO_DATA["matches"] = data.get("risultati", [])
            CALCIO_DATA["status"] = f"Dati Calcio ricevuti. {len(CALCIO_DATA['matches'])} partite trovate."
            
        except (httpx.ConnectError, httpx.RequestError) as e:
            CALCIO_DATA["status"] = f"ERRORE CALCIO: Impossibile connettersi all'API. {str(e)}. (Probabile URL non valido)"
        
        except Exception as e:
            CALCIO_DATA["status"] = f"ERRORE CALCIO GENERICO: {str(e)}"

        CALCIO_DATA["last_update"] = current_time
        
        if connections_calcio:
            message = json.dumps(CALCIO_DATA)
            await asyncio.gather(*[ws.send_text(message) for ws in connections_calcio], return_exceptions=True) 
            
        await asyncio.sleep(60) 


# ===============================================
# GESTIONE DEL CICLO DI VITA E ENDPOINT
# ===============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Avvia i loop di aggiornamento dati live all'avvio dell'app."""
    print("Avvio dei loop di aggiornamento dati live (F1 e Calcio) e calcolo Odds...")
    asyncio.create_task(update_f1_data())
    asyncio.create_task(update_calcio_data()) 
    asyncio.create_task(calculate_championship_odds())
    yield
    print("Arresto del server completato.")

# === Inizializzazione FastAPI ===
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# === ENDPOINT HTTP (Routing delle Pagine) ===

@app.get("/", response_class=HTMLResponse)
async def home_hub(request: Request):
    """Pagina principale (Hub)."""
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/f1/live", response_class=HTMLResponse)
async def f1_live_tracker(request: Request):
    """Live Tracker F1."""
    return templates.TemplateResponse("f1_tracker.html", {"request": request})

# ENDPOINT PER LO STREAMING (AGGIORNATO CON NUOVO ID PLACEHOLDER)
@app.get("/f1/stream", response_class=HTMLResponse)
async def f1_stream(request: Request):
    """Pagina per lo streaming video incorporato (embed)."""
    # Dati per il video embed. 
    # **IMPORTANTE**: Sostituisci l'ID del video (dopo embed/) con quello di un feed live legale durante l'evento.
    stream_data = {
        "title": "F1 Live Stream Italia (Demo Legale)",
        # NUOVO ID PLACEHOLDER: Sostituisci con il tuo feed live autorizzato
        "youtube_id": "H_7o1m2QfB8" 
    }
    return templates.TemplateResponse("f1_stream.html", {"request": request, "stream": stream_data})

@app.get("/f1/storico", response_class=HTMLResponse)
async def f1_historic_hub(request: Request):
    """Pagina per visualizzare i dati storici e le quote."""
    return templates.TemplateResponse("f1_historic.html", {"request": request})

# ===============================================
# ENDPOINT: Dettagli Pilota LIVE
# ===============================================

@app.get("/api/f1/driver_details/{driver_abbr}")
async def get_driver_details_live(driver_abbr: str):
    """Restituisce i dettagli completi del pilota per la sessione live."""
    session = live_data_f1.get("active_session")
    
    if session is None:
        raise HTTPException(status_code=404, detail="Nessuna sessione F1 live attiva per recuperare i dettagli.")

    try:
        return _calculate_driver_details(session, driver_abbr)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Errore nel recupero dei dettagli LIVE per {driver_abbr}: {e}")
        raise HTTPException(status_code=500, detail=f"Errore interno del server durante il calcolo delle metriche: {str(e)}")


# ===============================================
# ENDPOINT: Dettagli Pilota STORICO
# ===============================================

@app.get("/api/f1/driver_details_historic/{year}/{round_num}/{session_type}/{driver_abbr}")
async def get_driver_details_historic(year: int, round_num: int, session_type: str, driver_abbr: str):
    """Restituisce i dettagli completi del pilota per una sessione storica specifica."""
    
    try:
        # 1. Carica la sessione storica
        session = fastf1.get_session(year, round_num, session_type)
        session.load(telemetry=False, weather=False) 
        
        # 2. Usa la funzione helper
        return _calculate_driver_details(session, driver_abbr)
        
    except HTTPException:
        raise
    except Exception as e:
          error_message = str(e)
          
          if "No results found for session" in error_message or "Data not available" in error_message:
              error_message = f"I dati Risultati per l'anno {year}, Round {round_num} ({session_type}) non sono disponibili. La sessione potrebbe non essere stata completata."
          elif "Session type" in error_message and "does not exist" in error_message:
              error_message = f"Session type '{session_type}' non esiste per questo evento."
          else:
              error_message = f"Errore generico FastF1: {error_message}"
            
          raise HTTPException(status_code=500, detail=f"ERRORE: Impossibile caricare i dettagli storici. Causa: {error_message}")


# ===============================================
# ENDPOINT STORICI CON FILTRO ANNO (Invariati)
# ===============================================
@app.get("/api/f1/years")
async def get_f1_years():
    return get_available_seasons()

@app.get("/api/f1/odds")
async def get_championship_odds():
    return championship_odds

@app.get("/api/f1/eventi/{year}")
async def get_f1_events(year: int):
    try:
        if year < 2018 or year > datetime.now().year + 1:
            raise HTTPException(status_code=400, detail="Anno non valido. Dati disponibili dal 2018.")

        schedule = fastf1.get_event_schedule(year)
        
        events = []
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)

        for index, row in schedule.iterrows():
            if row['EventName'] in ['Test', 'Testing'] or pd.isna(row['EventDate']):
                continue
            
            event_date = row['EventDate']
            
            if pd.isna(event_date): continue
            
            if event_date.tzinfo is None:
                 event_date = pytz.timezone(row.get('CountryTimezone', 'UTC')).localize(event_date)
            
            utc_event_date = event_date.tz_convert(pytz.utc)
            
            events.append({
                "Round": row['RoundNumber'],
                "EventName": row['EventName'],
                "EventDate": utc_event_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "Country": row['Country'],
                "Completed": utc_event_date < utc_now
            })
        
        return events
    except Exception as e:
        if "No event schedule" in str(e):
             raise HTTPException(status_code=404, detail=f"Calendario non disponibile per l'anno {year}.")
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento del calendario per l'anno {year}: {e}")

@app.get("/api/f1/risultati/{year}/{round_num}/{session_type}")
async def get_f1_results(year: int, round_num: int, session_type: str):
    try:
        if round_num == 0:
            raise HTTPException(status_code=400, detail="Numero di round non valido (deve essere > 0).")
        
        try:
             session = fastf1.get_session(year, round_num, session_type)
             session.load(telemetry=False, weather=False) 
             results = session.results
        
        except Exception as e:
             error_message = str(e)
             
             if "No results found for session" in error_message or "Data not available" in error_message:
                 error_message = f"I risultati per l'anno {year}, Round {round_num} ({session_type}) non sono disponibili. L'evento potrebbe non essere stato completato o i dati non sono stati ancora caricati."
             
             elif "Session type" in error_message and "does not exist" in error_message:
                 error_message = f"Session type '{session_type}' does not exist for this event. La sessione {session_type} potrebbe non essere disponibile per questa gara. Prova un altro tipo di sessione (es. R, Q, FP2)."
             
             else:
                 error_message = f"Errore generico FastF1: {error_message}"
             
             raise HTTPException(status_code=500, detail=f"ERRORE: Impossibile caricare i risultati. Causa: {error_message}")

        formatted_results = []
        for index, row in results.iterrows():
            driver_abbr = row.get('Abbreviation', row.get('Driver', '-'))
            
            formatted_results.append({
                "Position": int(row['Position']) if pd.notna(row['Position']) else "-",
                "Driver": driver_abbr,
                "Team": row.get('TeamName', '-'),
                "Time": format_timedelta(row.get('Time')) if pd.notna(row.get('Time')) and row.get('Time') != 0 else str(row.get('GapToLeader', '-')) if pd.notna(row.get('GapToLeader')) else "-",
                "Laps": int(row.get('Laps')) if pd.notna(row.get('Laps')) else 0,
                "Points": int(row.get('Points')) if pd.notna(row.get('Points')) else 0
            })
        
        return {
            "session_name": f"{session.event['EventName']} - {session_type}", 
            "results": formatted_results,
            "year": year,
            "round": round_num,
            "session_type": session_type,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERRORE: Errore interno nel server durante la formattazione dei dati. Causa: {str(e)}")


# === ENDPOINT WEBSOCKETS (Invariati) ===
@app.websocket("/ws/f1/live")
async def websocket_f1_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections_f1.append(websocket)
    try:
        while True: await asyncio.sleep(60)
    except: pass
    finally: connections_f1.remove(websocket)

@app.websocket("/ws/calcio/live")
async def websocket_calcio_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections_calcio.append(websocket)
    try:
        while True: await asyncio.sleep(60)
    except: pass
    finally: connections_calcio.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("start:app", host="0.0.0.0", port=8000, reload=True)