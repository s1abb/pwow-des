import json
from typing import Any, Dict


class JSONHandler:
    @staticmethod
    def export(timeline_data: Dict[str, Any], path: str, **kwargs):
        # write compact JSON by default; allow pretty via kwargs
        pretty = kwargs.get("pretty", False)
        with open(path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(timeline_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(timeline_data, f, separators=(",", ":"), ensure_ascii=False)
        return path

    @staticmethod
    def import_timeline(path: str, **kwargs):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def validate(path: str) -> bool:
        # basic validation: can we parse it?
        try:
            JSONHandler.import_timeline(path)
            return True
        except Exception:
            return False
