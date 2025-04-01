// frontend/js/websocket.js

// --- AJUSTAR IMPORTACIÓN ---
import { updateTrainingStatus, showError, updateTrainingProgress } from './ui.js'; // Quitar updateTrainingLog
import { updateCharts } from './charts.js';

// --- Constantes y Tipos ---
export const WSType = {
    WATCH: 'watch',
    TRAINING: 'training_updates',
};
const WS_URLS = {
    [WSType.WATCH]: `ws://${window.location.host}/ws/watch`,
    [WSType.TRAINING]: `ws://${window.location.host}/ws/training_updates`,
};

// --- Estado Interno del Módulo ---
const webSockets = {};

// --- Funciones Internas ---
function ensureWebSocketState(type, onMessage, onOpen, onClose) {
    if (!webSockets[type]) {
        webSockets[type] = {
            instance: null, status: 'disconnected', reconnectAttempts: 0,
            messageHandler: onMessage, openHandler: onOpen, closeHandler: onClose,
            url: WS_URLS[type]
        };
        // console.log(`WebSocket [${type}]: Estado inicializado.`); // Log opcional
    } else {
        webSockets[type].messageHandler = onMessage;
        webSockets[type].openHandler = onOpen;
        webSockets[type].closeHandler = onClose;
    }
}

function _connect(type) {
    const wsState = webSockets[type];
    if (!wsState || !wsState.url) {
        console.error(`WebSocket [${type}]: Configuración no encontrada.`);
        return;
    }
    if (wsState.status === 'connected' || wsState.status === 'connecting') {
        // console.warn(`WebSocket [${type}]: Ya está ${wsState.status}.`); // Log opcional
         if(wsState.status === 'connected' && typeof wsState.openHandler === 'function') {
             try { wsState.openHandler(); } catch(e) { console.error(`Error en openHandler [${type}] re-llamado:`, e); }
        }
        return;
    }
    console.log(`WebSocket [${type}]: Intentando conectar a ${wsState.url}...`);
    wsState.status = 'connecting';
    try {
        if (wsState.instance) { wsState.instance.close(); wsState.instance = null; }
        wsState.instance = new WebSocket(wsState.url);
    } catch (error) {
        console.error(`WebSocket [${type}]: Error al crear instancia:`, error);
        wsState.status = 'error';
        showError(`No se pudo crear WebSocket [${type}]: ${error.message}`);
        return;
    }

    wsState.instance.onopen = (event) => {
        console.log(`WebSocket [${type}]: Conexión abierta.`);
        wsState.status = 'connected';
        wsState.reconnectAttempts = 0;
        if (typeof wsState.openHandler === 'function') {
             try { wsState.openHandler(event); } catch(e) { console.error(`Error en openHandler [${type}]:`, e); }
        }
    };
    wsState.instance.onmessage = (event) => {
        if (typeof wsState.messageHandler === 'function') {
            try { wsState.messageHandler(event); } catch(e) { console.error(`Error en messageHandler [${type}]:`, e); }
        } else {
            _handleDefaultMessage(type, event);
        }
    };
    wsState.instance.onerror = (event) => {
        console.error(`WebSocket [${type}]: Error detectado:`, event);
        wsState.status = 'error';
    };
    wsState.instance.onclose = (event) => {
        console.log(`WebSocket [${type}]: Conexión cerrada. Código: ${event.code}, Razón: ${event.reason || 'N/A'}, Limpio: ${event.wasClean}`);
        if (wsState.status !== 'disconnecting') { wsState.status = 'disconnected'; }
        wsState.instance = null;
        if (typeof wsState.closeHandler === 'function') {
            try { wsState.closeHandler(event); } catch(e) { console.error(`Error en closeHandler [${type}]:`, e); }
        }
    };
}

function _handleDefaultMessage(type, event) {
    if (type === WSType.TRAINING) {
        try {
            const message = JSON.parse(event.data);
            switch (message.type) {
                case 'training_status':
                    updateTrainingStatus(message.data);
                    break;
                case 'training_metric':
                    updateCharts(message.data);
                    if (message.data.timestep !== undefined) {
                        updateTrainingProgress(message.data.timestep);
                    } else {
                        console.warn("WS: Mensaje training_metric recibido SIN timestep:", message.data);
                    }
                    break;
                case 'training_log':
                     // Ya no llamamos a updateTrainingLog
                     console.log("WS: Mensaje training_log recibido (ignorado en UI):", message.data);
                    break;
                default:
                    console.log(`WebSocket [${type}]: Mensaje tipo desconocido (default handler):`, message.type);
            }
        } catch (error) {
            console.error(`WebSocket [${type}]: Error procesando mensaje JSON (default handler):`, error);
            showError(`Error procesando datos del servidor [${type}]`);
        }
    } else {
         console.log(`WebSocket [${type}]: Mensaje recibido sin handler específico:`, event.data);
    }
}

// --- Funciones Exportadas ---
export function connectWebSocket(type, onMessage, onOpen, onClose) {
    if (!WS_URLS[type]) { console.error(`Tipo de WebSocket desconocido: ${type}`); return; }
    ensureWebSocketState(type, onMessage, onOpen, onClose);
    _connect(type);
}
export function sendMessage(type, message) {
    const wsState = webSockets[type];
    if (wsState && wsState.instance && wsState.status === 'connected') {
        try {
            const messageToSend = typeof message === 'string' ? message : JSON.stringify(message);
            wsState.instance.send(messageToSend);
        } catch (error) { console.error(`WebSocket [${type}]: Error al enviar mensaje:`, error); }
    } else { console.warn(`WebSocket [${type}]: No conectado. No se pudo enviar:`, message); }
}
export function closeWebSocket(type) {
    const wsState = webSockets[type];
    if (wsState && wsState.instance) {
        console.log(`WebSocket [${type}]: Cerrando conexión (iniciado por cliente)...`);
        wsState.status = 'disconnecting';
        wsState.instance.close(1000, "Cierre iniciado por el cliente");
    } else { /* console.log(`WebSocket [${type}]: Ya estaba cerrado.`); */ if(wsState) wsState.status = 'disconnected'; }
}
export function getWebSocketStatus(type) { return webSockets[type]?.status || 'unknown'; }

console.log("websocket.js cargado.");