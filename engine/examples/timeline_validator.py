import json
from pathlib import Path

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except Exception as e:
    raise ImportError("timeline_validator requires 'jsonschema' - install requirements-dev.txt") from e


def load_schema():
    here = Path(__file__).resolve().parent
    return json.loads((here / "timeline_schema.json").read_text(encoding="utf8"))


def validate_timeline(obj):
    """Validate `obj` against the timeline schema.

    Uses `jsonschema` if available; otherwise performs a permissive
    structural validation.
    """
    schema = load_schema()
    # Validate using jsonschema; will raise on failure
    jsonschema.validate(instance=obj, schema=schema)
    return True


def validate_file(path: str):
    data = json.loads(Path(path).read_text(encoding="utf8"))
    return validate_timeline(data)
