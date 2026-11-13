"""Gamepad reader, ported from TimeslotTV's controller.py.

Differences from the original: no background thread, no dummy SDL drivers and
no app callbacks. poll() is called once per frame from the main loop (after
the pygame event queue has been pumped) and leaves the current analog and
button state on the instance.
"""

import sys
import time

import pygame


class GameController:
    def __init__(self):
        self.controller = None
        self.controller_connected = False
        self.controller_type = None

        # Analog settings
        self.stick_deadzone = 0.1

        # Self-calibrating trigger rest point (see _normalize_trigger). Keyed
        # by 'left'/'right'; None until the axis has reported at least once.
        # Reset whenever the active controller changes.
        self._trigger_rest_observed = {'left': None, 'right': None}

        # Multi-joystick tracking: every attached joystick stays open so input
        # on a non-active one is noticed and the active controller switches
        # to it.
        self._candidates = []             # all opened pygame Joystick objects
        self._last_joystick_count = -1    # forces enumeration on first poll
        self._last_activity_scan = 0.0    # throttle for the candidate scan

        # D-pad mappings (hat)
        self.dpad_mappings = {
            (0, 1): 'dpad_up',
            (0, -1): 'dpad_down',
            (-1, 0): 'dpad_left',
            (1, 0): 'dpad_right',
        }
        self.button_mappings = {}

        # State as of the last poll()
        self.stick_x = 0.0          # left stick X, -1..1, deadzone applied
        self.left_trigger = 0.0     # 0..1
        self.right_trigger = 0.0    # 0..1
        self.buttons = frozenset()  # logical names currently held

        pygame.joystick.init()

        # Get platform-specific axis configuration
        self.axis_config = self.get_axis_config()

    def _uses_gc_controller_api(self, joystick):
        """True when a macOS joystick is being reported through SDL's
        GCController backend (Bluetooth), False for the HIDAPI/wired backend
        (USB) or any non-macOS platform.

        GCController-backed devices report the D-pad as buttons 11-14 with
        no hat; HIDAPI-backed (wired) devices report a real hat, same as
        Linux/Windows.
        """
        if sys.platform != 'darwin':
            return False
        if joystick is None:
            return True
        try:
            return joystick.get_numhats() == 0
        except Exception:
            return True

    def get_axis_config(self, joystick=None):
        """Get axis configuration based on platform, connection type, and controller"""
        if sys.platform.startswith('linux'):
            return {
                'left_trigger_axis': 2,
                'right_trigger_axis': 5,
                # On Linux both Xbox and DualSense: L2 occupies axis 2, so right stick shifts to 3,4
                'right_stick_x_axis': 3,
                'right_stick_y_axis': 4,
            }
        elif sys.platform == 'darwin' and self._uses_gc_controller_api(joystick):
            # macOS Xbox BT via SDL2 GCController: axes 0-3 are sticks, 4-5 are triggers.
            return {
                'left_trigger_axis': 4,
                'right_trigger_axis': 5,
                'right_stick_x_axis': 2,
                'right_stick_y_axis': 3,
            }
        elif sys.platform == 'darwin':
            # macOS wired USB: SDL uses the same HIDAPI driver as Linux, so
            # the axis layout matches Linux's, not the GCController layout.
            return {
                'left_trigger_axis': 2,
                'right_trigger_axis': 5,
                'right_stick_x_axis': 3,
                'right_stick_y_axis': 4,
            }
        else:
            return {
                'left_trigger_axis': 4,
                'right_trigger_axis': 5,
                # On Windows both Xbox and DualSense: right stick is on axes 2,3
                'right_stick_x_axis': 2,
                'right_stick_y_axis': 3,
            }

    def _normalize_trigger(self, name, raw):
        """Normalize a raw trigger axis to 0.0–1.0, self-calibrating its rest.

        Triggers usually rest at -1.0, but an axis that hasn't yet delivered
        its initial value (or a virtual gamepad) rests at 0.0, which a static
        (raw + 1) / 2 would read as half-pressed.

        Instead, track the minimum value actually observed for this trigger
        (starting from the first reading, so an untouched axis defines its own
        rest) and normalize against it. A real controller reports its true
        -1.0 rest within a frame or two; a genuine press still spans to +1.0
        and reads as fully pressed from either baseline; and an axis stuck at
        0.0 stays at 0.0.
        """
        try:
            raw = float(raw)
        except (TypeError, ValueError):
            return 0.0
        prev = self._trigger_rest_observed.get(name)
        rest = raw if prev is None else min(prev, raw)
        self._trigger_rest_observed[name] = rest
        span = 1.0 - rest
        if span <= 0.0:
            return 0.0
        return max(0.0, min(1.0, (raw - rest) / span))

    def setup_xbox_mapping(self, joystick=None):
        """Setup Xbox controller button mapping"""
        if self._uses_gc_controller_api(joystick):
            # macOS Xbox BT via SDL2 GCController API shifts button indices:
            # View(Back)=4, Menu(Start)=6, LS=7, RS=8, LB=9, RB=10.
            # D-pad is reported as buttons 11-14 (no hat), same layout as DualSense.
            self.button_mappings = {
                0: 'button_a',
                1: 'button_b',
                2: 'button_x',
                3: 'button_y',
                4: 'button_back',
                6: 'button_start',
                7: 'button_ls',
                8: 'button_rs',
                9: 'button_lb',
                10: 'button_rb',
                11: 'dpad_up',
                12: 'dpad_down',
                13: 'dpad_left',
                14: 'dpad_right',
            }
        else:
            self.button_mappings = {
                0: 'button_a',
                1: 'button_b',
                2: 'button_x',
                3: 'button_y',
                4: 'button_lb',
                5: 'button_rb',
                6: 'button_back',
                7: 'button_start',
                8: 'button_ls',
                9: 'button_rs',
            }

    def setup_dualsense_mapping(self):
        """Setup DualSense controller button mapping"""
        self.button_mappings = {
            0: 'button_a',      # Cross (A equivalent)
            1: 'button_b',      # Circle (B equivalent)
            2: 'button_x',      # Square (X equivalent)
            3: 'button_y',      # Triangle (Y equivalent)
            9: 'button_lb',     # L1
            10: 'button_rb',    # R1
            4: 'button_back',   # Create/Share
            6: 'button_start',  # Options
            7: 'button_ls',     # L3
            8: 'button_rs',     # R3
            11: 'dpad_up',
            12: 'dpad_down',
            13: 'dpad_left',
            14: 'dpad_right',
        }

    # Name-based preference when more than one joystick is attached, most
    # preferred first.
    _NAME_PRIORITY = (
        'steam virtual',        # Steam Input / Remote Play virtual gamepad
        'xbox', 'x360', '360', 'xinput',
        'dualsense', 'ps5', 'playstation',
        'wireless controller',  # DualShock/DualSense generic name
        'gamepad',
    )

    def _pick_preferred(self, candidates):
        """Choose the best joystick from a list by _NAME_PRIORITY (stable)."""
        def score(js):
            try:
                n = js.get_name().lower()
            except Exception:
                return len(self._NAME_PRIORITY)
            for rank, key in enumerate(self._NAME_PRIORITY):
                if key in n:
                    return rank
            return len(self._NAME_PRIORITY)
        return min(candidates, key=score)

    def _set_active_joystick(self, joystick):
        """Make `joystick` the active controller and load its button mapping."""
        try:
            controller_name = joystick.get_name().lower()
        except Exception:
            controller_name = ''
        if ('dualsense' in controller_name or 'ps5' in controller_name
                or 'playstation 5' in controller_name):
            self.controller_type = 'dualsense'
            self.setup_dualsense_mapping()
        else:
            self.controller_type = 'xbox'
            self.setup_xbox_mapping(joystick)
        self.axis_config = self.get_axis_config(joystick)
        self.controller = joystick
        self.controller_connected = True
        # New device: forget the previous trigger rest calibration so the new
        # controller's rest point is re-learned.
        self._trigger_rest_observed = {'left': None, 'right': None}
        print(f"Controller system: Active controller: {joystick.get_name()} "
              f"({self.controller_type} mapping)")

    def _refresh_joysticks(self):
        """Re-enumerate attached joysticks after an attach/detach.

        Opens every device (so the activity scan can read them all), logs the
        full list for diagnostics, keeps the current active controller when it
        is still attached, and otherwise activates the preferred candidate.
        """
        count = pygame.joystick.get_count()
        self._last_joystick_count = count

        active_iid = None
        if self.controller is not None:
            try:
                active_iid = self.controller.get_instance_id()
            except Exception:
                active_iid = None

        candidates = []
        names = []
        for i in range(count):
            try:
                js = pygame.joystick.Joystick(i)
                js.init()
                candidates.append(js)
                names.append(js.get_name())
            except Exception as e:
                print(f"Controller system: could not open joystick {i}: {e}")
        self._candidates = candidates
        print(f"Controller system: {count} joystick(s) attached: {names}")

        if not candidates:
            self._clear_active()
            return

        keep = None
        if active_iid is not None:
            for js in candidates:
                try:
                    if js.get_instance_id() == active_iid:
                        keep = js
                        break
                except Exception:
                    pass
        if keep is not None:
            self.controller = keep  # same device, mapping unchanged
        else:
            self._set_active_joystick(self._pick_preferred(candidates))

    def _joystick_has_activity(self, joystick):
        """True when a non-active joystick shows deliberate user input.

        Buttons, hats and the left stick only — trigger axes rest at -1.0 on
        most backends and would read as permanent 'activity'.
        """
        try:
            for i in range(joystick.get_numbuttons()):
                if joystick.get_button(i):
                    return True
            for i in range(joystick.get_numhats()):
                if joystick.get_hat(i) != (0, 0):
                    return True
            for i in range(min(2, joystick.get_numaxes())):
                if abs(joystick.get_axis(i)) > 0.6:
                    return True
        except Exception:
            pass
        return False

    def _clear_active(self):
        self.controller = None
        self.controller_connected = False
        self._clear_state()

    def _clear_state(self):
        self.stick_x = 0.0
        self.left_trigger = 0.0
        self.right_trigger = 0.0
        self.buttons = frozenset()

    def _apply_deadzone(self, value):
        """Zero inside the deadzone, rescaled so the output still spans -1..1."""
        magnitude = abs(value)
        if magnitude <= self.stick_deadzone:
            return 0.0
        scaled = (magnitude - self.stick_deadzone) / (1.0 - self.stick_deadzone)
        return min(1.0, scaled) if value > 0 else -min(1.0, scaled)

    def _read_buttons(self):
        """Logical names of every held button, including the D-pad."""
        held = set()
        num_buttons = self.controller.get_numbuttons()

        # Which source a controller uses for the D-pad — a hat or buttons
        # 11-14 — depends on the SDL build and connection type, not just the
        # platform, so detect it from the device: prefer the hat when one
        # exists, and only fall back to buttons when there is no hat.
        use_hat_dpad = self.controller.get_numhats() > 0

        for button_id, button_name in self.button_mappings.items():
            # Guard against button indices the device doesn't expose, which
            # SDL rejects with "Invalid joystick button".
            if button_id >= num_buttons:
                continue
            if button_name.startswith('dpad_') and use_hat_dpad:
                continue
            if self.controller.get_button(button_id):
                held.add(button_name)

        if use_hat_dpad:
            hat_x, hat_y = self.controller.get_hat(0)
            for hat in ((hat_x, 0), (0, hat_y)):
                direction = self.dpad_mappings.get(hat)
                if direction:
                    held.add(direction)

        return frozenset(held)

    def poll(self):
        """Read the active controller. Call once per frame, after the pygame
        event queue has been pumped."""
        try:
            # Attach/detach detection. get_count() detects newly-connected
            # devices without reinitializing the joystick subsystem.
            if pygame.joystick.get_count() != self._last_joystick_count:
                self._refresh_joysticks()

            if not self.controller:
                return

            # If another attached joystick shows deliberate input while the
            # active one is idle in hand, switch to it.
            current_time = time.time()
            if (len(self._candidates) > 1
                    and current_time - self._last_activity_scan > 0.25):
                self._last_activity_scan = current_time
                for js in self._candidates:
                    if js is self.controller:
                        continue
                    if self._joystick_has_activity(js):
                        print("Controller system: input detected on "
                              f"{js.get_name()} — switching active controller")
                        self._set_active_joystick(js)
                        break

            num_axes = self.controller.get_numaxes()

            self.stick_x = (self._apply_deadzone(self.controller.get_axis(0))
                            if num_axes >= 1 else 0.0)

            lt_axis = self.axis_config['left_trigger_axis']
            rt_axis = self.axis_config['right_trigger_axis']
            self.left_trigger = (
                self._normalize_trigger('left', self.controller.get_axis(lt_axis))
                if num_axes > lt_axis else 0.0)
            self.right_trigger = (
                self._normalize_trigger('right', self.controller.get_axis(rt_axis))
                if num_axes > rt_axis else 0.0)

            self.buttons = self._read_buttons()

        except pygame.error as e:
            print(f"Controller system: Controller disconnected or error: {e}")
            self._candidates = []
            self._last_joystick_count = -1  # force re-enumeration
            self._clear_active()
