// frontend/js/watch_ai.js

import { SnakeVisualizer } from './snake_visualizer.js';
import { updateScore, showGameOver, setInstructions, showError } from './ui.js';
// Asumimos que websocket.js exporta funciones para conectar/enviar/gestionar el WS
import { connectWebSocket, sendMessage, closeWebSocket, WSType } from './websocket.js';

/** @type {SnakeVisualizer | null} */
let visualizerInstance = null;
let isWatching = false; // Flag para saber si estamos activamente en este modo

/**
 * Maneja los mensajes recibidos del WebSocket de /ws/watch.
 * @param {object} event - El objeto del evento del mensaje WebSocket.
 */
function handleWebSocketMessage(event) {
    if (!isWatching) return; // Ignorar si no estamos en modo Watch AI

    try {
        const message = JSON.parse(event.data);
        // console.log("Watch AI - Mensaje WS recibido:", message); // Para depuración

        switch (message.type) {
            case 'game_state_update':
                if (visualizerInstance && message.data) {
                    visualizerInstance.update(message.data.snake, message.data.food);
                    updateScore(message.data.score);
                    showGameOver(message.data.gameOver);
                    if(message.data.gameOver) {
                         setInstructions("IA: ¡Episodio terminado! Reiniciando...");
                         // Podrías añadir una pausa visual aquí antes de que el backend reinicie
                    }
                }
                break;
            case 'error':
                console.error("Watch AI - Error recibido del backend:", message.data.message);
                showError(`Error del servidor (Ver IA): ${message.data.message}`);
                setInstructions("Error recibido del servidor. Deteniendo.");
                stopWatchAI(); // Detener si hay error
                break;
            // Podrías manejar otros tipos de mensajes si el backend los envía
            default:
                console.log("Watch AI - Mensaje WS tipo desconocido:", message.type);
        }
    } catch (error) {
        console.error("Watch AI - Error procesando mensaje WS:", error);
        showError("Error procesando datos del servidor (Ver IA).");
    }
}

/**
 * Se llama cuando la conexión WebSocket se cierra.
 */
function handleWebSocketClose() {
    if (!isWatching) return; // Solo actuar si estábamos viendo activamente
    console.log("Watch AI: Conexión WebSocket cerrada.");
    setInstructions("Conexión perdida con el servidor. Intenta reconectar.");
    showError("Desconectado del servidor (Ver IA).");
    isWatching = false; // Marcar como no activo
    // No limpiar visualizador aquí, puede ser útil mantener el último estado
}

/**
 * Se llama cuando la conexión WebSocket se abre con éxito.
 */
function handleWebSocketOpen() {
     if (!isWatching) return; // Solo actuar si el modo sigue activo
    console.log("Watch AI: Conexión WebSocket establecida.");
    setInstructions("Conectado. Solicitando inicio de visualización...");
    showError(null); // Limpiar errores previos
    // Enviar mensaje 'start' al backend para que empiece a enviar estados
    sendMessage(WSType.WATCH, 'start');
}


/**
 * Inicia el modo "Ver IA".
 * @param {SnakeVisualizer} visualizer - Instancia del visualizador 3D.
 */
export function startWatchAI(visualizer) {
    console.log("Iniciando modo Watch AI...");
    if (!visualizer) {
        console.error("Watch AI: Se requiere una instancia de SnakeVisualizer.");
        setInstructions("Error: Visualizador no disponible.");
        return;
    }
     if (isWatching) {
        console.warn("Watch AI ya está activo.");
        return;
    }

    visualizerInstance = visualizer;
    isWatching = true;
    showError(null); // Limpiar errores

    // Limpiar estado visual anterior (opcional)
    visualizerInstance.update([], null);
    updateScore(0);
    showGameOver(false);
    setInstructions("Conectando a WebSocket para ver IA...");

    // Conectar al WebSocket (usando la función de websocket.js)
    // Pasamos los manejadores específicos para este modo
    connectWebSocket(WSType.WATCH, handleWebSocketMessage, handleWebSocketOpen, handleWebSocketClose);
}

/** Detiene el modo "Ver IA". */
export function stopWatchAI() {
     if (!isWatching) return; // Ya está detenido

    console.log("Deteniendo modo Watch AI...");
    isWatching = false;

    // Enviar mensaje 'stop' al backend para que deje de enviar estados (y potencialmente detenga la evaluación)
    // Es importante hacerlo ANTES de cerrar el WS localmente
    sendMessage(WSType.WATCH, 'stop');

    // Cerrar la conexión WebSocket (usando la función de websocket.js)
    closeWebSocket(WSType.WATCH);

    // No limpiamos el visualizador para que quede el último estado visible
    // visualizerInstance = null; // No liberar aquí, main.js podría reutilizarlo

    setInstructions("Modo 'Ver IA' detenido.");
    // Resetear UI relacionada (opcional)
    // updateScore(0);
    // showGameOver(false);
}

console.log("watch_ai.js cargado.");