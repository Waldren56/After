import fastf1
import pandas as pd
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import json
from contextlib import asynccontextmanager
import pytz # Necessario per la conversione del fuso orario

# Abilita cache FastF1
fastf1.Cache.enable_cache("f1_cache")

# Variabili di configurazione e stato
templates = Jinja2Templates(directory="templates")
live_data = {"laps": [], "last_update": None, "session_info": ""}
connections = [] # Lista WebSocket connessi


# ===============================================
# HELPER: Funzione di Formattazione dei Tempi
# ===============================================

def format_timedelta(td):
    """Converte un oggetto pandas Timedelta in una stringa di tempo leggibile (M:SS.mmm)."""
    if pd.isna(td):
        return "-"
    try:
        total_seconds = td.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        # Formatta in M:SS.mmm
        return f"{minutes}:{seconds:06.3f}"
    except AttributeError:
        # Gestisce il caso in cui td non sia un timedelta valido
        return str(td)


# ===============================================
# LOOP: Aggiornamento Dati Live
# ===============================================

async def update_live_data():
    """Loop per aggiornare i dati FastF1 live e inviarli ai client tramite WebSocket."""
    while True:
        try:
            current_year = datetime.utcnow().year
            # Tenta di caricare lo schedule (potrebbe fallire per problemi di rete/API)
            schedule = fastf1.get_event_schedule(current_year)

            session_found = False
            next_session_details = None
            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)

            for _, event in schedule.iterrows():
                # Cicla su tutte le possibili sessioni di un evento
                possible_sessions = ["FP1", "FP2", "FP3", "Q", "SprintQ", "R", "Test"]
                
                for ses in possible_sessions:
                    if ses in event and pd.notna(event[ses]):
                        session_time_utc = pd.to_datetime(event[ses], utc=True).replace(tzinfo=pytz.utc)
                        
                        # 1. Rileva sessione ATTIVA (dal tempo di inizio fino a 2 ore dopo)
                        if now_utc >= session_time_utc and now_utc <= session_time_utc + timedelta(hours=2):
                            # LOGICA SESSIONE LIVE
                            session_found = True
                            
                            session = fastf1.get_session(event["EventName"], ses, current_year)
                            
                            try:
                                session.load(live=True, allow_cached=False)
                            except Exception as load_error:
                                live_data["session_info"] = f"Sessione {event['EventName']} - {ses} in corso, ma FastF1 non riesce a caricare i dati live: {str(load_error)}"
                                break # Passa al broadcast dei dati

                            laps = session.laps.copy()
                            # ... (Tutta la tua logica Classifica) ...
                            if ses in ["FP1", "FP2", "FP3", "Q", "SprintQ"]:
                                best_laps = laps.pick_fastest().sort_values('LapTime')
                            else:
                                laps['TotalLapTime'] = laps.groupby('Driver')['LapTime'].cumsum()
                                last_lap = laps.groupby('Driver').last()
                                best_laps = last_lap.sort_values(['LapNumber', 'TotalLapTime'], ascending=[False, True])
                            # =======================
                            
                            # Prepara i dati e FORMATTA I TEMPI PRIMA DI INVIARLI
                            live_data["laps"] = [
                                {
                                    'Driver': row['Driver'],
                                    'LapNumber': int(row['LapNumber']) if pd.notna(row['LapNumber']) else '-',
                                    'LapTime': format_timedelta(row['LapTime']),
                                    'Sector1Time': format_timedelta(row['Sector1Time']),
                                    'Sector2Time': format_timedelta(row['Sector2Time']),
                                    'Sector3Time': format_timedelta(row['Sector3Time']),
                                }
                                for index, row in best_laps.iterrows()
                            ]
                            live_data["session_info"] = f"LIVE: {event['EventName']} - {ses}"
                            break # Esci dal ciclo delle sessioni di questo evento
                        
                        # 2. Rileva la PROSSIMA sessione (futura)
                        elif now_utc < session_time_utc:
                            if not next_session_details or session_time_utc < next_session_details['time_utc']:
                                next_session_details = {
                                    'time_utc': session_time_utc,
                                    'grand_prix': event["EventName"], 
                                    'session_name': ses,
                                    'location': event['Location'],
                                    'location_tz': event['CountryTimezone'], 
                                }
                
                if session_found:
                    break # Esci dal ciclo degli eventi (se ne hai trovata una live)

            # ----------------------------------------------------
            # Gestione Sessione non trovata (Prossima o Stagione Finita)
            # ----------------------------------------------------
            if not session_found:
                live_data["laps"] = []
                
                if next_session_details:
                    # LOGICA PROSSIMA SESSIONE COMPLETA
                    
                    # Converte da UTC al TimeZone locale del circuito
                    local_tz_name = next_session_details['location_tz']
                    
                    # Garantisci che l'oggetto timezone sia valido
                    try:
                         local_tz = pytz.timezone(local_tz_name)
                    except pytz.exceptions.UnknownTimeZoneError:
                        local_tz = pytz.utc # Fallback a UTC se il fuso orario non è riconosciuto

                    time_local = next_session_details['time_utc'].astimezone(local_tz)

                    # Calcola il tempo rimanente
                    time_remaining = next_session_details['time_utc'] - now_utc
                    
                    days = time_remaining.days
                    hours = time_remaining.seconds // 3600
                    minutes = (time_remaining.seconds % 3600) // 60
                    
                    remaining_str = f"{days}g {hours}h {minutes}m"
                    
                    # Imposta il messaggio completo
                    live_data["session_info"] = (
                        f"Nessuna sessione live. Prossima sessione in **{remaining_str}**: "
                        f"**{next_session_details['session_name']}** "
                        f"del **{next_session_details['grand_prix']}** (Circuito: {next_session_details['location']}). "
                        f"Ora locale: {time_local.strftime('%d-%m %H:%M %Z')}"
                    )
                else:
                    # Nessuna sessione futura trovata
                    live_data["session_info"] = f"Stagione F1 {current_year} terminata o schedule non disponibile."

            # Imposta il tempo di aggiornamento per il frontend
            live_data["last_update"] = datetime.utcnow().strftime("%H:%M:%S")

            # Invia dati a tutti i WebSocket connessi
            if connections:
                message = json.dumps(live_data)
                await asyncio.gather(*[ws.send_text(message) for ws in connections])

        except Exception as e:
            # Gestione ERRORI CRITICI (es. fallimento nel caricare la schedule FastF1)
            error_msg = f"ERRORE F1: Impossibile ottenere lo schedule FastF1. Problema di rete/API. Dettagli: {str(e)}"
            print(error_msg)
            
            live_data["laps"] = []
            live_data["session_info"] = error_msg
            live_data["last_update"] = datetime.utcnow().strftime("%H:%M:%S") + " (ERRORE)"
        
        await asyncio.sleep(5) 
        
# ===============================================
# GESTIONE DEL CICLO DI VITA E ENDPOINT (Resto del file)
# ===============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Avvia il loop di aggiornamento dati live all'avvio dell'app."""
    print("Avvio del loop di aggiornamento dati live...")
    # Assicurati che l'istanza del loop sia avviata
    asyncio.create_task(update_live_data())
    yield
    print("Arresto del server completato.")

# === Inizializzazione FastAPI ===
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# === ENDPOINT HTTP (Routing delle Pagine) ===
@app.get("/", response_class=HTMLResponse)
async def home_hub(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/f1/live", response_class=HTMLResponse)
async def f1_live_tracker(request: Request):
    return templates.TemplateResponse("f1_tracker.html", {"request": request})

# === ENDPOINT WEBSOCKET ===
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    try:
        while True:
            await asyncio.sleep(60)
    except:
        pass
    finally:
        connections.remove(websocket)