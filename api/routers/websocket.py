# Copyright (C) 2025 Lumina AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
WebSocket endpoints for real-time task progress
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from api.tasks import task_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/tasks/{task_id}")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task progress updates.
    
    Connect to receive live progress updates for a video generation task.
    
    Messages sent to client:
    {
        "task_id": "string",
        "status": "pending|running|completed|failed|cancelled",
        "progress": {
            "current": 0,
            "total": 5,
            "percentage": 0.0,
            "message": "Generating narrations..."
        },
        "result": {...},  // Only when completed
        "error": "string"  // Only when failed
    }
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for task {task_id}")
    
    try:
        while True:
            task = task_manager.get_task(task_id)
            
            if not task:
                await websocket.send_json({
                    "task_id": task_id,
                    "status": "not_found",
                    "error": f"Task {task_id} not found"
                })
                break
            
            # Send current state
            message = {
                "task_id": task.task_id,
                "status": task.status.value,
                "progress": task.progress.model_dump() if task.progress else None,
                "result": task.result,
                "error": task.error,
            }
            await websocket.send_json(message)
            
            # If terminal state, close connection
            if task.status.value in ("completed", "failed", "cancelled"):
                logger.info(f"Task {task_id} reached terminal state: {task.status.value}")
                break
            
            # Wait before next poll
            await asyncio.sleep(1)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
