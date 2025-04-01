// frontend/js/ui.js

// --- Referencias a Elementos del DOM ---
// Botones de Modo
const modeTrainingBtn = document.getElementById('mode-training-btn');
const modeSoloBtn = document.getElementById('mode-solo-btn');
const modeWatchBtn = document.getElementById('mode-watch-btn');

// Secciones de la Barra Lateral (Sidebar)
const trainingUiSidebar = document.getElementById('training-ui');
const gameUiSidebar = document.getElementById('game-ui');

// Secciones del Área Principal (Main Content)
const gameContainer = document.getElementById('game-container');
const trainingDisplayArea = document.getElementById('training-display-area');

// Elementos UI de Entrenamiento (Sidebar)
const trainingStatusEl = document.getElementById('training-status');
const trainingProgressEl = document.getElementById('training-progress');
const startTrainingBtn = document.getElementById('start-training-btn');
const continueTrainingBtn = document.getElementById('continue-training-btn');
const stopTrainingBtn = document.getElementById('stop-training-btn');
const paramTimestepsInput = document.getElementById('param-timesteps');
const paramCpusInput = document.getElementById('param-cpus');
const paramLrInput = document.getElementById('param-lr');

// Elementos UI de Juego (Sidebar)
const gameModeTitleEl = document.getElementById('game-mode-title');
const scoreEl = document.getElementById('score');
const gameOverMessageEl = document.getElementById('game-over-message');
const resetGameBtn = document.getElementById('reset-game-btn');
const instructionsEl = document.getElementById('instructions');

// Display de Errores
const errorDisplayEl = document.getElementById('error-display');

// Variable para recordar el total_steps actual (necesario para calcular %)
let currentTotalSteps = 0;

// --- Funciones Exportadas ---

/**
 * Establece el modo activo de la aplicación, mostrando/ocultando
 * las secciones de UI correspondientes.
 * @param {'training' | 'solo' | 'watch'} mode - El modo a activar.
 */
export function setActiveMode(mode) {
    console.log(`UI: Cambiando a modo: ${mode}`);

    // --- PASO 1: Ocultar AMBOS contenedores principales ---
    if (gameContainer) gameContainer.classList.add('hidden');
    else console.error("UI Error: #game-container no encontrado");
    if (trainingDisplayArea) trainingDisplayArea.classList.add('hidden');
    else console.error("UI Error: #training-display-area no encontrado");

    // Ocultar también las UIs de la sidebar
    if (trainingUiSidebar) trainingUiSidebar.classList.add('hidden');
    else console.error("UI Error: #training-ui no encontrado");
    if (gameUiSidebar) gameUiSidebar.classList.add('hidden');
    else console.error("UI Error: #game-ui no encontrado");

    // Habilitar todos los botones de modo (se deshabilitará el activo)
    if (modeTrainingBtn) modeTrainingBtn.disabled = false;
    if (modeSoloBtn) modeSoloBtn.disabled = false;
    if (modeWatchBtn) modeWatchBtn.disabled = false;

    // --- PASO 2: Mostrar los elementos CORRECTOS para el nuevo modo ---
    switch (mode) {
        case 'training':
            console.log("UI: Activando elementos para modo TRAINING");
            if (trainingUiSidebar) trainingUiSidebar.classList.remove('hidden');
            if (trainingDisplayArea) trainingDisplayArea.classList.remove('hidden'); // Mostrar gráficos
            if (modeTrainingBtn) modeTrainingBtn.disabled = true;
            // Redimensionar gráficos
            try {
                if (window.rewardChartInstance) window.rewardChartInstance.resize();
                if (window.lengthChartInstance) window.lengthChartInstance.resize();
                if (window.valueLossChartInstance) window.valueLossChartInstance.resize();
                if (window.explainedVarianceChartInstance) window.explainedVarianceChartInstance.resize();
            } catch (e) { console.warn("No se pudieron redimensionar los gráficos:", e); }
            break;

        case 'solo':
            console.log("UI: Activando elementos para modo SOLO");
            if (gameUiSidebar) gameUiSidebar.classList.remove('hidden');
            if (gameContainer) gameContainer.classList.remove('hidden'); // Mostrar canvas 3D
            updateGameModeTitle('Jugar Solo');
            if (resetGameBtn) resetGameBtn.classList.remove('hidden');
            // La instrucción inicial se pone en play_solo.js al llamar a resetGame
            // setInstructions("Usa las flechas para moverte...");
            if (modeSoloBtn) modeSoloBtn.disabled = true;
            break;

        case 'watch':
            console.log("UI: Activando elementos para modo WATCH");
            if (gameUiSidebar) gameUiSidebar.classList.remove('hidden');
            if (gameContainer) gameContainer.classList.remove('hidden'); // Mostrar canvas 3D
            updateGameModeTitle('Viendo IA');
            if (resetGameBtn) resetGameBtn.classList.add('hidden');
            setInstructions("Observando al agente IA. Conectando...");
            if (modeWatchBtn) modeWatchBtn.disabled = true;
            break;

        default:
            console.error(`Modo desconocido: ${mode}`);
            setInstructions("Selecciona un modo para empezar.");
            // Asegurarse de que algo sea visible por defecto si falla
            if (gameContainer) gameContainer.classList.remove('hidden'); // Mostrar juego como fallback?
    }
     // Limpiar errores al cambiar de modo
     showError(null);
}

/**
 * Actualiza el texto de estado y progreso del entrenamiento, y habilita/deshabilita botones.
 * Usado para mensajes 'training_status' completos.
 * @param {object} statusData - El objeto de estado recibido (ej: { status: 'Entrenando', current_step: 1000, total_steps: 100000, message: '...' })
 */
export function updateTrainingStatus(statusData) {
    if (!statusData) return;
    // console.log("UI Recibió statusData:", statusData); // Mantener si se necesita depurar

    const status = statusData.status || 'Desconocido';
    const currentStep = statusData.current_step;
    const totalSteps = statusData.total_steps;
    // const message = statusData.message || ''; // Mensaje no se muestra actualmente

    if (trainingStatusEl) {
        trainingStatusEl.textContent = `Estado: ${status}`;
        if (status.toLowerCase() === 'error') {
            trainingStatusEl.classList.add('status-error');
        } else {
            trainingStatusEl.classList.remove('status-error');
        }
    } else { console.error("UI Error: #training-status no encontrado"); }


    if (totalSteps !== undefined && totalSteps > 0) {
        // console.log(`UI: updateTrainingStatus - Guardando currentTotalSteps = ${totalSteps}`);
        currentTotalSteps = totalSteps;
    }

    if (currentStep !== undefined) {
         updateTrainingProgress(currentStep);
    } else if (status === 'Completado' && currentTotalSteps > 0) {
         if(trainingProgressEl) trainingProgressEl.textContent = `Progreso: Completado (${currentTotalSteps.toLocaleString()} pasos)`;
         else console.error("UI Error: #training-progress no encontrado");
    } else if (status === 'Detenido' && trainingProgressEl && trainingProgressEl.textContent.includes('/')) {
         // Mantener último progreso visible si se detuvo manualmente
    } else if (status !== 'Entrenando' && status !== 'Iniciando' && status !== 'Inicializando'){
         if(trainingProgressEl) trainingProgressEl.textContent = 'Progreso: N/A';
         else console.error("UI Error: #training-progress no encontrado");
    }


    const isTraining = status === 'Entrenando' || status === 'Iniciando' || status === 'Inicializando';
    // console.log(`UI: Status recibido='${status}', isTraining=${isTraining}`);

    // Habilitar/deshabilitar botones según el estado
    if (startTrainingBtn) startTrainingBtn.disabled = isTraining;
    else console.error("UI Error: #start-training-btn no encontrado");
    if (continueTrainingBtn) continueTrainingBtn.disabled = isTraining;
    else console.error("UI Error: #continue-training-btn no encontrado");
    if (stopTrainingBtn) stopTrainingBtn.disabled = !isTraining;
    else console.error("UI Error: #stop-training-btn no encontrado");
}

/**
 * Actualiza únicamente el texto de progreso del entrenamiento.
 * Usado para mensajes 'training_metric' que incluyen 'timestep'.
 * @param {number} stepValue - El número actual de pasos (recibido como timestep).
 */
export function updateTrainingProgress(stepValue) {
     // console.log(`UI: updateTrainingProgress INTENTANDO con stepValue=${stepValue}, currentTotalSteps=${currentTotalSteps}`);
     if (!trainingProgressEl) {
         console.error("UI: ERROR - trainingProgressEl no encontrado en updateTrainingProgress!");
         return;
     }
     if (stepValue === undefined || stepValue === null) {
         // console.warn("UI: updateTrainingProgress - SKIPPING update (stepValue es undefined/null)");
         return;
     }

     if (currentTotalSteps > 0) {
        const percentage = ((stepValue / currentTotalSteps) * 100);
        const displayPercentage = Math.min(percentage, 100).toFixed(1);
        const newText = `Progreso: ${stepValue.toLocaleString()} / ${currentTotalSteps.toLocaleString()} (${displayPercentage}%)`;
        if (trainingProgressEl.textContent !== newText) {
             trainingProgressEl.textContent = newText;
             // console.log(`UI: Progress TEXTO ACTUALIZADO a: ${newText}`);
        }
    } else {
         const newText = `Progreso: ${stepValue.toLocaleString()} pasos`;
          if (trainingProgressEl.textContent !== newText) {
             trainingProgressEl.textContent = newText;
             // console.log(`UI: Progress TEXTO ACTUALIZADO (sin total) a: ${newText}`);
          }
    }
}

/**
 * Actualiza el marcador de puntuación.
 * @param {number} newScore - La nueva puntuación.
 */
export function updateScore(newScore) {
    if (scoreEl) {
        scoreEl.textContent = newScore;
    } else { console.error("UI Error: #score no encontrado"); }
}

/**
 * Muestra u oculta el mensaje de "Game Over".
 * @param {boolean} visible - True para mostrar, false para ocultar.
 */
export function showGameOver(visible) {
    if (gameOverMessageEl) {
        gameOverMessageEl.classList.toggle('hidden', !visible);
    } else { console.error("UI Error: #game-over-message no encontrado"); }
}

/**
 * Establece el texto de instrucciones en la UI de juego.
 * @param {string} text - El texto a mostrar.
 */
export function setInstructions(text) {
    if (instructionsEl) {
        instructionsEl.textContent = text;
    } else { console.error("UI Error: #instructions no encontrado"); }
}

/**
 * Actualiza el título H2 en la UI de juego (Sidebar).
 * @param {string} title - El nuevo título.
 */
export function updateGameModeTitle(title) {
    if (gameModeTitleEl) {
        gameModeTitleEl.textContent = title;
    } else { console.error("UI Error: #game-mode-title no encontrado"); }
}

/**
 * Muestra un mensaje de error en el área designada.
 * @param {string | null} message - El mensaje de error o null para ocultar.
 */
export function showError(message) {
    if (errorDisplayEl) {
        if (message) {
            errorDisplayEl.textContent = message;
            errorDisplayEl.classList.remove('hidden');
            console.error("Error mostrado en UI:", message);
        } else {
            errorDisplayEl.textContent = '';
            errorDisplayEl.classList.add('hidden');
        }
    } else {
        if (message) {
            alert(`Error: ${message}`); // Fallback
            console.error("Error (sin #error-display):", message);
        }
    }
}

/**
 * Rellena los campos de parámetros de entrenamiento con valores por defecto.
 * @param {object} params - Objeto con los parámetros (ej: { total_timesteps: 1M, num_cpu: 4, learning_rate: 0.0003 })
 */
export function setDefaultTrainingParams(params) {
    if (paramTimestepsInput && params.total_timesteps !== undefined) {
        paramTimestepsInput.value = params.total_timesteps;
    } else if (!paramTimestepsInput) { console.error("UI Error: #param-timesteps no encontrado"); }

    if (paramCpusInput && params.num_cpu !== undefined) {
        paramCpusInput.value = params.num_cpu;
    } else if (!paramCpusInput) { console.error("UI Error: #param-cpus no encontrado"); }

    if (paramLrInput && params.learning_rate !== undefined) {
        paramLrInput.value = params.learning_rate;
    } else if (!paramLrInput) { console.error("UI Error: #param-lr no encontrado"); }
}

/**
 * Obtiene los valores actuales de los parámetros de entrenamiento desde la UI.
 * @returns {object} - Objeto con los parámetros leídos.
 */
export function getTrainingParams() {
    const params = {};
    if (paramTimestepsInput) {
        params.total_timesteps = parseInt(paramTimestepsInput.value, 10) || 1000000;
    } else { params.total_timesteps = 1000000; console.error("UI Error: #param-timesteps no encontrado, usando default."); }

    if (paramCpusInput) {
        params.num_cpu = parseInt(paramCpusInput.value, 10) || 1;
    } else { params.num_cpu = 1; console.error("UI Error: #param-cpus no encontrado, usando default."); }

    if (paramLrInput) {
        params.learning_rate = parseFloat(paramLrInput.value) || 0.0003;
    } else { params.learning_rate = 0.0003; console.error("UI Error: #param-lr no encontrado, usando default."); }

    // console.log("Parámetros de entrenamiento leídos de la UI:", params); // Log opcional
    return params;
}

console.log("ui.js cargado."); // Log para confirmar carga