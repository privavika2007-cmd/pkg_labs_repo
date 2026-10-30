from dataclasses import dataclass
from typing import Optional

from core.parallel import WORKERS, Job
from memory.buffer import PixelBuffer


@dataclass
class Context:
    job: Job
    workers: int = WORKERS
    second: Optional[PixelBuffer] = None
