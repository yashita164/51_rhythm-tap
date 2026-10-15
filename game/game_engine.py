
import math
import random
from array import array

import pygame

from game.beat import (
    Note,
    LANES,
    LANE_KEYS,
    LANE_LABELS,
    LANE_COLORS,
)

WIDTH, HEIGHT = 480, 640
FPS = 60
HIT_Y = HEIGHT - 80
HIT_WINDOW = 30
BG = (15, 10, 25)
LANE_W = WIDTH // LANES

# BPM-synchronized spawning
INITIAL_BPM = 120
MAX_BPM = 180
BPM_STEP = 5
DIFFICULTY_INTERVAL = 10.0

INITIAL_SPEED = 300.0
HOLD_CHANCE = 0.20


class GameEngine:
    def __init__(self):
        pygame.init()

        self.audio_available = False
        self.sounds = {}

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(
                    frequency=22050,
                    size=-16,
                    channels=1,
                    buffer=512,
                )

            self.audio_available = True
            self.create_hit_sounds()

            print("Audio initialized:", pygame.mixer.get_init())
            print("Loaded hit sounds:", list(self.sounds.keys()))

        except pygame.error as error:
            self.audio_available = False
            print("Audio initialization failed:", error)

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Rhythm Tap")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 26, bold=True)
        self.big_font = pygame.font.SysFont("monospace", 40, bold=True)
        self.small_font = pygame.font.SysFont("monospace", 19, bold=True)

        self.keys_down = set()
        self.reset()

    # ---------------------------------------------------------
    # TASK 1: HIT SOUND EFFECTS
    # ---------------------------------------------------------

    def create_hit_sounds(self):
        """Generate hit sounds without external audio files."""
        sample_rate = 22050

        sound_settings = {
            "PERFECT": (880, 0.10),
            "GREAT": (660, 0.12),
            "OK": (440, 0.14),
        }

        self.sounds.clear()

        for grade, (frequency, duration) in sound_settings.items():
            sample_count = int(sample_rate * duration)
            samples = array("h")

            for i in range(sample_count):
                t = i / sample_rate

                attack = min(1.0, t / 0.008)
                release = min(1.0, (duration - t) / 0.025)
                envelope = max(0.0, min(attack, release))

                amplitude = 10000 * envelope
                value = int(
                    amplitude * math.sin(2 * math.pi * frequency * t)
                )
                samples.append(value)

            try:
                self.sounds[grade] = pygame.mixer.Sound(
                    buffer=samples.tobytes()
                )
                self.sounds[grade].set_volume(1.0)

            except pygame.error as error:
                self.sounds.clear()
                self.audio_available = False
                print(f"Could not create {grade} sound:", error)
                return

        print("Loaded hit sounds:", list(self.sounds.keys()))

    def play_hit_sound(self, grade):
        """Play the sound associated with a successful hit."""
        sound = self.sounds.get(grade)

        print(
            f"Playing sound: {grade} | "
            f"Audio available: {self.audio_available} | "
            f"Sound found: {sound is not None}"
        )

        if sound is not None:
            try:
                sound.set_volume(1.0)
                channel = sound.play()

                if channel is None:
                    print("Warning: no audio channel available.")

            except pygame.error as error:
                print("Sound playback error:", error)

    # ---------------------------------------------------------
    # INITIALIZATION AND RESET
    # ---------------------------------------------------------

    def reset(self):
        self.notes = []

        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.misses = 0

        # Task 4: Track each judgment.
        self.grade_counts = {
            "PERFECT": 0,
            "GREAT": 0,
            "OK": 0,
            "MISS": 0,
        }

        # Task 3: BPM scheduling.
        self.bpm = INITIAL_BPM
        self.beat_interval = 60.0 / self.bpm
        self.beat_timer = 0.0

        self.speed = INITIAL_SPEED
        self.elapsed_time = 0.0
        self.difficulty_elapsed = 0.0

        # Feedback entries: [text, color, ttl, x, y].
        self.feedback = []
        self.game_over = False
        self.keys_down = set()

    # ---------------------------------------------------------
    # TASK 3: BPM-SYNCHRONIZED NOTE SPAWNING
    # ---------------------------------------------------------

    def spawn_note(self):
        """Spawn one note on the current beat."""
        lane = random.randint(0, LANES - 1)
        is_hold = random.random() < HOLD_CHANCE

        self.notes.append(
            Note(
                lane,
                y=-30,
                speed=self.speed,
                is_hold=is_hold,
            )
        )

    def update_bpm(self, dt):
        """Increase difficulty at regular time intervals."""
        self.difficulty_elapsed += dt

        while self.difficulty_elapsed >= DIFFICULTY_INTERVAL:
            self.difficulty_elapsed -= DIFFICULTY_INTERVAL

            self.speed = min(600.0, self.speed + 30.0)
            self.bpm = min(MAX_BPM, self.bpm + BPM_STEP)
            self.beat_interval = 60.0 / self.bpm

    # ---------------------------------------------------------
    # INPUT HANDLING
    # ---------------------------------------------------------

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self.reset()
                    continue

                if self.game_over:
                    continue

                if event.key in LANE_KEYS:
                    if event.key in self.keys_down:
                        continue

                    self.keys_down.add(event.key)
                    lane = LANE_KEYS.index(event.key)
                    self.process_tap(lane, event.key)

            elif event.type == pygame.KEYUP:
                if event.key in self.keys_down:
                    self.keys_down.remove(event.key)
                    self.handle_key_release(event.key)

        return True

    # ---------------------------------------------------------
    # JUDGMENT AND SCORING
    # ---------------------------------------------------------

    def get_grade(self, distance):
        if distance < 8:
            return "PERFECT", 300, (255, 220, 0)

        if distance < 18:
            return "GREAT", 200, (100, 220, 100)

        return "OK", 100, (180, 180, 255)

    def add_feedback(self, text, color, lane):
        lane_x = lane * LANE_W + LANE_W // 2

        self.feedback.append(
            [text, color, 40, lane_x, HIT_Y - 30]
        )

    def register_miss(self, lane, note=None):
        """Register a miss once for the supplied note or failed tap."""
        if note is not None:
            if note.hit or note.missed:
                return

            note.missed = True
            note.holding = False
            note.hold_key = None

        self.misses += 1
        self.grade_counts["MISS"] += 1
        self.combo = 0

        self.add_feedback("MISS", (220, 60, 60), lane)

    def award_hit(self, grade, points, color, lane):
        """Record a successful note and award points."""
        self.grade_counts[grade] += 1

        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)

        multiplier = max(1, self.combo // 5)
        self.score += points * multiplier

        self.add_feedback(grade, color, lane)
        self.play_hit_sound(grade)

    def process_tap(self, lane, key):
        if self.game_over:
            return

        best_note = None
        best_distance = float("inf")

        for note in self.notes:
            if note.hit or note.missed or note.holding:
                continue

            if note.lane != lane:
                continue

            head_center = note.y + Note.HEIGHT / 2
            distance = abs(head_center - HIT_Y)

            if distance < best_distance:
                best_distance = distance
                best_note = note

        if best_note is None or best_distance > HIT_WINDOW:
            self.register_miss(lane)
            return

        grade, points, color = self.get_grade(best_distance)

        if best_note.is_hold:
            # Hold notes are graded when their full hold is completed.
            best_note.holding = True
            best_note.hold_key = key
            best_note.hold_grade = grade
            best_note.hold_points = points
            best_note.hold_color = color

            self.add_feedback("HOLD", (255, 255, 255), lane)

        else:
            best_note.hit = True
            self.award_hit(grade, points, color, lane)

    # ---------------------------------------------------------
    # TASK 2: HOLD NOTES
    # ---------------------------------------------------------

    def complete_hold(self, note):
        if note.hit or note.missed or not note.holding:
            return

        note.hit = True
        note.holding = False
        note.hold_key = None

        self.award_hit(
            note.hold_grade,
            note.hold_points,
            note.hold_color,
            note.lane,
        )

    def handle_key_release(self, key):
        for note in self.notes:
            if (
                note.is_hold
                and note.holding
                and note.hold_key == key
                and not note.hit
                and not note.missed
            ):
                tail_center = (
                    note.y
                    - note.hold_length
                    + Note.HEIGHT / 2
                )

                if tail_center >= HIT_Y:
                    self.complete_hold(note)
                else:
                    self.register_miss(note.lane, note)

                break

    # ---------------------------------------------------------
    # GAME UPDATE
    # ---------------------------------------------------------

    def update(self, dt):
        if self.game_over:
            return

        # Prevent extreme frame-time jumps.
        dt = max(0.0, min(dt, 0.1))

        self.elapsed_time += dt

        # Update difficulty independently of spawning.
        self.update_bpm(dt)

        # Spawn notes at BPM intervals.
        self.beat_timer += dt

        while self.beat_timer >= self.beat_interval:
            self.beat_timer -= self.beat_interval
            self.spawn_note()

        for note in self.notes:
            if note.hit or note.missed:
                continue

            note.update(dt)

            if note.is_hold and note.holding:
                if note.hold_key not in self.keys_down:
                    self.register_miss(note.lane, note)
                    continue

                tail_center = (
                    note.y
                    - note.hold_length
                    + Note.HEIGHT / 2
                )

                if tail_center >= HIT_Y:
                    self.complete_hold(note)

            elif (
                note.y + Note.HEIGHT / 2
                > HIT_Y + HIT_WINDOW
            ):
                self.register_miss(note.lane, note)

        # Remove completed notes.
        self.notes = [
            note
            for note in self.notes
            if not note.hit and not note.missed
        ]

        self.feedback = [
            [text, color, ttl - 1, x, y]
            for text, color, ttl, x, y in self.feedback
            if ttl > 1
        ]

        if self.misses >= 15:
            self.game_over = True

    # ---------------------------------------------------------
    # TASK 4: GRADE SUMMARY AND ACCURACY
    # ---------------------------------------------------------

    def calculate_accuracy(self):
        """
        Grade-weighted accuracy:
        PERFECT = 300, GREAT = 200, OK = 100, MISS = 0.
        Combo multipliers do not affect accuracy.
        """
        total_judgments = sum(self.grade_counts.values())

        if total_judgments == 0:
            return 0.0

        weighted_points = (
            self.grade_counts["PERFECT"] * 300
            + self.grade_counts["GREAT"] * 200
            + self.grade_counts["OK"] * 100
        )

        maximum_points = total_judgments * 300

        return (weighted_points / maximum_points) * 100.0

    def draw_centered_text(self, text, font, color, y):
        surface = font.render(text, True, color)

        self.screen.blit(
            surface,
            (WIDTH // 2 - surface.get_width() // 2, y),
        )

    def draw_grade_summary(self):
        """Display final score, judgment counts, and accuracy."""
        overlay = pygame.Surface(
            (WIDTH, HEIGHT),
            pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 220))
        self.screen.blit(overlay, (0, 0))

        self.draw_centered_text(
            "GAME OVER",
            self.big_font,
            (255, 90, 90),
            55,
        )

        self.draw_centered_text(
            f"Final Score: {self.score}",
            self.font,
            (240, 240, 240),
            115,
        )

        self.draw_centered_text(
            "GRADE SUMMARY",
            self.small_font,
            (180, 180, 220),
            165,
        )

        summary_rows = [
            ("PERFECT", (255, 220, 0)),
            ("GREAT", (100, 220, 100)),
            ("OK", (180, 180, 255)),
            ("MISS", (220, 80, 80)),
        ]

        for index, (grade, color) in enumerate(summary_rows):
            y = 205 + index * 42

            label = self.small_font.render(
                grade,
                True,
                color,
            )

            count = self.small_font.render(
                str(self.grade_counts[grade]),
                True,
                (240, 240, 240),
            )

            self.screen.blit(label, (95, y))
            self.screen.blit(
                count,
                (WIDTH - 95 - count.get_width(), y),
            )

        accuracy = self.calculate_accuracy()

        self.draw_centered_text(
            f"Accuracy: {accuracy:.2f}%",
            self.font,
            (100, 220, 220),
            390,
        )

        self.draw_centered_text(
            f"Max Combo: {self.max_combo}x",
            self.small_font,
            (255, 220, 80),
            435,
        )

        self.draw_centered_text(
            f"Final BPM: {self.bpm}",
            self.small_font,
            (200, 200, 200),
            468,
        )

        self.draw_centered_text(
            "Press R to Restart",
            self.small_font,
            (180, 180, 180),
            530,
        )

    # ---------------------------------------------------------
    # RENDERING
    # ---------------------------------------------------------

    def draw(self):
        self.screen.fill(BG)

        # Lane dividers.
        for i in range(LANES + 1):
            pygame.draw.line(
                self.screen,
                (40, 40, 60),
                (i * LANE_W, 0),
                (i * LANE_W, HEIGHT),
                1,
            )

        # Hit line.
        pygame.draw.line(
            self.screen,
            (80, 80, 100),
            (0, HIT_Y),
            (WIDTH, HIT_Y),
            2,
        )

        # Lane pads and key labels.
        for i in range(LANES):
            lane_x = i * LANE_W + LANE_W // 2

            pygame.draw.rect(
                self.screen,
                LANE_COLORS[i],
                pygame.Rect(
                    lane_x - Note.WIDTH // 2,
                    HIT_Y - 12,
                    Note.WIDTH,
                    24,
                ),
                border_radius=6,
            )

            label = self.font.render(
                LANE_LABELS[i],
                True,
                (20, 20, 20),
            )

            self.screen.blit(
                label,
                (
                    lane_x - label.get_width() // 2,
                    HIT_Y - 10,
                ),
            )

        # Draw hold bodies and note heads.
        for note in self.notes:
            if note.hit or note.missed:
                continue

            lane_x = note.lane * LANE_W + LANE_W // 2
            color = LANE_COLORS[note.lane]

            if note.is_hold:
                body_rect = note.get_hold_rect(lane_x)

                body_color = tuple(
                    max(0, int(channel * 0.55))
                    for channel in color
                )

                pygame.draw.rect(
                    self.screen,
                    body_color,
                    body_rect,
                    border_radius=5,
                )

                pygame.draw.rect(
                    self.screen,
                    color,
                    body_rect,
                    width=2,
                    border_radius=5,
                )

            head_rect = note.get_rect(lane_x)

            pygame.draw.rect(
                self.screen,
                color,
                head_rect,
                border_radius=5,
            )

            if note.is_hold and note.holding:
                pygame.draw.rect(
                    self.screen,
                    (255, 255, 255),
                    head_rect,
                    width=2,
                    border_radius=5,
                )

        # Hit feedback.
        for text, color, ttl, x, y in self.feedback:
            surface = self.font.render(text, True, color)
            surface.set_alpha(min(255, ttl * 7))

            self.screen.blit(
                surface,
                (x - surface.get_width() // 2, y),
            )

        # HUD.
        score_text = self.font.render(
            f"Score: {self.score}",
            True,
            (220, 220, 220),
        )

        combo_text = self.font.render(
            f"Combo: {self.combo}x",
            True,
            (255, 220, 80),
        )

        miss_text = self.font.render(
            f"Misses: {self.misses}/15",
            True,
            (220, 100, 100),
        )

        bpm_text = self.small_font.render(
            f"BPM: {self.bpm}",
            True,
            (180, 180, 220),
        )

        self.screen.blit(score_text, (10, 10))
        self.screen.blit(combo_text, (10, 40))

        self.screen.blit(
            miss_text,
            (WIDTH - miss_text.get_width() - 10, 10),
        )

        self.screen.blit(bpm_text, (10, 72))

        if self.game_over:
            self.draw_grade_summary()

        pygame.display.flip()

    # ---------------------------------------------------------
    # MAIN LOOP
    # ---------------------------------------------------------

    def run(self):
        running = True

        while running:
            dt = self.clock.tick(FPS) / 1000.0

            running = self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
