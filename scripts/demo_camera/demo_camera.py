#!/usr/bin/env python
"""Simulate the retinopathy camera's 4-step workflow against a live server.

Usage:
    python demo_camera.py --host https://edc.example.com --token YOUR_TOKEN \
        --subject 105-10-0001-2 --initials JD --sex M --age 35

    # Minimal (uses defaults for optional fields):
    python demo_camera.py --host http://localhost:8000 --token abc123 \\ # ggignore
        --subject 105-10-0001-2 --initials JD --sex M

    # With real image files:
    python demo_camera.py --host http://localhost:8000 --token abc123 \\ # ggignore
        --subject 105-10-0001-2 --initials JD --sex M \
        --left-image /path/to/left.jpg \
        --right-image /path/to/right.jpg \
        --report /path/to/report.pdf
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

STATUS_OK = 200
STATUS_CODE_CREATED = 201


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_dummy_jpeg(size: int = 2048) -> bytes:
    """Create minimal bytes that pass JPEG magic-byte validation."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * (size - 4)


def make_dummy_pdf(size: int = 2048) -> bytes:
    """Create minimal bytes that pass PDF magic-byte validation."""
    return b"%PDF-1.4" + b"\x00" * (size - 8)


def main() -> None:  # noqa: C901 PLR0912 PLR0915
    parser = argparse.ArgumentParser(
        description="Simulate the retinopathy camera workflow",
    )
    parser.add_argument("--host", required=True, help="Server base URL")
    parser.add_argument("--token", required=True, help="DRF auth token")
    parser.add_argument("--subject", required=True, help="Subject identifier")
    parser.add_argument("--initials", required=True, help="Subject initials")
    parser.add_argument("--sex", required=True, choices=["M", "F"])
    parser.add_argument("--age", type=int, default=None, help="Age in years")
    parser.add_argument("--device-id", default="DEMO-CAM-001")
    parser.add_argument("--site-id", default="")
    parser.add_argument("--left-image", type=Path, default=None)
    parser.add_argument("--right-image", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Send SHA-256 checksums",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print request/response JSON payloads",
    )
    args = parser.parse_args()

    base = args.host.rstrip("/") + "/api/retinopathy"
    headers = {"Authorization": f"Token {args.token}"}
    now_iso = datetime.now(UTC).isoformat()

    print(f"Target: {base}")  # noqa T201
    print(f"Subject: {args.subject}")  # noqa T201
    print()  # noqa T201

    # --- Step 0: Ping ---
    print("Step 0: Ping ...", end=" ", flush=True)  # noqa T201
    r = requests.get(f"{base}/ping/", headers=headers, timeout=10)
    if r.status_code == STATUS_OK:
        print(f"OK ({r.json()})")  # noqa T201
        if args.verbose:
            print(f"  Response: {json.dumps(r.json(), indent=2)}")  # noqa T201
    else:
        print(f"FAILED {r.status_code}: {r.text}")  # noqa T201
        sys.exit(1)

    # --- Step 1: Resolve ---
    print("Step 1: Resolve ...", end=" ", flush=True)  # noqa T201
    payload = {
        "subject_identifier": args.subject,
        "initials": args.initials,
        "sex": args.sex,
    }
    if args.age is not None:
        payload["age"] = args.age
    if args.device_id:
        payload["device_id"] = args.device_id
    if args.site_id:
        payload["site_id"] = args.site_id

    if args.verbose:
        print()  # noqa T201
        print(f"  Request:  POST {base}/resolve/")  # noqa T201
        print(f"  Payload:  {json.dumps(payload, indent=2)}")  # noqa T201

    r = requests.post(f"{base}/resolve/", json=payload, headers=headers, timeout=10)
    if r.status_code in (STATUS_OK, STATUS_CODE_CREATED):
        data = r.json()
        eye_exam_register_id = data["eye_exam_register_id"]
        reactivated = data.get("reactivated", False)
        label = "reactivated" if reactivated else "created"
        print(  # noqa T201
            f"OK — {data['subject_identifier']}, session {eye_exam_register_id} ({label})",
        )
        if args.verbose:
            print(f"  Response: {json.dumps(data, indent=2)}")  # noqa T201
    else:
        print(f"FAILED {r.status_code}: {r.text}")  # noqa T201
        if args.verbose:
            with contextlib.suppress(ValueError):
                print(f"  Response: {json.dumps(r.json(), indent=2)}")  # noqa T201
        sys.exit(1)

    # --- Step 2-4: Upload files ---
    uploads = [
        ("left", args.left_image, make_dummy_jpeg, "image/jpeg", "left_eye.jpg"),
        ("right", args.right_image, make_dummy_jpeg, "image/jpeg", "right_eye.jpg"),
        ("report", args.report, make_dummy_pdf, "application/pdf", "report.pdf"),
    ]

    for step, (file_type, real_path, dummy_fn, mime, default_name) in enumerate(
        uploads,
        start=2,
    ):
        print(f"Step {step}: Upload {file_type} ...", end=" ", flush=True)  # noqa T201

        if real_path and real_path.exists():
            file_data = real_path.read_bytes()
            filename = real_path.name
        else:
            if real_path:
                print(f"(file not found: {real_path}, using dummy) ", end="")  # noqa T201
            file_data = dummy_fn()
            filename = default_name

        form_data = {
            "capture_datetime": (None, now_iso),
        }
        files = {
            "file": (filename, file_data, mime),
        }

        if args.checksum:
            form_data["checksum"] = (None, sha256_bytes(file_data))

        url = f"{base}/{args.subject}/{file_type}/?eye_exam_register_id={eye_exam_register_id}"

        if args.verbose:
            print()  # noqa T201
            print(f"  Request:  POST {url}")  # noqa T201
            print(  # noqa T201
                f"  Fields:   capture_datetime={now_iso}, file={filename} "
                f"({len(file_data)} bytes, {mime})",
            )
            if args.checksum:
                print(f"  Checksum: {sha256_bytes(file_data)}")  # noqa T201

        r = requests.post(url, files=files, data=form_data, headers=headers, timeout=30)
        if r.status_code in (STATUS_OK, STATUS_CODE_CREATED):
            data = r.json()
            status_label = "new" if r.status_code == STATUS_CODE_CREATED else "replaced"
            print(f"OK — {data['stored_filename']} ({status_label})")  # noqa T201
            if args.verbose:
                print(f"  Response: {json.dumps(data, indent=2)}")  # noqa T201
        else:
            print(f"FAILED {r.status_code}: {r.text}")  # noqa T201
            if args.verbose:
                with contextlib.suppress(ValueError):
                    print(f"  Response: {json.dumps(r.json(), indent=2)}")  # noqa T201
            continue

    # --- Final: Check status ---
    print()  # noqa T201
    print("Session status ...", end=" ", flush=True)  # noqa T201
    status_url = f"{base}/{args.subject}/status/"
    r = requests.get(status_url, headers=headers, timeout=10)
    if r.status_code == STATUS_OK:
        data = r.json()
        print("OK")  # noqa T201
        print(f"  Subject:  {data['subject_identifier']}")  # noqa T201
        print(f"  Session:  {data['eye_exam_register_id']}")  # noqa T201
        print(f"  Uploaded: {data['uploaded']}")  # noqa T201
        print(f"  Missing:  {data['missing']}")  # noqa T201
        print(f"  Complete: {data['complete']}")  # noqa T201
        if args.verbose:
            print(f"  Response: {json.dumps(data, indent=2)}")  # noqa T201
    else:
        print(f"FAILED {r.status_code}: {r.text}")  # noqa T201

    print()  # noqa T201
    print("Done.")  # noqa T201


if __name__ == "__main__":
    main()
