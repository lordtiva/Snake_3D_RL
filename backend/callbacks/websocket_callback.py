# backend/callbacks/websocket_callback.py
import json
import logging
import queue
import numpy as np
import collections
from stable_baselines3.common.callbacks import BaseCallback
# from stable_baselines3.common.vec_env import VecEnv # Para type hints si es necesario

# Configurar logger para este módulo
logger = logging.getLogger(__name__)
# Asegúrate que el nivel de logging general (configurado en main.py)
# permita ver los mensajes DEBUG si los necesitas para depurar.

class WebSocketUpdateCallback(BaseCallback):
    """
    Callback personalizado de Stable Baselines3 para enviar métricas de entrenamiento
    a través de una cola (queue) para ser transmitidas por WebSocket.

    Calcula la media de recompensa y longitud de los últimos episodios y
    extrae métricas clave seleccionadas del logger interno de SB3.
    """
    def __init__(self, update_queue: queue.Queue, verbose=0):
        """
        Inicializa el callback.
        :param update_queue: La cola donde se pondrán los mensajes JSON para el WebSocket.
        :param verbose: Nivel de verbosidad (0 o 1).
        """
        super().__init__(verbose)
        self.update_queue = update_queue
        # Usar deque para almacenar eficientemente la información de los últimos N episodios
        self.ep_info_buffer = collections.deque(maxlen=100) # Almacena info de los últimos 100 episodios

    def _on_step(self) -> bool:
        """
        Se llama después de cada paso del entorno (o colección de pasos en VecEnv).
        Recolecta información de episodios terminados.
        """
        # 'infos' es un array de diccionarios, uno por entorno paralelo, disponible después de env.step()
        if "infos" in self.locals:
            for info in self.locals.get("infos", []):
                 # Buscar la clave 'episode' que añade RecordEpisodeStatistics o Monitor
                maybe_ep_info = info.get("episode")
                if maybe_ep_info is not None:
                    # SB3 v2+ con RecordEpisodeStatistics añade 'r', 'l', 't'
                    if 'r' in maybe_ep_info and 'l' in maybe_ep_info:
                         self.ep_info_buffer.append(maybe_ep_info)
                # Fallback por si la info está directamente en el dict (menos común con VecEnv)
                elif 'r' in info and 'l' in info:
                     self.ep_info_buffer.append({'r': info['r'], 'l': info['l']})

        # Siempre devolver True para continuar el entrenamiento
        return True

    def _on_rollout_end(self) -> None:
        """
        Se llama al final de cada rollout (colección de n_steps).
        Calcula métricas promedio y las pone en la cola.
        """
        metrics = {} # Diccionario para almacenar las métricas de este rollout
        current_timestep = self.num_timesteps # Timestep actual total del entrenamiento

        # --- 1. Calcular Métricas de Episodio (Recompensa/Longitud Media) ---
        if self.ep_info_buffer:
            all_rewards = [ep['r'] for ep in self.ep_info_buffer if 'r' in ep]
            all_lengths = [ep['l'] for ep in self.ep_info_buffer if 'l' in ep]
            if all_rewards:
                 metrics["ep_rew_mean"] = round(np.mean(all_rewards), 2)
            if all_lengths:
                 metrics["ep_len_mean"] = round(np.mean(all_lengths), 2)

        # --- 2. Extraer Métricas Seleccionadas del Logger Interno de SB3 ---
        keys_to_log_from_sb3 = [
            "train/value_loss",           # Pérdida de la función de valor
            "rollout/explained_variance", # Varianza explicada
        ]

        # Acceder al diccionario de valores del logger de SB3 de forma segura
        sb3_logger_values = self.logger.name_to_value if hasattr(self.logger, 'name_to_value') else {}

        # --- Log para ver qué claves están disponibles (Nivel DEBUG) ---
        # Descomenta la siguiente línea si necesitas depurar qué métricas registra SB3
        # logger.debug(f"Callback WS: Claves disponibles en logger SB3: {list(sb3_logger_values.keys())}")
        # --- Fin Log ---

        if isinstance(sb3_logger_values, dict):
            for key in keys_to_log_from_sb3:
                 if key in sb3_logger_values:
                    # --- Log específico para ver si se encuentra la clave (Nivel DEBUG) ---
                    logger.debug(f"Callback WS: Clave '{key}' encontrada en logger SB3.")
                    # --- Fin Log ---
                    value = sb3_logger_values[key]
                    metric_name = key.split("/")[-1] # Tomar el nombre después de '/'
                    # Asegurarse de que el valor sea numérico antes de añadirlo
                    if isinstance(value, (int, float, np.number)):
                         # Redondear flotantes a 4 decimales, convertir numpy numbers a float/int estándar
                         if isinstance(value, (np.floating, float)):
                            metrics[metric_name] = round(float(value), 4)
                         elif isinstance(value, (np.integer, int)):
                             metrics[metric_name] = int(value)
                         else: # Otros tipos numéricos de numpy
                              metrics[metric_name] = float(value)
                    else:
                         logger.warning(f"Callback WS: Valor para clave '{key}' no es numérico: {value} (Tipo: {type(value)})")

                 # --- Log si la clave NO se encuentra (Nivel DEBUG) ---
                 # else:
                 #    logger.debug(f"Callback WS: Clave '{key}' NO encontrada en logger SB3 en este rollout.")
                 # --- Fin Log ---

        # --- 3. Enviar Métricas si Hay Alguna ---
        if metrics:
            metrics['timestep'] = current_timestep # Añadir siempre timestep

            # --- Log para ver qué se va a enviar (Nivel DEBUG) ---
            logger.debug(f"Callback WS: Métricas a enviar: {metrics}")
            # --- Fin Log ---

            message = { "type": "training_metric", "data": metrics }
            try:
                self.update_queue.put_nowait(json.dumps(message, separators=(',', ':')))
            except queue.Full:
                logger.warning("Cola de métricas WS llena (rollout_end). Mensaje descartado.")
            except Exception as e:
                logger.error(f"Error al poner métricas en cola WS (rollout_end): {e}")
        # else:
             # logger.debug("Callback WS: No se enviaron métricas (diccionario vacío).") # Log opcional

    def _on_training_start(self) -> None:
        """
        Se llama una vez al inicio del entrenamiento.
        """
        self.ep_info_buffer.clear()
        logger.info("Callback WS: Inicio del entrenamiento.")
        message = { "type": "training_log", "data": {"message": "Inicio del entrenamiento."}}
        try:
            self.update_queue.put_nowait(json.dumps(message))
        except queue.Full: pass # Ignorar si la cola está llena para este log
        except Exception as e: logger.error(f"Error en cola WS (training_start): {e}")


    def _on_training_end(self) -> None:
        """
        Se llama una vez al final del entrenamiento.
        """
        logger.info("Callback WS: Fin del entrenamiento.")
        message = { "type": "training_log", "data": {"message": "Fin del entrenamiento."}}
        try:
            self.update_queue.put_nowait(json.dumps(message))
        except queue.Full: pass # Ignorar si la cola está llena para este log
        except Exception as e: logger.error(f"Error en cola WS (training_end): {e}")