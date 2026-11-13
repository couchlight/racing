Racing game prototype

Low-poly 3D arcade racer. Python, pygame (window / input / audio), ModernGL (rendering).

## Run

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

## Controls

| | Gamepad | Keyboard |
|---|---|---|
| Steer | Left stick | Left / Right or A / D |
| Throttle | RT | Up or W |
| Brake | LT | Down or S |
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
