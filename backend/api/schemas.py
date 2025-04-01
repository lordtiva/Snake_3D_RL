# backend/api/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any # Añadir Dict y Any

class TrainingParams(BaseModel):
    """Parámetros para iniciar un nuevo entrenamiento."""
    total_timesteps: int = Field(..., gt=0, description="Número total de pasos de entrenamiento (o adicionales si se continúa).")
    num_cpu: int = Field(..., ge=1, description="Número de CPUs/entornos paralelos.")
    learning_rate: float = Field(..., gt=0, description="Tasa de aprendizaje inicial.")

    # --- MEJORAS: Añadir nuevos parámetros configurables ---
    board_size: Optional[int] = Field(20, ge=5, description="Tamaño del tablero (lado N para NxN). Mínimo 5.")
    seed: Optional[int] = Field(None, description="Semilla aleatoria para reproducibilidad (opcional).")
    # policy_kwargs permite pasar argumentos al constructor de la política (ej: arquitectura de red)
    # Usamos Dict[str, Any] para flexibilidad, pero se podría definir un schema más estricto si se quisiera.
    policy_kwargs: Optional[Dict[str, Any]] = Field(None, description="Argumentos adicionales para la política (ej: {'net_arch': ...}).")
    # --- FIN MEJORAS ---

    # Ejemplo de otros hiperparámetros que podrías añadir aquí:
    # gamma: float = Field(0.99, gt=0, lt=1, description="Factor de descuento.")
    # ent_coef: float = Field(0.0, ge=0, description="Coeficiente de entropía.")
    # clip_range: float = Field(0.2, gt=0, description="Rango de recorte PPO.")
    # n_epochs: int = Field(10, gt=0, description="Épocas de optimización por actualización.")
    # batch_size: int = Field(64, gt=0, description="Tamaño del minibatch.")
    # gae_lambda: float = Field(0.95, gt=0, le=1, description="Factor Lambda para GAE.")

    class Config:
        # Ejemplo para Pydantic v1 (si usas v2, esto no es necesario o cambia)
        # extra = 'ignore' # Ignorar campos extra enviados por el frontend
        pass


class TrainingStatus(BaseModel):
    """Estado actual del proceso de entrenamiento."""
    status: str = Field(..., description="Estado actual (ej: Detenido, Entrenando, Error).")
    current_step: int = Field(0, description="Paso actual del entrenamiento.")
    total_steps: int = Field(0, description="Número total de pasos objetivo para el entrenamiento actual.")
    message: Optional[str] = Field(None, description="Mensajes adicionales o de error.")