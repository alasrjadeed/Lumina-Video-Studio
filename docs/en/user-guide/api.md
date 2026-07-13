# API Usage

Lumina Video Studio provides a complete Python API for easy integration into your projects.

---

## Quick Start

```python
from lumina_video.service import LuminaVideoCore
import asyncio

async def main():
    # Initialize
    lumina = LuminaVideoCore()
    await lumina.initialize()
    
    # Generate video
    result = await lumina.generate_video(
        text="Why develop a reading habit",
        mode="generate",
        n_scenes=5
    )
    
    print(f"Video generated: {result.video_path}")

# Run
asyncio.run(main())
```

---

## API Reference

For detailed API documentation, see [API Overview](../reference/api-overview.md).

---

## Examples

For more usage examples, check the `examples/` directory in the project.

