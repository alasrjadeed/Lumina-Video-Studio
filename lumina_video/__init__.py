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
Lumina Video Studio - AI-powered video generator

Convention-based system with unified configuration management.

Usage:
    from lumina_video import lumina_video
    
    # Initialize
    await lumina_video.initialize()
    
    # Use capabilities
    answer = await lumina_video.llm("Explain atomic habits")
    audio = await lumina_video.tts("Hello world")
    
    # Generate video with different pipelines
    # Standard pipeline (default)
    result = await lumina_video.generate_video(
        text="如何提高学习效率",
        n_scenes=5
    )
    
    # Custom pipeline (template for your own logic)
    result = await lumina_video.generate_video(
        text=your_content,
        pipeline="custom",
        custom_param_example="custom_value"
    )
    
    # Check available pipelines
    print(lumina_video.pipelines.keys())  # dict_keys(['standard', 'custom'])
"""

from lumina_video.service import LuminaVideoCore, lumina_video
from lumina_video.config import config_manager

__version__ = "0.2.0"

__all__ = ["LuminaVideoCore", "lumina_video", "config_manager"]
