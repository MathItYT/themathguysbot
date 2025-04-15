import manim


class TitleAnimation(manim.Animation):
    def __init__(self, mobject: manim.Mobject, angle: float = -manim.PI / 3, shift_down: float = 0.7, **kwargs):
        if kwargs.get("lag_ratio") is None:
            kwargs["lag_ratio"] = 0.2
        if kwargs.get("rate_func") is None:
            kwargs["rate_func"] = manim.linear
        self.angle = angle
        self.shift_down = shift_down
        super().__init__(mobject, **kwargs)

    def interpolate_submobject(self, submobject: manim.Mobject, starting_submobject: manim.Mobject, alpha: float):
        if alpha == 0:
            submobject.become(manim.VMobject())
            return
        submobject.become(starting_submobject)
        center = submobject.get_center()
        submobject.scale_to_fit_height(manim.interpolate(0, starting_submobject.height, manim.rate_functions.ease_out_back(alpha)))
        submobject.rotate(manim.interpolate(self.angle, 0, manim.rate_functions.ease_out_back(alpha)))
        submobject.move_to(center + manim.interpolate(self.shift_down * manim.DOWN, manim.ORIGIN, manim.rate_functions.ease_out_back(alpha)))