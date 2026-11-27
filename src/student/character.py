from abc import ABC, abstractmethod

from src.api import CharacterDefinition, Position


class WorldEntity(ABC):
    def __init__(self, entity_id: str) -> None:
        self.__entity_id = self.validate_id(entity_id, "entity_id")

    @property
    def entity_id(self) -> str:
        return self.__entity_id

    @staticmethod
    def validate_id(value: str, field_name: str) -> str:
        if type(value) is not str:
            raise TypeError(f"{field_name} must be a string.")
        if not value or value != value.strip():
            raise ValueError(f"{field_name} must be nonempty and trimmed.")
        return value

    @staticmethod
    def validate_position(value: Position) -> Position:
        if type(value) is not Position:
            raise TypeError("position must be a Position.")
        return Position(value.row, value.column)

    @abstractmethod
    def kind(self) -> str:
        pass

    @abstractmethod
    def to_definition(self):
        pass

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.to_definition() == other.to_definition()

    def __repr__(self) -> str:
        return f"{self.kind()}(id={self.entity_id!r})"


class PositionedEntity(WorldEntity):
    def __init__(self, entity_id: str, position: Position) -> None:
        super().__init__(entity_id)
        self.__position = self.validate_position(position)

    @property
    def position(self) -> Position:
        return self.__position

    def distance_to(self, other: Position) -> int:
        target = self.validate_position(other)
        return self.__position.manhattan_distance(target)

    def is_adjacent_to(self, other: Position) -> bool:
        return self.distance_to(other) == 1

    def __repr__(self) -> str:
        return f"{self.kind()}(id={self.entity_id!r}, position={self.position!r})"


class Character(WorldEntity):
    def __init__(self, agent_id: str) -> None:
        definition = CharacterDefinition(agent_id)
        super().__init__(definition.agent_id)

    @property
    def agent_id(self) -> str:
        return self.entity_id

    def kind(self) -> str:
        return "Character"

    def to_definition(self) -> CharacterDefinition:
        return CharacterDefinition(self.agent_id)
