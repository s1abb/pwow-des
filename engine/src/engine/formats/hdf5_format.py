import h5py
import numpy as np
from typing import Any, Dict, List, Optional, Tuple


class HDF5Handler:
    @staticmethod
    def export(timeline_data: Dict[str, Any], path: str, compression: str = "gzip", **kwargs):
        frames = timeline_data.get("frames", [])
        times = np.array([frame.get("t", 0.0) for frame in frames], dtype=np.float64)

        # collect actor ids
        actor_ids = set()
        for frame in frames:
            for s in frame.get("actor_states", []):
                actor_ids.add(str(s.get("id")))

        with h5py.File(path, "w") as f:
            # metadata
            meta = timeline_data.get("metadata", {})
            for k, v in meta.items():
                try:
                    f.attrs[k] = v
                except Exception:
                    # h5py may not accept some python types as attributes
                    f.attrs[k] = str(v)

            # times
            f.create_dataset("times", data=times, compression=compression)

            # positions per actor
            n_frames = len(frames)
            for actor_id in sorted(actor_ids):
                positions = np.zeros((n_frames, 3), dtype=np.float32)
                for i, frame in enumerate(frames):
                    # find actor state if present
                    state = next((s for s in frame.get("actor_states", []) if str(s.get("id")) == actor_id), None)
                    if state is not None:
                        pos = state.get("pos", [0.0, 0.0, 0.0])
                        positions[i, :len(pos)] = np.array(pos, dtype=np.float32)

                grp = f.require_group(f"actors/{actor_id}")
                # create positions dataset under the actor group
                grp.create_dataset("positions", data=positions, compression=compression)

                # write per-actor metadata if provided in timeline_data["actors"]
                actors_meta = timeline_data.get("actors", {})
                actor_meta = actors_meta.get(str(actor_id)) or actors_meta.get(actor_id)
                if isinstance(actor_meta, dict):
                    for mk, mv in actor_meta.items():
                        try:
                            grp.attrs[mk] = mv
                        except Exception:
                            grp.attrs[mk] = str(mv)

        return path

    @staticmethod
    def import_timeline(path: str, time_range: Optional[Tuple[float, float]] = None, actors: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        with h5py.File(path, "r") as f:
            times = f["times"][...]

            # determine slice for time_range
            if time_range is not None:
                start, end = float(time_range[0]), float(time_range[1])
                idx0 = int(np.searchsorted(times, start, side="left"))
                idx1 = int(np.searchsorted(times, end, side="right"))
            else:
                idx0, idx1 = 0, len(times)

            selected_times = times[idx0:idx1]

            # collect actors
            actor_ids = []
            if "actors" in f:
                actor_ids = list(f["actors"].keys())
            else:
                # infer from groups
                actor_ids = [name for name in f.keys() if name.startswith("actors/")]
                # but the above won't list nested groups; instead enumerate actors group
                if "actors" in f:
                    actor_ids = list(f["actors"].keys())

            if actors is not None:
                actor_ids = [a for a in actor_ids if a in actors]

            frames = []
            for i, t in enumerate(selected_times, start=idx0):
                actor_states = []
                for actor_id in actor_ids:
                    ds = f[f"actors/{actor_id}/positions"]
                    pos = ds[i]
                    actor_states.append({"id": actor_id, "pos": pos.tolist()})

                frames.append({"t": float(t), "actor_states": actor_states})

            meta = {k: v for k, v in f.attrs.items()}

            # read per-actor metadata (attributes on each actors/{id} group)
            actors_meta = {}
            if "actors" in f:
                for aid in f["actors"].keys():
                    try:
                        grp = f[f"actors/{aid}"]
                        # convert attrs mapping to plain dict
                        am = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in grp.attrs.items()}
                        actors_meta[str(aid)] = am
                    except Exception:
                        # ignore malformed actor groups
                        pass

            return {"metadata": meta, "frames": frames, "actors": actors_meta}

    @staticmethod
    def validate(path: str) -> bool:
        try:
            with h5py.File(path, "r"):
                return True
        except Exception:
            return False
