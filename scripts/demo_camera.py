#!/usr/bin/env python
"""Simulate the retinopathy camera's 4-step workflow against a live server.

Usage:
    python demo_camera.py --host https://edc.example.com --token YOUR_TOKEN \
        --subject 105-10-0001-2 --initials JD --sex M --age 35

    # Minimal (uses defaults for optional fields):
    python demo_camera.py --host http://localhost:8000 --token abc123 \  # ggignore
        --subject 105-10-0001-2 --initials JD --sex M

    # With real image files:
    python demo_camera.py --host http://localhost:8000 --token abc123 \  # ggignore
        --subject 105-10-0001-2 --initials JD --sex M \
        --left-image /path/to/left.jpg \
        --right-image /path/to/right.jpg \
        --report /path/to/report.pdf
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate the retinopathy camera workflow"
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
        "--checksum", action="store_true", help="Send SHA-256 checksums"
    )
    args = parser.parse_args()

    base = args.host.rstrip("/") + "/api/retinopathy"
    headers = {"Authorization": f"Token {args.token}"}
    now_iso = datetime.now(timezone.utc).isoformat()

    print(f"Target: {base}")
    print(f"Subject: {args.subject}")
    print()

    # --- Step 0: Ping ---
    print("Step 0: Ping ...", end=" ", flush=True)
    r = requests.get(f"{base}/ping/", headers=headers, timeout=10)
    if r.status_code == 200:
        print(f"OK ({r.json()})")
    else:
        print(f"FAILED {r.status_code}: {r.text}")
        sys.exit(1)

    # --- Step 1: Resolve ---
    print("Step 1: Resolve ...", end=" ", flush=True)
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

    r = requests.post(
        f"{base}/resolve/", json=payload, headers=headers, timeout=10
    )
    if r.status_code in (200, 201):
        data = r.json()
        session_id = data["session_id"]
        reactivated = data.get("reactivated", False)
        label = "reactivated" if reactivated else "created"
        print(f"OK — session {session_id} ({label})")
    else:
        print(f"FAILED {r.status_code}: {r.text}")
        sys.exit(1)

    # --- Step 2-4: Upload files ---
    uploads = [
        ("left", args.left_image, make_dummy_jpeg, "image/jpeg", "left_eye.jpg"),
        ("right", args.right_image, make_dummy_jpeg, "image/jpeg", "right_eye.jpg"),
        ("report", args.report, make_dummy_pdf, "application/pdf", "report.pdf"),
    ]

    for step, (file_type, real_path, dummy_fn, mime, default_name) in enumerate(
        uploads, start=2
    ):
        print(f"Step {step}: Upload {file_type} ...", end=" ", flush=True)

        if real_path and real_path.exists():
            file_data = real_path.read_bytes()
            filename = real_path.name
        else:
            if real_path:
                print(f"(file not found: {real_path}, using dummy) ", end="")
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

        url = f"{base}/{args.subject}/{file_type}/?session_id={session_id}"
        r = requests.post(
            url, files=files, data=form_data, headers=headers, timeout=30
        )
        if r.status_code in (200, 201):
            data = r.json()
            status_label = "new" if r.status_code == 201 else "already exists"
            print(
                f"OK — {data['stored_filename']} ({status_label})"
            )
        else:
            print(f"FAILED {r.status_code}: {r.text}")
            continue

    # --- Final: Check status ---
    print()
    print("Session status ...", end=" ", flush=True)
    r = requests.get(
        f"{base}/{args.subject}/status/", headers=headers, timeout=10
    )
    if r.status_code == 200:
        data = r.json()
        print(f"OK")
        print(f"  Session:  {data['session_id']}")
        print(f"  Uploaded: {data['uploaded']}")
        print(f"  Missing:  {data['missing']}")
        print(f"  Complete: {data['complete']}")
    else:
        print(f"FAILED {r.status_code}: {r.text}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
