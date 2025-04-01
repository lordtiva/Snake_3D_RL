// frontend/js/play_solo.js

import { SnakeVisualizer } from './snake_visualizer.js';
import { updateScore, showGameOver, setInstructions } from './ui.js';

// --- Constantes del Juego ---
const BOARD_SIZE = 20;
const GAME_SPEED_MS = 150;
const DIRECTIONS = { UP: 0, RIGHT: 1, DOWN: 2, LEFT: 3 };
const KEY_MAP = { ArrowUp: DIRECTIONS.UP, ArrowRight: DIRECTIONS.RIGHT, ArrowDown: DIRECTIONS.DOWN, ArrowLeft: DIRECTIONS.LEFT };
const OPPOSITE_DIRECTION = { [DIRECTIONS.UP]: DIRECTIONS.DOWN, [DIRECTIONS.RIGHT]: DIRECTIONS.LEFT, [DIRECTIONS.DOWN]: DIRECTIONS.UP, [DIRECTIONS.LEFT]: DIRECTIONS.RIGHT };

// --- Variables de Estado del Juego ---
let snake = [];
let food = null;
let currentDirection = DIRECTIONS.RIGHT;
let nextDirection = DIRECTIONS.RIGHT;
let score = 0;
let isGameOver = false;
let gameLoopInterval = null;
/** @type {SnakeVisualizer | null} */
let visualizerInstance = null;
let isActive = false;
// --- !! NUEVA VARIABLE DE ESTADO !! ---
let isGamePaused = true; // Iniciar pausado hasta la primera pulsación

// --- Funciones Internas del Juego ---

function placeFood() {
    let newFoodPos;
    const snakeSet = new Set(snake.map(segment => `${segment[0]},${segment[1]}`));
    do {
        newFoodPos = [Math.floor(Math.random() * BOARD_SIZE), Math.floor(Math.random() * BOARD_SIZE)];
    } while (snakeSet.has(`${newFoodPos[0]},${newFoodPos[1]}`));
    food = newFoodPos;
}

function resetGame() {
    console.log("Play Solo: Reiniciando juego...");
    const startY = Math.floor(BOARD_SIZE / 2);
    const startX = Math.floor(BOARD_SIZE / 2);
    snake = [[startY, startX]];
    currentDirection = DIRECTIONS.RIGHT;
    nextDirection = currentDirection;
    score = 0;
    isGameOver = false;
    // --- !! RESTABLECER PAUSA !! ---
    isGamePaused = true; // Pausar al reiniciar

    placeFood();

    updateScore(score);
    showGameOver(isGameOver);
    if (visualizerInstance) {
        visualizerInstance.update(snake, food);
    }
    // --- !! ACTUALIZAR INSTRUCCIONES !! ---
    setInstructions("Presiona una flecha para empezar..."); // Instrucción inicial
}

function moveSnake() {
    // --- !! COMPROBAR PAUSA !! ---
    // No mover si está pausado, terminado o inactivo
    if (isGamePaused || isGameOver || !isActive) return;

    currentDirection = nextDirection; // Actualizar dirección ANTES de mover

    const head = snake[0];
    let moveY = 0, moveX = 0;
    switch (currentDirection) {
        case DIRECTIONS.UP: moveY = -1; break;
        case DIRECTIONS.RIGHT: moveX = 1; break;
        case DIRECTIONS.DOWN: moveY = 1; break;
        case DIRECTIONS.LEFT: moveX = -1; break;
    }
    const newHead = [head[0] + moveY, head[1] + moveX];

    // 1. Colisión paredes
    if (newHead[0] < 0 || newHead[0] >= BOARD_SIZE || newHead[1] < 0 || newHead[1] >= BOARD_SIZE) {
        isGameOver = true;
        console.log("Play Solo: Game Over - Colisión con pared");
        return;
    }

    // 2. Colisión cuerpo
    const checkBody = snake.length > 1 ? snake.slice(0, -1) : [];
    const bodySet = new Set(checkBody.map(segment => `${segment[0]},${segment[1]}`));
    if (bodySet.has(`${newHead[0]},${newHead[1]}`)) {
        isGameOver = true;
        console.log("Play Solo: Game Over - Colisión consigo misma");
        return;
        // Nota: La lógica anterior que permitía moverse a la posición de la cola eliminada
        // se ha simplificado aquí. Si quieres esa lógica más compleja, se puede reintroducir.
    }

    // 3. Comer comida
    let ateFood = false;
    if (food && newHead[0] === food[0] && newHead[1] === food[1]) {
        ateFood = true;
        score++;
        console.log("Play Solo: Comida ingerida! Score:", score);
        placeFood();
    }

    // 4. Actualizar serpiente
    snake.unshift(newHead);
    if (!ateFood) {
        snake.pop();
    }
}

function gameLoop() {
    if (!isActive) { // Solo comprobar inactividad general aquí
        console.log("Play Solo: Deteniendo game loop por inactividad.");
        clearInterval(gameLoopInterval);
        gameLoopInterval = null;
        return;
    }

    // Mover la serpiente (la función interna comprobará isGameOver y isGamePaused)
    moveSnake();

    // Actualizar UI y Visualizador (solo si no terminó en moveSnake)
    if (!isGameOver) {
        updateScore(score);
        if (visualizerInstance) {
            visualizerInstance.update(snake, food);
        }
    } else {
         // Si el juego terminó DENTRO de moveSnake, actualizar UI aquí y detener bucle
         showGameOver(true);
         setInstructions("¡Juego Terminado! Presiona Reiniciar.");
         clearInterval(gameLoopInterval);
         gameLoopInterval = null;
         console.log("Play Solo: Game loop detenido por Game Over.");
    }
}

function handleKeyDown(event) {
    if (!isActive || isGameOver) return; // Ignorar si no activo o terminado

    const requestedDir = KEY_MAP[event.key];

    if (requestedDir !== undefined) {
        event.preventDefault();

        // --- !! DESACTIVAR PAUSA EN LA PRIMERA PULSACIÓN !! ---
        if (isGamePaused) {
            isGamePaused = false;
            setInstructions("¡En marcha!"); // O quitar instrucciones
            console.log("Play Solo: Juego reanudado por primera pulsación.");
        }
        // --- FIN DESACTIVACIÓN PAUSA ---

        // Actualizar nextDirection si no es la opuesta
        if (snake.length <= 1 || requestedDir !== OPPOSITE_DIRECTION[currentDirection]) {
            nextDirection = requestedDir;
        }
    }
}

// --- Funciones Exportadas para Control Externo ---

export function startPlaySolo(visualizer) {
    console.log("Iniciando modo Play Solo...");
    if (!visualizer) {
        console.error("Play Solo: Se requiere una instancia de SnakeVisualizer.");
        setInstructions("Error: Visualizador no disponible.");
        return;
    }
    if (isActive) {
        console.warn("Play Solo ya está activo.");
        return;
    }

    visualizerInstance = visualizer;
    isActive = true;
    isGamePaused = true; // Asegurar que empieza pausado

    resetGame(); // Reinicia estado (esto también establece isGamePaused=true y la instrucción inicial)

    if (!gameLoopInterval) {
        gameLoopInterval = setInterval(gameLoop, GAME_SPEED_MS);
    }

    window.addEventListener('keydown', handleKeyDown);

    const resetButton = document.getElementById('reset-game-btn');
    if (resetButton) {
        resetButton.onclick = () => {
            if (isActive) {
                if (gameLoopInterval) clearInterval(gameLoopInterval);
                resetGame(); // Resetear estado y pausar
                gameLoopInterval = setInterval(gameLoop, GAME_SPEED_MS);
            }
        };
    }
}

export function stopPlaySolo() {
    if (!isActive) return;
    console.log("Deteniendo modo Play Solo...");
    isActive = false;
    isGamePaused = true; // Asegurar que esté pausado si se reanuda

    if (gameLoopInterval) {
        clearInterval(gameLoopInterval);
        gameLoopInterval = null;
    }
    window.removeEventListener('keydown', handleKeyDown);
    visualizerInstance = null;
    setInstructions("Modo 'Jugar Solo' detenido.");
    const resetButton = document.getElementById('reset-game-btn');
    if (resetButton) resetButton.onclick = null;
}

console.log("play_solo.js cargado.");