Racing game prototype

Low-poly 3D arcade racer. Python, pygame (window / input / audio), ModernGL (rendering).

## Run

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

Pass a number to pick the track seed (default 1):

```bash
python main.py 5
```

## Game

Three laps against seven opponents, starting last. The timer counts down and
is extended at each checkpoint gantry; the race ends when it reaches zero.

## Controls

| | Gamepad | Keyboard |
|---|---|---|
| Steer | Left stick | Left / Right or A / D |
| Throttle | RT | Up or W |
| Brake / reverse | LT | Down or S |
| Restart | Start | Enter |
| Toggle chase view | | C |
| Quit | | Esc |

## Build (Windows exe)

From "Developer PowerShell for VS 2022":

```bash
python build_windows.py
```

Output: `dist_msvc/Racing.dist/Racing.exe`

## Release

```bash
python release_windows.py
```

Version bump, build, optional signing, ZIP + SHA-256 in `update_output/`.
