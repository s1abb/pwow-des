"""
Import a timeline JSON produced by the engine and create Blender objects
with keyed locations so you can animate the simulation in Blender.

Usage inside Blender (recommended via the VS Code "Blender Development" extension):
- Start Blender via the extension (Blender: Start) and open this script in VS Code.
- Run the script in Blender (Blender: Run Script) or execute inside Blender's Text Editor.

Command-line (non-Blender-safe): this file imports `bpy` and must be run inside Blender.

Behavior:
- Reads a timeline JSON (default: collision_timeline.json in the current working dir).
- Sets scene.fps to 1/sample_dt if present and reasonable (clamped to int >= 1).
- Creates one Empty per actor id (name = id) if not present, and inserts location keyframes
  for every sampled frame present in the timeline.

Notes:
- The script is intentionally minimal and avoids advanced features. You can extend it
  to create better meshes, materials, cameras, etc.
"""

import json
from pathlib import Path
import sys

# This script must run inside Blender where `bpy` is available
try:
    import bpy
except Exception as e:
    raise RuntimeError("This script must be run inside Blender where bpy is available") from e


def import_timeline(path: Path):
    data = json.loads(path.read_text(encoding="utf8"))

    meta = data.get("metadata", {})
    sample_dt = float(meta.get("sample_dt", 1.0 / 24.0))

    # derive fps from sample_dt (clamped)
    try:
        fps = int(round(1.0 / sample_dt))
        if fps < 1:
            fps = 24
    except Exception:
        fps = 24

    scene = bpy.context.scene
    scene.render.fps = fps

    frames = data.get("frames", [])
    if not frames:
        print("No frames found in timeline")
        return

    # collect actor ids
    actor_ids = set()
    for f in frames:
        for s in f.get("actor_states", []):
            actor_ids.add(s.get("id"))

    # create empties for each actor id if not present
    objs = {}
    for aid in actor_ids:
        if aid in bpy.data.objects:
            objs[aid] = bpy.data.objects[aid]
        else:
            empty = bpy.data.objects.new(aid, None)
            # place at origin initially
            empty.empty_display_type = 'SPHERE'
            empty.empty_display_size = 0.2
            bpy.context.collection.objects.link(empty)
            objs[aid] = empty

    # insert keyframes
    for frame_entry in frames:
        t = float(frame_entry.get("t", 0.0))
        frame_idx = int(round(t * fps))
        for s in frame_entry.get("actor_states", []):
            aid = s.get("id")
            pos = s.get("pos", [0.0, 0.0, 0.0])
            obj = objs.get(aid)
            if obj is None:
                continue
            # Blender uses (x, y, z). If your timeline uses different axes, transform here.
            obj.location = (float(pos[0]), float(pos[1]), float(pos[2]))
            obj.keyframe_insert(data_path="location", frame=frame_idx)

    # set frame range
    start_frame = int(round(frames[0].get("t", 0.0) * fps))
    end_frame = int(round(frames[-1].get("t", start_frame) * fps))
    scene.frame_start = start_frame
    scene.frame_end = end_frame

    print(f"Imported timeline: {len(frames)} frames, fps={fps}, actors={len(actor_ids)}")


if __name__ == "__main__":
    path = Path(sys.argv[-1]) if len(sys.argv) > 1 else Path("collision_timeline.json")
    if not path.exists():
        print(f"Timeline file not found: {path}")
        sys.exit(1)
    import_timeline(path)
    print("Done")
