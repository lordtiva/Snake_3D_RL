# backend/main.py
import asyncio
import json
import os
import time
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware # Importar CORS
from starlette.websockets import WebSocketState

# Importar componentes de RL y entorno
from stable_baselines3 import PPO # O el algoritmo que uses
from core.snake_env import SnakeEnv

# Importar el router de la API y las *funciones de dependencia* desde dependencies.py
from api import routes as api_routes
from dependencies import get_training_manager_instance, get_websocket_manager_instance, set_main_event_loop_in_tm

# Importar las clases de los gestores (para type hints si es necesario)
from api.websocket_manager import WebSocketManager
from core.training_manager import TrainingManager


# Configuración básica de logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constantes y Configuración ---
BOARD_SIZE = 20 # Asegúrate que coincida con el entrenamiento y snake_env.py
BEST_MODEL_PATH_WATCH = os.path.join("logs", "best_model", "best_model.zip") # Ruta al mejor modelo para visualización
FRONTEND_DIR = "../frontend" # Ruta relativa a la carpeta del frontend

# --- Instancia de FastAPI ---
# Pydantic v2+ puede requerir `context_vars_warning=False` si usas contextos, pero no aquí.
app = FastAPI(title="Snake RL Control Panel", version="1.0.0")

# --- Configuración CORS (Opcional) ---
# Descomenta y ajusta si sirves el frontend desde un puerto diferente (ej: 5500)
# origins = [
#     "http://localhost:5500",
#     "http://127.0.0.1:5500",
# ]
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# --- Evento Startup de FastAPI ---
@app.on_event("startup")
async def startup_event():
    """Se ejecuta cuando FastAPI inicia, inyecta el loop en el TrainingManager."""
    logger.info("Aplicación FastAPI iniciada. Inyectando bucle de eventos en TrainingManager...")
    # Llamar a la función definida en dependencies.py para establecer el loop
    set_main_event_loop_in_tm()

# --- Incluir el router de la API REST ---
# Las rutas usarán Depends(get_..._instance) importado desde dependencies.py
app.include_router(api_routes.router)


# --- Clase AiEvaluator (Modificada para cargar modelo en start) ---
class AiEvaluator:
    def __init__(self, websocket: WebSocket, ws_manager: WebSocketManager):
        self.websocket = websocket
        self.ws_manager = ws_manager
        self.env: SnakeEnv | None = None # Inicializar a None, crear en run
        self.task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._loaded_watch_model = None # Guardar modelo cargado para esta instancia

    async def _initialize_env(self):
        """Crea el entorno si no existe."""
        if self.env is None:
            try:
                self.env = SnakeEnv(board_size=BOARD_SIZE)
                logger.info(f"Cliente {self.websocket.client}: Entorno SnakeEnv creado.")
            except Exception as e:
                 logger.error(f"Cliente {self.websocket.client}: Error creando SnakeEnv: {e}", exc_info=True)
                 await self.send_error("Error interno al crear el entorno del juego.")
                 return False
        return True

    async def _close_env(self):
        """Cierra el entorno si existe."""
        if self.env:
             try: self.env.close()
             except Exception as e_close: logger.error(f"Error cerrando env de evaluación: {e_close}")
             self.env = None


    async def run_evaluation_loop(self, model_to_use, delay=0.08):
        """Ejecuta la evaluación y envía estados por WebSocket."""
        if model_to_use is None:
            logger.warning(f"Cliente {self.websocket.client}: Modelo no disponible para run_evaluation_loop.")
            # El error ya se envió en start(), no enviar de nuevo.
            return

        if not await self._initialize_env():
            return # Salir si no se pudo crear el entorno

        logger.info(f"Cliente {self.websocket.client}: Iniciando bucle de evaluación con modelo.")
        try:
            while not self._stop_event.is_set():
                obs, info = self.env.reset()
                terminated = False
                truncated = False
                score = 0
                await self.send_state() # Enviar estado inicial

                while not terminated and not truncated and not self._stop_event.is_set():
                    action, _ = model_to_use.predict(obs, deterministic=True)
                    obs, reward, terminated, truncated, info = self.env.step(action.item())
                    score += reward
                    await self.send_state()
                    await asyncio.sleep(delay)

                if self._stop_event.is_set():
                    logger.info(f"Cliente {self.websocket.client}: Bucle de evaluación detenido por señal.")
                    break

                final_score = info.get('snake_length', 1) - 1
                logger.info(f"Cliente {self.websocket.client}: Episodio de evaluación terminado. Score: {final_score}")
                await asyncio.sleep(1.0) # Pausa entre episodios

        except WebSocketDisconnect:
            logger.info(f"Cliente {self.websocket.client}: WebSocket desconectado durante la evaluación.")
            self._stop_event.set()
        except Exception as e:
            logger.error(f"Cliente {self.websocket.client}: Error en el bucle de evaluación: {e}", exc_info=True)
            await self.send_error(f"Error interno durante la evaluación: {type(e).__name__}")
            self._stop_event.set()
        finally:
            await self._close_env() # Cerrar entorno al finalizar
            logger.info(f"Cliente {self.websocket.client}: Bucle de evaluación finalizado.")


    async def send_state(self):
        """Envía el estado actual del juego al cliente WebSocket."""
        if self.websocket.client_state != WebSocketState.CONNECTED:
             return

        is_done = False
        final_score = 0
        snake_list_python = [] # Lista para tipos Python
        food_pos_python = None # Variable para tipos Python

        try:
            if self.env:
                is_terminated = self.env._is_terminated()
                is_truncated = self.env._is_truncated()
                is_done = is_terminated or is_truncated

                # --- CONVERSIÓN A TIPOS PYTHON ---
                if self.env.snake:
                    final_score = len(self.env.snake) - 1
                    # Convertir cada coordenada de cada segmento a int nativo
                    snake_list_python = [
                        (int(seg[0]), int(seg[1])) for seg in self.env.snake
                    ]
                else:
                    final_score = 0
                    snake_list_python = []

                if self.env.food_pos:
                    # Convertir coordenadas de comida a int nativo
                    food_pos_python = (int(self.env.food_pos[0]), int(self.env.food_pos[1]))
                else:
                    food_pos_python = None
                # --- FIN CONVERSIÓN ---

            else:
                is_done = True
                final_score = -1 # O 0 si prefieres

        except AttributeError:
             logger.warning("Métodos _is_terminated o _is_truncated no encontrados en SnakeEnv.")
             is_done = False
             if self.env:
                # --- CONVERSIÓN (También en fallback) ---
                if self.env.snake:
                    final_score = len(self.env.snake) - 1
                    snake_list_python = [(int(seg[0]), int(seg[1])) for seg in self.env.snake]
                else:
                     final_score = 0
                     snake_list_python = []
                if self.env.food_pos:
                     food_pos_python = (int(self.env.food_pos[0]), int(self.env.food_pos[1]))
                else:
                    food_pos_python = None
                # --- FIN CONVERSIÓN ---
             else:
                 final_score = -1

        except Exception as e:
             logger.error(f"Error obteniendo estado del entorno: {e}", exc_info=True)
             is_done = True
             final_score = -1

        # Usar las variables convertidas a tipos Python
        state_data = {
            "type": "game_state_update", "data": {
                "snake": snake_list_python, # <--- USAR LISTA PYTHON
                "food": food_pos_python,    # <--- USAR TUPLA PYTHON
                "score": int(final_score),  # <--- Asegurar que score sea int
                "gameOver": bool(is_done)   # <--- Asegurar que sea bool
            }
        }
        try:
            await self.websocket.send_text(json.dumps(state_data))
        except Exception as e:
            logger.warning(f"Cliente {self.websocket.client}: Error enviando estado (puede estar desconectándose): {e}")


    async def send_error(self, error_message: str):
         """Envía un mensaje de error al cliente WebSocket."""
         if self.websocket.client_state == WebSocketState.CONNECTED:
            error_data = { "type": "error", "data": {"message": error_message} }
            try:
                await self.websocket.send_text(json.dumps(error_data))
            except Exception as e:
                logger.warning(f"Cliente {self.websocket.client}: Error enviando mensaje de error (puede estar desconectándose): {e}")

    async def start(self): # Hacer start async para poder usar await send_error
        """Inicia la tarea del bucle de evaluación, cargando el modelo."""
        if self.task is None or self.task.done():
            logger.info(f"Cliente {self.websocket.client}: Iniciando evaluación. Intentando cargar modelo desde {BEST_MODEL_PATH_WATCH}...")
            self._stop_event.clear()
            self._loaded_watch_model = None # Resetear

            # Cargar el modelo BAJO DEMANDA
            if not os.path.exists(BEST_MODEL_PATH_WATCH):
                 logger.warning(f"Cliente {self.websocket.client}: Modelo no encontrado en {BEST_MODEL_PATH_WATCH}.")
                 await self.send_error("Modelo 'best_model.zip' no encontrado. Entrena un modelo primero.")
                 return # No iniciar tarea
            else:
                 try:
                    self._loaded_watch_model = PPO.load(BEST_MODEL_PATH_WATCH, device='cpu')
                    logger.info(f"Cliente {self.websocket.client}: Modelo cargado exitosamente desde {BEST_MODEL_PATH_WATCH}.")
                 except Exception as e:
                     logger.error(f"Cliente {self.websocket.client}: Error al cargar el modelo desde {BEST_MODEL_PATH_WATCH}: {e}", exc_info=True)
                     self._loaded_watch_model = None
                     await self.send_error(f"Error al cargar modelo: {type(e).__name__}")
                     return # No iniciar tarea

            # Si llegamos aquí, el modelo se cargó (o era None y falló)
            if self._loaded_watch_model:
                 # Crear tarea solo si el modelo se cargó bien
                 self.task = asyncio.create_task(self.run_evaluation_loop(self._loaded_watch_model))
            else:
                # Este caso no debería ocurrir si las comprobaciones anteriores son correctas
                logger.error(f"Cliente {self.websocket.client}: No se pudo iniciar la tarea de evaluación (modelo no válido después de intentar cargar).")


        else:
             logger.warning(f"Cliente {self.websocket.client}: Intento de iniciar tarea de evaluación ya existente.")

    async def stop(self):
        """Detiene la tarea del bucle de evaluación y cierra el entorno."""
        task_stopped = False
        if self.task and not self.task.done():
            if not self._stop_event.is_set():
                self._stop_event.set()
                logger.info(f"Cliente {self.websocket.client}: Enviando señal de parada a la tarea de evaluación.")
            try:
                await asyncio.wait_for(self.task, timeout=0.5)
                task_stopped = True
            except asyncio.TimeoutError:
                logger.warning(f"Cliente {self.websocket.client}: La tarea de evaluación no terminó a tiempo, cancelando.")
                self.task.cancel()
                task_stopped = True # Considerarla detenida aunque fuera por cancelación
            except asyncio.CancelledError:
                 logger.info(f"Cliente {self.websocket.client}: Tarea de evaluación cancelada.")
                 task_stopped = True
            except Exception as e:
                logger.error(f"Cliente {self.websocket.client}: Error esperando a que la tarea se detenga: {e}")
            finally:
                 self.task = None # Limpiar referencia
                 logger.info(f"Cliente {self.websocket.client}: Tarea de evaluación detenida o cancelada.")
        # else:
             # logger.info(f"Cliente {self.websocket.client}: No había tarea de evaluación activa para detener.")

        # Siempre intentar cerrar el entorno al detener
        await self._close_env()
        return task_stopped


# --- WebSocket Endpoint para "Ver IA" ---
@app.websocket("/ws/watch")
async def websocket_watch_ai(websocket: WebSocket):
    ws_manager = await get_websocket_manager_instance()
    await ws_manager.connect(websocket, "watch")
    evaluator = AiEvaluator(websocket, ws_manager)
    try:
        while True:
            message = await websocket.receive_text()
            client_info = f"Cliente {websocket.client} (/ws/watch)"
            logger.info(f"{client_info}: Mensaje recibido: {message}")
            if message == "start":
                # Detener anterior por si acaso, luego iniciar nuevo
                await evaluator.stop()
                await evaluator.start() # start ahora es async
            elif message == "stop":
                 await evaluator.stop()
            else:
                 logger.warning(f"{client_info}: Mensaje desconocido: {message}")
                 await evaluator.send_error(f"Comando desconocido: {message}")
    except WebSocketDisconnect:
        logger.info(f"Cliente {websocket.client} (Ver IA) desconectado.")
    except Exception as e:
         logger.error(f"Error en el manejo del WebSocket /ws/watch ({websocket.client}): {e}", exc_info=True)
    finally:
        # Asegurarse de detener la tarea y desconectar al salir
        logger.info(f"Limpiando conexión /ws/watch para {websocket.client}...")
        await evaluator.stop()
        ws_manager.disconnect(websocket, "watch")
        logger.info(f"Cliente {websocket.client} (Ver IA) limpiado completamente.")


# --- WebSocket Endpoint para Actualizaciones de Entrenamiento ---
@app.websocket("/ws/training_updates")
async def websocket_training_updates(websocket: WebSocket):
    ws_manager = await get_websocket_manager_instance()
    tm = await get_training_manager_instance()
    await ws_manager.connect(websocket, "training")
    client_info = f"Cliente {websocket.client} (Training)"
    try:
        # Enviar estado actual
        current_status = tm.get_status()
        status_message = {
            "type": "training_status",
            "data": current_status.model_dump() if hasattr(current_status, 'model_dump') else current_status.dict()
        }
        await websocket.send_text(json.dumps(status_message))
        logger.info(f"{client_info}: Estado inicial enviado: {current_status.status}")

        # Mantener conexión
        while True:
            # Esperar desconexión limpiamente
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info(f"{client_info} desconectado.")
    except Exception as e:
        logger.error(f"Error en WebSocket /ws/training_updates ({client_info}): {e}", exc_info=True)
    finally:
        ws_manager.disconnect(websocket, "training")
        logger.info(f"{client_info} limpiado.")


# --- Servir Archivos Estáticos del Frontend ---
@app.get("/", include_in_schema=False)
async def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        logger.error(f"No se encontró index.html en: {os.path.abspath(index_path)}")
        raise HTTPException(status_code=404, detail="index.html not found")

try:
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), FRONTEND_DIR))
    if not os.path.isdir(static_dir):
        logger.error(f"Directorio frontend no encontrado en: {static_dir}. Verifica la ruta FRONTEND_DIR.")
    else:
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static_frontend")
        logger.info(f"Sirviendo archivos estáticos desde: {static_dir}")
except Exception as e:
    logger.error(f"Error al montar directorio estático: {e}", exc_info=True)


# --- Punto de Entrada Uvicorn ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Iniciando servidor Uvicorn para la aplicación FastAPI...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )