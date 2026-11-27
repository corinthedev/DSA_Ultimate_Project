from abc import ABC, abstractmethod
from itertools import product
import random
from typing import Callable, Generic, TypeVar

from src.api import GenerationFailure, Terrain, TerrainGenerationSpec, TerrainTopology

T = TypeVar("T")


def _identity_key(item):
    return item


def merge_sort(items: list[T], key: Callable[[T], object] | None = None) -> list[T]:
    if len(items) <= 1:
        return list(items)
    key_fn = key if key is not None else _identity_key
    midpoint = len(items) // 2
    left_half = merge_sort(items[:midpoint], key_fn)
    right_half = merge_sort(items[midpoint:], key_fn)
    return _merge_sorted(left_half, right_half, key_fn)


def _merge_sorted(left: list[T], right: list[T], key_fn: Callable[[T], object]) -> list[T]:
    merged: list[T] = []
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        if key_fn(left[left_index]) <= key_fn(right[right_index]):
            merged.append(left[left_index])
            left_index += 1
        else:
            merged.append(right[right_index])
            right_index += 1
    merged.extend(left[left_index:])
    merged.extend(right[right_index:])
    return merged


class TreeNode(Generic[T]):
    def __init__(self, value: T, parent: "TreeNode[T] | None" = None) -> None:
        self.__value = value
        self.__parent = parent
        self.__children: list[TreeNode[T]] = []

    @property
    def value(self) -> T:
        return self.__value

    @property
    def parent(self) -> "TreeNode[T] | None":
        return self.__parent

    @property
    def children(self) -> tuple["TreeNode[T]", ...]:
        return tuple(self.__children)

    def add_child(self, child_value: T) -> "TreeNode[T]":
        child = TreeNode(child_value, parent=self)
        self.__children.append(child)
        return child

    def collect_values(self) -> list[T]:
        values: list[T] = [self.__value]
        for child in self.__children:
            values.extend(child.collect_values())
        return values


class TerrainStrategy(ABC):
    DIRECTIONS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

    def neighbors(self, row: int, col: int, rows: int, cols: int) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for dr, dc in self.DIRECTIONS:
            nr = row + dr
            nc = col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                result.append((nr, nc))
        return result

    @abstractmethod
    def generate(
        self,
        rows: int,
        cols: int,
        low: int,
        high: int,
        attempts: int,
        rng: random.Random,
    ) -> set[tuple[int, int]]:
        pass


class StraightPathStrategy(TerrainStrategy):
    def generate(
        self,
        rows: int,
        cols: int,
        low: int,
        high: int,
        attempts: int,
        rng: random.Random,
    ) -> set[tuple[int, int]]:
        target = rng.randint(low, high)
        candidates: list[set[tuple[int, int]]] = []

        if target <= cols:
            for row in range(rows):
                for start_col in range(cols - target + 1):
                    candidates.append({(row, start_col + offset) for offset in range(target)})

        if target <= rows:
            for col in range(cols):
                for start_row in range(rows - target + 1):
                    candidates.append({(start_row + offset, col) for offset in range(target)})

        if not candidates:
            raise GenerationFailure("TerrainGenerator", "No straight path fits the specification.")
        return rng.choice(candidates)


class BentPathStrategy(TerrainStrategy):
    def generate(
        self,
        rows: int,
        cols: int,
        low: int,
        high: int,
        attempts: int,
        rng: random.Random,
    ) -> set[tuple[int, int]]:
        for _ in range(attempts):
            target = rng.randint(low, high)
            tiles = self._try_random_bent_path(rows, cols, target, rng)
            if tiles is not None:
                return tiles
        return self._fallback_bent_path(rows, cols, low, high, rng)

    def _try_random_bent_path(
        self,
        rows: int,
        cols: int,
        target: int,
        rng: random.Random,
    ) -> set[tuple[int, int]] | None:
        start = (rng.randrange(rows), rng.randrange(cols))
        path: list[tuple[int, int]] = [start]
        visited: set[tuple[int, int]] = {start}

        for _ in range(target - 1):
            cur_row, cur_col = path[-1]
            earlier = visited - {path[-1]}
            valid_steps: list[tuple[int, int]] = []
            for nbr in self.neighbors(cur_row, cur_col, rows, cols):
                if nbr in visited:
                    continue
                touches_earlier = any(
                    adj in earlier for adj in self.neighbors(nbr[0], nbr[1], rows, cols)
                )
                if not touches_earlier:
                    valid_steps.append(nbr)
            if not valid_steps:
                return None
            step = rng.choice(valid_steps)
            path.append(step)
            visited.add(step)

        has_bend = len({r for r, _ in path}) > 1 and len({c for _, c in path}) > 1
        return visited if has_bend else None

    def _fallback_bent_path(
        self,
        rows: int,
        cols: int,
        low: int,
        high: int,
        rng: random.Random,
    ) -> set[tuple[int, int]]:
        candidates: list[set[tuple[int, int]]] = []
        for tile_count in range(low, high + 1):
            total_steps = tile_count - 1
            min_east = max(1, total_steps - (rows - 1))
            max_east = min(cols - 1, total_steps - 1)
            for east in range(min_east, max_east + 1):
                south = total_steps - east
                candidates.append(
                    {(0, c) for c in range(east + 1)}
                    | {(r, east) for r in range(south + 1)}
                )
                if east >= 2:
                    mid_e = east // 2
                    candidates.append(
                        {(0, c) for c in range(mid_e + 1)}
                        | {(r, mid_e) for r in range(south + 1)}
                        | {(south, c) for c in range(mid_e, east + 1)}
                    )
                if south >= 2:
                    mid_s = south // 2
                    candidates.append(
                        {(r, 0) for r in range(mid_s + 1)}
                        | {(mid_s, c) for c in range(east + 1)}
                        | {(r, east) for r in range(mid_s, south + 1)}
                    )

        if not candidates:
            raise GenerationFailure("TerrainGenerator", "Unable to construct a valid BENT_PATH.")
        return rng.choice(candidates)


class BranchingTreeStrategy(TerrainStrategy):
    def generate(
        self,
        rows: int,
        cols: int,
        low: int,
        high: int,
        attempts: int,
        rng: random.Random,
    ) -> set[tuple[int, int]]:
        hub_pool = self._hub_candidates(rows, cols)

        for _ in range(max(attempts, 12)):
            target = rng.randint(low, high)
            hub = rng.choice(hub_pool)
            hub_neighbors = self.neighbors(hub[0], hub[1], rows, cols)
            rng.shuffle(hub_neighbors)

            root = TreeNode(hub)
            nodes_by_cell: dict[tuple[int, int], TreeNode[tuple[int, int]]] = {hub: root}
            for nbr in hub_neighbors[:3]:
                nodes_by_cell[nbr] = root.add_child(nbr)

            while len(nodes_by_cell) < target:
                choice = self._pick_frontier_cell(nodes_by_cell, rows, cols, rng)
                if choice is None:
                    break
                cell, parent_cell = choice
                nodes_by_cell[cell] = nodes_by_cell[parent_cell].add_child(cell)

            tiles = set(root.collect_values())
            if len(tiles) == target and self._has_branch(tiles, rows, cols):
                return tiles

        raise GenerationFailure("TerrainGenerator", "Unable to construct a valid BRANCHING_TREE.")

    def _hub_candidates(self, rows: int, cols: int) -> list[tuple[int, int]]:
        hubs = [
            (r, c)
            for r, c in product(range(rows), range(cols))
            if len(self.neighbors(r, c, rows, cols)) >= 3
        ]
        interior = [cell for cell in hubs if len(self.neighbors(cell[0], cell[1], rows, cols)) == 4]
        return interior or hubs

    def _has_branch(self, tiles: set[tuple[int, int]], rows: int, cols: int) -> bool:
        for cell in tiles:
            degree = sum(1 for nbr in self.neighbors(cell[0], cell[1], rows, cols) if nbr in tiles)
            if degree >= 3:
                return True
        return False

    def _pick_frontier_cell(
        self,
        nodes_by_cell: dict[tuple[int, int], TreeNode[tuple[int, int]]],
        rows: int,
        cols: int,
        rng: random.Random,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        frontier: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for r, c in product(range(rows), range(cols)):
            if (r, c) in nodes_by_cell:
                continue
            touching = [nbr for nbr in self.neighbors(r, c, rows, cols) if nbr in nodes_by_cell]
            if len(touching) == 1:
                frontier.append(((r, c), touching[0]))

        if not frontier:
            return None

        degrees = {
            cell: sum(1 for nbr in self.neighbors(cell[0], cell[1], rows, cols) if nbr in nodes_by_cell)
            for cell in nodes_by_cell
        }
        leaf_ext = [(cell, par) for cell, par in frontier if degrees[par] == 1]
        branch_ext = [(cell, par) for cell, par in frontier if degrees[par] == 2]

        if leaf_ext and (not branch_ext or rng.random() < 0.78):
            straight = self._straight_extensions(leaf_ext, nodes_by_cell)
            if straight and rng.random() < 0.65:
                return rng.choice(straight)
            return rng.choice(leaf_ext)
        if branch_ext:
            return rng.choice(branch_ext)
        return rng.choice(frontier)

    @staticmethod
    def _straight_extensions(
        leaf_ext: list[tuple[tuple[int, int], tuple[int, int]]],
        nodes_by_cell: dict[tuple[int, int], TreeNode[tuple[int, int]]],
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        straight: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for cell, parent_cell in leaf_ext:
            grandparent_node = nodes_by_cell[parent_cell].parent
            if grandparent_node is None:
                continue
            gp = grandparent_node.value
            if (cell[0] - parent_cell[0], cell[1] - parent_cell[1]) == (
                parent_cell[0] - gp[0],
                parent_cell[1] - gp[1],
            ):
                straight.append((cell, parent_cell))
        return straight




class GeneralTerrainStrategy(TerrainStrategy):

    def generate(
        self,
        rows: int,
        cols: int,
        target: int,
        low: int,
        high: int,
        attempts: int,
        rng: random.Random,
    ) -> set[tuple[int, int]]:

        target = rng.randint(low, high)
        target = min(target, rows * cols)

        region = set()

        # Start at a random tile
        start_row = rng.randrange(rows)
        start_col = rng.randrange(cols)
        region.add((start_row, start_col))

        # Expand the terrain
        while len(region) < target:
            frontier = []

            for row, col in region:
                neighbors = self.neighbors(row, col, rows, cols)

                for tile in neighbors:
                    if tile not in region and tile not in frontier:
                        frontier.append(tile)

            if not frontier:
                break

            region.add(rng.choice(frontier))

        return region

class TerrainGenerator:
    def __init__(self) -> None:
        self.__strategies: dict[TerrainTopology, TerrainStrategy] = {
            TerrainTopology.STRAIGHT_PATH: StraightPathStrategy(),
            TerrainTopology.BENT_PATH: BentPathStrategy(),
            TerrainTopology.BRANCHING_TREE: BranchingTreeStrategy(),
            TerrainTopology.GENERAL: GeneralTerrainStrategy(),
        }

    def generate_terrain(self, specification: TerrainGenerationSpec, seed: int) -> Terrain:
        low, high = self._resolve_tile_bounds(specification)
        rng = random.Random(seed)
        strategy = self.__strategies[specification.topology]
        open_tiles = strategy.generate(
            specification.rows,
            specification.columns,
            low,
            high,
            specification.max_attempts,
            rng,
        )
        return self._build_terrain(specification.rows, specification.columns, open_tiles)

    def _resolve_tile_bounds(self, specification: TerrainGenerationSpec) -> tuple[int, int]:
        rows = specification.rows
        cols = specification.columns
        topology = specification.topology

        if topology == TerrainTopology.STRAIGHT_PATH and max(rows, cols) < 2:
            raise GenerationFailure("TerrainGenerator", "STRAIGHT_PATH requires at least 2 cells along one axis.")
        if topology == TerrainTopology.BENT_PATH and (rows < 2 or cols < 2):
            raise GenerationFailure("TerrainGenerator", "BENT_PATH requires at least a 2x2 grid.")
        if topology == TerrainTopology.BRANCHING_TREE and (rows < 2 or cols < 2 or rows * cols < 5):
            raise GenerationFailure("TerrainGenerator", "BRANCHING_TREE requires at least a 2x3 or 3x2 grid.")

        min_by_topology = {
            TerrainTopology.STRAIGHT_PATH: 2,
            TerrainTopology.BENT_PATH: 3,
            TerrainTopology.BRANCHING_TREE: 4,
            TerrainTopology.GENERAL: 1,
        }
        capacity_by_topology = {
            TerrainTopology.STRAIGHT_PATH: max(rows, cols),
            TerrainTopology.BENT_PATH: rows * cols - 1,
            TerrainTopology.BRANCHING_TREE: rows * cols,
            TerrainTopology.GENERAL: rows * cols,
        }

        low = max(specification.min_open_tiles, min_by_topology[topology])
        high = min(specification.max_open_tiles, capacity_by_topology[topology])
        if low > high:
            raise GenerationFailure("TerrainGenerator", "Open-tile bounds cannot satisfy topology requirements.")
        return low, high

    @staticmethod
    def _build_terrain(rows: int, cols: int, open_tiles: set[tuple[int, int]]) -> Terrain:
        terrain_rows = tuple(
            "".join("." if (r, c) in open_tiles else "#" for c in range(cols))
            for r in range(rows)
        )
        return Terrain(terrain_rows)
