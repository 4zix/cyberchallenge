import os
import json
import glob
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from pydantic import BaseModel, Field

# --- MODELOS DE DATOS (PYDANTIC) ---
# Definir modelos para la validación de datos mejora la seguridad y claridad.

class CPUInfo(BaseModel):
    physical_cores: int | None = None
    total_cores: int | None = None
    frequency: float | str | None = None
    usage_percent: float | None = None
    error: str | None = None

class ProcessInfo(BaseModel):
    pid: int
    name: str
    username: str | None = None

class UserInfo(BaseModel):
    user: str
    terminal: str | None = None

class SystemData(BaseModel):
    """Modelo Pydantic para validar los datos que envía el agente."""
    os_name: str
    os_version: str
    cpu_info: CPUInfo
    running_processes: list[ProcessInfo | dict]
    logged_in_users: list[UserInfo] | dict

# --- CONFIGURACIÓN DE LA APLICACIÓN ---
app = FastAPI(
    title="System Info Collector API",
    description="API para recolectar y consultar información de sistemas operativos.",
    version="1.0.0"
)

# Token de seguridad para validar las peticiones del agente.
API_TOKEN = "micompania_secret_token_12345"
# Directorio para almacenar los logs de datos.
DATA_DIR = "data"

# --- LÓGICA DE SEGURIDAD ---

async def verify_token(authorization: str = Header(...)):
    """Dependencia para verificar el token de autorización."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato de token inválido")
    
    token = authorization.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token de autorización inválido")

# --- ENDPOINTS DE LA API ---

@app.post("/collect", dependencies=[Depends(verify_token)])
async def collect_data(data: SystemData, request: Request):
    """
    Endpoint para recibir datos del agente.
    Valida el token y guarda la información en un archivo .jsonl.
    """
    client_ip = request.client.host
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    # Usamos la extensión .jsonl para indicar que es un archivo JSON Lines
    filename = os.path.join(DATA_DIR, f"{client_ip}_{today_date}.jsonl")
    
    # Asegura que el directorio de datos exista
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Crea un registro con timestamp del servidor y los datos del agente
    record = {
        "server_timestamp": datetime.now().isoformat(),
        "payload": data.model_dump() # Convierte el modelo Pydantic a dict
    }
    
    # Agrega el nuevo registro como una nueva línea en el archivo.
    # Esto es mucho más eficiente que leer y reescribir un array JSON completo.
    with open(filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        
    return {"status": "success", "message": f"Datos recibidos de {client_ip}"}

@app.get("/query/{ip_address}")
async def query_data(ip_address: str) -> list[dict[str, Any]]:
    """
    Endpoint para consultar todos los registros de una IP específica.
    Busca todos los archivos .jsonl que coincidan con la IP.
    """
    search_pattern = os.path.join(DATA_DIR, f"{ip_address}_*.jsonl")
    matching_files = glob.glob(search_pattern)
    
    if not matching_files:
        raise HTTPException(status_code=404, detail=f"No se encontraron datos para la IP: {ip_address}")
    
    all_records = []
    for file_path in sorted(matching_files, reverse=True): # Procesar los más recientes primero
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip(): # Evitar líneas vacías
                        all_records.append(json.loads(line))
        except Exception as e:
            # Si un archivo está corrupto, lo informamos pero continuamos
            print(f"Advertencia: No se pudo leer el archivo {file_path}. Error: {e}")
            
    return all_records

@app.get("/")
def read_root():
    """Endpoint raíz para verificar que la API está funcionando."""
    return {"message": "API de recolección de datos está en línea."}