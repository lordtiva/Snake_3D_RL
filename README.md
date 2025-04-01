# Snake 3D RL

## Descripción General

Este proyecto implementa el clásico juego de la Serpiente (Snake) en un entorno 3D utilizando **Three.js** para la visualización. La característica principal es que el control de la serpiente puede ser realizado por un agente de **Inteligencia Artificial (IA)** entrenado mediante técnicas de **Aprendizaje por Refuerzo (RL)**.

El proyecto incluye:

1.  Un **backend** en Python (usando **FastAPI**) que maneja:
    *   La lógica del entorno del juego de Snake (compatible con **Gymnasium**).
    *   El entrenamiento de agentes de RL usando **Stable Baselines3**.
    *   Una API REST para controlar el proceso de entrenamiento.
    *   WebSockets para enviar actualizaciones en tiempo real (estado del juego de la IA, métricas de entrenamiento).
    *   Servir los archivos del frontend.
2.  Un **frontend** web (HTML, CSS, JavaScript) que proporciona:
    *   Una **visualización 3D** interactiva del juego de Snake.
    *   Un modo para **jugar manualmente**.
    *   Un modo para **observar al agente de IA** entrenado jugar.
    *   Una **interfaz de control** para iniciar, detener y monitorizar el proceso de entrenamiento de RL.
    *   **Gráficos en tiempo real** (usando **Chart.js**) para visualizar las métricas de entrenamiento (recompensa, longitud de episodio, etc.).

El objetivo es crear una plataforma completa para experimentar con RL aplicado al juego Snake, con una interfaz visual atractiva e interactiva.

## Características Implementadas

*   **Visualización 3D:** Entorno del juego renderizado en 3D con Three.js.
*   **Control de Cámara:** Órbita y zoom en la vista 3D (OrbitControls).
*   **Modo de Juego Manual:** El usuario controla la serpiente usando el teclado.
*   **Modo de Visualización de IA:** Observa al mejor agente de RL entrenado jugar en tiempo real (comunicación vía WebSocket).
*   **Entorno RL Personalizado:** `SnakeEnv` compatible con la interfaz de Gymnasium.
*   **Entrenamiento RL:**
    *   Uso de Stable Baselines3 (PPO configurado por defecto).
    *   Paralelización del entorno usando `SubprocVecEnv` para aprovechar múltiples núcleos de CPU.
    *   Aceleración por GPU (si está disponible y configurada con PyTorch/CUDA).
*   **Panel de Control Web:**
    *   Interfaz para seleccionar modos (Entrenamiento, Jugar, Ver IA).
    *   Controles para iniciar nuevo entrenamiento, continuar entrenamiento anterior, detener entrenamiento (vía API REST).
    *   Configuración de parámetros básicos de entrenamiento (Total Timesteps, CPUs, Learning Rate) desde la UI.
*   **Monitorización en Tiempo Real:**
    *   Estado actual del entrenamiento (Detenido, Entrenando, Error, etc.).
    *   Progreso del entrenamiento (pasos actuales / pasos totales) - vía polling de API o WebSocket.
    *   Gráficos en tiempo real de métricas clave (Recompensa Media, Longitud Media) vía WebSocket y Chart.js.
*   **Gestión de Modelos:**
    *   Guardado automático del mejor modelo durante el entrenamiento (`EvalCallback`).
    *   Guardado automático de checkpoints periódicos (`CheckpointCallback`).
    *   Guardado del último modelo al finalizar/detener (`last_model.zip`).
    *   Carga del `best_model.zip` para el modo "Ver IA".
    *   Carga del `last_model.zip` para continuar el entrenamiento.
*   **Gestión Centralizada:** Uso de un `TrainingManager` en el backend para encapsular la lógica de RL y un `WebSocketManager` para las conexiones.
*   **Arquitectura Modular:** Código separado en frontend y backend, con módulos específicos para UI, API, WebSockets, Visualización, Lógica del Juego, etc.

## Tecnologías Utilizadas

**Backend:**

*   **Python:** (Se recomienda 3.9, 3.10 para evitar problemas con `imghdr` en dependencias)
*   **FastAPI:** Framework web asíncrono para la API REST y WebSockets.
*   **Uvicorn:** Servidor ASGI para ejecutar FastAPI.
*   **WebSockets:** Biblioteca integrada en FastAPI para comunicación en tiempo real.
*   **Stable Baselines3 (`stable-baselines3[extra]`):** Biblioteca principal para algoritmos de RL (PPO, DQN, A2C).
*   **Gymnasium:** Toolkit estándar para definir el entorno RL (`SnakeEnv`).
*   **PyTorch:** Backend de deep learning para Stable Baselines3 (aprovecha la GPU si está configurada).
*   **NumPy:** Para operaciones numéricas (estados del tablero, cálculos).
*   **psutil:** Para obtener información del sistema (número de CPUs).

**Frontend:**

*   **HTML5**
*   **CSS3**
*   **JavaScript (ES6 Modules):** Lógica del frontend.
*   **Three.js:** Biblioteca para renderizado 3D (WebGL).
    *   `OrbitControls`: Addon para control de cámara.
*   **Chart.js:** Biblioteca para crear gráficos de métricas.
*   **Import Maps:** Utilizado en `index.html` para gestionar las dependencias JS del navegador sin necesidad de un bundler.

## Instrucciones de Configuración

**Prerrequisitos:**

*   **Python:** Versión 3.9 o 3.10 recomendada. (Puede funcionar con >=3.8, pero 3.11+ puede tener problemas con dependencias viejas que usan `imghdr`). Asegúrate de que `python` y `pip` estén en tu PATH.
*   **Git:** Para clonar el repositorio.
*   **(Opcional) GPU y CUDA:** Si deseas entrenamiento acelerado por GPU, necesitarás una GPU NVIDIA compatible, los drivers NVIDIA adecuados y una versión de PyTorch instalada con soporte CUDA.

**Pasos:**

1.  **Clonar el Repositorio:**
    ```bash
    git clone https://github.com/lordtiva/Snake_3D_RL.git
    cd Snake_3D_RL
    ```

2.  **Configurar Backend:**
    *   Navega a la carpeta `backend`:
        ```bash
        cd backend
        ```
    *   Crea un entorno virtual:
        ```bash
        python -m venv .venv
        ```
    *   Activa el entorno virtual:
        *   Windows: `.\.venv\Scripts\activate`
        *   macOS/Linux: `source .venv/bin/activate`
    *   Instala las dependencias de Python:
        ```bash
        pip install torch --index-url https://download.pytorch.org/whl/cu126
        pip install fastapi uvicorn websockets python-multipart "stable-baselines3[extra]" gymnasium numpy psutil pydantic starlette
        ```

3.  **Configurar Frontend:**
    *   Las dependencias principales de JavaScript (`three.js`, `OrbitControls.js`, `chart.js`) se esperan dentro de la carpeta `frontend/libs/`.
    *   Asegúrate de que estos archivos existan en esa ubicación. Si no, descárgalos de sus respectivas fuentes (CDNs, sitios oficiales) y colócalos allí.
        *   Three.js Core (`three.core.js`): Desde el paquete de Three.js.
        *   Three.js Module (`three.module.js`): Desde el paquete de Three.js.
        *   OrbitControls (`OrbitControls.js`): Desde los ejemplos (`examples/jsm/controls/`) de Three.js.
        *   Chart.js (`chart.umd.min.js`): Desde el sitio de Chart.js.
    *   No se requiere `npm install` para esta configuración basada en `importmap`.

## Ejecutar la Aplicación

1.  **Iniciar el Servidor Backend:**
    *   Asegúrate de estar en la carpeta `backend`.
    *   Asegúrate de que el entorno virtual `(.venv)` esté activado.
    *   Ejecuta Uvicorn:
        ```bash
        uvicorn main:app --host 0.0.0.0 --port 8000 --reload
        ```
        *   `--host 0.0.0.0`: Permite el acceso desde otras máquinas en tu red local.
        *   `--port 8000`: Puerto en el que correrá el servidor.
        *   `--reload`: Reinicia automáticamente el servidor si detecta cambios en los archivos Python.

2.  **Acceder al Frontend:**
    *   Abre tu navegador web.
    *   Navega a: `http://localhost:8000` (o `http://<IP-de-tu-máquina>:8000` si accedes desde otro dispositivo en la red).

    FastAPI servirá el `index.html` y todos los archivos JS/CSS necesarios.

## Cómo Funciona

*   **Servidor FastAPI (`main.py`):** Actúa como el punto central. Define los endpoints WebSocket (`/ws/watch`, `/ws/training_updates`), incluye las rutas de la API REST (`/api/...`) desde `api/routes.py`, y sirve los archivos estáticos del frontend. Gestiona el ciclo de vida de la aplicación (ej. inyectar el loop de eventos en el `startup`).
*   **API REST (`api/routes.py`):** Proporciona endpoints HTTP para que el frontend controle el entrenamiento (iniciar, detener, continuar, obtener estado, obtener configuración). Estas rutas interactúan con la instancia singleton del `TrainingManager`.
*   **Gestor de Entrenamiento (`core/training_manager.py`):**
    *   Mantiene el estado del proceso de entrenamiento (`Detenido`, `Entrenando`, etc.).
    *   Contiene la lógica para configurar y lanzar el entrenamiento de Stable Baselines 3 (`model.learn()`).
    *   Ejecuta `model.learn()` en un **hilo separado (`threading.Thread`)** para no bloquear el servidor web FastAPI.
    *   Utiliza una `queue.Queue` y un hilo "broadcaster" dedicado para enviar actualizaciones (estado, métricas, logs) de forma segura desde el hilo de entrenamiento al `WebSocketManager` (que corre en el bucle de eventos principal de FastAPI).
    *   Maneja la carga y guardado de modelos (`last_model.zip`).
*   **Gestor de WebSockets (`api/websocket_manager.py`):** Mantiene un registro de los clientes WebSocket conectados a los diferentes endpoints (`watch` y `training`) y proporciona métodos para enviar mensajes (broadcast) a los clientes relevantes.
*   **Callbacks (`callbacks/websocket_callback.py`, `EvalCallback`, etc.):**
    *   `WebSocketUpdateCallback`: Se engancha al bucle de SB3 (`_on_rollout_end`) para extraer métricas y ponerlas en la cola del `TrainingManager`.
    *   `EvalCallback`: Evalúa periódicamente el agente y guarda el mejor modelo (`best_model.zip`).
    *   `CheckpointCallback`: Guarda el estado del modelo periódicamente.
    *   `StopTrainingCallback`: Permite detener el entrenamiento limpiamente desde la API.
*   **Frontend (`main.js`, `ui.js`, `api.js`, `websocket.js`):** Orquesta la interfaz, llama a la API REST para enviar comandos, se conecta a los WebSockets para recibir actualizaciones, y actualiza la UI (estado, logs, gráficos) y la visualización 3D en consecuencia.
*   **Visualización (`snake_visualizer.js`):** Módulo dedicado a Three.js que recibe datos lógicos (posiciones de serpiente/comida) y los renderiza en el canvas 3D.
*   **Modos de Juego (`play_solo.js`, `watch_ai.js`):** Contienen la lógica específica para cada modo, interactuando con el visualizador y/o los WebSockets según sea necesario.
*   **Dependencias (`dependencies.py`):** Centraliza la creación de las instancias singleton de `TrainingManager` y `WebSocketManager` y proporciona las funciones `get_..._instance` para la inyección de dependencias en FastAPI, evitando importaciones circulares.

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - mira el archivo [LICENSE](LICENSE) para más detalles.
