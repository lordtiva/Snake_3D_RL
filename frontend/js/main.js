// frontend/js/main.js

// Importar módulos principales
import * as ui from './ui.js'; // Importa todas las funciones exportadas de ui.js
import * as api from './api.js'; // Funciones para interactuar con el backend API
import * as websocket from './websocket.js'; // Funciones para manejar WebSockets
import * as charts from './charts.js'; // Funciones para inicializar/actualizar gráficos

// Importar módulos específicos de modo y visualización
import { SnakeVisualizer } from './snake_visualizer.js';
import { startPlaySolo, stopPlaySolo } from './play_solo.js';
import { startWatchAI, stopWatchAI } from './watch_ai.js';

// --- Constantes ---
const BOARD_SIZE = 20; // Debe coincidir con backend/visualizador
const CANVAS_ID = 'gameCanvas';

// --- Variables Globales ---
let currentMode = null; // 'training', 'solo', 'watch'
/** @type {SnakeVisualizer | null} */
let visualizer = null;

// --- Funciones de Orquestación ---

/** Cambia el modo activo de la aplicación */
function changeMode(newMode) {
    if (newMode === currentMode) return;
    console.log(`Cambiando modo de '${currentMode}' a '${newMode}'`);

    // Detener actividades del modo anterior
    switch (currentMode) {
        case 'solo': stopPlaySolo(); break;
        case 'watch': stopWatchAI(); break;
        case 'training': break; // Nada que detener aquí específicamente
    }

    // --- 1. Establecer nuevo modo en la UI ---
    ui.setActiveMode(newMode);

    // --- 2. Iniciar actividades Y FORZAR REDIMENSIONADO si es necesario ---
    currentMode = newMode; // Actualizar modo actual ANTES del switch
    switch (newMode) {
        case 'solo':
            if (visualizer) {
                startPlaySolo(visualizer);
            } else { console.error("Visualizador no disponible para modo 'solo'"); }
            break;
        case 'watch':
             if (visualizer) {
                startWatchAI(visualizer);
            } else { console.error("Visualizador no disponible para modo 'watch'"); }
            break;
        case 'training':
             if (charts) charts.initCharts(); // Asegurar inicialización de gráficos
             // ui.setInstructions("Monitorizando..."); // La UI ya lo hace
             // api.getTrainingStatus().then(ui.updateTrainingStatus).catch(handleApiError); // Podría ser redundante si WS funciona bien
            break;
    }

    // --- !! PASO 3: FORZAR REDIMENSIONADO DEL VISUALIZADOR SI SE MOSTRÓ !! ---
    if ((newMode === 'solo' || newMode === 'watch') && visualizer) {
        // Usar requestAnimationFrame para esperar el próximo ciclo de pintado del navegador,
        // dando tiempo a que se apliquen los cambios de estilo (quitar 'hidden').
        requestAnimationFrame(() => {
            console.log(`Forzando visualizer.handleResize() para modo ${newMode}...`);
            visualizer.handleResize();
        });
        // Alternativa (menos ideal): setTimeout(() => visualizer.handleResize(), 0);
    }

}

/** Manejador genérico para errores de API */
function handleApiError(error) {
    console.error("Error de API:", error);
    ui.showError(`Error de comunicación con el servidor: ${error.message || 'Error desconocido'}`);
    // Podrías querer actualizar el estado de entrenamiento a 'Error' en algunos casos
     if (currentMode === 'training') {
         // Actualizar UI para reflejar el posible error en la obtención de datos
         ui.updateTrainingStatus({ status: 'Error Com.', message: 'Fallo al comunicar' });
     }
}

// --- Inicialización Principal ---

// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM Cargado. Inicializando aplicación...");

    // 1. Inicializar Visualizador 3D
    try {
        visualizer = new SnakeVisualizer(CANVAS_ID, BOARD_SIZE);
    } catch (error) {
        console.error("Error fatal inicializando SnakeVisualizer:", error);
        ui.showError(`Error crítico al iniciar visualizador: ${error.message}`);
        // Deshabilitar botones si falla
        const soloBtn = document.getElementById('mode-solo-btn');
        const watchBtn = document.getElementById('mode-watch-btn');
        if(soloBtn) soloBtn.disabled = true;
        if(watchBtn) watchBtn.disabled = true;
    }

    // 2. Inicializar Gráficos (se usarán en modo 'training')
    // Se inicializan aquí para que los canvas estén listos, pero se llenarán con datos luego.
    charts.initCharts(); // Llama a la función exportada desde charts.js

    // 3. Configurar Listeners para Botones de Modo
    const modeTrainingBtn = document.getElementById('mode-training-btn');
    const modeSoloBtn = document.getElementById('mode-solo-btn');
    const modeWatchBtn = document.getElementById('mode-watch-btn');

    if (modeTrainingBtn) modeTrainingBtn.addEventListener('click', () => changeMode('training'));
    if (modeSoloBtn) modeSoloBtn.addEventListener('click', () => changeMode('solo'));
    if (modeWatchBtn) modeWatchBtn.addEventListener('click', () => changeMode('watch'));

    // 4. Configurar Listeners para Botones de Entrenamiento
    const startTrainingBtn = document.getElementById('start-training-btn');
    const continueTrainingBtn = document.getElementById('continue-training-btn');
    const stopTrainingBtn = document.getElementById('stop-training-btn');

    if (startTrainingBtn) {
        startTrainingBtn.addEventListener('click', () => {
            console.log("Botón 'Iniciar Nuevo' presionado.");
            ui.showError(null); // Limpiar errores previos
            charts.clearCharts(); // Limpiar gráficos anteriores
            console.log("Solicitando inicio de nuevo entrenamiento..."); // Usar console.log si se quiere feedback
            const params = ui.getTrainingParams(); // Obtener parámetros de la UI
            console.log('Enviando parámetros:', params); // <--- LOG
            api.startTraining(params)
                .then(response => {
                    console.log("Respuesta API (startTraining):", response);
                    // La actualización de estado vendrá por WebSocket
                })
                .catch(error => {
                     handleApiError(error);
                });
        });
    }

    if (continueTrainingBtn) {
        continueTrainingBtn.addEventListener('click', () => {
            console.log("Botón 'Continuar' presionado.");
             ui.showError(null);
             charts.clearCharts(); // Opcional: decidir si limpiar gráficos al continuar
             // Nota: La API de continuar no toma parámetros en el diseño actual
             console.log("Solicitando continuar entrenamiento...");
             api.continueTraining()
                 .then(response => {
                     console.log("Respuesta API (continueTraining):", response);
                 })
                 .catch(error => {
                     handleApiError(error);
                     // Mostrar error específico si no se encuentra el archivo
                     if (error.status === 404) {
                        ui.showError("Error: No se encontró 'last_model.zip' para continuar.");
                     }
                 });
        });
    }

     if (stopTrainingBtn) {
        stopTrainingBtn.addEventListener('click', () => {
            console.log("Botón 'Detener' presionado.");
             ui.showError(null);
             api.stopTraining()
                 .then(response => {
                     console.log("Respuesta API (stopTraining):", response);
                      // El estado final ('Detenido') debería llegar por WebSocket
                 })
                 .catch(handleApiError);
        });
    }

    // 5. Obtener parámetros de entrenamiento por defecto
    api.getDefaultTrainingParams()
        .then(params => {
            console.log("Parámetros por defecto recibidos:", params);
            ui.setDefaultTrainingParams(params);
        })
        .catch(error => {
            console.error("Error obteniendo params por defecto:", error);
            // No es crítico, pero informar
        });

    // 6. Conectar WebSocket de Entrenamiento para actualizaciones de estado/métricas
    // Conectamos aquí para recibir estado aunque no estemos en modo 'training' inicialmente
    // Los mensajes se manejarán internamente en websocket.js (llamando a ui y charts)
    websocket.connectWebSocket(websocket.WSType.TRAINING);

     // 7. Establecer Modo Inicial
     // ¡¡ NO LLAMAR A ui.initUI() !!
     // En su lugar, decidimos el modo inicial y lo activamos:
     changeMode('training'); // Empezar en el modo de entrenamiento por defecto

    console.log("Aplicación inicializada.");
});

console.log("main.js cargado.");