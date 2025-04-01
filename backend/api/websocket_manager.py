# backend/api/websocket_manager.py
import asyncio
import json
import logging
from typing import List, Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Mantener conjuntos separados para diferentes tipos de conexiones
        self.watch_connections: Set[WebSocket] = set()
        self.training_connections: Set[WebSocket] = set()
        logger.info("WebSocketManager inicializado.")

    async def connect(self, websocket: WebSocket, connection_type: str):
        """Registra una nueva conexión."""
        await websocket.accept()
        if connection_type == "watch":
            self.watch_connections.add(websocket)
            logger.info(f"Cliente Watch conectado. Total: {len(self.watch_connections)}")
        elif connection_type == "training":
            self.training_connections.add(websocket)
            logger.info(f"Cliente Training conectado. Total: {len(self.training_connections)}")
        else:
            logger.warning(f"Tipo de conexión desconocido: {connection_type}")

    def disconnect(self, websocket: WebSocket, connection_type: str):
        """Elimina una conexión."""
        if connection_type == "watch":
            self.watch_connections.discard(websocket)
            logger.info(f"Cliente Watch desconectado. Total: {len(self.watch_connections)}")
        elif connection_type == "training":
            self.training_connections.discard(websocket)
            logger.info(f"Cliente Training desconectado. Total: {len(self.training_connections)}")

    async def broadcast_to_training(self, message: str):
        """Envía un mensaje a todos los clientes de entrenamiento conectados."""
        # Crear una copia para evitar problemas si el conjunto cambia durante la iteración
        disconnected_clients = set()
        for connection in self.training_connections:
            try:
                await connection.send_text(message)
            except Exception as e: # Capturar desconexiones u otros errores
                 logger.warning(f"Error enviando a cliente training, desconectando: {e}")
                 disconnected_clients.add(connection)

        # Limpiar clientes desconectados
        for client in disconnected_clients:
             self.training_connections.discard(client)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Envía un mensaje a un cliente específico."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Error enviando mensaje personal, desconectando: {e}")
            self.disconnect(websocket, "unknown") # Desconectar si falla el envío

# Instancia Singleton del gestor
websocket_manager_instance = WebSocketManager()

# Función para inyección de dependencias
async def get_websocket_manager() -> WebSocketManager:
    return websocket_manager_instance