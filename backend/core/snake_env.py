# backend/core/snake_env.py
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import collections  # Para usar deque
import logging

# --- Definir Logger a Nivel de Módulo ---
logger = logging.getLogger(__name__) # <-- DEFINIR LOGGER AQUÍ

class SnakeEnv(gym.Env):
    """
    Entorno Gymnasium para Snake 20x20 con observación mejorada,
    recompensa ajustada y soporte para action masking.
    """
    metadata = {'render_modes': ['human', 'ansi'], 'render_fps': 10}
    DEFAULT_BOARD_SIZE = 20

    def __init__(self, board_size=DEFAULT_BOARD_SIZE, render_mode=None):
        super().__init__()
        self.board_size = board_size
        assert board_size >= 5
        self.render_mode = render_mode
        logger.info(f"Inicializando SnakeEnv con board_size={board_size}")

        self.action_space = spaces.Discrete(4) # 0:Up, 1:Right, 2:Down, 3:Left

        # Espacio de Observación (18 características)
        self.obs_dim = 18
        low = np.full(self.obs_dim, -1.0, dtype=np.float32)
        high = np.full(self.obs_dim, 1.0, dtype=np.float32)
        low[0:7]=0; high[0:7]=1; low[9:13]=0; high[9:13]=1; low[13:17]=0; high[13:17]=1; low[17]=0; high[17]=1
        self.observation_space = spaces.Box(low, high, dtype=np.float32)
        logger.info(f"Observation space: {self.observation_space}")

        # Estado interno
        self.snake = None
        self.direction = None
        self.food_pos = None
        self.current_step = 0
        self.max_steps_without_food = board_size * board_size * 2
        self.steps_since_last_food = 0
        self.last_reward = 0
        self._terminated = False
        self._truncated = False
        self.np_random = None

        # --- Mapa de acciones a vectores de movimiento (dy, dx) ---
        self._action_to_direction = {
            0: np.array([-1, 0]),  # Arriba (UP)
            1: np.array([0, 1]),   # Derecha (RIGHT)
            2: np.array([1, 0]),   # Abajo (DOWN)
            3: np.array([0, -1])   # Izquierda (LEFT)
        }

    def _place_food(self):
        # ... (sin cambios)
        if self.np_random is None:
            seed = np.random.randint(0, 2**32 - 1); super().reset(seed=seed)
            logger.warning("np_random reinicializado en _place_food.")
        while True:
            pos = tuple(self.np_random.integers(0, self.board_size, size=2))
            if pos not in set(self.snake): self.food_pos = pos; return

    def _get_info(self):
        """Devuelve información adicional (útil para logging/debugging)."""
        return {
            "snake_length": len(self.snake) if self.snake else 0,
            "food_pos": self.food_pos,
            "head_pos": self.snake[0] if self.snake else None,
            "direction": self.direction,
            "steps_since_food": self.steps_since_last_food,
            "last_reward": self.last_reward, # Recompensa del paso anterior
            "current_step": self.current_step,
        }

    def _is_collision(self, point):
        """Comprueba colisión inmediata con paredes o cuerpo ACTUAL."""
        y, x = point
        # Paredes
        if not (0 <= y < self.board_size and 0 <= x < self.board_size):
            return True
        # Cuerpo (incluyendo la cabeza actual para la comprobación de máscara,
        # ya que si la acción lleva a la posición actual de un segmento, es inválida)
        # Usamos toda la serpiente actual para la máscara.
        if self.snake and tuple(point) in set(list(self.snake)):
             return True
        return False

    # --- !! NUEVO MÉTODO: action_masks !! ---
    def action_masks(self) -> np.ndarray:
        """
        Devuelve una máscara booleana indicando acciones válidas.
        Una acción es inválida si lleva a una colisión inmediata (pared o cuerpo).
        """
        head_np = np.array(self.snake[0])
        valid_actions = [True] * 4 # Empezar asumiendo que todas son válidas

        for action, move_vec in self._action_to_direction.items():
            potential_next_head = head_np + move_vec
            # Si moverse a potential_next_head es una colisión, la acción es inválida
            if self._is_collision(tuple(potential_next_head)):
                valid_actions[action] = False

        return np.array(valid_actions)
    # --- FIN NUEVO MÉTODO ---

    def _get_obs(self):
        # ... (Lógica de observación sin cambios, usa _is_collision) ...
        # Asegúrate de que _is_collision aquí use la lógica correcta para la observación
        # (probablemente excluyendo la cola si no se comió, como estaba antes)
        # La función _is_collision definida arriba es para la MÁSCARA.
        # Podrías necesitar renombrar o duplicar la lógica si difieren.
        # Por simplicidad, asumiremos que la _is_collision actual funciona para ambos,
        # aunque la comprobación de máscara es más estricta (incluye la cabeza).
        # --- (Código de _get_obs igual que en la versión anterior) ---
        if not self.snake: return np.zeros(self.observation_space.shape, dtype=np.float32)
        head=self.snake[0]; head_y, head_x = head
        dir_vectors={0:(-1,0),1:(0,1),2:(1,0),3:(0,-1)}; current_dir_vec=np.array(dir_vectors[self.direction])
        left_dir_vec=np.array([current_dir_vec[1],-current_dir_vec[0]]); right_dir_vec=np.array([-current_dir_vec[1],current_dir_vec[0]])
        point_ahead=np.array(head)+current_dir_vec; point_left=np.array(head)+left_dir_vec; point_right=np.array(head)+right_dir_vec
        danger_ahead=1.0 if self._is_collision(point_ahead) else 0.0 # Usa _is_collision (¿correcto para obs?)
        danger_left=1.0 if self._is_collision(point_left) else 0.0
        danger_right=1.0 if self._is_collision(point_right) else 0.0
        point_N=(head_y-1,head_x); point_S=(head_y+1,head_x); point_E=(head_y,head_x+1); point_W=(head_y,head_x-1)
        danger_N=1.0 if self._is_collision(point_N) else 0.0; danger_S=1.0 if self._is_collision(point_S) else 0.0
        danger_E=1.0 if self._is_collision(point_E) else 0.0; danger_W=1.0 if self._is_collision(point_W) else 0.0
        food_y,food_x = self.food_pos if self.food_pos else (head_y,head_x)
        food_dir_y_norm=np.clip((food_y-head_y)/self.board_size,-1.,1.); food_dir_x_norm=np.clip((food_x-head_x)/self.board_size,-1.,1.)
        dist_N_norm=head_y/(self.board_size-1) if self.board_size>1 else 0; dist_S_norm=(self.board_size-1-head_y)/(self.board_size-1) if self.board_size>1 else 0
        dist_W_norm=head_x/(self.board_size-1) if self.board_size>1 else 0; dist_E_norm=(self.board_size-1-head_x)/(self.board_size-1) if self.board_size>1 else 0
        dir_one_hot=np.zeros(4,dtype=np.float32);
        if self.direction is not None: dir_one_hot[self.direction]=1.0
        len_norm=len(self.snake)/(self.board_size*self.board_size)
        observation=np.array([danger_ahead,danger_left,danger_right,danger_N,danger_S,danger_E,danger_W,
                              food_dir_y_norm,food_dir_x_norm,dist_N_norm,dist_S_norm,dist_W_norm,dist_E_norm,
                              dir_one_hot[0],dir_one_hot[1],dir_one_hot[2],dir_one_hot[3],len_norm], dtype=np.float32)
        if observation.shape[0] != self.obs_dim:
             logger.error(f"¡Error de forma en observación! Esperado {self.obs_dim}, Obtenido {observation.shape[0]}")
             return np.zeros(self.observation_space.shape, dtype=np.float32)
        return observation


    def reset(self, seed=None, options=None):
        """Reinicia el entorno a un estado inicial."""
        super().reset(seed=seed) # Importante llamar primero

        start_y = self.board_size // 2
        start_x = self.board_size // 2
        self.snake = collections.deque([(start_y, start_x)])
        self.direction = self.action_space.sample()
        self._place_food()
        self.current_step = 0
        self.steps_since_last_food = 0
        self.last_reward = 0
        self._terminated = False
        self._truncated = False

        observation = self._get_obs()
        info = self._get_info() # Asegurarse que info no contenga claves que interfieran con wrappers

        if self.render_mode == "human":
            self._render_frame()

        # --- !! CORRECCIÓN: Añadir return !! ---
        return observation, info
        # --- FIN CORRECCIÓN ---

    def step(self, action):
        # --- Lógica de Recompensa y Movimiento Ajustada Anteriormente ---
        # Mantener la recompensa de -0.05 por paso, +40 por comida, -100 por muerte
        # (Ajusta si quieres experimentar más)
        REWARD_FOOD = 40.0
        REWARD_DEATH = -100.0
        REWARD_STEP = -0.05
        REWARD_DIST_FACTOR = 0.1 # Factor para recompensa por distancia

        old_head = self.snake[0]; old_food_pos = self.food_pos
        self.current_step += 1; self.steps_since_last_food += 1
        self._terminated = False; self._truncated = False; reward = 0.0

        # --- Determinar Dirección Real (evitar reversa) ---
        opposite_direction = (self.direction + 2) % 4
        if len(self.snake) > 1 and action == opposite_direction: action = self.direction
        self.direction = action

        # --- Mover Cabeza ---
        move_vec = self._action_to_direction[self.direction]
        new_head = (old_head[0] + move_vec[0], old_head[1] + move_vec[1])

        # --- Comprobar Colisiones (Paredes y Cuerpo) ---
        # Usar la misma lógica de colisión que la máscara aquí es consistente
        if self._is_collision(new_head):
             self._terminated = True
             reward = REWARD_DEATH
             logger.debug(f"Step {self.current_step}: Muerte por colisión. Pos: {new_head}")

        # --- Comida y Recompensas (si no muerto) ---
        ate_food = False
        if not self._terminated:
            if new_head == self.food_pos:
                ate_food = True
                reward = REWARD_FOOD
                self.steps_since_last_food = 0
                # logger.debug(f"Step {self.current_step}: Comida! Score: {len(self.snake)}")
            else:
                # Penalización por paso + Recompensa/Penalización por Distancia
                reward = REWARD_STEP
                if old_food_pos: # Calcular distancia solo si había comida
                    old_dist = np.linalg.norm(np.array(old_head) - np.array(old_food_pos))
                    new_dist = np.linalg.norm(np.array(new_head) - np.array(old_food_pos))
                    reward += (old_dist - new_dist) * REWARD_DIST_FACTOR

        # --- Actualizar Serpiente ---
        if not self._terminated:
            self.snake.appendleft(new_head)
            if ate_food: self._place_food()
            elif len(self.snake) > 1: self.snake.pop()

        # --- Truncamiento ---
        if not self._terminated and self.steps_since_last_food > self.max_steps_without_food:
             self._truncated = True
             # logger.debug(f"Step {self.current_step}: Truncado por inanición.")

        # --- Final ---
        observation = self._get_obs()
        info = self._get_info()
        self.last_reward = reward
        info["reward"] = reward # Incluir recompensa del paso actual

        # --- Action Mask para el *siguiente* estado (SB3 lo pide aquí) ---
        # Es crucial que esto se devuelva en 'info' si el VecEnv no lo maneja automáticamente
        # SB3 MaskablePPO espera encontrar la máscara aquí si no la obtiene del VecEnv wrapper
        info["action_mask"] = self.action_masks()

        if self.render_mode == "human": self._render_frame()
        elif self.render_mode == "ansi": print(self._render_ansi())
        return observation, reward, self._terminated, self._truncated, info

    # --- Métodos Helper y Renderizado ---

    def render(self):
        """Renderiza el estado actual según el modo."""
        if self.render_mode == 'ansi':
            print(self._render_ansi())
        elif self.render_mode == 'human':
            # Aquí podría ir lógica para Pygame/etc.
            # Por ahora, puede imprimir ANSI o nada.
             print(self._render_ansi()) # Usar ANSI para human temporalmente
             # import time # Descomentar si quieres pausa
             # time.sleep(max(0.01, 1.0 / self.metadata['render_fps']))

    def _render_frame(self):
       """Lógica interna para renderizado 'human' (placeholder)."""
       # Por ahora, no hace nada distinto a render()
       pass

    def _render_ansi(self):
        """Renderiza el estado actual en formato texto para la consola."""
        # Crear rejilla vacía
        grid = [['.' for _ in range(self.board_size)] for _ in range(self.board_size)]
        # Dibujar comida
        if self.food_pos and 0 <= self.food_pos[0] < self.board_size and 0 <= self.food_pos[1] < self.board_size:
            grid[self.food_pos[0]][self.food_pos[1]] = 'F'
        # Dibujar serpiente
        if self.snake:
            for i, segment in enumerate(self.snake):
                if 0 <= segment[0] < self.board_size and 0 <= segment[1] < self.board_size:
                    grid[segment[0]][segment[1]] = 'H' if i == 0 else 'S'
        # Construir output
        # Dibujar borde superior
        output = "+-" + "-".join(["-"] * self.board_size) + "-+\n"
        # Dibujar filas
        for row in grid:
            output += "| " + " ".join(row) + " |\n"
         # Dibujar borde inferior
        output += "+-" + "-".join(["-"] * self.board_size) + "-+\n"
        score = len(self.snake) -1 if self.snake else 0
        output += f"Score: {score} | Step: {self.current_step} | Steps w/o food: {self.steps_since_last_food} | LastRew: {self.last_reward:.2f}"
        if self._terminated: output += " | TERMINATED"
        if self._truncated: output += " | TRUNCATED"
        return output

    def close(self):
        """Limpia recursos si es necesario."""
        # Si usaras Pygame, cerrarías la ventana aquí
        logger.info("Cerrando SnakeEnv.")
        pass
