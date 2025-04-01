// frontend/js/charts.js
// Chart global (asumiendo <script src...>)

// --- Variables ---
let rewardChartInstance = null;
let lengthChartInstance = null;
let valueLossChartInstance = null;
let explainedVarianceChartInstance = null;

// --- !! COMENTAR O ELIMINAR ESTA CONSTANTE !! ---
// Ya no limitaremos los puntos de datos de esta manera
// const MAX_DATA_POINTS = 100;
// --- FIN CAMBIO ---

// --- Funciones Internas (createChartConfig sin cambios) ---
function createChartConfig(label, color) {
    return {
        type: 'line',
        data: {
            labels: [], // Timesteps irán aquí
            datasets: [{
                label: label,
                data: [], // Valores de la métrica irán aquí
                borderColor: color,
                backgroundColor: color.replace('1)', '0.2)'),
                borderWidth: 1.5,
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: { display: true, text: 'Timestep', color: '#aaa' },
                    ticks: { color: '#aaa', autoSkip: true, maxTicksLimit: 15 }, // autoSkip y maxTicksLimit ayudan a que no se solapen los labels
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                y: {
                    beginAtZero: false,
                    title: { display: true, text: 'Valor Medio', color: '#aaa' },
                     ticks: { color: '#aaa' },
                     grid: { color: 'rgba(255, 255, 255, 0.1)' }
                }
            },
            plugins: {
                legend: { labels: { color: '#eee' } },
                tooltip: { /* ... */ }
            },
            // Opcional: Desactivar animación para mejor rendimiento con muchos puntos
            // animation: false
        }
    };
}


/**
 * Añade un nuevo punto de datos a un gráfico.
 * @param {Chart} chartInstance - La instancia del gráfico de Chart.js.
 * @param {number|string} label - La etiqueta para el eje X (ej: timestep).
 * @param {number} value - El valor para el eje Y (ej: recompensa media).
 */
function addDataPoint(chartInstance, label, value) {
    if (!chartInstance) return;

    const data = chartInstance.data;
    data.labels.push(label);
    data.datasets[0].data.push(value);

    // --- !! ELIMINAR O COMENTAR ESTE BLOQUE !! ---
    // Ya no quitamos los datos antiguos
    /*
    if (data.labels.length > MAX_DATA_POINTS) {
        data.labels.shift(); // Elimina el primer elemento
        data.datasets[0].data.shift(); // Elimina el primer dato
    }
    */
    // --- FIN CAMBIO ---

    // Actualizar el gráfico sin animación para mejor rendimiento (opcional)
    chartInstance.update('none'); // 'none' desactiva la animación para esta actualización
}

// --- Funciones Exportadas (initCharts, updateCharts, clearCharts sin cambios internos relevantes) ---
export function initCharts() {
    console.log("Inicializando gráficos clave...");
    const rewardCtx = document.getElementById('reward-chart')?.getContext('2d');
    const lengthCtx = document.getElementById('length-chart')?.getContext('2d');
    const valueLossCtx = document.getElementById('value-loss-chart')?.getContext('2d');
    const explainedVarianceCtx = document.getElementById('explained-variance-chart')?.getContext('2d');

    if (rewardCtx && !rewardChartInstance) {
        const config = createChartConfig('Recompensa Media', 'rgba(75, 192, 192, 1)');
        rewardChartInstance = new Chart(rewardCtx, config);
        window.rewardChartInstance = rewardChartInstance;
        // console.log("Gráfico de Recompensa inicializado."); // Reducir logs
    }
    if (lengthCtx && !lengthChartInstance) {
        const config = createChartConfig('Longitud Media Episodio', 'rgba(255, 159, 64, 1)');
        lengthChartInstance = new Chart(lengthCtx, config);
        window.lengthChartInstance = lengthChartInstance;
        // console.log("Gráfico de Longitud inicializado.");
    }
    if (valueLossCtx && !valueLossChartInstance) {
        const config = createChartConfig('Pérdida Valor (Value Loss)', 'rgba(153, 102, 255, 1)');
        valueLossChartInstance = new Chart(valueLossCtx, config);
        window.valueLossChartInstance = valueLossChartInstance;
        // console.log("Gráfico de Pérdida Valor inicializado.");
    }
    if (explainedVarianceCtx && !explainedVarianceChartInstance) {
        const config = createChartConfig('Varianza Explicada', 'rgba(54, 162, 235, 1)');
        config.options.scales.y.min = -1;
        config.options.scales.y.max = 1;
        explainedVarianceChartInstance = new Chart(explainedVarianceCtx, config);
        window.explainedVarianceChartInstance = explainedVarianceChartInstance;
        // console.log("Gráfico de Varianza Explicada inicializado.");
    }
     console.log("Inicialización de gráficos completada.");
}

export function updateCharts(metricsData) {
    const timestep = metricsData.timestep;
    if (timestep === undefined) return;
    const label = timestep > 1000000 ? `${(timestep / 1000000).toFixed(1)}M` :
                  timestep > 1000 ? `${(timestep / 1000).toFixed(0)}k` : timestep;

    if (metricsData.ep_rew_mean !== undefined && rewardChartInstance) {
        addDataPoint(rewardChartInstance, label, metricsData.ep_rew_mean);
    }
    if (metricsData.ep_len_mean !== undefined && lengthChartInstance) {
        addDataPoint(lengthChartInstance, label, metricsData.ep_len_mean);
    }
    if (metricsData.value_loss !== undefined && valueLossChartInstance) {
        addDataPoint(valueLossChartInstance, label, metricsData.value_loss);
    }
    if (metricsData.explained_variance !== undefined && explainedVarianceChartInstance) {
        addDataPoint(explainedVarianceChartInstance, label, metricsData.explained_variance);
    }
}

export function clearCharts() {
    console.log("Limpiando datos de los gráficos...");
    const chartInstances = [
        rewardChartInstance, lengthChartInstance,
        valueLossChartInstance, explainedVarianceChartInstance
    ];
    chartInstances.forEach(instance => {
        if (instance) {
            instance.data.labels = [];
            instance.data.datasets.forEach((dataset) => { dataset.data = []; });
            instance.update('none'); // Actualizar sin animación
        }
    });
}

console.log("charts.js cargado.");