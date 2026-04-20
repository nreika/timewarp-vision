# TouchDesigner Setup

This project can notify TouchDesigner in real time whenever a new prediction image is written into `captures`.

## What the server sends

The Node server sends one UDP JSON message per saved image to `127.0.0.1:9989` by default.

Each message contains:

- The scene key (`sceneA`, `sceneB`, `sceneC`)
- The saved image path
- A normalized forward-slash path for Windows
- The newest timestamped file path for that scene
- The label and timestamp

## TouchDesigner network

1. Add a `UDP In DAT`
2. Set `Port` to `9989`
3. Set `Row/Callback Format` to `One Per Message`
4. Create a `Text DAT` and paste in `td_capture_listener.py`
5. Point the `UDP In DAT` `Callbacks DAT` parameter at that script
6. Create three `Movie File In TOP` operators named `moviefilein_scene_a`, `moviefilein_scene_b`, `moviefilein_scene_c`
7. Optional: keep a fallback single `Movie File In TOP` named `moviefilein1`
8. Optional: create a `Table DAT` named `capture_info`

When a message arrives, the callback uses `sceneKey` to update the matching `Movie File In TOP` to the newest timestamped file and pulses `reloadpulse`.

## Notes

- The app currently saves three timeline images per capture, so TouchDesigner will receive three messages in sequence.
- Images are stored with timestamped names such as `timewarp_Timeline_A_1776160553565.png`.
- `captures/latest_scenes.json` keeps track of which timestamped file is currently newest for each scene.
- If a UDP packet is missed, you can recover the newest state from `captures/latest_scenes.json` or `http://localhost:3000/api/latest-captures`.

## GitHub Workflow

For GitHub-backed project management, keep the TouchDesigner-side source files in this `touchdesigner/` folder:

- `td_capture_listener.py`
- exported `.tox` components if you modularize the network
- `.toe` project checkpoints only when you want an intentional binary snapshot

The generated files in `captures/` are ignored by Git, so repository history stays focused on source files rather than prediction output images.
