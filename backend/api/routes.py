# backend/api/routes.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional

# --- IMPORTAR DESDE dependencies.py ---
from dependencies import get_training_manager_instance # Correcto

# Importar CLASE TrainingManager y Schemas
from core.training_manager import TrainingManager # Correcto
from .schemas import TrainingParams, TrainingStatus # Correcto

router = APIRouter(prefix="/api", tags=["Training Control"])

# Usar la función importada en Depends en TODAS las rutas

# --- Ruta /train/start ---
@router.post("/train/start", status_code=202)
async def start_new_training(
    params: TrainingParams, # Recibe parámetros del frontend
    manager: TrainingManager = Depends(get_training_manager_instance) # Inyecta el manager
) -> Dict[str, str]:
    try:
        # Pasa los parámetros recibidos al manager
        manager.start_training_session(params) # <--- Parece correcto
        return {"message": "Solicitud de inicio de entrenamiento recibida."}
    except ValueError as e: raise HTTPException(status_code=409, detail=str(e))
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error interno: {e}")
# --- Conclusión /train/start: La ruta parece pasar correctamente el objeto 'params' recibido del frontend
# --- al TrainingManager. Si los timesteps no se aplican, el problema es probablemente DENTRO del manager.

# --- Ruta /train/continue ---
@router.post("/train/continue", status_code=202)
async def continue_existing_training(
    manager: TrainingManager = Depends(get_training_manager_instance) # Inyecta el manager
) -> Dict[str, str]:
    try:
        # Llama a la función de continuar en el manager (no pasa params desde aquí)
        manager.continue_training_session() # <--- Parece correcto
        return {"message": "Solicitud para continuar entrenamiento recibida."}
    except ValueError as e: raise HTTPException(status_code=409, detail=str(e)) # Ej: ya entrenando
    except FileNotFoundError as e: raise HTTPException(status_code=404, detail=str(e)) # Ej: no hay last_model.zip
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error interno: {e}")
# --- Conclusión /train/continue: La ruta llama correctamente a la función del manager. Si "Continuar" actúa
# --- como "Iniciar Nuevo", el problema está dentro del manager.

# --- Ruta /train/stop ---
@router.post("/train/stop", status_code=200)
async def stop_current_training(
    manager: TrainingManager = Depends(get_training_manager_instance) # Inyecta el manager
) -> Dict[str, str]:
    try:
        # Llama a la función async de detener
        stopped = await manager.stop_training_session() # <--- Parece correcto (uso de await)
        return {"message": "Señal de parada enviada." if stopped else "No había entrenamiento activo."}
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error interno: {e}")
# --- Conclusión /train/stop: La ruta parece correcta.

# --- Ruta /status ---
@router.get("/status", response_model=TrainingStatus)
async def get_training_status(
    manager: TrainingManager = Depends(get_training_manager_instance) # Inyecta el manager
) -> TrainingStatus:
    return manager.get_status() # <--- Parece correcto
# --- Conclusión /status: La ruta devuelve lo que el manager indique. Si el estado que ve el frontend
# --- (vía WebSocket) es incorrecto, el problema no está en esta ruta de polling, sino en las
# --- actualizaciones WS enviadas por el manager.

# --- Rutas /config/defaults y /hardware-info ---
# Ambas parecen correctas, llaman a las funciones correspondientes del manager.
@router.get("/config/defaults", response_model=Dict)
async def get_default_config(
    manager: TrainingManager = Depends(get_training_manager_instance)
) -> Dict:
    try: return manager.get_default_parameters()
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error obteniendo defaults: {e}")

@router.get("/hardware-info", response_model=Dict)
async def get_hardware_info(
    manager: TrainingManager = Depends(get_training_manager_instance)
) -> Dict:
    try: return manager.get_hardware_info()
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error obteniendo info hardware: {e}")