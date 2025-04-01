# backend/dependencies.py
import asyncio
import logging
from typing import TYPE_CHECKING

# Importar las clases de los gestores
from api.websocket_manager import WebSocketManager
from core.training_manager import TrainingManager

# Evitar importación circular completa usando TYPE_CHECKING para type hints
# if TYPE_CHECKING:
#     from api.websocket_manager import WebSocketManager
#     from core.training_manager import TrainingManager

logger = logging.getLogger(__name__)

# --- Crear Instancias Singleton ---
# Asegurarse que las clases ya estén definidas al importar este módulo
try:
    ws_manager_singleton = WebSocketManager()
    # Pasar la instancia de WS al crear el TM
    training_manager_singleton = TrainingManager(ws_manager_singleton)
    logger.info("Instancias singleton de WebSocketManager y TrainingManager creadas.")
except Exception as e:
    logger.error(f"Error creando instancias singleton: {e}", exc_info=True)
    # Manejar el error como sea apropiado, quizás salir o usar instancias dummy
    ws_manager_singleton = None
    training_manager_singleton = None

# Definir una función para establecer el loop DESPUÉS de que FastAPI arranque
def set_main_event_loop_in_tm():
    try:
        loop = asyncio.get_running_loop()
        if training_manager_singleton:
            training_manager_singleton.set_main_event_loop(loop) # <--- Nuevo método en TM
            logger.info("Bucle de eventos principal inyectado en TrainingManager.")
    except RuntimeError:
         logger.error("No se pudo obtener/inyectar el bucle de eventos principal.")


# --- Funciones de Inyección de Dependencia ---
async def get_websocket_manager_instance() -> WebSocketManager:
    """Devuelve la instancia singleton del WebSocketManager."""
    if ws_manager_singleton is None:
         raise RuntimeError("WebSocketManager no pudo ser inicializado.")
    return ws_manager_singleton

async def get_training_manager_instance() -> TrainingManager:
    """Devuelve la instancia singleton del TrainingManager."""
    if training_manager_singleton is None:
         raise RuntimeError("TrainingManager no pudo ser inicializado.")
    return training_manager_singleton