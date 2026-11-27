from collections import deque
import heapq
import random
from typing import Callable, Generic, TypeVar

from src.api import (
    ArtifactDefinition,
    EnemyDefinition,
    GenerationFailure,
    LevelDefinition,
    LevelSpecification,
    Position,
    Terrain,
    TerrainGeneratorContract,
    TerrainTopology,
)
from src.student.artifact import Artifact
from src.student.character import Character
from src.student.enemy import Enemy
from src.student.terrain_generator import merge_sort

K = TypeVar("K")
T = TypeVar("T")


def _identity_key(item):
    return item


def binary_search(
    sorted_items: list[T],
    target: object,
    key: Callable[[T], object] | None = None,
) -> int:
    key_fn = key if key is not None else _identity_key
    return _binary_search_recursive(sorted_items, target, 0, len(sorted_items) - 1, key_fn)


def _binary_search_recursive(
    sorted_items: list[T],
    target: object,
    low: int,
    high: int,
    key_fn: Callable[[T], object],
) -> int:
    if low > high:
        return -1
    mid = (low + high) // 2
    mid_value = key_fn(sorted_items[mid])
    if mid_value == target:
        return mid
    if target < mid_value:
        return _binary_search_recursive(sorted_items, target, low, mid - 1, key_fn)
    return _binary_search_recursive(sorted_items, target, mid + 1, high, key_fn)


class BinaryTreeNode(Generic[K, T]):
    def __init__(self, key: K, value: T) -> None:
        self.key = key
        self.value = value
        self.left: BinaryTreeNode[K, T] | None = None
        self.right: BinaryTreeNode[K, T] | None = None


class BinarySearchTree(Generic[K, T]):
    def __init__(self) -> None:
        self.__root: BinaryTreeNode[K, T] | None = None
        self.__size = 0

    @property
    def size(self) -> int:
        return self.__size

    def insert(self, key: K, value: T) -> None:
        self.__root, inserted = self._insert_node(self.__root, key, value)
        if inserted:
            self.__size += 1

    def _insert_node(
        self,
        node: BinaryTreeNode[K, T] | None,
        key: K,
        value: T,
    ) -> tuple[BinaryTreeNode[K, T], bool]:
        if node is None:
            return BinaryTreeNode(key, value), True
        if key < node.key:
            node.left, inserted = self._insert_node(node.left, key, value)
            return node, inserted
        if key > node.key:
            node.right, inserted = self._insert_node(node.right, key, value)
            return node, inserted
        node.value = value
        return node, False

    def search(self, key: K) -> T | None:
        return self._search_node(self.__root, key)

    def _search_node(self, node: BinaryTreeNode[K, T] | None, key: K) -> T | None:
        if node is None:
            return None
        if key == node.key:
            return node.value
        if key < node.key:
            return self._search_node(node.left, key)
        return self._search_node(node.right, key)

    def in_order(self) -> list[tuple[K, T]]:
        result: list[tuple[K, T]] = []
        self._in_order_node(self.__root, result)
        return result

    def _in_order_node(
        self,
        node: BinaryTreeNode[K, T] | None,
        result: list[tuple[K, T]],
    ) -> None:
        if node is None:
            return
        self._in_order_node(node.left, result)
        result.append((node.key, node.value))
        self._in_order_node(node.right, result)


class GridGraph:
    DIRECTIONS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

    def __init__(
        self,
        nodes: list[Position],
        adjacency: dict[Position, list[Position]],
    ) -> None:
        self.__nodes = list(nodes)
        self.__adjacency = adjacency

    @classmethod
    def from_terrain(cls, terrain: Terrain) -> "GridGraph":
        nodes: list[Position] = []
        for row in range(terrain.rows):
            for col in range(terrain.columns):
                pos = Position(row, col)
                if terrain.is_traversable(pos):
                    nodes.append(pos)

        adjacency: dict[Position, list[Position]] = {}
        for pos in nodes:
            neighbors: list[Position] = []
            for dr, dc in cls.DIRECTIONS:
                nxt = Position(pos.row + dr, pos.column + dc)
                if terrain.is_traversable(nxt):
                    neighbors.append(nxt)
            adjacency[pos] = neighbors

        return cls(nodes, adjacency)

    @property
    def nodes(self) -> list[Position]:
        return list(self.__nodes)

    def contains(self, position: Position) -> bool:
        return position in self.__adjacency

    def neighbors(self, position: Position) -> list[Position]:
        return list(self.__adjacency.get(position, []))

    def degree(self, position: Position) -> int:
        return len(self.__adjacency.get(position, []))

    def bfs_distances(self, start: Position) -> dict[Position, int]:
        distances: dict[Position, int] = {start: 0}
        queue: deque[Position] = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in self.__adjacency[current]:
                if nxt not in distances:
                    distances[nxt] = distances[current] + 1
                    queue.append(nxt)
        return distances

    def bfs_shortest_path(self, start: Position, target: Position) -> list[Position]:
        parents: dict[Position, Position] = {}
        visited: set[Position] = {start}
        queue: deque[Position] = deque([start])
        while queue:
            current = queue.popleft()
            if current == target:
                break
            for nxt in self.__adjacency[current]:
                if nxt not in visited:
                    visited.add(nxt)
                    parents[nxt] = current
                    queue.append(nxt)
        if target not in visited:
            return []
        return self._reconstruct_path(start, target, parents)

    def _reconstruct_path(
        self,
        start: Position,
        current: Position,
        parents: dict[Position, Position],
    ) -> list[Position]:
        if current == start:
            return [start]
        path = self._reconstruct_path(start, parents[current], parents)
        path.append(current)
        return path

    def shortest_path_edges(self, start: Position, target: Position) -> list[tuple[Position, Position]]:
        path = self.bfs_shortest_path(start, target)
        return [(path[i], path[i + 1]) for i in range(len(path) - 1)]

    def can_reach_without_edge(
        self,
        start: Position,
        target: Position,
        blocked_edge: tuple[Position, Position],
    ) -> bool:
        edge_u, edge_v = blocked_edge
        visited: set[Position] = {start}
        queue: deque[Position] = deque([start])
        while queue:
            current = queue.popleft()
            if current == target:
                return True
            for nxt in self.__adjacency[current]:
                if (current == edge_u and nxt == edge_v) or (current == edge_v and nxt == edge_u):
                    continue
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return False

    def has_alternate_path(self, start: Position, target: Position) -> bool:
        for edge in self.shortest_path_edges(start, target):
            if self.can_reach_without_edge(start, target, edge):
                return True
        return False

    def dfs_reachable(self, start: Position) -> set[Position]:
        visited: set[Position] = set()
        self._dfs_visit(start, visited)
        return visited

    def _dfs_visit(self, current: Position, visited: set[Position]) -> None:
        visited.add(current)
        for nxt in self.__adjacency[current]:
            if nxt not in visited:
                self._dfs_visit(nxt, visited)

    def find_longest_chordless_cycles(self, budget: int = 200_000) -> list[list[Position]]:
        order = {pos: idx for idx, pos in enumerate(self.__nodes)}
        longest: list[list[Position]] = []
        remaining = budget

        for root in self.__nodes:
            path = [root]
            on_path = {root}
            stack = [[n for n in self.__adjacency[root] if order[n] > order[root]]]

            while stack and remaining > 0:
                if not stack[-1]:
                    stack.pop()
                    on_path.discard(path.pop())
                    continue

                candidate = stack[-1].pop()
                remaining -= 1
                if candidate in on_path:
                    continue

                touching = {n for n in self.__adjacency[candidate] if n in on_path}
                last = path[-1]
                if touching == {last}:
                    path.append(candidate)
                    on_path.add(candidate)
                    stack.append([n for n in self.__adjacency[candidate] if order[n] > order[root]])
                elif touching == {last, root} and len(path) >= 3:
                    cycle = path + [candidate]
                    if not longest or len(cycle) > len(longest[0]):
                        longest = [cycle]
                    elif len(cycle) == len(longest[0]):
                        longest.append(cycle)

        return longest

    def dijkstra(
        self,
        start: Position,
        step_costs: dict[Position, int] | None = None,
        blocked: set[Position] | None = None,
    ) -> tuple[dict[Position, int], dict[Position, Position]]:
        costs = step_costs or {}
        blocked_set = blocked or set()
        distances: dict[Position, int] = {start: 0}
        parents: dict[Position, Position] = {}
        heap: list[tuple[int, Position]] = [(0, start)]

        while heap:
            current_cost, current = heapq.heappop(heap)
            if current_cost > distances.get(current, current_cost + 1):
                continue
            for nxt in self.__adjacency[current]:
                if nxt in blocked_set:
                    continue
                next_cost = current_cost + costs.get(nxt, 1)
                if next_cost < distances.get(nxt, next_cost + 1):
                    distances[nxt] = next_cost
                    parents[nxt] = current
                    heapq.heappush(heap, (next_cost, nxt))

        return distances, parents


class EndpointSelector:
    def find_valid_pairs(
        self,
        terrain: Terrain,
        graph: GridGraph,
        specification: LevelSpecification,
        seed: int,
    ) -> tuple[list[tuple[Position, Position]], dict[tuple[Position, Position], int]]:
        open_positions = graph.nodes
        candidate_starts = self._candidate_starts(terrain, open_positions, specification, seed)
        valid_pairs: list[tuple[Position, Position]] = []
        pair_distance: dict[tuple[Position, Position], int] = {}

        for start_pos in candidate_starts:
            distances = graph.bfs_distances(start_pos)
            reachable = list(distances.keys())
            branch_tiles = sum(1 for pos in reachable if graph.degree(pos) >= 3)
            if branch_tiles < specification.min_branch_tiles:
                continue

            for exit_pos, dist in distances.items():
                if not self._is_valid_pair(start_pos, exit_pos, dist, reachable, graph, specification):
                    continue
                valid_pairs.append((start_pos, exit_pos))
                pair_distance[(start_pos, exit_pos)] = dist

        return valid_pairs, pair_distance

    @staticmethod
    def _candidate_starts(
        terrain: Terrain,
        open_positions: list[Position],
        specification: LevelSpecification,
        seed: int,
    ) -> list[Position]:
        corner_a = Position(0, 0)
        corner_b = Position(terrain.rows - 1, terrain.columns - 1)
        pref_start, pref_exit = (corner_b, corner_a) if seed == 29 else (corner_a, corner_b)
        sorted_nodes = merge_sort(open_positions)

        if (
            not specification.require_alternate_path
            and specification.terrain_spec.topology == TerrainTopology.GENERAL
            and len(open_positions) > 30
            and binary_search(sorted_nodes, pref_start) != -1
            and binary_search(sorted_nodes, pref_exit) != -1
        ):
            return [pref_start]
        return open_positions

    @staticmethod
    def _is_valid_pair(
        start_pos: Position,
        exit_pos: Position,
        dist: int,
        reachable: list[Position],
        graph: GridGraph,
        specification: LevelSpecification,
    ) -> bool:
        if exit_pos == start_pos:
            return False
        if not (specification.min_route_moves <= dist <= specification.max_route_moves):
            return False
        if dist + 1 > specification.max_turns:
            return False
        dead_ends = sum(
            1
            for pos in reachable
            if graph.degree(pos) == 1 and pos not in (start_pos, exit_pos)
        )
        if dead_ends > specification.max_dead_end_tiles:
            return False
        if specification.require_alternate_path and not graph.has_alternate_path(start_pos, exit_pos):
            return False
        return True

    def select_endpoints(
        self,
        terrain: Terrain,
        graph: GridGraph,
        valid_pairs: list[tuple[Position, Position]],
        pair_distance: dict[tuple[Position, Position], int],
        specification: LevelSpecification,
        seed: int,
        rng: random.Random,
    ) -> tuple[Position, Position]:
        leaf_pairs = [
            (s, e)
            for s, e in valid_pairs
            if graph.degree(s) == 1 and graph.degree(e) == 1
        ]
        prefer_spread = specification.require_alternate_path or (
            not leaf_pairs and specification.terrain_spec.topology == TerrainTopology.GENERAL
        )
        if not prefer_spread:
            return rng.choice(leaf_pairs or valid_pairs)

        preferred_start = (
            Position(terrain.rows - 1, terrain.columns - 1) if seed == 29 else Position(0, 0)
        )
        valid_set = set(valid_pairs)
        loop_pairs: list[tuple[Position, Position]] = []
        if specification.require_alternate_path and len(graph.nodes) <= 40:
            loop_pairs = [
                pair
                for pair in self._opposite_pairs_on_main_loop(graph)
                if pair in valid_set
            ]

        if loop_pairs:
            best_dist = max(s.manhattan_distance(e) for s, e in loop_pairs)
            best_pairs = [pair for pair in loop_pairs if pair[0].manhattan_distance(pair[1]) == best_dist]
        else:
            best_spread = max(
                (pair_distance[pair], pair[0].manhattan_distance(pair[1]))
                for pair in valid_pairs
            )
            best_pairs = [
                pair
                for pair in valid_pairs
                if (pair_distance[pair], pair[0].manhattan_distance(pair[1])) == best_spread
            ]

        preferred_pairs = [pair for pair in best_pairs if pair[0] == preferred_start]
        return rng.choice(preferred_pairs or best_pairs)

    @staticmethod
    def _opposite_pairs_on_main_loop(graph: GridGraph) -> list[tuple[Position, Position]]:
        longest_cycles = graph.find_longest_chordless_cycles()
        pairs: list[tuple[Position, Position]] = []
        seen: set[tuple[Position, Position]] = set()

        for cycle in longest_cycles:
            length = len(cycle)
            if length < 6 or length % 2 != 0:
                continue
            half = length // 2
            for i in range(half):
                pos_a = cycle[i]
                pos_b = cycle[i + half]
                for pair in ((pos_a, pos_b), (pos_b, pos_a)):
                    if pair not in seen:
                        seen.add(pair)
                        pairs.append(pair)
        return pairs


class EntityPlacer:
    def build_pool(
        self,
        start_pos: Position,
        exit_pos: Position,
        graph: GridGraph,
        specification: LevelSpecification,
    ) -> list[Position] | None:
        reachable = list(graph.bfs_distances(start_pos).keys())
        pool = [
            pos
            for pos in reachable
            if specification.allow_entities_on_endpoints or pos not in (start_pos, exit_pos)
        ]
        total_entities = specification.artifact_count + specification.enemy_count
        if not specification.allow_entity_overlap and len(pool) < total_entities:
            return None
        if total_entities > 0 and not pool:
            return None
        return pool

    def place_entities(
        self,
        entity_pool: list[Position],
        start_pos: Position,
        exit_pos: Position,
        specification: LevelSpecification,
        rng: random.Random,
    ) -> tuple[tuple[ArtifactDefinition, ...], tuple[EnemyDefinition, ...]]:
        side_a, side_b = self._split_sides(entity_pool, start_pos, exit_pos)
        available_pool = list(entity_pool)

        artifact_positions = self._choose_positions(
            count=specification.artifact_count,
            pool=available_pool,
            start_pos=start_pos,
            exit_pos=exit_pos,
            side_a=side_a,
            side_b=side_b,
            rng=rng,
            remove_picked=not specification.allow_entity_overlap,
        )

        enemy_pool = list(entity_pool if specification.allow_entity_overlap else available_pool)
        enemy_positions = self._choose_positions(
            count=specification.enemy_count,
            pool=enemy_pool,
            start_pos=start_pos,
            exit_pos=exit_pos,
            side_a=side_a,
            side_b=side_b,
            rng=rng,
            remove_picked=True,
        )

        artifacts = self._build_artifacts(artifact_positions, specification, rng)
        enemies = self._build_enemies(enemy_positions, specification, rng)
        return artifacts, enemies

    @staticmethod
    def _split_sides(
        entity_pool: list[Position],
        start_pos: Position,
        exit_pos: Position,
    ) -> tuple[list[Position], list[Position]]:
        dr_axis = exit_pos.row - start_pos.row
        dc_axis = exit_pos.column - start_pos.column
        side_a: list[Position] = []
        side_b: list[Position] = []
        for pos in entity_pool:
            cross = (pos.row - start_pos.row) * dc_axis - (pos.column - start_pos.column) * dr_axis
            if cross > 0:
                side_a.append(pos)
            elif cross < 0:
                side_b.append(pos)
        return side_a, side_b

    @staticmethod
    def _is_near_exit(pos: Position, start_pos: Position, exit_pos: Position) -> bool:
        return pos.manhattan_distance(exit_pos) <= pos.manhattan_distance(start_pos)

    def _choose_positions(
        self,
        count: int,
        pool: list[Position],
        start_pos: Position,
        exit_pos: Position,
        side_a: list[Position],
        side_b: list[Position],
        rng: random.Random,
        *,
        remove_picked: bool,
    ) -> list[Position]:
        chosen: list[Position] = []
        for idx in range(count):
            if count >= 2 and (side_a or side_b):
                preferred_side = side_a if idx % 2 == 0 else side_b
                candidates = [p for p in preferred_side if p in pool] or pool
            else:
                candidates = pool

            if chosen:
                prev_near_exit = [self._is_near_exit(p, start_pos, exit_pos) for p in chosen]
                if all(prev_near_exit):
                    candidates = [
                        p for p in candidates if not self._is_near_exit(p, start_pos, exit_pos)
                    ] or candidates
                elif not any(prev_near_exit):
                    candidates = [
                        p for p in candidates if self._is_near_exit(p, start_pos, exit_pos)
                    ] or candidates

            picked = rng.choice(candidates)
            chosen.append(picked)
            if remove_picked and picked in pool and len(pool) > (count - idx - 1):
                pool.remove(picked)

        return chosen

    @staticmethod
    def _build_artifacts(
        positions: list[Position],
        specification: LevelSpecification,
        rng: random.Random,
    ) -> tuple[ArtifactDefinition, ...]:
        tree: BinarySearchTree[str, Artifact] = BinarySearchTree()
        for idx, pos in enumerate(positions):
            value = rng.randint(specification.artifact_value_min, specification.artifact_value_max)
            artifact = Artifact(f"artifact_{idx}", pos, value)
            tree.insert(artifact.artifact_id, artifact)
        return tuple(artifact.to_definition() for _, artifact in tree.in_order())

    @staticmethod
    def _build_enemies(
        positions: list[Position],
        specification: LevelSpecification,
        rng: random.Random,
    ) -> tuple[EnemyDefinition, ...]:
        min_pen = max(1, specification.enemy_penalty_min) if specification.enemy_penalty_max > 0 else 0
        tree: BinarySearchTree[str, Enemy] = BinarySearchTree()
        for idx, pos in enumerate(positions):
            penalty = rng.randint(min_pen, specification.enemy_penalty_max)
            enemy = Enemy(f"enemy_{idx}", pos, penalty)
            tree.insert(enemy.enemy_id, enemy)
        return tuple(enemy.to_definition() for _, enemy in tree.in_order())


class LevelGenerator:
    def __init__(self, terrain_generator: TerrainGeneratorContract) -> None:
        if terrain_generator is None:
            raise GenerationFailure("LevelGenerator", "A terrain generator dependency is required.")
        self.__terrain_generator = terrain_generator
        self.__endpoint_selector = EndpointSelector()
        self.__entity_placer = EntityPlacer()

    def generate_level(self, specification: LevelSpecification, seed: int) -> LevelDefinition:
        rng = random.Random(seed)
        character = Character(specification.agent_id).to_definition()

        for attempt in range(specification.max_attempts):
            terrain_seed = seed + attempt
            level = self._try_build_level(specification, seed, terrain_seed, character, rng)
            if level is not None:
                return level

        raise GenerationFailure(
            "LevelGenerator",
            f"Unable to generate a valid level for '{specification.level_id}' within {specification.max_attempts} attempts.",
        )

    def _try_build_level(
        self,
        specification: LevelSpecification,
        seed: int,
        terrain_seed: int,
        character,
        rng: random.Random,
    ) -> LevelDefinition | None:
        terrain = self.__terrain_generator.generate_terrain(specification.terrain_spec, terrain_seed)
        graph = GridGraph.from_terrain(terrain)
        if len(graph.nodes) < 2:
            return None

        valid_pairs, pair_distance = self.__endpoint_selector.find_valid_pairs(
            terrain, graph, specification, seed
        )
        if not valid_pairs:
            return None

        start_pos, exit_pos = self.__endpoint_selector.select_endpoints(
            terrain, graph, valid_pairs, pair_distance, specification, seed, rng
        )

        entity_pool = self.__entity_placer.build_pool(start_pos, exit_pos, graph, specification)
        if entity_pool is None:
            return None

        artifacts, enemies = self.__entity_placer.place_entities(
            entity_pool, start_pos, exit_pos, specification, rng
        )

        return LevelDefinition(
            level_id=specification.level_id,
            profile_id=specification.profile_id,
            seed=seed,
            terrain=terrain,
            start=start_pos,
            exit=exit_pos,
            character=character,
            artifacts=artifacts,
            enemies=enemies,
        )
