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
FastAPI Dependencies

Provides dependency injection for LuminaVideoCore and other services.
"""

from typing import Annotated
from fastapi import Depends
from loguru import logger

from lumina_video.service import LuminaVideoCore


# Global Lumina Video Studio instance
_lumina_video_instance: LuminaVideoCore = None


async def get_lumina_video() -> LuminaVideoCore:
    """
    Get Lumina Video Studio core instance (dependency injection)
    
    Returns:
        LuminaVideoCore instance
    """
    global _lumina_video_instance
    
    if _lumina_video_instance is None:
        _lumina_video_instance = LuminaVideoCore()
        await _lumina_video_instance.initialize()
        logger.info("✅ Lumina Video Studio initialized for API")
    
    return _lumina_video_instance


async def shutdown_lumina_video():
    """Shutdown Lumina Video Studio instance and cleanup resources"""
    global _lumina_video_instance
    if _lumina_video_instance:
        logger.info("Shutting down Lumina Video Studio...")
        await _lumina_video_instance.cleanup()
        _lumina_video_instance = None
    
    from lumina_video.services.frame_html import HTMLFrameGenerator
    await HTMLFrameGenerator.close_browser()


# Type alias for dependency injection
LuminaVideoDep = Annotated[LuminaVideoCore, Depends(get_lumina_video)]

