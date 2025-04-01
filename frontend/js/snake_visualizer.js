// frontend/js/snake_visualizer.js

import * as THREE from 'three';
// Asegúrate de que la ruta a OrbitControls sea correcta según tu estructura en libs/
// Si OrbitControls.js está directamente en libs/, la ruta es correcta.
// Si está en libs/controls/, sería 'three/addons/controls/OrbitControls.js'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export class SnakeVisualizer {
    /**
     * @param {string} canvasId - ID del elemento canvas HTML.
     * @param {number} boardSize - Tamaño del tablero (ej: 10 para 10x10).
     * @param {object} [colors] - Opcional: objeto con colores personalizados.
     * @param {number} [colors.background=0x111111] - Color de fondo.
     * @param {number} [colors.grid=0x444444] - Color de la rejilla.
     * @param {number} [colors.snakeHead=0x33FF33] - Color cabeza serpiente.
     * @param {number} [colors.snakeBody=0x00AA00] - Color cuerpo serpiente.
     * @param {number} [colors.food=0xFF3333] - Color comida.
     */
    constructor(canvasId, boardSize, colors = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas con ID "${canvasId}" no encontrado.`);
        }
        this.container = this.canvas.parentElement;
        if (!this.container) {
            throw new Error(`El canvas "${canvasId}" debe tener un elemento padre.`);
        }

        this.boardSize = boardSize;
        this.cellSize = 1.0;
        this.gridSize = this.boardSize * this.cellSize;

        this.colors = {
            background: colors.background !== undefined ? colors.background : 0x111111,
            grid: colors.grid !== undefined ? colors.grid : 0x444444,
            snakeHead: colors.snakeHead !== undefined ? colors.snakeHead : 0x33FF33,
            snakeBody: colors.snakeBody !== undefined ? colors.snakeBody : 0x00AA00,
            food: colors.food !== undefined ? colors.food : 0xFF3333,
        };

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.snakeGroup = new THREE.Group(); // Inicializar siempre aquí
        this.foodMesh = null;
        this._boundOnWindowResize = this._onWindowResize.bind(this); // Guardar referencia bind

        this._init(); // Llamar a la inicialización
    }

    /** Inicializa la escena, cámara, renderer, luces y controles. */
    _init() {
        // Escena
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(this.colors.background);

        // Cámara (Aspecto inicial se ajustará en el primer resize)
        this.camera = new THREE.PerspectiveCamera(60, this.container.clientWidth / this.container.clientHeight || 1, 0.1, 100);
        this.camera.position.set(this.gridSize / 2, this.gridSize * 1.2, this.gridSize * 1.1);
        this.camera.lookAt(this.gridSize / 2, 0, this.gridSize / 2);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
        this.renderer.setPixelRatio(window.devicePixelRatio);
        // El tamaño se establece en _onWindowResize

        // Luces
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 10, 7);
        this.scene.add(directionalLight);

        // Controles de Órbita
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.set(this.gridSize / 2, 0, this.gridSize / 2);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.1;
        this.controls.screenSpacePanning = false;
        this.controls.maxPolarAngle = Math.PI / 1.8;
        this.controls.minDistance = this.gridSize * 0.5;
        this.controls.maxDistance = this.gridSize * 3;

        // Crear la rejilla del tablero
        this._createBoardGrid();

        // Añadir grupo de la serpiente a la escena (ya inicializado en constructor)
        if (this.scene && this.snakeGroup) {
             this.scene.add(this.snakeGroup);
        } else {
             console.error("Error en _init: scene o snakeGroup no definidos antes de añadir.");
        }

        // Listener para redimensionar
        window.addEventListener('resize', this._boundOnWindowResize, false);

        // Iniciar bucle de animación
        this._animate();

        // Llamar resize inicial DESPUÉS de que todo esté configurado
        // Usar un pequeño timeout puede ayudar si el contenedor tarda en obtener tamaño
        requestAnimationFrame(() => { this._onWindowResize(); });


        console.log("SnakeVisualizer inicializado.");
    }

    /** Crea la rejilla visual del tablero. */
    _createBoardGrid() {
        const gridHelper = new THREE.GridHelper(this.gridSize, this.boardSize, this.colors.grid, this.colors.grid);
        gridHelper.position.set(this.gridSize / 2, 0, this.gridSize / 2);
        this.scene.add(gridHelper);

        const planeGeometry = new THREE.PlaneGeometry(this.gridSize, this.gridSize);
        const planeMaterial = new THREE.MeshStandardMaterial({ color: 0x282828, side: THREE.DoubleSide, transparent: true, opacity: 0.5 });
        const plane = new THREE.Mesh(planeGeometry, planeMaterial);
        plane.rotation.x = -Math.PI / 2;
        plane.position.set(this.gridSize / 2, -0.01, this.gridSize / 2);
        this.scene.add(plane);
    }

    /** Limpia los objetos 3D de la serpiente y la comida de la escena. */
    _clearObjects() {
        // Limpiar serpiente
        if (this.snakeGroup) {
            while (this.snakeGroup.children.length > 0) {
                const child = this.snakeGroup.children[0];
                this.snakeGroup.remove(child);
                if (child.geometry) child.geometry.dispose();
                if (child.material) {
                    if (Array.isArray(child.material)) child.material.forEach(material => material.dispose());
                    else child.material.dispose();
                }
            }
        } else {
            console.warn("_clearObjects: Intento de limpiar, pero this.snakeGroup no existe.");
        }

        // Limpiar comida
        if (this.foodMesh) {
            if (this.scene) this.scene.remove(this.foodMesh);
            else console.warn("_clearObjects: No se puede quitar foodMesh porque this.scene no existe.");
            if (this.foodMesh.geometry) this.foodMesh.geometry.dispose();
            if (this.foodMesh.material) this.foodMesh.material.dispose();
            this.foodMesh = null;
        }
    }

    /**
     * Convierte coordenadas del tablero 2D [fila, columna] a coordenadas del mundo 3D [x, y, z].
     */
    _boardToWorldCoords(boardCoords) {
        const y = this.cellSize / 2;
        const x = boardCoords[1] * this.cellSize + this.cellSize / 2;
        const z = boardCoords[0] * this.cellSize + this.cellSize / 2;
        return new THREE.Vector3(x, y, z);
    }

    /**
     * Actualiza la visualización 3D con las nuevas posiciones de la serpiente y la comida.
     * @param {Array<Array<number>>} snakeBody - Array de coordenadas [fila, columna] para cada segmento.
     * @param {Array<number> | null} foodPos - Coordenadas [fila, columna] de la comida, o null.
     */
    update(snakeBody, foodPos) {
        // 1. Limpiar objetos anteriores
        this._clearObjects();

        // 2. Verificar si snakeGroup existe (debería, pero por seguridad)
        if (!this.snakeGroup) {
            console.error("SnakeVisualizer.update: this.snakeGroup es null/undefined. Recreando...");
            this.snakeGroup = new THREE.Group();
            if (this.scene) this.scene.add(this.snakeGroup);
            else { console.error("No se puede añadir snakeGroup recreado, la escena no existe"); return; }
        }

        // 3. Crear y posicionar nuevos objetos
        const segmentSize = this.cellSize * 0.9;
        const snakeGeometry = new THREE.BoxGeometry(segmentSize, segmentSize, segmentSize);
        const headMaterial = new THREE.MeshStandardMaterial({ color: this.colors.snakeHead });
        const bodyMaterial = new THREE.MeshStandardMaterial({ color: this.colors.snakeBody });

        snakeBody.forEach((segmentCoords, index) => {
            const material = (index === 0) ? headMaterial : bodyMaterial;
            const segmentMesh = new THREE.Mesh(snakeGeometry, material);
            segmentMesh.position.copy(this._boardToWorldCoords(segmentCoords));
            this.snakeGroup.add(segmentMesh); // Añadir al grupo (ya verificado)
        });

        // Crear y posicionar comida (si existe y hay escena)
        if (foodPos && this.scene) {
             const foodSize = this.cellSize * 0.4;
            const foodGeometry = new THREE.SphereGeometry(foodSize, 16, 16);
            const foodMaterial = new THREE.MeshStandardMaterial({ color: this.colors.food, roughness: 0.5 });
            this.foodMesh = new THREE.Mesh(foodGeometry, foodMaterial);
            this.foodMesh.position.copy(this._boardToWorldCoords(foodPos));
            // Centrar la esfera verticalmente en su celda (su origen es el centro)
            this.foodMesh.position.y = this.cellSize / 2;
            this.scene.add(this.foodMesh);
        }

        // No disponer geometría/materiales aquí si se reutilizan (como es el caso)
    }

    /** Bucle de animación/renderizado. */
    _animate() {
        // Usar una referencia ligada (bound) para asegurar el contexto 'this' correcto
        this._requestAnimationFrameId = requestAnimationFrame(this._animate.bind(this));

        if (this.controls) {
            this.controls.update(); // Actualizar controles de órbita (para damping)
        }

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    /** Manejador para redimensionar la ventana o cuando el contenedor cambia de tamaño. */
    _onWindowResize() {
        if (this.camera && this.renderer && this.container) {
            const width = this.container.clientWidth;
            const height = this.container.clientHeight;

            // Solo actualizar si las dimensiones son válidas
            if (width > 0 && height > 0) {
                this.camera.aspect = width / height;
                this.camera.updateProjectionMatrix();
                this.renderer.setSize(width, height);
                // console.log(`Visualizer resized to ${width}x${height}`);
            } else {
                // console.warn(`Visualizer resize skipped: Invalid dimensions ${width}x${height}`);
            }
        }
    }

    /**
     * Llama explícitamente a la lógica de redimensionamiento.
     * Útil cuando el contenedor se hace visible o cambia de tamaño mediante JS.
     */
    handleResize() {
        // Llamar al método interno que hace el trabajo
        this._onWindowResize();
        // console.log("Visualizer: handleResize() llamado programáticamente."); // Log opcional
    }

    /** Limpia recursos Three.js y listeners. */
    dispose() {
        console.log("Disposing SnakeVisualizer...");
        // Detener bucle de animación
        if (this._requestAnimationFrameId) {
            cancelAnimationFrame(this._requestAnimationFrameId);
            this._requestAnimationFrameId = null;
        }
        // Quitar listener de resize usando la referencia guardada
        window.removeEventListener('resize', this._boundOnWindowResize, false);

        this._clearObjects(); // Limpiar serpiente y comida

        // Limpiar escena completamente
        if (this.scene) {
            // Eliminar otros objetos (luces, grid, plano) si es necesario
            // O simplemente vaciar la escena
            while(this.scene.children.length > 0){
                this.scene.remove(this.scene.children[0]);
            }
            this.scene = null;
        }

        if (this.renderer) {
             this.renderer.dispose(); // Liberar contexto WebGL
             this.renderer.domElement = null; // Ayudar al recolector de basura
             this.renderer = null;
        }
        if(this.controls) {
            this.controls.dispose();
            this.controls = null;
        }
        this.camera = null;
        this.snakeGroup = null; // Poner a null
        this.container = null; // Romper referencia al contenedor
        this.canvas = null; // Romper referencia al canvas

        console.log("SnakeVisualizer dispuesto.");
    }
} // Fin de la clase SnakeVisualizer

console.log("snake_visualizer.js cargado.");