"""Race rules: start countdown, arcade timer extended at checkpoints, laps,
opponents and race position."""

import math

from game.car import Car
from game.opponent import Opponent, speed_limits

COUNTDOWN, RACING, FINISHED, TIME_UP = "countdown", "racing", "finished", "time_up"

LAPS = 3
OPPONENT_COUNT = 7
OPPONENT_SKILLS = (0.80, 0.97)   # slowest and fastest opponent

COUNTDOWN_SECONDS = 3.0
MESSAGE_SECONDS = 2.0

# Timer: each checkpoint section is budgeted at REFERENCE_SPEED.
REFERENCE_SPEED = 38.0           # metres per second
START_TIME_FACTOR = 1.5          # sections of time on the clock at the start
START_TIME_BONUS = 6.0           # allowance for the standing start
EXTENSION_FACTOR = 1.1           # sections of time added at each checkpoint

# Starting grid: two staggered columns behind the start line.
GRID_FIRST_ROW = 6.0             # pole position's distance behind the line
GRID_ROW_SPACING = 9.0
GRID_LATERAL = 3.0

# Car-to-car contact
CONTACT_LENGTH = 4.2
CONTACT_WIDTH = 1.9
PUSH_RATE = 6.0                  # lateral metres per second while overlapping
BUMP_SPEED_KEEP = 0.97           # player's speed relative to the car it ran into

# Opponent traffic
PASS_LOOKAHEAD = 25.0            # start changing lane this far behind a slower car
FOLLOW_GAP = 7.0                 # match the speed of a car this close ahead
SAME_LANE_WIDTH = 2.2
PASS_OFFSET = 2.8
LANE_MARGIN = 1.6                # keep this far from the walls


class Race:
    def __init__(self, track, checkpoint_count):
        self.track = track
        self.checkpoint_spacing = track.length / checkpoint_count
        self.checkpoints_per_lap = checkpoint_count
        self.laps = LAPS
        self._limits = speed_limits(track)
        section_time = self.checkpoint_spacing / REFERENCE_SPEED
        self._start_time = section_time * START_TIME_FACTOR + START_TIME_BONUS
        self.extension = section_time * EXTENSION_FACTOR
        self.player = Car(track)
        self.reset()

    def _grid_slot(self, slot):
        """(distance behind the line, lateral) for grid slot 0 (pole) onwards."""
        behind = GRID_FIRST_ROW + slot * GRID_ROW_SPACING / 2.0
        return -behind, GRID_LATERAL if slot % 2 else -GRID_LATERAL

    def reset(self):
        """Line everything up on the grid. The player starts last."""
        self.opponents = []
        for slot in range(OPPONENT_COUNT):
            distance, lateral = self._grid_slot(slot)
            # Fastest at the front.
            fraction = 1.0 - slot / max(1, OPPONENT_COUNT - 1)
            skill = OPPONENT_SKILLS[0] + (OPPONENT_SKILLS[1] - OPPONENT_SKILLS[0]) * fraction
            self.opponents.append(
                Opponent(self.track, self._limits, distance, lateral, skill))

        distance, lateral = self._grid_slot(OPPONENT_COUNT)
        self.player.place(distance, lateral)
        self.progress = distance          # unwrapped distance, like Opponent.distance
        self._last_s = self.player.s

        self.state = COUNTDOWN
        self.countdown = COUNTDOWN_SECONDS
        self.time_left = self._start_time
        self.lap = 1
        self.checkpoints_passed = 0
        self.position = self.car_count
        self.message = ""
        self._message_timer = 0.0

    @property
    def car_count(self):
        return len(self.opponents) + 1

    @property
    def countdown_number(self):
        return int(math.ceil(self.countdown))

    def _show(self, message, seconds=MESSAGE_SECONDS):
        self.message = message
        self._message_timer = seconds

    def update(self, steer, throttle, brake, dt):
        if self._message_timer > 0.0:
            self._message_timer -= dt
            if self._message_timer <= 0.0:
                self.message = ""

        if self.state == COUNTDOWN:
            self.countdown -= dt
            if self.countdown <= 0.0:
                self.state = RACING
                self._show("GO!", 1.0)
            return

        if self.state == RACING:
            self.player.update(steer, throttle, brake, dt)
            self.time_left -= dt
            if self.time_left <= 0.0:
                self.time_left = 0.0
                self.state = TIME_UP
        else:
            # Race over for the player: roll to a stop.
            self.player.update(0.0, 0.0, 1.0 if self.player.forward_speed > 0.5 else 0.0, dt)

        self._update_opponents(dt)
        self._resolve_contact(dt)

        s = self.player.s
        self.progress += self.track.wrap(s - self._last_s)
        self._last_s = s

        if self.state == RACING:
            self._check_checkpoints()
            self.position = 1 + sum(o.distance > self.progress for o in self.opponents)

    def _check_checkpoints(self):
        while self.progress >= (self.checkpoints_passed + 1) * self.checkpoint_spacing:
            self.checkpoints_passed += 1
            if self.checkpoints_passed % self.checkpoints_per_lap == 0:
                if self.lap == self.laps:
                    self.state = FINISHED
                    return
                self.lap += 1
            self.time_left += self.extension
            if self.checkpoints_passed % self.checkpoints_per_lap:
                self._show("CHECKPOINT")
            else:
                self._show("FINAL LAP" if self.lap == self.laps else f"LAP {self.lap}")

    def _update_opponents(self, dt):
        lane_limit = self.track.half_width - LANE_MARGIN
        cars = [(o.s, o.lateral, o.speed, o) for o in self.opponents]
        cars.append((self.player.s, self.player.lateral,
                     max(0.0, self.player.forward_speed), self.player))

        for opponent in self.opponents:
            blocked_speed = None
            nearest = PASS_LOOKAHEAD
            for s, lateral, speed, car in cars:
                if car is opponent:
                    continue
                gap = self.track.wrap(s - opponent.s)
                if not 0.0 < gap < nearest:
                    continue
                if abs(lateral - opponent.lateral) > SAME_LANE_WIDTH:
                    continue
                nearest = gap
                if speed < opponent.speed:
                    # Pull out to whichever side has room, preferring the nearer.
                    sides = sorted((lateral - PASS_OFFSET, lateral + PASS_OFFSET),
                                   key=lambda lane: abs(lane - opponent.lateral))
                    for lane in sides:
                        if abs(lane) <= lane_limit:
                            opponent.lane = lane
                            break
                blocked_speed = speed if gap < FOLLOW_GAP else None
            opponent.update(dt, blocked_speed)

    def _resolve_contact(self, dt):
        """Keep the player and opponents from driving through each other."""
        lane_limit = self.track.half_width - LANE_MARGIN
        player = self.player
        for opponent in self.opponents:
            gap = self.track.wrap(opponent.s - player.s)     # positive: opponent ahead
            side = opponent.lateral - player.lateral
            if abs(gap) >= CONTACT_LENGTH or abs(side) >= CONTACT_WIDTH:
                continue

            push = min(CONTACT_WIDTH - abs(side), PUSH_RATE * dt) / 2.0
            direction = 1.0 if side >= 0.0 else -1.0
            player.shift_lateral(-direction * push)
            opponent.lateral = max(-lane_limit, min(lane_limit, opponent.lateral + direction * push))
            opponent.lane = opponent.lateral

            if gap > 0.0 and player.forward_speed > opponent.speed:
                player.scale_speed(
                    max(opponent.speed, 1.0) * BUMP_SPEED_KEEP / player.forward_speed)
            elif gap < 0.0 and opponent.speed > player.forward_speed:
                opponent.speed = max(0.0, player.forward_speed)
