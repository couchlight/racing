"""On-screen display, drawn with pygame at the renderer's internal resolution."""

import math

import pygame

from game import race as race_rules

WHITE = (255, 255, 255)
YELLOW = (255, 220, 40)
RED = (255, 60, 40)
SHADOW = (0, 0, 0)
LOW_TIME = 10.0     # the timer turns red below this many seconds
MARGIN = 6


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}TH"
    return f"{n}{ {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH') }"


class Hud:
    def __init__(self, size):
        self.width, self.height = size
        self.surface = pygame.Surface(size, pygame.SRCALPHA)
        self.small = pygame.font.Font(None, 14)
        self.medium = pygame.font.Font(None, 22)
        self.large = pygame.font.Font(None, 38)

    def _text(self, font, text, color, **anchor):
        """Draw text with a 1-pixel shadow. `anchor` is a pygame Rect keyword,
        e.g. topleft=(x, y). Returns the text's rect."""
        image = font.render(text, False, color)
        rect = image.get_rect(**anchor)
        self.surface.blit(font.render(text, False, SHADOW), rect.move(1, 1))
        self.surface.blit(image, rect)
        return rect

    def draw(self, race):
        """Redraw for the current race state and return RGBA bytes, bottom row first."""
        w, h = self.width, self.height
        self.surface.fill((0, 0, 0, 0))

        # Position, top left
        self._text(self.small, "POS", YELLOW, topleft=(MARGIN, MARGIN))
        rect = self._text(self.large, str(race.position), WHITE, topleft=(MARGIN, MARGIN + 9))
        self._text(self.medium, f"/{race.car_count}", WHITE, bottomleft=(rect.right + 1, rect.bottom - 3))

        # Countdown timer, top centre
        self._text(self.small, "TIME", YELLOW, midtop=(w // 2, MARGIN))
        low = race.time_left < LOW_TIME
        self._text(self.large, str(int(math.ceil(race.time_left))),
                   RED if low else WHITE, midtop=(w // 2, MARGIN + 9))

        # Lap, top right
        self._text(self.small, "LAP", YELLOW, topright=(w - MARGIN, MARGIN))
        self._text(self.medium, f"{race.lap}/{race.laps}", WHITE, topright=(w - MARGIN, MARGIN + 11))

        # Gear, bottom left
        self._text(self.small, "GEAR", YELLOW, bottomleft=(MARGIN, h - MARGIN - 26))
        self._text(self.large, race.player.gear_label, WHITE, bottomleft=(MARGIN, h - MARGIN + 4))

        # Speed, bottom right
        rect = self._text(self.small, "km/h", YELLOW, bottomright=(w - MARGIN, h - MARGIN))
        self._text(self.large, str(int(race.player.speed_kmh)), WHITE,
                   bottomright=(rect.left - 3, h - MARGIN + 4))

        # Centre message
        center = (w // 2, h // 2 - 30)
        if race.state == race_rules.COUNTDOWN:
            self._text(self.large, str(race.countdown_number), YELLOW, center=center)
        elif race.state == race_rules.TIME_UP:
            self._text(self.large, "GAME OVER", RED, center=center)
        elif race.state == race_rules.FINISHED:
            self._text(self.large, "FINISH", YELLOW, center=center)
            self._text(self.medium, _ordinal(race.position), WHITE,
                       center=(center[0], center[1] + 26))
        elif race.message:
            self._text(self.large, race.message, YELLOW, center=center)

        if race.state in (race_rules.TIME_UP, race_rules.FINISHED):
            self._text(self.small, "ENTER / START TO RESTART", WHITE,
                       center=(w // 2, h // 2 + 30))

        return pygame.image.tobytes(self.surface, "RGBA", True)
