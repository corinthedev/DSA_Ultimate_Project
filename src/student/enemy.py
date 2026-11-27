from src.api import EnemyDefinition, Position
from src.student.character import PositionedEntity


class Enemy(PositionedEntity):
    def __init__(self, enemy_id: str, position: Position, encounter_penalty: int) -> None:
        definition = EnemyDefinition(enemy_id, position, encounter_penalty)
        super().__init__(definition.enemy_id, definition.position)
        self.__encounter_penalty = definition.encounter_penalty

    @property
    def enemy_id(self) -> str:
        return self.entity_id

    @property
    def encounter_penalty(self) -> int:
        return self.__encounter_penalty

    def kind(self) -> str:
        return "Enemy"

    def total_engagement_cost(self) -> int:
        return 1 + self.__encounter_penalty

    def to_definition(self) -> EnemyDefinition:
        return EnemyDefinition(self.enemy_id, self.position, self.encounter_penalty)

    def __repr__(self) -> str:
        return (
            f"Enemy(enemy_id={self.enemy_id!r}, "
            f"position={self.position!r}, encounter_penalty={self.encounter_penalty!r})"
        )
