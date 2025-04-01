// frontend/js/api.js

// --- Helper para manejar respuestas de fetch ---
async function handleResponse(response) {
    if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try {
            // Intentar obtener más detalles del cuerpo de la respuesta JSON del backend (FastAPI suele enviar 'detail')
            const errorData = await response.json();
            errorDetail += ` - ${errorData.detail || JSON.stringify(errorData)}`;
        } catch (e) {
            // Si el cuerpo no es JSON o hay otro error al parsear
            errorDetail += ` - ${response.statusText || 'No se pudo obtener detalle'}`;
        }
        const error = new Error(errorDetail);
        error.status = response.status; // Adjuntar status HTTP al objeto de error
        throw error;
    }

    // Manejar respuestas sin contenido (ej: 202 Accepted, 204 No Content)
    if (response.status === 204 || response.status === 202) {
        // Para 202 Accepted (usado en start/continue), un objeto vacío es razonable
        // o podrías devolver un objeto de éxito si lo prefieres: { success: true }
        return {};
    }

    // Intentar parsear JSON si hay contenido
    try {
        return await response.json();
    } catch (e) {
        // Manejar el caso raro de respuesta OK pero cuerpo no JSON válido
        console.warn("Respuesta API OK pero no es JSON válido:", response.status, response.statusText);
        // Puedes decidir qué devolver aquí, quizás un objeto vacío o lanzar un error diferente
        return {}; // Devolver objeto vacío para no romper la cadena .then si no es crítico
    }
}

// --- Funciones de API Exportadas ---

/** Llama a la API para iniciar un nuevo entrenamiento. */
export async function startTraining(params) {
    console.log('Llamando a API: startTraining con params:', params); // Log para depuración
    const response = await fetch('/api/train/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json' // Ser explícito
        },
        body: JSON.stringify(params),
    });
    return handleResponse(response);
}

/** Llama a la API para continuar un entrenamiento existente. */
export async function continueTraining() {
    console.log('Llamando a API: continueTraining'); // Log para depuración
    const response = await fetch('/api/train/continue', {
        method: 'POST',
        headers: { 'Accept': 'application/json' }
    });
    return handleResponse(response);
}

/** Llama a la API para detener el entrenamiento actual. */
export async function stopTraining() {
    console.log('Llamando a API: stopTraining'); // Log para depuración
    const response = await fetch('/api/train/stop', {
        method: 'POST',
        headers: { 'Accept': 'application/json' }
    });
    return handleResponse(response);
}

/** Llama a la API para obtener el estado actual del entrenamiento. */
// --- !! CORRECCIÓN: Añadir 'export' !! ---
export async function getTrainingStatus() {
    // console.log('Llamando a API: getTrainingStatus'); // Log menos frecuente quizás
    const response = await fetch('/api/status', {
         headers: { 'Accept': 'application/json' }
    });
    return handleResponse(response);
}

/** Llama a la API para obtener los parámetros de configuración por defecto. */
// --- !! CORRECCIÓN: Añadir 'export' !! ---
export async function getDefaultTrainingParams() {
    console.log('Llamando a API: getDefaultTrainingParams'); // Log para depuración
    const response = await fetch('/api/config/defaults', {
         headers: { 'Accept': 'application/json' }
    });
    return handleResponse(response);
}

/** Llama a la API para obtener información del hardware (opcional). */
export async function getHardwareInfo() {
    console.log('Llamando a API: getHardwareInfo'); // Log para depuración
    const response = await fetch('/api/hardware-info', {
         headers: { 'Accept': 'application/json' }
    });
    return handleResponse(response);
}

console.log("api.js cargado."); // Log para confirmar carga