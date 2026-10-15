import pygame

LANES = 4

LANE_KEYS = [
    pygame.K_d,
    pygame.K_f,
    pygame.K_j,
    pygame.K_k,
]

LANE_LABELS = ["D", "F", "J", "K"]

LANE_COLORS = [
    (255, 90, 120),
    (255, 190, 80),
    (90, 220, 160),
    (100, 160, 255),
]

HOLD_SECONDS = 1.0


class Note:
    WIDTH = 70
    HEIGHT = 20
    HOLD_SECONDS = HOLD_SECONDS

    def __init__(self, lane, y=-30, speed=300.0, is_hold=False):
        self.lane = lane
        self.y = float(y)
        self.speed = float(speed)
        self.is_hold = is_hold

        self.hold_length = (
            self.speed * self.HOLD_SECONDS if self.is_hold else 0.0
        )

        self.hit = False
        self.missed = False

        self.holding = False
        self.hold_key = None
        self.hold_grade = None
        self.hold_points = 0
        self.hold_color = None

    def update(self, dt):
        """Move the note using elapsed time in seconds."""
        self.y += self.speed * dt

    def get_rect(self, lane_x):
        """Return the note head rectangle."""
        return pygame.Rect(
            lane_x - self.WIDTH // 2,
            int(self.y),
            self.WIDTH,
            self.HEIGHT,
        )

    def get_hold_rect(self, lane_x):
        """Return the full hold-note rectangle."""
        if not self.is_hold:
            return self.get_rect(lane_x)

        return pygame.Rect(
            lane_x - self.WIDTH // 2,
            int(self.y - self.hold_length),
            self.WIDTH,
            int(self.hold_length + self.HEIGHT),
        )