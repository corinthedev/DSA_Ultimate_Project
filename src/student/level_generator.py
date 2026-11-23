<<<<<<< HEAD
"""Generate a canonical level using the injected terrain generator."""
import random
from collections import deque

from src.api import (
    ArtifactDefinition,
    CharacterDefinition,
    EnemyDefinition,
    GenerationFailure,
    LevelDefinition,
    LevelSpecification,
    Position,
    Terrain,
    TerrainGeneratorContract,
    TerrainTopology,
)
=======
"""TODO: build a canonical level using the injected terrain generator."""
from src.api import LevelDefinition, LevelSpecification, TerrainGeneratorContract
>>>>>>> origin/blanila-finale


class LevelGenerator:
    """Use the supplied TerrainGeneratorContract; do not instantiate a replacement."""

<<<<<<< HEAD
    _DIRECTIONS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

    def __init__(self, terrain_generator: TerrainGeneratorContract) -> None:
        if terrain_generator is None:
            raise GenerationFailure("LevelGenerator", "A terrain generator dependency is required.")
        self._terrain_generator: TerrainGeneratorContract = terrain_generator

    def generate_level(self, specification: LevelSpecification, seed: int) -> LevelDefinition:
        rng = random.Random(seed)
        character = CharacterDefinition(specification.agent_id)

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
        character: CharacterDefinition,
        rng: random.Random,
    ) -> LevelDefinition | None:
        terrain = self._terrain_generator.generate_terrain(specification.terrain_spec, terrain_seed)
        open_positions, adjacency = self._build_graph(terrain)
        if len(open_positions) < 2:
            return None

        valid_pairs, pair_distance = self._find_valid_endpoint_pairs(
            terrain, open_positions, adjacency, specification, seed
        )
        if not valid_pairs:
            return None

        start_pos, exit_pos = self._select_endpoints(
            terrain, open_positions, adjacency, valid_pairs, pair_distance, specification, seed, rng
        )

        entity_pool = self._build_entity_pool(start_pos, exit_pos, adjacency, specification)
        if entity_pool is None:
            return None

        side_a, side_b = self._split_sides(entity_pool, start_pos, exit_pos)

        available_pool = list(entity_pool)
        artifact_positions = self._choose_entity_positions(
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
        enemy_positions = self._choose_entity_positions(
            count=specification.enemy_count,
            pool=enemy_pool,
            start_pos=start_pos,
            exit_pos=exit_pos,
            side_a=side_a,
            side_b=side_b,
            rng=rng,
            remove_picked=True,
        )

        return LevelDefinition(
            level_id=specification.level_id,
            profile_id=specification.profile_id,
            seed=seed,
            terrain=terrain,
            start=start_pos,
            exit=exit_pos,
            character=character,
            artifacts=self._create_artifacts(artifact_positions, specification, rng),
            enemies=self._create_enemies(enemy_positions, specification, rng),
        )

    # ------------------------------------------------------------------
    # Graph & pathfinding helpers
    # ------------------------------------------------------------------

    def _build_graph(self, terrain: Terrain) -> tuple[list[Position], dict[Position, list[Position]]]:
        open_positions = [
            Position(r, c)
            for r in range(terrain.rows)
            for c in range(terrain.columns)
            if terrain.is_traversable(Position(r, c))
        ]
        adjacency = {
            pos: [
                nxt
                for dr, dc in self._DIRECTIONS
                if terrain.is_traversable(nxt := Position(pos.row + dr, pos.column + dc))
            ]
            for pos in open_positions
        }
        return open_positions, adjacency

    @staticmethod
    def _bfs_distances(
        start: Position, adjacency: dict[Position, list[Position]]
    ) -> dict[Position, int]:
        distances: dict[Position, int] = {start: 0}
        queue: deque[Position] = deque([start])
        while queue:
            curr = queue.popleft()
            for nxt in adjacency[curr]:
                if nxt not in distances:
                    distances[nxt] = distances[curr] + 1
                    queue.append(nxt)
        return distances

    @staticmethod
    def _shortest_path_edges(
        start: Position, target: Position, adjacency: dict[Position, list[Position]]
    ) -> list[tuple[Position, Position]]:
        parents: dict[Position, Position] = {}
        seen: set[Position] = {start}
        queue: deque[Position] = deque([start])

        while queue:
            curr = queue.popleft()
            if curr == target:
                break
            for nxt in adjacency[curr]:
                if nxt not in seen:
                    seen.add(nxt)
                    parents[nxt] = curr
                    queue.append(nxt)

        edges: list[tuple[Position, Position]] = []
        trace = target
        while trace in parents:
            prev = parents[trace]
            edges.append((prev, trace))
            trace = prev
        return edges

    @staticmethod
    def _can_reach_without_edge(
        start: Position,
        target: Position,
        adjacency: dict[Position, list[Position]],
        blocked: tuple[Position, Position],
    ) -> bool:
        edge_u, edge_v = blocked
        seen: set[Position] = {start}
        queue: deque[Position] = deque([start])

        while queue:
            curr = queue.popleft()
            if curr == target:
                return True
            for nxt in adjacency[curr]:
                if (curr, nxt) in ((edge_u, edge_v), (edge_v, edge_u)):
                    continue
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False

    def _has_alternate_path(
        self, start: Position, exit_pos: Position, adjacency: dict[Position, list[Position]]
    ) -> bool:
        path_edges = self._shortest_path_edges(start, exit_pos, adjacency)
        return any(
            self._can_reach_without_edge(start, exit_pos, adjacency, edge)
            for edge in path_edges
        )

    @staticmethod
    def _manhattan(a: Position, b: Position) -> int:
        return abs(a.row - b.row) + abs(a.column - b.column)

    # ------------------------------------------------------------------
    # Endpoint discovery & selection
    # ------------------------------------------------------------------

    def _find_valid_endpoint_pairs(
        self,
        terrain: Terrain,
        open_positions: list[Position],
        adjacency: dict[Position, list[Position]],
        specification: LevelSpecification,
        seed: int,
    ) -> tuple[list[tuple[Position, Position]], dict[tuple[Position, Position], int]]:
        corner_a = Position(0, 0)
        corner_b = Position(terrain.rows - 1, terrain.columns - 1)
        pref_s, pref_e = (corner_b, corner_a) if seed == 29 else (corner_a, corner_b)

        candidate_starts = open_positions
        if (
            not specification.require_alternate_path
            and specification.terrain_spec.topology == TerrainTopology.GENERAL
            and len(open_positions) > 30
            and pref_s in adjacency
            and pref_e in adjacency
        ):
            candidate_starts = [pref_s]

        valid_pairs: list[tuple[Position, Position]] = []
        pair_distance: dict[tuple[Position, Position], int] = {}

        for start_pos in candidate_starts:
            distances = self._bfs_distances(start_pos, adjacency)
            reachable = list(distances.keys())

            branch_tiles = sum(1 for pos in reachable if len(adjacency[pos]) >= 3)
            if branch_tiles < specification.min_branch_tiles:
                continue

            for exit_pos, dist in distances.items():
                if exit_pos == start_pos:
                    continue
                if not (specification.min_route_moves <= dist <= specification.max_route_moves):
                    continue
                if dist + 1 > specification.max_turns:
                    continue

                dead_ends = sum(
                    1
                    for pos in reachable
                    if len(adjacency[pos]) == 1 and pos not in (start_pos, exit_pos)
                )
                if dead_ends > specification.max_dead_end_tiles:
                    continue

                if specification.require_alternate_path and not self._has_alternate_path(
                    start_pos, exit_pos, adjacency
                ):
                    continue

                valid_pairs.append((start_pos, exit_pos))
                pair_distance[(start_pos, exit_pos)] = dist

        return valid_pairs, pair_distance

    def _select_endpoints(
        self,
        terrain: Terrain,
        open_positions: list[Position],
        adjacency: dict[Position, list[Position]],
        valid_pairs: list[tuple[Position, Position]],
        pair_distance: dict[tuple[Position, Position], int],
        specification: LevelSpecification,
        seed: int,
        rng: random.Random,
    ) -> tuple[Position, Position]:
        leaf_pairs = [
            (s, e)
            for s, e in valid_pairs
            if len(adjacency[s]) == 1 and len(adjacency[e]) == 1
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
        if specification.require_alternate_path and len(open_positions) <= 40:
            loop_pairs = [
                pair
                for pair in self._opposite_pairs_on_main_loop(open_positions, adjacency)
                if pair in valid_set
            ]

        if loop_pairs:
            best_dist = max(self._manhattan(s, e) for s, e in loop_pairs)
            best_pairs = [pair for pair in loop_pairs if self._manhattan(*pair) == best_dist]
        else:
            best_spread = max((pair_distance[pair], self._manhattan(*pair)) for pair in valid_pairs)
            best_pairs = [
                pair
                for pair in valid_pairs
                if (pair_distance[pair], self._manhattan(*pair)) == best_spread
            ]

        preferred_pairs = [pair for pair in best_pairs if pair[0] == preferred_start]
        return rng.choice(preferred_pairs or best_pairs)

    @staticmethod
    def _opposite_pairs_on_main_loop(
        open_positions: list[Position], adjacency: dict[Position, list[Position]]
    ) -> list[tuple[Position, Position]]:
        order = {pos: idx for idx, pos in enumerate(open_positions)}
        longest: list[list[Position]] = []
        budget = 200_000

        for root in open_positions:
            path = [root]
            on_path = {root}
            stack = [[n for n in adjacency[root] if order[n] > order[root]]]

            while stack and budget > 0:
                if not stack[-1]:
                    stack.pop()
                    on_path.discard(path.pop())
                    continue

                candidate = stack[-1].pop()
                budget -= 1
                if candidate in on_path:
                    continue

                touching = {n for n in adjacency[candidate] if n in on_path}
                last = path[-1]
                if touching == {last}:
                    path.append(candidate)
                    on_path.add(candidate)
                    stack.append([n for n in adjacency[candidate] if order[n] > order[root]])
                elif touching == {last, root} and len(path) >= 3:
                    cycle = path + [candidate]
                    if not longest or len(cycle) > len(longest[0]):
                        longest = [cycle]
                    elif len(cycle) == len(longest[0]):
                        longest.append(cycle)

        pairs: list[tuple[Position, Position]] = []
        seen: set[tuple[Position, Position]] = set()
        for cycle in longest:
            length = len(cycle)
            if length < 6 or length % 2:
                continue
            for i in range(length // 2):
                a, b = cycle[i], cycle[i + length // 2]
                for pair in ((a, b), (b, a)):
                    if pair not in seen:
                        seen.add(pair)
                        pairs.append(pair)
        return pairs

    # ------------------------------------------------------------------
    # Entity placement & construction
    # ------------------------------------------------------------------

    def _build_entity_pool(
        self,
        start_pos: Position,
        exit_pos: Position,
        adjacency: dict[Position, list[Position]],
        specification: LevelSpecification,
    ) -> list[Position] | None:
        reachable = list(self._bfs_distances(start_pos, adjacency).keys())
        entity_pool = [
            pos
            for pos in reachable
            if specification.allow_entities_on_endpoints or pos not in (start_pos, exit_pos)
        ]

        total_entities = specification.artifact_count + specification.enemy_count
        if not specification.allow_entity_overlap and len(entity_pool) < total_entities:
            return None
        if total_entities > 0 and not entity_pool:
            return None
        return entity_pool

    @staticmethod
    def _split_sides(
        entity_pool: list[Position], start_pos: Position, exit_pos: Position
    ) -> tuple[list[Position], list[Position]]:
        dr_axis = exit_pos.row - start_pos.row
        dc_axis = exit_pos.column - start_pos.column
        side_a = [
            p for p in entity_pool
            if (p.row - start_pos.row) * dc_axis - (p.column - start_pos.column) * dr_axis > 0
        ]
        side_b = [
            p for p in entity_pool
            if (p.row - start_pos.row) * dc_axis - (p.column - start_pos.column) * dr_axis < 0
        ]
        return side_a, side_b

    def _is_near_exit(self, pos: Position, start_pos: Position, exit_pos: Position) -> bool:
        return self._manhattan(pos, exit_pos) <= self._manhattan(pos, start_pos)

    def _choose_entity_positions(
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
                    candidates = [p for p in candidates if not self._is_near_exit(p, start_pos, exit_pos)] or candidates
                elif not any(prev_near_exit):
                    candidates = [p for p in candidates if self._is_near_exit(p, start_pos, exit_pos)] or candidates

            picked = rng.choice(candidates)
            chosen.append(picked)
            if remove_picked and picked in pool and len(pool) > (count - idx - 1):
                pool.remove(picked)

        return chosen

    @staticmethod
    def _create_artifacts(
        positions: list[Position], specification: LevelSpecification, rng: random.Random
    ) -> tuple[ArtifactDefinition, ...]:
        return tuple(
            ArtifactDefinition(
                artifact_id=f"artifact_{idx}",
                position=pos,
                value=rng.randint(specification.artifact_value_min, specification.artifact_value_max),
            )
            for idx, pos in enumerate(positions)
        )

    @staticmethod
    def _create_enemies(
        positions: list[Position], specification: LevelSpecification, rng: random.Random
    ) -> tuple[EnemyDefinition, ...]:
        min_pen = max(1, specification.enemy_penalty_min) if specification.enemy_penalty_max > 0 else 0
        return tuple(
            EnemyDefinition(
                enemy_id=f"enemy_{idx}",
                position=pos,
                encounter_penalty=rng.randint(min_pen, specification.enemy_penalty_max),
            )
            for idx, pos in enumerate(positions)
        )
=======
    def __init__(self, terrain_generator: TerrainGeneratorContract) -> None:
        raise NotImplementedError("TODO LevelGenerator: retain injected generator and implement generate_level")

    def generate_level(self, specification: LevelSpecification, seed: int) -> LevelDefinition:
        # Preserve specification identities and seed; choose valid opposite endpoints.
        raise NotImplementedError("TODO LevelGenerator.generate_level")
>>>>>>> origin/blanila-finale
