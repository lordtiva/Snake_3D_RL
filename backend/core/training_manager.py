# backend/core/training_manager.py
import os
import threading
import time
import logging
import psutil
import torch
import queue
import json
import asyncio
from typing import Optional, Dict, Any # Añadir Any para policy_kwargs

# Importar wrappers y tipos necesarios de Gymnasium y SB3
from gymnasium.wrappers import RecordEpisodeStatistics
from stable_baselines3 import PPO
from sb3_contrib import MaskablePPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv, VecEnv # Importar VecEnv base
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback, EvalCallback
from stable_baselines3.common.policies import ActorCriticPolicy # Para type hint si fuera necesario

# Importar nuestros componentes personalizados
from callbacks.websocket_callback import WebSocketUpdateCallback
from core.snake_env import SnakeEnv # Asumiendo que SnakeEnv puede aceptar board_size
# Asegúrate de que TrainingParams en schemas.py se actualice si añades board_size, seed, policy_kwargs
from api.schemas import TrainingParams, TrainingStatus

logger = logging.getLogger(__name__)

# --- Directorios y Constantes ---
LOG_DIR = "logs"
TENSORBOARD_LOG_DIR = os.path.join(LOG_DIR, "tensorboard_logs")
BEST_MODEL_SAVE_PATH = os.path.join(LOG_DIR, "best_model")
CHECKPOINT_SAVE_PATH = os.path.join(LOG_DIR, "checkpoints")
LAST_MODEL_PATH = os.path.join(LOG_DIR, "last_model.zip")

# Crear directorios si no existen
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(TENSORBOARD_LOG_DIR, exist_ok=True)
os.makedirs(BEST_MODEL_SAVE_PATH, exist_ok=True)
os.makedirs(CHECKPOINT_SAVE_PATH, exist_ok=True)

# --- Callback para detener el entrenamiento (Simple y correcto) ---
class StopTrainingCallback(BaseCallback):
    """
    Callback simple para detener el entrenamiento de SB3 cuando un evento threading se activa.
    """
    def __init__(self, stop_event: threading.Event, verbose=0):
        super().__init__(verbose)
        self.stop_event = stop_event

    def _on_step(self) -> bool:
        """
        Se llama en cada paso del algoritmo. Devuelve False para detener el entrenamiento.
        """
        if self.stop_event.is_set():
            logger.info("StopTrainingCallback: Señal de parada detectada.")
            return False  # Detiene model.learn()
        return True

# --- Clase TrainingManager ---
class TrainingManager:
    """
    Gestiona el ciclo de vida del entrenamiento de RL (usando Stable Baselines 3),
    maneja el estado, parámetros, y comunicación con el frontend vía WebSockets.
    """
    def __init__(self, ws_manager):
        """
        Inicializa el gestor de entrenamiento.
        :param ws_manager: Instancia del WebSocketManager para enviar actualizaciones.
        """
        self.current_status = TrainingStatus(status="Detenido") # Estado inicial
        self._training_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event() # Evento para señalar la parada del entrenamiento
        self._model: Optional[PPO] = None # Instancia del modelo SB3
        self._vec_env: Optional[VecEnv] = None # Entorno vectorizado SB3
        self._eval_env: Optional[RecordEpisodeStatistics] = None # Entorno de evaluación
        self.current_params: Optional[TrainingParams] = None # Parámetros del entrenamiento actual
        self._update_queue = queue.Queue() # Cola para comunicación Thread -> Async loop
        self._ws_manager = ws_manager # Gestor de WebSockets
        self._message_broadcaster_thread: Optional[threading.Thread] = None # Hilo para enviar mensajes WS
        self._run_broadcaster = threading.Event() # Señal para controlar el hilo broadcaster
        self._main_event_loop = None # Referencia al loop asyncio principal (inyectado después)

        logger.info("TrainingManager instanciado.")

    def set_main_event_loop(self, loop):
        """Establece el bucle de eventos principal y arranca el broadcaster de mensajes."""
        if not self._main_event_loop:
            self._main_event_loop = loop
            logger.info("Bucle de eventos principal establecido en TrainingManager.")
            self._start_message_broadcaster() # Arrancar broadcaster ahora
        else:
            logger.warning("Intento de re-establecer el bucle de eventos principal.")

    # --- Métodos para manejar el Broadcaster de mensajes WS (Thread-safe) ---
    def _start_message_broadcaster(self):
        """Inicia el hilo que envía mensajes de la cola al WebSocketManager."""
        if self._main_event_loop is None:
             logger.error("No se puede iniciar el broadcaster: falta el bucle de eventos principal.")
             return
        if self._message_broadcaster_thread is None or not self._message_broadcaster_thread.is_alive():
            self._run_broadcaster.set()
            # Asegurar cola limpia al (re)iniciar
            while not self._update_queue.empty():
                try: self._update_queue.get_nowait()
                except queue.Empty: break
            self._message_broadcaster_thread = threading.Thread(target=self._broadcast_messages, daemon=True, name="WSBroadcasterThread")
            self._message_broadcaster_thread.start()
            logger.info("Hilo broadcaster de mensajes WebSocket iniciado.")

    def _stop_message_broadcaster(self):
        """Detiene el hilo broadcaster y limpia la cola."""
        if not self._run_broadcaster.is_set(): # Si ya se pidió detener, no hacer nada
            return
        logger.info("Deteniendo hilo broadcaster de mensajes WebSocket...")
        self._run_broadcaster.clear()
        self._update_queue.put_nowait(None) # Despertar al hilo si está esperando en get()
        if self._message_broadcaster_thread and self._message_broadcaster_thread.is_alive():
            self._message_broadcaster_thread.join(timeout=1.0)
            if self._message_broadcaster_thread.is_alive():
                 logger.warning("El hilo broadcaster no terminó limpiamente después de 1s.")
        self._message_broadcaster_thread = None
        logger.info("Hilo broadcaster de mensajes WebSocket detenido.")
        # Limpiar cola por si quedaron mensajes
        while not self._update_queue.empty():
            try: self._update_queue.get_nowait()
            except queue.Empty: break

    def _schedule_broadcast(self, message_json: str):
        """Planifica la ejecución de broadcast_to_training en el loop principal (thread-safe)."""
        if self._main_event_loop and self._main_event_loop.is_running():
            self._main_event_loop.call_soon_threadsafe(
                asyncio.create_task,
                self._ws_manager.broadcast_to_training(message_json)
            )
        else:
            logger.warning("Intento de planificar broadcast sin bucle principal activo o disponible.")

    def _broadcast_messages(self):
        """Función ejecutada por el hilo broadcaster. Lee de la cola y planifica envíos."""
        logger.info("Hilo broadcaster iniciado y esperando mensajes...")
        while self._run_broadcaster.is_set():
            try:
                message_json = self._update_queue.get(block=True, timeout=1.0)
                if message_json is None:
                    logger.info("Hilo broadcaster recibió señal de parada (None).")
                    break
                self._schedule_broadcast(message_json)
                # self._update_queue.task_done() # No es estrictamente necesario si no se usa join() en la cola
            except queue.Empty:
                continue # Simplemente volver a esperar si hay timeout
            except Exception as e:
                logger.error(f"Error en el hilo broadcaster: {e}", exc_info=True)
                time.sleep(0.1) # Evitar bucle rápido en caso de error persistente
        logger.info("Hilo broadcaster finalizado.")

    # --- Actualización y envío de Estado ---
    def _update_status(self, status: str, message: Optional[str] = None, current_step: Optional[int] = None, total_steps: Optional[int] = None):
        """Actualiza el estado interno y pone el nuevo estado en la cola para broadcast."""
        # Actualizar estado interno
        changed = False
        if status is not None and self.current_status.status != status:
            self.current_status.status = status
            changed = True
        if message is not None and self.current_status.message != message:
             self.current_status.message = message
             changed = True
        # Limpiar mensaje si el estado ya no es final/informativo
        elif status not in ["Error", "Completado", "Detenido"] and self.current_status.message is not None:
             self.current_status.message = None
             changed = True

        if current_step is not None and self.current_status.current_step != current_step:
            self.current_status.current_step = current_step
            changed = True
        if total_steps is not None and self.current_status.total_steps != total_steps:
            self.current_status.total_steps = total_steps
            changed = True

        # Solo loguear y enviar si algo cambió para reducir ruido
        if changed:
            logger.info(f"Estado actualizado: Status='{self.current_status.status}', "
                        f"Steps={self.current_status.current_step}/{self.current_status.total_steps}, "
                        f"Msg='{self.current_status.message or ''}'")

            # Crear y poner en cola el mensaje
            status_data = self.current_status.model_dump() if hasattr(self.current_status, 'model_dump') else self.current_status.dict()
            status_message = {"type": "training_status", "data": status_data}
            try:
                self._update_queue.put_nowait(json.dumps(status_message))
            except queue.Full:
                logger.warning("Cola de actualizaciones WS llena al enviar estado.")
            except Exception as e:
                logger.error(f"Error al poner estado en cola WS: {e}")

    # --- Bucle Principal de Entrenamiento (Ejecutado en un Hilo Separado) ---
    def _training_loop(self, params: TrainingParams, continue_mode: bool = False):
        """Contiene la lógica principal de configuración y ejecución del entrenamiento SB3."""
        # Obtener parámetros configurables o usar defaults
        # Asumiendo que estos campos existen en TrainingParams (schemas.py) o usar getattr
        board_size = getattr(params, 'board_size', 20)
        seed = getattr(params, 'seed', None)
        policy_kwargs = getattr(params, 'policy_kwargs', None)

        logger.info(f"Iniciando _training_loop: continue={continue_mode}, board_size={board_size}, seed={seed}, policy_kwargs={policy_kwargs}, params={params.dict()}")
        self._stop_event.clear()
        self._eval_env = None # Reiniciar para el bloque finally

        try:
            # --- 1. Estado Inicial y Preparación ---
            initial_total_steps = params.total_timesteps if not continue_mode else 0
            self._update_status(status="Inicializando", total_steps=initial_total_steps, current_step=0, message="Configurando entorno...")

            # --- 2. Crear Entorno Vectorizado ---
            env_lambda = lambda: SnakeEnv(board_size=board_size)
            vec_env_cls = SubprocVecEnv if params.num_cpu > 1 else DummyVecEnv
            self._vec_env = make_vec_env(env_lambda, n_envs=params.num_cpu, vec_env_cls=vec_env_cls, seed=seed)
            logger.info(f"Entorno VecEnv creado: {vec_env_cls.__name__} con {params.num_cpu} envs (size={board_size}, seed={seed}).")

            total_timesteps_for_learn = 0
            start_step = 0

            # --- 3. Crear o Cargar Modelo SB3 ---
            if continue_mode:
                logger.info(f"[CONTINUE] Intentando cargar modelo MaskablePPO desde: {LAST_MODEL_PATH}")
                if not os.path.exists(LAST_MODEL_PATH):
                    raise FileNotFoundError(f"No se encontró {LAST_MODEL_PATH} para continuar.")

                self._update_status(status="Inicializando", message="Cargando modelo MaskablePPO...")
                # Nota: policy_kwargs generalmente no se pasa a load, se usan los del modelo guardado.
                # Para cambiar hiperparámetros al continuar, se usan otros métodos de SB3.
                self._model = MaskablePPO.load(LAST_MODEL_PATH, env=self._vec_env, device="auto", tensorboard_log=TENSORBOARD_LOG_DIR)
                start_step = self._model.num_timesteps
                # params.total_timesteps son los pasos *adicionales*
                total_timesteps_for_learn = start_step + params.total_timesteps
                logger.info(f"[CONTINUE] Modelo cargado. Pasos anteriores: {start_step}. "
                            f"Entrenando {params.total_timesteps} pasos adicionales. Objetivo: {total_timesteps_for_learn}")
                self._update_status(status="Inicializando", current_step=start_step, total_steps=total_timesteps_for_learn, message="Modelo cargado.")

            else: # Nuevo entrenamiento
                 logger.info("[NEW] Creando nuevo modelo PPO...")
                 self._update_status(status="Inicializando", message="Creando nuevo modelo...")
                 n_steps_per_env = max(128, 2048 // params.num_cpu)

                 # Usar policy_kwargs si se proporcionó, sino usar default
                 final_policy_kwargs = policy_kwargs if policy_kwargs else dict(net_arch=dict(pi=[128, 128], vf=[128, 128])) # Usar la red más grande
                 logger.info(f"Usando policy_kwargs: {final_policy_kwargs}")

                 self._model = MaskablePPO( "MlpPolicy", self._vec_env, verbose=0, tensorboard_log=TENSORBOARD_LOG_DIR,
                                   learning_rate=params.learning_rate, n_steps=n_steps_per_env, batch_size=64, n_epochs=10,
                                   gamma=0.99, gae_lambda=0.95, clip_range=0.2, ent_coef=0.0, vf_coef=0.5, max_grad_norm=0.5,
                                   policy_kwargs=final_policy_kwargs, seed=seed, device="auto")
                 start_step = 0
                 total_timesteps_for_learn = params.total_timesteps # Total a alcanzar
                 logger.info(f"[NEW] Modelo PPO creado. Entrenando por {params.total_timesteps} pasos. "
                             f"n_steps={n_steps_per_env}, lr={params.learning_rate}, seed={seed}")
                 self._update_status(status="Inicializando", total_steps=total_timesteps_for_learn, current_step=0, message="Modelo creado.")

            # --- 4. Configurar Callbacks ---
            logger.info("Configurando callbacks...")
            stop_callback = StopTrainingCallback(self._stop_event)
            websocket_callback = WebSocketUpdateCallback(self._update_queue, verbose=0)
            callback_list = [stop_callback, websocket_callback]

            try:
                self._eval_env = RecordEpisodeStatistics(SnakeEnv(board_size=board_size))
                steps_to_learn_this_session = total_timesteps_for_learn - start_step
                eval_freq = max(steps_to_learn_this_session // 10 // params.num_cpu, 1)
                checkpoint_freq = max(steps_to_learn_this_session // 5 // params.num_cpu, 1)
                eval_freq = max(eval_freq, 5000 // params.num_cpu) # Mínimo razonable
                checkpoint_freq = max(checkpoint_freq, 10000 // params.num_cpu) # Mínimo razonable

                logger.info(f"Entorno de evaluación creado (size={board_size}). Frecuencia eval: {eval_freq}, checkpoint: {checkpoint_freq}")
                eval_callback = EvalCallback(self._eval_env, best_model_save_path=BEST_MODEL_SAVE_PATH, log_path=LOG_DIR,
                                            eval_freq=eval_freq, n_eval_episodes=5, deterministic=True, render=False, verbose=0)
                checkpoint_callback = CheckpointCallback(save_freq=checkpoint_freq, save_path=CHECKPOINT_SAVE_PATH, name_prefix="rl_model")
                callback_list.extend([eval_callback, checkpoint_callback])
                logger.info("EvalCallback y CheckpointCallback añadidos.")
            except Exception as e_eval:
                 logger.error(f"No se pudo crear/configurar EvalCallback/CheckpointCallback: {e_eval}", exc_info=True)
                 self._eval_env = None

            # --- 5. Iniciar el Entrenamiento ---
            logger.info(f"Preparado para iniciar MaskablePPO model.learn | Objetivo total: {total_timesteps_for_learn} | "
                        f"Reset Timesteps: {not continue_mode}")
            self._update_status(status="Entrenando", current_step=start_step, total_steps=total_timesteps_for_learn, message="Iniciando bucle de aprendizaje...")
            start_time = time.time()

            # Llamada bloqueante al entrenamiento
            if self._model: # Check por si la creación/carga falló
                self._model.learn(
                    total_timesteps=total_timesteps_for_learn,
                    callback=CallbackList(callback_list),
                    log_interval=100, # Frecuencia cálculo métricas internas SB3
                    reset_num_timesteps= not continue_mode
                )
            else:
                 raise RuntimeError("El modelo no se inicializó correctamente antes de llamar a learn().")

            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"model.learn finalizado. Duración: {duration:.2f}s")

            # --- 6. Manejar Fin del Entrenamiento ---
            # Obtener pasos finales (puede ser ligeramente > total_timesteps_for_learn)
            final_steps = self._model.num_timesteps if self._model else self.current_status.current_step

            if self._stop_event.is_set():
                logger.info(f"Entrenamiento detenido por señal de stop en el paso {final_steps}.")
                self._update_status(status="Detenido", message="Entrenamiento detenido por usuario.", current_step=final_steps)
            else:
                logger.info(f"Entrenamiento completado normalmente al alcanzar {final_steps} pasos.")
                self._update_status(status="Completado", message="Entrenamiento completado.", current_step=final_steps, total_steps=total_timesteps_for_learn)

            # --- 7. Guardar Modelo Final ---
            if self._model:
                logger.info(f"Guardando último modelo en: {LAST_MODEL_PATH}")
                try:
                    self._model.save(LAST_MODEL_PATH)
                    logger.info("Último modelo guardado exitosamente.")
                except Exception as e_save:
                    logger.error(f"Error al guardar el último modelo: {e_save}", exc_info=True)
                    self._update_status(status="Error", message=f"Error guardando modelo final: {e_save}")

        except FileNotFoundError as e:
             logger.error(f"Error de archivo no encontrado en hilo de entrenamiento: {e}", exc_info=True)
             self._update_status(status="Error", message=f"Error: {e}")
        except Exception as e:
            logger.error(f"Error inesperado en el hilo de entrenamiento: {e}", exc_info=True)
            if isinstance(e, EOFError): self._update_status(status="Error", message="Error de comunicación con subproceso (EOFError).")
            else: self._update_status(status="Error", message=f"Error interno del entrenamiento: {type(e).__name__}")
        finally:
            # --- 8. Limpieza de Recursos ---
            logger.info("Inicio de limpieza de recursos del hilo de entrenamiento...")
            if self._eval_env:
                try: self._eval_env.close(); logger.info("EvalEnv cerrado.")
                except Exception as e_close: logger.error(f"Error cerrando EvalEnv: {e_close}")
                self._eval_env = None
            if self._vec_env:
                try: self._vec_env.close(); logger.info("VecEnv cerrado.")
                except Exception as e_close: logger.error(f"Error cerrando VecEnv: {e_close}")
                self._vec_env = None
            if self._model:
                 logger.info("Limpiando referencia del modelo.")
                 self._model = None
            self._stop_event.clear() # Resetear evento para la próxima vez
            logger.info("Fin de limpieza de recursos del hilo de entrenamiento.")
            # El estado final ("Detenido", "Completado", "Error") ya se envió
            # El broadcaster sigue activo hasta que se detenga explícitamente o muera la app


    # --- Métodos Públicos de Control ---
    def start_training_session(self, params: TrainingParams):
        """Inicia una nueva sesión de entrenamiento en un hilo separado."""
        logger.info(f"Solicitud para iniciar NUEVA sesión con params: {params.dict()}")
        if self._training_thread is not None and self._training_thread.is_alive():
            logger.warning("Intento de iniciar entrenamiento mientras otro ya está en curso.")
            raise ValueError("Ya hay un entrenamiento en curso.")

        self.current_params = params
        self._stop_event.clear()
        self._start_message_broadcaster() # Asegurar que esté activo
        # El estado "Iniciando" indica que la solicitud fue aceptada y el hilo se está creando
        self._update_status(status="Iniciando", current_step=0, total_steps=params.total_timesteps, message="Preparando para iniciar...")

        self._training_thread = threading.Thread(target=self._training_loop, args=(params, False), daemon=True, name="TrainingThread")
        self._training_thread.start()
        logger.info("Hilo de entrenamiento (nuevo) iniciado.")

    def continue_training_session(self, additional_timesteps: int = 1_000_000):
        """Continúa el último entrenamiento guardado en un hilo separado."""
        logger.info(f"Solicitud para CONTINUAR entrenamiento. Pasos adicionales solicitados (aprox): {additional_timesteps}")
        if self._training_thread is not None and self._training_thread.is_alive():
            raise ValueError("Ya hay un entrenamiento en curso.")
        if not os.path.exists(LAST_MODEL_PATH):
            raise FileNotFoundError("No se encontró 'last_model.zip' para continuar.")

        num_cpu_available = self.get_hardware_info()['num_cpu']
        # Crear params temporales. El loop usará los pasos adicionales.
        # Otros params como LR, policy_kwargs, board_size idealmente vendrían del modelo guardado o config.
        temp_params = TrainingParams(
            total_timesteps=additional_timesteps, num_cpu=num_cpu_available, learning_rate=0.0003 # LR es placeholder
            # board_size=...? # Podríamos intentar extraerlo si se guarda en zip
            # seed=...?
            # policy_kwargs=...?
        )
        self.current_params = temp_params
        self._stop_event.clear()
        self._start_message_broadcaster()
        self._update_status(status="Iniciando", current_step=0, total_steps=0, message="Preparando para continuar...") # Total steps se actualiza al cargar

        self._training_thread = threading.Thread(target=self._training_loop, args=(temp_params, True), daemon=True, name="TrainingThread")
        self._training_thread.start()
        logger.info("Hilo de entrenamiento (continuar) iniciado.")

    async def stop_training_session(self) -> bool:
        """Envía la señal de parada al hilo de entrenamiento."""
        stopped = False
        if self._training_thread is not None and self._training_thread.is_alive():
            if not self._stop_event.is_set():
                logger.info("Enviando señal de parada al hilo de entrenamiento...")
                self._stop_event.set()
                await asyncio.sleep(0.1) # Pequeña pausa para que el evento se procese
                stopped = True
                logger.info("Señal de parada enviada.")
                # No detener el broadcaster aquí, esperar al estado final del loop
            else:
                logger.info("La señal de parada ya estaba activa.")
                stopped = True
        else:
            logger.info("No había ningún entrenamiento activo para detener.")
            # Si no había hilo activo, detener el broadcaster por si quedó huérfano
            self._stop_message_broadcaster()

        # Limpiar referencia si el hilo ya terminó (puede pasar entre el check y ahora)
        if self._training_thread is not None and not self._training_thread.is_alive():
             logger.info("(stop_training_session) Limpiando referencia a hilo finalizado.")
             self._training_thread = None
        return stopped

    # --- Métodos de Información ---
    def get_status(self) -> TrainingStatus:
        """Devuelve el estado actual, comprobando consistencia con el hilo."""
        active_statuses = ["Entrenando", "Iniciando", "Inicializando"]
        is_thread_alive = self._training_thread is not None and self._training_thread.is_alive()

        if self.current_status.status in active_statuses and not is_thread_alive:
             logger.warning(f"Estado inconsistente detectado: Status='{self.current_status.status}' pero hilo no activo. Actualizando...")
             # Si el evento stop está activo, asumimos que se detuvo pero no actualizó estado final
             if self._stop_event.is_set():
                  self._update_status(status="Detenido", message="El hilo terminó después de señal de parada (detectado por get_status).")
             else: # Si no, asumimos que falló
                  self._update_status(status="Error", message="El hilo de entrenamiento terminó inesperadamente (detectado por get_status).")
             # Detener broadcaster en caso de inconsistencia
             self._stop_message_broadcaster()
             self._training_thread = None # Limpiar referencia

        # Detener broadcaster si el estado es final Y el hilo ya no está vivo
        elif self.current_status.status not in active_statuses and not is_thread_alive:
             self._stop_message_broadcaster()
             # Limpiar referencia al hilo si ya terminó
             if self._training_thread is not None:
                  self._training_thread = None


        return self.current_status

    def get_default_parameters(self) -> Dict:
         """Devuelve parámetros por defecto razonables."""
         physical_cpus = psutil.cpu_count(logical=False) or 1
         default_cpus = physical_cpus if physical_cpus > 0 else (psutil.cpu_count(logical=True) or 1)
         # Añadir otros defaults si se añaden a TrainingParams
         return {
             "total_timesteps": 2_000_000,
             "num_cpu": default_cpus,
             "learning_rate": 0.0003,
             # "board_size": 10, # Si lo añades a TrainingParams
             # "seed": None, # Si lo añades
             # "policy_kwargs": None # Si lo añades
         }

    def get_hardware_info(self) -> Dict:
        """Obtiene información básica de hardware (CPU/GPU)."""
        gpu_available = torch.cuda.is_available()
        gpu_name = "N/A"
        if gpu_available:
            try: gpu_name = torch.cuda.get_device_name(0)
            except Exception as e: logger.warning(f"Error obteniendo nombre de GPU: {e}"); gpu_name = "Error"
        return {"num_cpu": psutil.cpu_count(logical=False) or 1,
                "num_cpu_logical": psutil.cpu_count(logical=True) or 1,
                "gpu_available": gpu_available, "gpu_name": gpu_name}