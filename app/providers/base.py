from abc import ABC, abstractmethod
from ..models import Assignment, SpecialistResult

class Specialist(ABC):
    name: str
    @abstractmethod
    async def run(self, assignment: Assignment) -> SpecialistResult:
        raise NotImplementedError
