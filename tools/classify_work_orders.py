"""
Batch classifier for hauling work order descriptions using the OpenAI Batch API.

Categories
----------
  1. Powertrain / Engine          - Engine, exhaust, cooling, transmission
  2. Hydraulics                   - Cylinders, hoses, pumps, valves
  3. Electrical / Controls / Technology - Sensors, comms, automation, cameras
  4. Lubrication / Filtration     - Grease systems, oil filters, fuel filters
  5. Ground Engaging Tools (GET)  - Lips, shrouds, adaptors, teeth, buckets
  6. Structural / Fabrication     - Cracks, welds, handrails, frames
  7. Modification / Improvement   - Proactive changes, not a failure
  8. Tyres                        - Tyre removal, installation, repair
  9. Other                        - Does not fit any category above

Workflow (run each phase in order)
-----------------------------------
  python classify_work_orders.py prepare   [--input FILE] [--batch-size N]
  python classify_work_orders.py submit    [--input-jsonl FILE]
  python classify_work_orders.py status    --batch-id BATCH_ID
  python classify_work_orders.py retrieve  --batch-id BATCH_ID
  python classify_work_orders.py merge     [--input FILE] [--output FILE]

Environment
-----------
  OPENAI_API_KEY  - required

Output files (all written to the same folder as the input CSV)
--------------------------------------------------------------
  hauling_work_order_data_batch_input.jsonl   - batch API requests
  hauling_work_order_data_batch_id.txt        - submitted batch id
  hauling_work_order_data_batch_output.jsonl  - raw API results
  hauling_work_order_data_classified.csv      - original CSV + category columns
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed; fall back to environment variables

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path(r"C:\repos\pwow-des\actuals\hauling_work_order_data.csv")
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BATCH_SIZE = 25  # rows per API request (reduces total request count)

CATEGORIES = [
    "Powertrain / Engine",
    "Hydraulics",
    "Brakes",
    "Suspension",
    "Electrical / Controls / Technology",
    "Lubrication / Filtration",
    "Ground Engaging Tools (GET)",
    "Track / Undercarriage",
    "Swing / Slew System",
    "Structural / Fabrication",
    "Cab / Body",
    "Fire Suppression",
    "Modification / Improvement",
    "Tyres",
    "Other",
]

SYSTEM_PROMPT = f"""You are a maintenance classification assistant for a large open-pit mining operation.
Classify each work order into exactly one of the following categories based on the description and context provided.

Categories:
{chr(10).join(f'  - {c}' for c in CATEGORIES)}

Category guidance:
- "Powertrain / Engine"  — engine, exhaust, cooling system, turbocharger, transmission, drive shaft, differentials, alternator, belts.
- "Hydraulics"           — hydraulic hoses, cylinders (hoist, steering ram, boom, arm, bucket), pumps, valves, hydraulic oil leaks, contamination events (e.g. "Contam CH02", "Contam Alarm"). Does NOT include brake or suspension hydraulics.
- "Brakes"               — service brakes, park brakes, brake accumulators, brake cooling (motors, hoses, oil coolers), brake valves, brake sensors.
- "Suspension"           — struts (front/rear), suspension cylinders, gas-and-oil changeouts, strut height resets, strut spigot NDT.
- "Electrical / Controls / Technology" — sensors, wiring harnesses, VIMS, Wenco, AHS/autonomous systems, cameras, radar, comms, lights, dash displays.
- "Lubrication / Filtration" — auto-lube systems, grease pumps, oil filters, fuel filters, air filters, fuel system components, scheduled services (SVC/INS activity types) when no specific component is identifiable.
- "Ground Engaging Tools (GET)" — lips, shrouds, adaptors, teeth, buckets, tray wear parts, bucket teeth, cutting edges.
- "Track / Undercarriage" — track idlers, track rollers, track pins, track shoes, carrier rollers, sprockets, undercarriage frames; UND activity type. Applies to excavators and other tracked equipment.
- "Swing / Slew System"  — swing motors, slew rings, slew bearings, slew gearboxes, swing brakes, sight glasses on slew/swing components.
- "Structural / Fabrication" — cracks in frames/tray/deck, welds, handrails, platforms, ladders, body panels (structural).
- "Cab / Body"           — doors, windows, mirrors, seals, seats, air conditioning, cab interior, wipers, steps.
- "Fire Suppression"     — fire suppression systems, bottles, actuators, servicing, refills, nozzles.
- "Modification / Improvement" — proactive upgrades, retrofits, installations not caused by failure (MOD activity type).
- "Tyres"                — tyre removal, installation, rotation, repair (TYR activity type).
- "Other"                — clearly does not fit any category above.

Rules:
- Use "Modification / Improvement" only for proactive, non-failure changes (e.g. upgrades, retrofits).
- Use "Tyres" for any tyre removal, installation, rotation, or repair work.
- Contamination events ("Contam", "Contamination") classify as "Hydraulics" unless context clearly indicates lubrication system.
- Generic scheduled services/inspections (e.g. "1D MEC INS EX012", "8W MEC C SVC EX003") with no specific component mentioned classify as "Lubrication / Filtration" (routine servicing).
- Use "Other" only when the description clearly does not fit any category.
- Descriptions may be abbreviated mine-site shorthand (e.g. "c/o" = changeout, "u/s" = underside, "LHS" = left-hand side, "RPL" = replace).
- Consider the maintenance_activity_type alongside the description:
    MNR=Minor repair, RPL=Replace, RPR=Repair, SVC=Service, MJR=Major repair,
    TYR=Tyres, NDT=Non-destructive testing, INS=Inspection, MOD=Modification,
    GET=Ground engaging tools, FAB=Fabrication, UND=Undercarriage.

Respond with a JSON object with a single key "results" containing an array, one entry per input row, in the same order. Each entry must be:
  {{"id": "<custom_id>", "category": "<category>", "confidence": "<high|medium|low>"}}

Do not include any other text."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _out_path(input_csv: Path, suffix: str) -> Path:
    return input_csv.parent / (input_csv.stem + suffix)


def _resolve_batch_id(args: argparse.Namespace) -> str:
    """Return batch ID from --batch-id flag or the saved ID file."""
    if args.batch_id:
        return args.batch_id
    id_file = _out_path(Path(args.input), "_batch_id.txt")
    if not id_file.exists():
        sys.exit(
            f"ERROR: --batch-id not provided and no saved batch ID found at {id_file}.\n"
            "Run 'submit' first, or pass --batch-id explicitly."
        )
    batch_id = id_file.read_text(encoding="utf-8").strip()
    print(f"  Using saved batch ID: {batch_id}")
    return batch_id


def _require_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        sys.exit("ERROR: OPENAI_API_KEY environment variable is not set.")
    return key


def _openai_client():
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("ERROR: openai package not installed. Run: pip install openai")
    return OpenAI(api_key=_require_api_key())


# ---------------------------------------------------------------------------
# Phase 1 – Prepare
# ---------------------------------------------------------------------------

def cmd_prepare(args: argparse.Namespace) -> None:
    input_csv = Path(args.input)
    batch_size = args.batch_size
    out_jsonl = _out_path(input_csv, "_batch_input.jsonl")

    print(f"Reading {input_csv} ...")
    df = pd.read_csv(input_csv, dtype=str, low_memory=False)
    print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")

    # --resume: skip rows already classified in the output CSV (apply BEFORE --limit)
    if args.resume:
        classified_csv = _out_path(input_csv, "_classified.csv")
        if not classified_csv.exists():
            print(f"  [resume] No classified CSV found at {classified_csv} — processing all rows.")
        else:
            done = pd.read_csv(classified_csv, dtype=str, low_memory=False, usecols=["work_order_id", "work_category"])
            already_done = set(done.loc[done["work_category"].notna(), "work_order_id"])
            before = len(df)
            df = df[~df["work_order_id"].isin(already_done)]
            print(f"  [resume] Skipping {before - len(df):,} already-classified rows, {len(df):,} remaining.")

    if args.limit:
        df = df.head(args.limit)
        print(f"  Limiting to {len(df):,} rows (--limit {args.limit})")

    if len(df) == 0:
        print("  Nothing to do — all rows are already classified.")
        return

    # Columns included in the prompt
    prompt_cols = [
        "work_order_id",
        "order_description",
        "maintenance_activity_type_id",
        "sort_field",          # equipment label (e.g. DT073)
        "asset_description",
    ]
    missing = [c for c in prompt_cols if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: Columns not found in CSV: {missing}")

    rows = df[prompt_cols].fillna("").to_dict(orient="records")

    request_count = 0
    with open(out_jsonl, "w", encoding="utf-8") as fout:
        for i in range(0, len(rows), batch_size):
            chunk = rows[i : i + batch_size]
            # Build a numbered list for the model
            user_lines = []
            for j, row in enumerate(chunk, start=1):
                user_lines.append(
                    f"{j}. id={row['work_order_id']} | "
                    f"activity={row['maintenance_activity_type_id']} | "
                    f"equipment={row['sort_field']} ({row['asset_description']}) | "
                    f"description: {row['order_description']}"
                )
            user_content = "\n".join(user_lines)

            # custom_id encodes the batch index so we can reconstruct order
            custom_id = f"batch_{i}_{i + len(chunk) - 1}"

            request = {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": args.model,
                    "temperature": 0,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "classifications",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "results": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "category": {"type": "string", "enum": CATEGORIES},
                                                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                            },
                                            "required": ["id", "category", "confidence"],
                                            "additionalProperties": False,
                                        },
                                    }
                                },
                                "required": ["results"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                },
            }
            fout.write(json.dumps(request) + "\n")
            request_count += 1

    print(f"  Wrote {request_count:,} requests ({batch_size} rows each) → {out_jsonl}")
    print("\nNext step:  python classify_work_orders.py submit")


# ---------------------------------------------------------------------------
# Phase 2 – Submit
# ---------------------------------------------------------------------------

def cmd_submit(args: argparse.Namespace) -> None:
    input_csv = Path(args.input)
    in_jsonl = Path(args.input_jsonl) if args.input_jsonl else _out_path(input_csv, "_batch_input.jsonl")
    id_file = _out_path(input_csv, "_batch_id.txt")

    if not in_jsonl.exists():
        sys.exit(f"ERROR: {in_jsonl} not found. Run 'prepare' first.")

    client = _openai_client()

    print(f"Uploading {in_jsonl} ({in_jsonl.stat().st_size / 1_048_576:.1f} MB) ...")
    with open(in_jsonl, "rb") as f:
        uploaded = client.files.create(file=f, purpose="batch")
    print(f"  File id: {uploaded.id}")

    print("Submitting batch ...")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    print(f"  Batch id: {batch.id}  status: {batch.status}")
    id_file.write_text(batch.id, encoding="utf-8")
    print(f"  Batch id saved → {id_file}")
    print(f"\nNext step:  python classify_work_orders.py status --batch-id {batch.id}")


# ---------------------------------------------------------------------------
# Phase 3 – Status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> None:
    client = _openai_client()
    batch = client.batches.retrieve(_resolve_batch_id(args))
    counts = batch.request_counts
    print(
        f"Batch {batch.id}\n"
        f"  status    : {batch.status}\n"
        f"  completed : {counts.completed:,}\n"
        f"  failed    : {counts.failed:,}\n"
        f"  total     : {counts.total:,}"
    )
    if batch.status == "completed":
        print(f"\nNext step:  python classify_work_orders.py retrieve --batch-id {batch.id}")
    elif batch.status == "failed":
        print("Batch failed. Check the OpenAI dashboard for details.")


# ---------------------------------------------------------------------------
# Phase 4 – Retrieve
# ---------------------------------------------------------------------------

def cmd_retrieve(args: argparse.Namespace) -> None:
    input_csv = Path(args.input)
    out_jsonl = _out_path(input_csv, "_batch_output.jsonl")
    client = _openai_client()

    stall_timeout = getattr(args, "stall_timeout", 10)  # minutes with no progress before cancelling

    # Poll until done
    batch_id = _resolve_batch_id(args)
    batch = client.batches.retrieve(batch_id)
    poll_interval = 60  # seconds
    last_completed = -1
    stall_minutes = 0

    cancelling_wait = 0
    while batch.status in ("validating", "in_progress", "finalizing", "cancelling"):
        counts = batch.request_counts
        print(
            f"  [{batch.status}] {counts.completed:,}/{counts.total:,} completed "
            f"— retrying in {poll_interval}s ..."
        )
        # Stall detection (in_progress only)
        if counts.completed == last_completed and batch.status == "in_progress":
            stall_minutes += poll_interval / 60
            if stall_minutes >= stall_timeout:
                print(f"  [WARN] No progress for {stall_timeout} minutes — cancelling batch to retrieve partial results.")
                client.batches.cancel(batch_id)
                stall_minutes = 0
        else:
            stall_minutes = 0
        # Cap time waiting for cancellation to complete (some batches get stuck in cancelling)
        if batch.status == "cancelling":
            cancelling_wait += poll_interval / 60
            if cancelling_wait >= 5:  # 5 minutes in cancelling → give up waiting
                print("  [WARN] Batch stuck in cancelling state — giving up and moving on.")
                break
        else:
            cancelling_wait = 0
        last_completed = counts.completed
        time.sleep(poll_interval)
        batch = client.batches.retrieve(batch_id)

    if batch.status not in ("completed", "cancelled", "cancelling"):
        print(f"  [WARN] Batch ended with status '{batch.status}' — affected rows will be retried in the next chunk.")
        return

    if batch.status in ("cancelled", "cancelling"):
        counts = batch.request_counts
        print(f"  Batch was cancelled ({counts.completed}/{counts.total} completed) — waiting up to 10 min for partial output file...")
        for wait_min in range(10):
            if batch.output_file_id:
                break
            time.sleep(60)
            batch = client.batches.retrieve(batch_id)
            print(f"  [{wait_min+1}min] output_file_id: {batch.output_file_id or 'None'}")

    if not batch.output_file_id:
        counts = batch.request_counts
        print(f"  [WARN] No output file available after waiting (batch status: {batch.status}, {counts.completed}/{counts.total} completed).")
        print("  Affected rows will be retried in the next chunk.")
        return

    if batch.status in ("cancelled", "cancelling"):
        counts = batch.request_counts
        print(f"  Downloading partial results ({counts.completed:,}/{counts.total:,} completed).")

    print(f"Downloading output file {batch.output_file_id} ...")
    content = client.files.content(batch.output_file_id)
    out_jsonl.write_bytes(content.read())
    line_count = sum(1 for _ in out_jsonl.open(encoding="utf-8"))
    print(f"  Saved {line_count:,} result lines → {out_jsonl}")
    print("\nNext step:  python classify_work_orders.py merge")


# ---------------------------------------------------------------------------
# Phase 5 – Merge
# ---------------------------------------------------------------------------

def cmd_merge(args: argparse.Namespace) -> None:
    input_csv = Path(args.input)
    out_jsonl = _out_path(input_csv, "_batch_output.jsonl")
    out_csv = Path(args.output) if args.output else _out_path(input_csv, "_classified.csv")

    if not out_jsonl.exists():
        sys.exit(f"ERROR: {out_jsonl} not found. Run 'retrieve' first.")

    print(f"Reading original CSV: {input_csv}")
    df = pd.read_csv(input_csv, dtype=str, low_memory=False)

    # Seed from existing classified CSV to preserve prior results (resume support)
    if out_csv.exists():
        existing = pd.read_csv(out_csv, dtype=str, low_memory=False, usecols=["work_order_id", "work_category", "work_category_confidence"])
        already = existing[existing["work_category"].notna()].set_index("work_order_id")
        pre_classified = len(already)
        print(f"  Seeding {pre_classified:,} existing classifications from {out_csv.name}")
    else:
        already = pd.DataFrame(columns=["work_category", "work_category_confidence"])
        already.index.name = "work_order_id"
        pre_classified = 0

    df["work_category"] = df["work_order_id"].map(already["work_category"]).astype(object)
    df["work_category_confidence"] = df["work_order_id"].map(already["work_category_confidence"]).astype(object)

    # Index df by work_order_id for fast lookup
    id_to_idx = {row["work_order_id"]: i for i, row in df.iterrows()}

    parsed_count = 0
    error_count = 0

    print(f"Parsing results: {out_jsonl}")
    with open(out_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            result = json.loads(line)

            if result.get("error"):
                error_count += 1
                print(f"  [WARN] Request {result['custom_id']} failed: {result['error']}")
                continue

            try:
                content_str = result["response"]["body"]["choices"][0]["message"]["content"]
                content = json.loads(content_str)
                # Model returns either {"results": [...]} or a bare array
                items = content.get("results") or content.get("classifications") or list(content.values())[0]
                if isinstance(items, dict):
                    items = [items]
            except Exception as exc:
                error_count += 1
                print(f"  [WARN] Could not parse {result['custom_id']}: {exc}")
                continue

            for item in items:
                wid = str(item.get("id", "")).strip()
                category = item.get("category", "Other")
                confidence = item.get("confidence", "")
                if category not in CATEGORIES:
                    print(f"  [WARN] Unknown category '{category}' for id={wid} — remapping to 'Other'")
                    category = "Other"
                if wid in id_to_idx:
                    idx = id_to_idx[wid]
                    df.at[idx, "work_category"] = category
                    df.at[idx, "work_category_confidence"] = confidence
                    parsed_count += 1

    classified = df["work_category"].notna().sum()
    unclassified = df["work_category"].isna().sum()
    invalid = (parsed_count - classified + unclassified)  # already remapped, so just report
    print(f"\n  Parsed     : {parsed_count:,} classifications")
    print(f"  Classified : {classified:,} rows")
    print(f"  Blank      : {unclassified:,} rows (batch errors or missing)")
    print(f"  Errors     : {error_count:,} failed requests")

    if unclassified:
        print(f"  [INFO] Unclassified rows will have blank work_category — re-run phases for failed requests if needed.")

    print(f"\nCategory distribution:")
    print(df["work_category"].value_counts(dropna=False).to_string())

    df.to_csv(out_csv, index=False)
    print(f"\nSaved → {out_csv}")


# ---------------------------------------------------------------------------
# Auto-run – submit in chunks to stay under token enqueue limits
# ---------------------------------------------------------------------------

DEFAULT_CHUNK_SIZE = 10_000  # rows per batch submission (400 requests × 25 rows)


def _count_unclassified(input_csv: Path) -> int:
    """Return number of rows not yet classified in the output CSV."""
    out_csv = _out_path(input_csv, "_classified.csv")
    if not out_csv.exists():
        return len(pd.read_csv(input_csv, dtype=str, low_memory=False, usecols=["work_order_id"]))
    df = pd.read_csv(out_csv, dtype=str, low_memory=False, usecols=["work_order_id", "work_category"])
    return df["work_category"].isna().sum()


def cmd_run(args: argparse.Namespace) -> None:
    input_csv = Path(args.input)
    chunk_size = args.chunk_size
    model = args.model
    batch_size = args.batch_size

    # Fake sub-args for reuse of existing commands
    class SubArgs:
        pass

    def make_args(**kwargs):
        a = SubArgs()
        a.input = str(input_csv)
        a.batch_id = None
        a.output = None
        a.input_jsonl = None
        a.stall_timeout = getattr(args, "stall_timeout", 10)
        for k, v in kwargs.items():
            setattr(a, k, v)
        return a

    total_df = pd.read_csv(input_csv, dtype=str, low_memory=False, usecols=["work_order_id"])
    total_rows = len(total_df)
    print(f"Total rows: {total_rows:,}  |  chunk size: {chunk_size:,}  |  model: {model}")

    chunk_num = 0
    while True:
        remaining = _count_unclassified(input_csv)
        if remaining == 0:
            print("\nAll rows classified!")
            break

        chunk_num += 1
        print(f"\n{'='*60}")
        print(f"Chunk {chunk_num}  |  {remaining:,} rows remaining  |  submitting up to {chunk_size:,}")
        print(f"{'='*60}")

        # Prepare
        prepare_args = make_args(batch_size=batch_size, limit=chunk_size, model=model, resume=True)
        cmd_prepare(prepare_args)

        # Check if anything was written (all done edge case)
        out_jsonl = _out_path(input_csv, "_batch_input.jsonl")
        if out_jsonl.stat().st_size == 0:
            print("Nothing to submit.")
            break

        # Submit
        cmd_submit(make_args())

        # Check batch didn't immediately fail (e.g. token limit)
        client = _openai_client()
        batch_id = _out_path(input_csv, "_batch_id.txt").read_text(encoding="utf-8").strip()
        batch = client.batches.retrieve(batch_id)
        if batch.status == "failed":
            errors = ", ".join(e.message for e in (batch.errors.data or []))
            print(f"  [WARN] Batch failed immediately: {errors}")
            if "token_limit" in errors.lower():
                print("  Token limit hit — waiting 5 minutes for quota to clear before retrying...")
                time.sleep(300)
            continue  # retry this chunk

        # Retrieve (polls until done)
        cmd_retrieve(make_args())

        # Merge
        cmd_merge(make_args())

        classified = total_rows - _count_unclassified(input_csv)
        pct = classified / total_rows * 100
        print(f"\nProgress: {classified:,}/{total_rows:,} rows classified ({pct:.1f}%)")

    # Final distribution
    out_csv = _out_path(input_csv, "_classified.csv")
    if out_csv.exists():
        df = pd.read_csv(out_csv, dtype=str, low_memory=False)
        print(f"\nFinal category distribution:")
        print(df["work_category"].value_counts(dropna=False).to_string())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-classify hauling work order descriptions via OpenAI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to hauling_work_order_data.csv (default: actuals/hauling_work_order_data.csv)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # prepare
    p_prepare = sub.add_parser("prepare", help="Build batch JSONL input file from CSV")
    p_prepare.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                           help=f"Rows per API request (default: {DEFAULT_BATCH_SIZE})")
    p_prepare.add_argument("--limit", type=int, default=None,
                           help="Only process the first N rows (useful for testing)")
    p_prepare.add_argument("--model", default=DEFAULT_MODEL,
                           help=f"OpenAI model to use (default: {DEFAULT_MODEL})")
    p_prepare.add_argument("--resume", action="store_true",
                           help="Skip rows already classified in the output CSV")
    p_prepare.set_defaults(func=cmd_prepare)

    # submit
    p_submit = sub.add_parser("submit", help="Upload JSONL and submit batch to OpenAI")
    p_submit.add_argument("--input-jsonl", default=None,
                          help="Override path to batch input JSONL")
    p_submit.set_defaults(func=cmd_submit)

    # status
    p_status = sub.add_parser("status", help="Check batch status")
    p_status.add_argument("--batch-id", default=None,
                          help="Batch ID (default: read from saved batch ID file)")
    p_status.set_defaults(func=cmd_status)

    # retrieve
    p_retrieve = sub.add_parser("retrieve", help="Download completed batch results (polls until done)")
    p_retrieve.add_argument("--batch-id", default=None,
                            help="Batch ID (default: read from saved batch ID file)")
    p_retrieve.add_argument("--stall-timeout", type=int, default=10,
                            help="Minutes without progress before auto-cancelling and saving partial results (default: 10)")
    p_retrieve.set_defaults(func=cmd_retrieve)

    # merge
    p_merge = sub.add_parser("merge", help="Join classifications back to original CSV")
    p_merge.add_argument("--output", default=None,
                         help="Override output CSV path")
    p_merge.set_defaults(func=cmd_merge)

    # run (automated chunked loop)
    p_run = sub.add_parser("run", help="Automatically classify all rows in chunks (handles token limits)")
    p_run.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                       help=f"Rows per batch submission (default: {DEFAULT_CHUNK_SIZE:,})")
    p_run.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                       help=f"Rows per API request (default: {DEFAULT_BATCH_SIZE})")
    p_run.add_argument("--model", default=DEFAULT_MODEL,
                       help=f"OpenAI model to use (default: {DEFAULT_MODEL})")
    p_run.add_argument("--stall-timeout", type=int, default=10,
                       help="Minutes without progress before auto-cancelling (default: 10)")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
