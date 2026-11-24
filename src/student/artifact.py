from src.api import ArtifactDefinition, Position
from src.student.character import PositionedEntity


class Artifact(PositionedEntity):
    def __init__(self, artifact_id: str, position: Position, value: int) -> None:
        definition = ArtifactDefinition(artifact_id, position, value)
        super().__init__(definition.artifact_id, definition.position)
        self.__value = definition.value

    @property
    def artifact_id(self) -> str:
        return self.entity_id

    @property
    def value(self) -> int:
        return self.__value

    def kind(self) -> str:
        return "Artifact"

    def is_worth_collecting(self, extra_cost: int, deduction_rate: int) -> bool:
        return self.__value > extra_cost * deduction_rate

    def to_definition(self) -> ArtifactDefinition:
        return ArtifactDefinition(self.artifact_id, self.position, self.value)

    def __repr__(self) -> str:
        return (
            f"Artifact(artifact_id={self.artifact_id!r}, "
            f"position={self.position!r}, value={self.value!r})"
        )
