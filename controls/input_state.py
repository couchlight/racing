from dataclasses import dataclass

import pygame

from controls.controller import GameController


@dataclass(frozen=True)
class InputState:
    steer: float = 0.0              # -1 (full left) .. 1 (full right)
    throttle: float = 0.0           # 0 .. 1
    brake: float = 0.0              # 0 .. 1
    buttons: frozenset = frozenset()  # held gamepad buttons, e.g. 'button_a'


class InputManager:
    """Merges the gamepad with the keyboard fallback into one InputState.

    Gamepad:  left stick = steer, RT = throttle, LT = brake.
    Keyboard: arrows or WASD.
    """

    def __init__(self):
        self.controller = GameController()

    def poll(self):
        """Call once per frame, after pygame.event.get()."""
        pad = self.controller
        pad.poll()

        keys = pygame.key.get_pressed()
        key_steer = (float(keys[pygame.K_RIGHT] or keys[pygame.K_d])
                     - float(keys[pygame.K_LEFT] or keys[pygame.K_a]))
        key_throttle = float(keys[pygame.K_UP] or keys[pygame.K_w])
        key_brake = float(keys[pygame.K_DOWN] or keys[pygame.K_s])

        return InputState(
            steer=pad.stick_x if abs(pad.stick_x) > abs(key_steer) else key_steer,
            throttle=max(pad.right_trigger, key_throttle),
            brake=max(pad.left_trigger, key_brake),
            buttons=pad.buttons,
        )
