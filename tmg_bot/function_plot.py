from manim import *
from typing import Callable, Tuple


def n_elements_from_range(range_: Tuple[float, float, float]) -> int:
    min_, max_, step = range_
    return round((max_ - min_) / step) + 1


class FunctionPlot(VMobject):
    def __init__(
        self,
        func: Callable[[float], tuple[float, float]],
        discontinuities: list[float] | None = None,
        t_domain: Tuple[float, float] = (-1.0, 1.0),
        x_range: Tuple[float, float, float] = (-1.0, 1.0, 0.2),
        y_range: Tuple[float, float, float] = (-1.0, 1.0, 0.2),
        min_depth: int = 8,
        max_depth: int = 14,
        threshold: float | None = None,
        **kwargs
    ) -> None:
        self.func = func
        self.discontinuities = discontinuities or []
        self.discontinuities.sort()
        self.t_domain = t_domain
        self.x_range = x_range
        self.y_range = y_range
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.threshold = threshold or 0.1 / (config.pixel_height / config.frame_height)
        self.previous_was_discontinuity: bool = False
        super().__init__(**kwargs)
        self.sample()
    
    def is_discontinuity(self, t: float) -> bool:
        for discontinuity in self.discontinuities:
            if np.isclose(t, discontinuity, atol=self.threshold):
                return True
        return False
    
    def sample(self) -> None:
        def subdivide(min_: float, max_: float, depth: int, p_min: tuple[float, float], p_max: tuple[float, float]) -> None:
            t = self.cheap_hash(min_, max_)
            mid = min_ + (max_ - min_) * t
            p_mid = self.func(mid)
            def deepen() -> None:
                subdivide(min_, mid, depth + 1, p_min, p_mid)
                if self.is_discontinuity(mid):
                    self.on_discontinuity(p_mid)
                else:
                    self.on_point(mid, p_mid)
                subdivide(mid, max_, depth + 1, p_mid, p_max)
            if depth < self.min_depth:
                deepen()
            elif depth < self.max_depth:
                fn_midpoint = np.array(p_min) + t * (np.array(p_max) - np.array(p_min))
                e = self.error_function(p_mid, fn_midpoint)
                if e > self.threshold:
                    deepen()
        min_, max_ = self.t_domain
        p_min = self.func(min_)
        p_max = self.func(max_)
        self.on_point(min_, p_min)
        subdivide(min_, max_, 0, p_min, p_max)
        self.on_point(max_, p_max)
    
    def on_point(self, t: float, p: tuple[float, float]) -> None:
        if self.right_bounds(p) and self.is_finite(p):
            if self.has_no_points() or self.previous_was_discontinuity:
                self.start_new_path(np.array([p[0], p[1], 0]))
                self.previous_was_discontinuity = False
            else:
                self.add_line_to(np.array([p[0], p[1], 0]))
    
    def on_discontinuity(self, p: tuple[float, float]) -> None:
        self.previous_was_discontinuity = True
    
    def is_finite(self, p: tuple[float, float]) -> bool:
        return all(np.isfinite(x) for x in p)
    
    def right_bounds(self, p: tuple[float, float]) -> bool:
        x, y = p
        return self.x_range[0] <= x <= self.x_range[1] and self.y_range[0] <= y <= self.y_range[1]

    def cheap_hash(self, min: float, max: float) -> float:
        result = np.sin(min * 12.9898 + max * 78.233) * 43758.5453
        return 0.4 + 0.2 * (result - np.floor(result))

    def error_function(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        ax, ay = a
        bx, by = b
        return (ax - bx) * (ax - bx) + (ay - by) * (ay - by)
