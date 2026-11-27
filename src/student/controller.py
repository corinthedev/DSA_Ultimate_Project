from abc import ABC, abstractmethod
import heapq

from src.api import Position, WorldAction, WorldActionType, WorldSnapshot
from src.student.artifact import Artifact
from src.student.enemy import Enemy
from src.student.level_generator import BinarySearchTree, GridGraph, binary_search
from src.student.terrain_generator import merge_sort


DIRECTION_ACTIONS: tuple[tuple[int, int, WorldActionType], ...] = (
    (-1, 0, WorldActionType.MOVE_NORTH),
    (1, 0, WorldActionType.MOVE_SOUTH),
    (0, -1, WorldActionType.MOVE_WEST),
    (0, 1, WorldActionType.MOVE_EAST),
)


class ScoreEvaluator:
    def __init__(self, state: WorldSnapshot) -> None:
        self.__base_points = state.base_points
        self.__deduction_rate = state.deduction_rate
        self.__baseline_cost = state.baseline_cost
        self.__zero_score_excess = state.zero_score_excess

    def evaluate(self, total_cost: int, artifact_reward: int) -> int:
        excess = max(0, total_cost - self.__baseline_cost)
        if excess >= self.__zero_score_excess:
            return 0
        raw_score = self.__base_points + artifact_reward - self.__deduction_rate * excess
        return max(0, raw_score)


class EntityIndex:
    def __init__(self, state: WorldSnapshot) -> None:
        collected_sorted = merge_sort(list(state.collected_artifact_ids))
        defeated_sorted = merge_sort(list(state.defeated_enemy_ids))
        patrol_ids_sorted = merge_sort([patrol.enemy_id for patrol in state.level.patrols])

        self.__artifact_tree: BinarySearchTree[str, Artifact] = BinarySearchTree()
        self.__static_enemy_tree: BinarySearchTree[str, Enemy] = BinarySearchTree()
        self.__remaining_artifacts: list[Artifact] = []
        self.__remaining_static_enemies: list[Enemy] = []

        for definition in state.level.artifacts:
            if binary_search(collected_sorted, definition.artifact_id) == -1:
                artifact = Artifact(definition.artifact_id, definition.position, definition.value)
                self.__artifact_tree.insert(artifact.artifact_id, artifact)
                self.__remaining_artifacts.append(artifact)

        for definition in state.level.enemies:
            is_patrol = binary_search(patrol_ids_sorted, definition.enemy_id) != -1
            is_defeated = binary_search(defeated_sorted, definition.enemy_id) != -1
            if not is_patrol and not is_defeated:
                enemy = Enemy(definition.enemy_id, definition.position, definition.encounter_penalty)
                self.__static_enemy_tree.insert(enemy.enemy_id, enemy)
                self.__remaining_static_enemies.append(enemy)

    @property
    def remaining_artifacts(self) -> list[Artifact]:
        return list(self.__remaining_artifacts)

    @property
    def remaining_static_enemies(self) -> list[Enemy]:
        return list(self.__remaining_static_enemies)

    def find_artifact(self, artifact_id: str) -> Artifact | None:
        return self.__artifact_tree.search(artifact_id)

    def find_static_enemy(self, enemy_id: str) -> Enemy | None:
        return self.__static_enemy_tree.search(enemy_id)


class RoutePlanner(ABC):
    @staticmethod
    def step_position(position: Position, action_type: WorldActionType) -> Position:
        for dr, dc, move_type in DIRECTION_ACTIONS:
            if move_type == action_type:
                return Position(position.row + dr, position.column + dc)
        return position

    def reconstruct_actions(
        self,
        state_key,
        parents: dict,
    ) -> list[WorldAction]:
        if state_key not in parents:
            return []
        previous_key, action = parents[state_key]
        actions = self.reconstruct_actions(previous_key, parents)
        actions.append(action)
        return actions

    @staticmethod
    def mask_reward(mask: int, artifacts: list[Artifact]) -> int:
        total = 0
        for idx, artifact in enumerate(artifacts):
            if mask & (1 << idx):
                total += artifact.value
        return total

    @abstractmethod
    def build_plan(
        self,
        state: WorldSnapshot,
        graph: GridGraph,
        index: EntityIndex,
    ) -> list[WorldAction]:
        pass


class StaticRoutePlanner(RoutePlanner):
    def build_plan(
        self,
        state: WorldSnapshot,
        graph: GridGraph,
        index: EntityIndex,
    ) -> list[WorldAction]:
        artifacts = index.remaining_artifacts
        enemies = index.remaining_static_enemies
        if len(artifacts) + len(enemies) > 10:
            return self._plan_direct_fallback(state, graph, enemies)
        return self._plan_optimal(state, graph, artifacts, enemies)

    def _plan_optimal(
        self,
        state: WorldSnapshot,
        graph: GridGraph,
        artifacts: list[Artifact],
        enemies: list[Enemy],
    ) -> list[WorldAction]:
        evaluator = ScoreEvaluator(state)
        allowed = set(state.allowed_actions)
        artifact_by_pos: dict[Position, list[tuple[int, Artifact]]] = {}
        for idx, artifact in enumerate(artifacts):
            artifact_by_pos.setdefault(artifact.position, []).append((idx, artifact))

        enemy_by_pos: dict[Position, list[tuple[int, Enemy]]] = {}
        for idx, enemy in enumerate(enemies):
            enemy_by_pos.setdefault(enemy.position, []).append((idx, enemy))

        start_key = (state.agent_position, 0, 0)
        best_cost: dict[tuple[Position, int, int], tuple[int, int]] = {start_key: (0, state.turn)}
        parents: dict[tuple[Position, int, int], tuple[tuple[Position, int, int], WorldAction]] = {}
        heap: list[tuple[int, int, Position, int, int]] = [(0, state.turn, state.agent_position, 0, 0)]

        best_choice: tuple[int, int, int, tuple[Position, int, int]] | None = None

        while heap:
            cost, turns, pos, collected_mask, defeated_mask = heapq.heappop(heap)
            state_key = (pos, collected_mask, defeated_mask)
            if (cost, turns) > best_cost[state_key]:
                continue

            if pos == state.exit_position and turns < state.max_turns:
                final_cost = state.turn + cost + 1
                reward = self.mask_reward(collected_mask, artifacts)
                score = evaluator.evaluate(final_cost, reward)
                candidate = (score, -final_cost, -(turns + 1), state_key)
                if best_choice is None or candidate[:3] > best_choice[:3]:
                    best_choice = candidate

            if turns + 1 >= state.max_turns:
                continue

            if WorldActionType.COLLECT in allowed and pos in artifact_by_pos:
                for idx, artifact in artifact_by_pos[pos]:
                    bit = 1 << idx
                    if collected_mask & bit:
                        continue
                    nxt_key = (pos, collected_mask | bit, defeated_mask)
                    nxt_metric = (cost + 1, turns + 1)
                    if nxt_key not in best_cost or nxt_metric < best_cost[nxt_key]:
                        best_cost[nxt_key] = nxt_metric
                        parents[nxt_key] = (
                            state_key,
                            WorldAction(WorldActionType.COLLECT, target_id=artifact.artifact_id),
                        )
                        heapq.heappush(heap, (nxt_metric[0], nxt_metric[1], pos, collected_mask | bit, defeated_mask))

            for dr, dc, action_type in DIRECTION_ACTIONS:
                if action_type not in allowed:
                    continue
                nxt_pos = Position(pos.row + dr, pos.column + dc)
                if not graph.contains(nxt_pos):
                    continue

                blocking_enemies = [
                    entry
                    for entry in enemy_by_pos.get(nxt_pos, [])
                    if not (defeated_mask & (1 << entry[0]))
                ]
                if blocking_enemies:
                    if WorldActionType.ENGAGE in allowed:
                        enemy_idx, enemy = blocking_enemies[0]
                        bit = 1 << enemy_idx
                        nxt_key = (pos, collected_mask, defeated_mask | bit)
                        nxt_metric = (cost + enemy.total_engagement_cost(), turns + 1)
                        if nxt_key not in best_cost or nxt_metric < best_cost[nxt_key]:
                            best_cost[nxt_key] = nxt_metric
                            parents[nxt_key] = (
                                state_key,
                                WorldAction(WorldActionType.ENGAGE, target_id=enemy.enemy_id),
                            )
                            heapq.heappush(
                                heap,
                                (nxt_metric[0], nxt_metric[1], pos, collected_mask, defeated_mask | bit),
                            )
                    continue

                nxt_key = (nxt_pos, collected_mask, defeated_mask)
                nxt_metric = (cost + 1, turns + 1)
                if nxt_key not in best_cost or nxt_metric < best_cost[nxt_key]:
                    best_cost[nxt_key] = nxt_metric
                    parents[nxt_key] = (state_key, WorldAction(action_type))
                    heapq.heappush(heap, (nxt_metric[0], nxt_metric[1], nxt_pos, collected_mask, defeated_mask))

        if best_choice is None:
            return [WorldAction.wait()]
        plan = self.reconstruct_actions(best_choice[3], parents)
        plan.append(WorldAction(WorldActionType.EXIT))
        return plan

    def _plan_direct_fallback(
        self,
        state: WorldSnapshot,
        graph: GridGraph,
        enemies: list[Enemy],
    ) -> list[WorldAction]:
        enemies_by_pos: dict[Position, list[Enemy]] = {}
        for enemy in enemies:
            enemies_by_pos.setdefault(enemy.position, []).append(enemy)
        step_costs = {
            pos: 1 + sum(enemy.total_engagement_cost() for enemy in tile_enemies)
            for pos, tile_enemies in enemies_by_pos.items()
        }
        _, parents = graph.dijkstra(state.agent_position, step_costs=step_costs)
        if state.exit_position != state.agent_position and state.exit_position not in parents:
            return [WorldAction.wait()]

        path = self._reconstruct_positions(state.agent_position, state.exit_position, parents)
        actions: list[WorldAction] = []
        for idx in range(len(path) - 1):
            curr = path[idx]
            nxt = path[idx + 1]
            for enemy in enemies_by_pos.get(nxt, []):
                actions.append(WorldAction(WorldActionType.ENGAGE, target_id=enemy.enemy_id))
            actions.append(self._move_between(curr, nxt))
        actions.append(WorldAction(WorldActionType.EXIT))
        return actions

    def _reconstruct_positions(
        self,
        start: Position,
        current: Position,
        parents: dict[Position, Position],
    ) -> list[Position]:
        if current == start:
            return [start]
        path = self._reconstruct_positions(start, parents[current], parents)
        path.append(current)
        return path

    @staticmethod
    def _move_between(source: Position, target: Position) -> WorldAction:
        dr = target.row - source.row
        dc = target.column - source.column
        for move_dr, move_dc, action_type in DIRECTION_ACTIONS:
            if dr == move_dr and dc == move_dc:
                return WorldAction(action_type)
        return WorldAction.wait()


class PatrolRoutePlanner(RoutePlanner):
    def build_plan(
        self,
        state: WorldSnapshot,
        graph: GridGraph,
        index: EntityIndex,
    ) -> list[WorldAction]:
        evaluator = ScoreEvaluator(state)
        allowed = set(state.allowed_actions)
        artifacts = index.remaining_artifacts
        static_enemies = index.remaining_static_enemies

        artifact_by_pos: dict[Position, list[tuple[int, Artifact]]] = {}
        for idx, artifact in enumerate(artifacts):
            artifact_by_pos.setdefault(artifact.position, []).append((idx, artifact))

        static_enemy_by_pos: dict[Position, list[tuple[int, Enemy]]] = {}
        for idx, enemy in enumerate(static_enemies):
            static_enemy_by_pos.setdefault(enemy.position, []).append((idx, enemy))

        turn_limit = state.max_turns
        if state.deadline_turn is not None:
            turn_limit = min(turn_limit, state.deadline_turn)

        patrol_at = self._build_patrol_schedule(state, turn_limit + 1)

        start_key = (state.agent_position, state.turn, 0, 0)
        best_cost: dict[tuple[Position, int, int, int], int] = {start_key: 0}
        parents: dict[tuple[Position, int, int, int], tuple[tuple[Position, int, int, int], WorldAction]] = {}
        heap: list[tuple[int, int, Position, int, int]] = [(0, state.turn, state.agent_position, 0, 0)]

        best_choice: tuple[int, int, int, tuple[Position, int, int, int]] | None = None

        while heap:
            cost, turn, pos, collected_mask, defeated_mask = heapq.heappop(heap)
            state_key = (pos, turn, collected_mask, defeated_mask)
            if cost > best_cost[state_key]:
                continue

            if pos == state.exit_position and turn < state.max_turns:
                final_cost = state.turn + cost + 1
                reward = self.mask_reward(collected_mask, artifacts)
                score = evaluator.evaluate(final_cost, reward)
                candidate = (score, -final_cost, -(turn + 1), state_key)
                if best_choice is None or candidate[:3] > best_choice[:3]:
                    best_choice = candidate

            next_turn = turn + 1
            if next_turn >= turn_limit:
                continue

            patrols_now = patrol_at[turn]
            patrols_next = patrol_at[next_turn]

            if pos not in patrols_next:
                if WorldActionType.WAIT in allowed:
                    self._relax(
                        heap,
                        best_cost,
                        parents,
                        state_key,
                        (pos, next_turn, collected_mask, defeated_mask),
                        cost + 1,
                        WorldAction.wait(),
                    )

                if WorldActionType.COLLECT in allowed and pos in artifact_by_pos:
                    for idx, artifact in artifact_by_pos[pos]:
                        bit = 1 << idx
                        if collected_mask & bit:
                            continue
                        self._relax(
                            heap,
                            best_cost,
                            parents,
                            state_key,
                            (pos, next_turn, collected_mask | bit, defeated_mask),
                            cost + 1,
                            WorldAction(WorldActionType.COLLECT, target_id=artifact.artifact_id),
                        )

            for dr, dc, action_type in DIRECTION_ACTIONS:
                if action_type not in allowed:
                    continue
                nxt_pos = Position(pos.row + dr, pos.column + dc)
                if not graph.contains(nxt_pos):
                    continue

                blocking_enemies = [
                    entry
                    for entry in static_enemy_by_pos.get(nxt_pos, [])
                    if not (defeated_mask & (1 << entry[0]))
                ]
                if blocking_enemies:
                    if WorldActionType.ENGAGE in allowed and pos not in patrols_next:
                        enemy_idx, enemy = blocking_enemies[0]
                        bit = 1 << enemy_idx
                        self._relax(
                            heap,
                            best_cost,
                            parents,
                            state_key,
                            (pos, next_turn, collected_mask, defeated_mask | bit),
                            cost + enemy.total_engagement_cost(),
                            WorldAction(WorldActionType.ENGAGE, target_id=enemy.enemy_id),
                        )
                    continue

                if nxt_pos in patrols_now or nxt_pos in patrols_next:
                    continue

                self._relax(
                    heap,
                    best_cost,
                    parents,
                    state_key,
                    (nxt_pos, next_turn, collected_mask, defeated_mask),
                    cost + 1,
                    WorldAction(action_type),
                )

        if best_choice is None:
            return [WorldAction.wait()]
        plan = self.reconstruct_actions(best_choice[3], parents)
        plan.append(WorldAction(WorldActionType.EXIT))
        return plan

    @staticmethod
    def _build_patrol_schedule(state: WorldSnapshot, max_turn: int) -> list[set[Position]]:
        schedule: list[set[Position]] = []
        for turn in range(max_turn + 1):
            occupied: set[Position] = set()
            for patrol in state.level.patrols:
                pos = patrol.positions[(patrol.initial_phase + turn) % patrol.period]
                occupied.add(pos)
            schedule.append(occupied)
        return schedule

    @staticmethod
    def _relax(
        heap: list[tuple[int, int, Position, int, int]],
        best_cost: dict[tuple[Position, int, int, int], int],
        parents: dict[tuple[Position, int, int, int], tuple[tuple[Position, int, int, int], WorldAction]],
        from_key: tuple[Position, int, int, int],
        to_key: tuple[Position, int, int, int],
        new_cost: int,
        action: WorldAction,
    ) -> None:
        if to_key not in best_cost or new_cost < best_cost[to_key]:
            best_cost[to_key] = new_cost
            parents[to_key] = (from_key, action)
            heapq.heappush(heap, (new_cost, to_key[1], to_key[0], to_key[2], to_key[3]))


class AgentController:
    def __init__(self) -> None:
        self.__plan: list[WorldAction] = []
        self.__expected_position: Position | None = None
        self.__static_planner: RoutePlanner = StaticRoutePlanner()
        self.__patrol_planner: RoutePlanner = PatrolRoutePlanner()

    def choose_action(self, state: WorldSnapshot, agent_id: str) -> WorldAction:
        if self._needs_replan(state):
            self.__plan = self._create_plan(state)

        action = self.__plan.pop(0) if self.__plan else WorldAction.wait()
        self.__expected_position = RoutePlanner.step_position(state.agent_position, action.action_type)
        return action

    def _needs_replan(self, state: WorldSnapshot) -> bool:
        if not self.__plan:
            return True
        if state.turn == 0:
            return True
        if self.__expected_position != state.agent_position:
            return True
        return False

    def _create_plan(self, state: WorldSnapshot) -> list[WorldAction]:
        graph = GridGraph.from_terrain(state.terrain)
        index = EntityIndex(state)
        planner = self._select_planner(state)
        return planner.build_plan(state, graph, index)

    def _select_planner(self, state: WorldSnapshot) -> RoutePlanner:
        if state.level.patrols or state.deadline_turn is not None:
            return self.__patrol_planner
        return self.__static_planner
