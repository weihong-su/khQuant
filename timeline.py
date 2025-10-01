# -*- coding: utf-8 -*-
from manim import *
from datetime import datetime

# 输出为绿幕，方便在剪映里色度键抠像；如需透明背景，渲染时加 --transparent true 并用 mov 格式
config.background_color = "#00FF00"
config.pixel_width = 3840
config.pixel_height = 2160
config.frame_rate = 30


def to_minutes(hhmm: str) -> int:
    dt = datetime.strptime(hhmm, "%H:%M")
    return dt.hour * 60 + dt.minute


# 可按需修改节点
NODES = [
    ("09:15", "集合竞价预备"),
    ("09:20", "集合竞价"),
    ("09:25", "开盘静默"),
    ("09:30", "开盘"),
    ("11:30", "午休"),
    ("13:00", "复盘开市"),
    ("14:57", "收盘竞价"),
    ("15:00", "收盘"),
]


class TradingDayTimeline(Scene):
    def construct(self) -> None:
        # 将时间映射到 [0, 1]
        start_min, end_min = to_minutes(NODES[0][0]), to_minutes(NODES[-1][0])
        xs = [(to_minutes(t) - start_min) / (end_min - start_min) for t, _ in NODES]

        # 底线
        axis_width = 12.0
        base_line = Line(LEFT * axis_width / 2, RIGHT * axis_width / 2,
                         color=GRAY_D, stroke_width=14).shift(DOWN * 1)
        self.add(base_line)

        # 进度与游标
        progress = ValueTracker(0.0)

        def progress_len() -> float:
            return max(0.001, progress.get_value() * axis_width)

        progress_bar = always_redraw(
            lambda: Rectangle(width=progress_len(), height=0.28,
                              color=BLUE_D, fill_color=BLUE_D, fill_opacity=1)
            .set_stroke(width=0)
            .align_to(base_line, LEFT)
            .shift(UP * 0.01)
        )

        cursor = always_redraw(
            lambda: Dot(point=base_line.get_start() + RIGHT * progress_len(),
                        radius=0.10, color=YELLOW).set_z_index(10)
        )

        self.add(progress_bar, cursor)

        # 刻度与标签
        ticks, labels = [], []
        for x, (tm, name) in zip(xs, NODES):
            tick = Line(UP * 0.35, DOWN * 0.35, color=WHITE, stroke_width=4)
            # 将刻度移动到底线的相应比例位置
            tick.move_to(base_line.point_from_proportion(x)).set_opacity(0)
            txt = VGroup(
                Text(tm, weight=BOLD, font_size=36),
                Text(name, font_size=36, color=WHITE),
            ).arrange(DOWN, buff=0.12).next_to(tick, UP, buff=0.26).set_opacity(0)
            ticks.append(tick)
            labels.append(txt)
            self.add(tick, txt)

        # 总时长（秒）可按需调整
        total_seconds = 12.0
        segments = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        min_seg = 0.35
        # 线性分配：保证每段最短停留，剩余按比例分配
        raw_sum = sum(segments) if sum(segments) > 1e-6 else 1.0
        scale = (total_seconds - min_seg * len(segments)) / raw_sum
        durations = [min_seg + seg * scale for seg in segments]

        # 入场
        self.play(FadeIn(base_line, shift=UP * 0.2), run_time=0.5)
        self.play(progress.animate.set_value(xs[0]), run_time=0.4, rate_func=smooth)
        self.play(ticks[0].animate.set_opacity(1), labels[0].animate.set_opacity(1), run_time=0.3)

        # 推进并在节点处显现标签
        for i, dur in enumerate(durations):
            self.play(progress.animate.set_value(xs[i + 1]), run_time=dur, rate_func=smooth)
            self.play(ticks[i + 1].animate.set_opacity(1), labels[i + 1].animate.set_opacity(1), run_time=0.25)

        self.wait(0.4)

