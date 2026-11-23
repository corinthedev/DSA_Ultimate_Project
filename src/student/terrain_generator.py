"""Generate canonical terrain deterministically from specification and seed."""
import random
from itertools import product

from src.api import GenerationFailure, Terrain, TerrainGenerationSpec, TerrainTopology


class TerrainGenerator:
    """Keep state local; identical inputs must also agree across fresh instances."""

    _DIRECTIONS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

    def __init__(self) -> None:
        pass

    def generate_terrain(self, specification: TerrainGenerationSpec, seed: int) -> Terrain:
        low, high = self._resolve_tile_bounds(specification)
        rng = random.Random(seed)
        rows, cols = specification.rows, specification.columns

        match specification.topology:
            case TerrainTopology.STRAIGHT_PATH:
                open_tiles = self._generate_straight_path(rows, cols, low, high, rng)
            case TerrainTopology.BENT_PATH:
                open_tiles = self._generate_bent_path(rows, cols, low, high, specification.max_attempts, rng)
            case TerrainTopology.BRANCHING_TREE:
                open_tiles = self._generate_branching_tree(rows, cols, low, high, specification.max_attempts, rng)
            case TerrainTopology.GENERAL:
                open_tiles = self._generate_general_terrain(rows, cols, low, high, rng)

        return self._build_terrain(rows, cols, open_tiles)

    def _resolve_tile_bounds(self, specification: TerrainGenerationSpec) -> tuple[int, int]:
        rows, cols = specification.rows, specification.columns
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

    def _neighbors(self, row: int, col: int, rows: int, cols: int) -> list[tuple[int, int]]:
        return [
            (row + dr, col + dc)
            for dr, dc in self._DIRECTIONS
            if 0 <= row + dr < rows and 0 <= col + dc < cols
        ]

    # ------------------------------------------------------------------
    # Straight path
    # ------------------------------------------------------------------

    def _generate_straight_path(
        self, rows: int, cols: int, low: int, high: int, rng: random.Random
    ) -> set[tuple[int, int]]:
        target = rng.randint(low, high)
        candidates: list[set[tuple[int, int]]] = []

        if target <= cols:
            for r in range(rows):
                for c_start in range(cols - target + 1):
                    candidates.append({(r, c_start + offset) for offset in range(target)})

        if target <= rows:
            for c in range(cols):
                for r_start in range(rows - target + 1):
                    candidates.append({(r_start + offset, c) for offset in range(target)})

        if not candidates:
            raise GenerationFailure("TerrainGenerator", "No straight path fits the specification.")
        return rng.choice(candidates)

    # ------------------------------------------------------------------
    # Bent path
    # ------------------------------------------------------------------

    def _generate_bent_path(
        self, rows: int, cols: int, low: int, high: int, attempts: int, rng: random.Random
    ) -> set[tuple[int, int]]:
        for _ in range(attempts):
            target = rng.randint(low, high)
            tiles = self._try_random_bent_path(rows, cols, target, rng)
            if tiles is not None:
                return tiles
        return self._fallback_bent_path(rows, cols, low, high, rng)

    def _try_random_bent_path(
        self, rows: int, cols: int, target: int, rng: random.Random
    ) -> set[tuple[int, int]] | None:
        path: list[tuple[int, int]] = [(rng.randrange(rows), rng.randrange(cols))]
        visited: set[tuple[int, int]] = set(path)

        for _ in range(target - 1):
            cur_r, cur_c = path[-1]
            earlier = visited - {path[-1]}
            valid_steps = [
                nbr
                for nbr in self._neighbors(cur_r, cur_c, rows, cols)
                if nbr not in visited and not any(adj in earlier for adj in self._neighbors(*nbr, rows, cols))
            ]
            if not valid_steps:
                return None
            step = rng.choice(valid_steps)
            path.append(step)
            visited.add(step)

        has_bend = len({r for r, _ in path}) > 1 and len({c for _, c in path}) > 1
        return visited if has_bend else None

    def _fallback_bent_path(
        self, rows: int, cols: int, low: int, high: int, rng: random.Random
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

    # ------------------------------------------------------------------
    # Branching tree
    # ------------------------------------------------------------------

    def _generate_branching_tree(
        self, rows: int, cols: int, low: int, high: int, attempts: int, rng: random.Random
    ) -> set[tuple[int, int]]:
        hub_pool = self._tree_hub_pool(rows, cols)

        for _ in range(max(attempts, 12)):
            target = rng.randint(low, high)
            hub = rng.choice(hub_pool)
            hub_nbrs = self._neighbors(*hub, rows, cols)
            rng.shuffle(hub_nbrs)

            tree: set[tuple[int, int]] = {hub, *hub_nbrs[:3]}
            parent_of: dict[tuple[int, int], tuple[int, int]] = {nbr: hub for nbr in hub_nbrs[:3]}

            while len(tree) < target:
                choice = self._pick_tree_frontier_cell(tree, parent_of, rows, cols, rng)
                if choice is None:
                    break
                cell, parent = choice
                tree.add(cell)
                parent_of[cell] = parent

            has_branch = any(
                sum(1 for nbr in self._neighbors(*cell, rows, cols) if nbr in tree) >= 3
                for cell in tree
            )
            if len(tree) == target and has_branch:
                return tree

        raise GenerationFailure("TerrainGenerator", "Unable to construct a valid BRANCHING_TREE.")

    def _tree_hub_pool(self, rows: int, cols: int) -> list[tuple[int, int]]:
        hubs = [
            (r, c)
            for r, c in product(range(rows), range(cols))
            if len(self._neighbors(r, c, rows, cols)) >= 3
        ]
        interior = [cell for cell in hubs if len(self._neighbors(*cell, rows, cols)) == 4]
        return interior or hubs

    def _pick_tree_frontier_cell(
        self,
        tree: set[tuple[int, int]],
        parent_of: dict[tuple[int, int], tuple[int, int]],
        rows: int,
        cols: int,
        rng: random.Random,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        frontier: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for r, c in product(range(rows), range(cols)):
            if (r, c) in tree:
                continue
            touching = [nbr for nbr in self._neighbors(r, c, rows, cols) if nbr in tree]
            if len(touching) == 1:
                frontier.append(((r, c), touching[0]))

        if not frontier:
            return None

        degrees = {
            cell: sum(1 for nbr in self._neighbors(*cell, rows, cols) if nbr in tree)
            for cell in tree
        }
        leaf_ext = [(cell, par) for cell, par in frontier if degrees[par] == 1]
        branch_ext = [(cell, par) for cell, par in frontier if degrees[par] == 2]

        if leaf_ext and (not branch_ext or rng.random() < 0.78):
            straight = [
                (cell, par)
                for cell, par in leaf_ext
                if par in parent_of
                and (cell[0] - par[0], cell[1] - par[1]) == (par[0] - parent_of[par][0], par[1] - parent_of[par][1])
            ]
            return rng.choice(straight if straight and rng.random() < 0.65 else leaf_ext)
        if branch_ext:
            return rng.choice(branch_ext)
        return rng.choice(frontier)

    # ------------------------------------------------------------------
    # General terrain
    # ------------------------------------------------------------------

    def _generate_general_terrain(
        self, rows: int, cols: int, low: int, high: int, rng: random.Random
    ) -> set[tuple[int, int]]:
        target = rng.randint(low, high)
        region: set[tuple[int, int]] = set()
        reserved: set[tuple[int, int]] = set()

        if rows >= 2 and cols >= 2 and target >= 4:
            main_ring = self._pick_main_ring(rows, cols, target, rng)
            region |= self._ring_cells(*main_ring)
            reserved |= self._interior_cells(*main_ring)
            if rows >= 3 and cols >= 3:
                self._add_extra_loops(region, reserved, rows, cols, target, rng)
        else:
            region.add((rng.randrange(rows), rng.randrange(cols)))

        self._expand_region(region, reserved, rows, cols, target, rng)
        return region

    @staticmethod
    def _ring_cells(top: int, left: int, height: int, width: int) -> set[tuple[int, int]]:
        bottom, right = top + height - 1, left + width - 1
        return (
            {(top, c) for c in range(left, right + 1)}
            | {(bottom, c) for c in range(left, right + 1)}
            | {(r, left) for r in range(top, bottom + 1)}
            | {(r, right) for r in range(top, bottom + 1)}
        )

    @staticmethod
    def _interior_cells(top: int, left: int, height: int, width: int) -> set[tuple[int, int]]:
        return {
            (r, c)
            for r in range(top + 1, top + height - 1)
            for c in range(left + 1, left + width - 1)
        }

    def _pick_main_ring(
        self, rows: int, cols: int, target: int, rng: random.Random
    ) -> tuple[int, int, int, int]:
        options = [
            (top, left, h, w)
            for h in range(2, rows + 1)
            for w in range(2, cols + 1)
            if 2 * (h + w) - 4 <= target
            for top in range(rows - h + 1)
            for left in range(cols - w + 1)
        ]
        holed = [opt for opt in options if opt[2] >= 3 and opt[3] >= 3]
        pool = holed or options

        largest = max(2 * (h + w) - 4 for _, _, h, w in pool)
        pool = [opt for opt in pool if 2 * (opt[2] + opt[3]) - 4 == largest]

        center_r, center_c = (rows - 1) / 2.0, (cols - 1) / 2.0

        def center_offset(opt: tuple[int, int, int, int]) -> float:
            t, l, h, w = opt
            return abs(t + (h - 1) / 2.0 - center_r) + abs(l + (w - 1) / 2.0 - center_c)

        min_offset = min(center_offset(opt) for opt in pool)
        centered = [opt for opt in pool if center_offset(opt) == min_offset]
        return rng.choice(centered)

    def _add_extra_loops(
        self,
        region: set[tuple[int, int]],
        reserved: set[tuple[int, int]],
        rows: int,
        cols: int,
        target: int,
        rng: random.Random,
    ) -> None:
        for _ in range(60):
            remaining = target - len(region)
            if remaining < 2:
                break
            height = rng.randint(3, rows)
            width = rng.randint(3, cols)
            top = rng.randrange(rows - height + 1)
            left = rng.randrange(cols - width + 1)

            loop = self._ring_cells(top, left, height, width)
            hole = self._interior_cells(top, left, height, width)
            new_cells = loop - region
            if (
                not new_cells
                or len(new_cells) > remaining
                or not (loop & region)
                or (new_cells & reserved)
                or hole <= region
            ):
                continue

            region |= loop
            reserved |= hole - region

    def _expand_region(
        self,
        region: set[tuple[int, int]],
        reserved: set[tuple[int, int]],
        rows: int,
        cols: int,
        target: int,
        rng: random.Random,
    ) -> None:
        while len(region) < target:
            frontier = sorted({
                nbr
                for r, c in region
                for nbr in self._neighbors(r, c, rows, cols)
                if nbr not in region
            })
            unreserved = [cell for cell in frontier if cell not in reserved]
            region.add(rng.choice(unreserved or frontier))

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _build_terrain(rows: int, cols: int, open_tiles: set[tuple[int, int]]) -> Terrain:
        terrain_rows = tuple(
            "".join("." if (r, c) in open_tiles else "#" for c in range(cols))
            for r in range(rows)
        )
        return Terrain(terrain_rows)
