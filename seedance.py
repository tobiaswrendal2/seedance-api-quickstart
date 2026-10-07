#!/usr/bin/env python3
"""One script for the four Seedance video models that share POST /v1/videos/generations.

    python seedance.py models                         # what each model takes, and the live model list
    python seedance.py compare -d 10 -r 720p          # the same job priced on every model
    python seedance.py check examples/seedance-2.5-edit.json
    python seedance.py run seedance-2.0-mini "A paper plane glides over a desk" -d 5 -o plane.mp4
    python seedance.py run --body examples/seedance-2.0-4k-frames.json -o skyline.mp4

Standard library only, Python 3.9+. Limits and prices come from the model pages and the
API guide (https://argolink.io/en/docs#/seedance), checked 2026-10-07.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

BASE_URL = os.environ.get("SEEDANCE_BASE_URL", "https://argolink.io/v1").rstrip("/")
FIXED_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
CHECKED = "2026-10-07"
# The API sits behind Cloudflare, which answers 403 (error 1010) to urllib's default
# "Python-urllib/3.x" User-Agent, so every request names its client.
USER_AGENT = "seedance-api-quickstart/1.0 (+https://github.com/tobiaswrendal2/seedance-api-quickstart)"


@dataclass(frozen=True)
class Spec:
    """What one Seedance model accepts and what a second of it costs (USD, no video input)."""

    max_seconds: int
    rates: Dict[str, float]
    official: Dict[str, float]
    images: int
    videos: int
    audios: int
    frame_ratios: Tuple[str, ...]
    audio_only: bool
    edits: bool
    best_for: str

    @property
    def max_assets(self) -> int:
        return self.images + self.videos + self.audios


TWO_O_LIMITS = dict(max_seconds=15, images=9, videos=3, audios=3,
                    frame_ratios=("adaptive",) + FIXED_RATIOS, audio_only=False, edits=False)

MODELS: Dict[str, Spec] = {
    "seedance-2.5": Spec(
        max_seconds=30, images=30, videos=10, audios=10, frame_ratios=("adaptive",), audio_only=True, edits=True,
        rates={"480p": 0.0874, "720p": 0.196, "1080p": 0.483},
        official={"480p": 0.1028, "720p": 0.2311, "1080p": 0.5686},
        best_for="long clips, big reference sets, editing existing video",
    ),
    "seedance-2.0": Spec(
        **TWO_O_LIMITS,
        rates={"480p": 0.053, "720p": 0.11, "1080p": 0.28, "4k": 0.58},
        official={"480p": 0.0703, "720p": 0.1512, "1080p": 0.3742, "4k": 0.7691},
        best_for="the only 4K route; top 2.0 quality",
    ),
    "seedance-2.0-fast": Spec(
        **TWO_O_LIMITS,
        rates={"480p": 0.042, "720p": 0.091}, official={"480p": 0.0562, "720p": 0.121},
        best_for="fastest turnaround, previews",
    ),
    "seedance-2.0-mini": Spec(
        **TWO_O_LIMITS,
        rates={"480p": 0.026, "720p": 0.057}, official={"480p": 0.0352, "720p": 0.0756},
        best_for="lowest price, drafts and batches",
    ),
}


def problems(body: dict) -> List[str]:
    """Rules the documented API would reject for this model; [] when the body looks valid."""
    model = body.get("model")
    spec = MODELS.get(model)
    if spec is None:
        return [f"unknown model {model!r}; use one of {', '.join(MODELS)}"]
    out: List[str] = []
    if not str(body.get("prompt", "")).strip():
        out.append("prompt is required in every mode")
    edit = body.get("omni_reference_task_type") == "edit"
    if edit and not spec.edits:
        out.append(f"{model} cannot edit video; only seedance-2.5 can")
    frames = "start_image" in body or "end_image" in body
    counts = [len(body.get(name) or []) for name in ("reference_images", "reference_videos", "reference_audios")]

    duration = body.get("duration")
    if edit:
        if duration not in (None, -1):
            out.append("an edit keeps its source length: leave duration out")
    elif duration is not None and not (isinstance(duration, int) and not isinstance(duration, bool)
                                       and 4 <= duration <= spec.max_seconds):
        out.append(f"{model} takes 4-{spec.max_seconds} whole seconds")
    resolution = body.get("resolution", "720p")
    if resolution not in spec.rates:
        out.append(f"{model} does not support {resolution}; it renders {', '.join(spec.rates)}")
    ratio = body.get("aspect_ratio")
    if ratio is not None:
        allowed = spec.frame_ratios if frames else ("adaptive",) if edit else FIXED_RATIOS
        if ratio not in allowed:
            out.append(f"aspect_ratio {ratio!r} is not accepted here; use {', '.join(allowed)}")
    if "end_image" in body and "start_image" not in body:
        out.append("end_image needs start_image")
    if frames and any(counts):
        out.append("frames and reference lists cannot be combined")
    for count, limit, kind in zip(counts, (spec.images, spec.videos, spec.audios), ("images", "videos", "audio clips")):
        if count > limit:
            out.append(f"{model} takes up to {limit} reference {kind}, not {count}")
    if sum(counts) > spec.max_assets:
        out.append(f"{model} takes up to {spec.max_assets} references in total")
    if counts[2] and not (counts[0] or counts[1]) and not spec.audio_only:
        out.append(f"{model} needs an image or a video next to reference audio")
    if "seed" in body or body.get("watermark") is True or body.get("n", 1) != 1:
        out.append("seed, watermark: true and n > 1 are not supported")
    return out


def billed_seconds(duration: float, reference_video_seconds: float = 0.0) -> int:
    """Output rounded to whole seconds, plus reference-video seconds with fractions dropped."""
    return int(math.floor(duration + 0.5)) + int(math.floor(reference_video_seconds))


def price(model: str, resolution: str, duration: float, reference_video_seconds: float = 0.0) -> float:
    return round(billed_seconds(duration, reference_video_seconds) * MODELS[model].rates[resolution], 4)


class Api:
    """The three video calls plus uploads. ``opener`` is replaceable for tests."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = BASE_URL,
                 opener: Callable = urllib.request.urlopen, sleep: Callable = time.sleep):
        self.key = api_key or os.environ.get("SEEDANCE_API_KEY")
        if not self.key:
            sys.exit("set SEEDANCE_API_KEY (create a key at https://argolink.io/app/keys)")
        self.base, self.opener, self.sleep = base_url.rstrip("/"), opener, sleep

    def call(self, method: str, path: str, payload: Optional[dict] = None, raw: bool = False):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Authorization": f"Bearer {self.key}", "User-Agent": USER_AGENT})
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self.opener(request, timeout=120) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path}: HTTP {error.code} {detail[:300]}") from None
        return body if raw else json.loads(body)

    def submit(self, body: dict) -> str:
        return self.call("POST", "/videos/generations", body)["request_id"]

    def wait(self, request_id: str, every: float = 12.0) -> dict:
        while True:
            job = self.call("GET", f"/videos/{request_id}")
            if job["status"] == "done":
                return job
            if job["status"] in ("failed", "expired"):
                raise RuntimeError(f"{request_id} {job['status']}: {json.dumps(job.get('error'))}")
            print(f"  {job.get('progress', 0)}%", file=sys.stderr)
            self.sleep(every)

    def download(self, request_id: str, path: str) -> None:
        with open(path, "wb") as handle:
            handle.write(self.call("GET", f"/videos/{request_id}/content", raw=True))


def cmd_models(_args) -> None:
    print(f"{'model':18} {'seconds':>7}  {'resolutions':22} {'refs (img/vid/aud)':18} {'from':>8}  best for")
    for name, spec in MODELS.items():
        refs = f"{spec.images}/{spec.videos}/{spec.audios}"
        cheapest = min(spec.rates.values())
        print(f"{name:18} {'4-' + str(spec.max_seconds):>7}  {', '.join(spec.rates):22} {refs:18} "
              f"${cheapest:<7}  {spec.best_for}")
    try:
        request = urllib.request.Request(f"{BASE_URL}/models", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=20) as response:
            live = [m["id"] for m in json.load(response)["data"] if m["id"].startswith("seedance")]
        print("\nlive on", BASE_URL + "/models:", ", ".join(live))
    except OSError as error:
        print(f"\n(could not read {BASE_URL}/models: {error})")


def cmd_compare(args) -> None:
    print(f"{args.duration} s at {args.resolution}"
          + (f" with {args.ref_seconds} s of reference video" if args.ref_seconds else "")
          + f" (rates checked {CHECKED}):")
    for name, spec in MODELS.items():
        if args.resolution not in spec.rates:
            print(f"  {name:18} -  (no {args.resolution})")
        elif args.duration > spec.max_seconds:
            print(f"  {name:18} -  (max {spec.max_seconds} s)")
        else:
            cost = price(name, args.resolution, args.duration, args.ref_seconds)
            print(f"  {name:18} ${cost:.4f}")


def cmd_check(args) -> None:
    with open(args.body) as handle:
        found = problems(json.load(handle))
    print("\n".join(found) if found else "ok")
    sys.exit(1 if found else 0)


def cmd_run(args) -> None:
    if args.body:
        with open(args.body) as handle:
            body = json.load(handle)
    else:
        if not args.model or not args.prompt:
            sys.exit("give a model and a prompt, or --body FILE")
        body = {"model": args.model, "prompt": args.prompt, "duration": args.duration,
                "resolution": args.resolution, "aspect_ratio": args.aspect_ratio}
    found = problems(body)
    if found:
        sys.exit("refusing to send: " + "; ".join(found))
    api = Api()
    request_id = api.submit(body)
    print(f"submitted {request_id} ({body['model']})", file=sys.stderr)
    job = api.wait(request_id)
    api.download(request_id, args.output)
    print(f"saved {args.output}; billed {job['usage']['billed_seconds']} s")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Seedance 2.0 / 2.0 Fast / 2.0 Mini / 2.5 quickstart")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="limits per model and the live model list").set_defaults(func=cmd_models)
    compare = sub.add_parser("compare", help="price one job on every model")
    compare.add_argument("-d", "--duration", type=int, default=5)
    compare.add_argument("-r", "--resolution", default="720p")
    compare.add_argument("--ref-seconds", type=float, default=0.0, help="total reference-video seconds")
    compare.set_defaults(func=cmd_compare)
    check = sub.add_parser("check", help="validate a JSON body for its model")
    check.add_argument("body")
    check.set_defaults(func=cmd_check)
    run = sub.add_parser("run", help="submit, wait and download")
    run.add_argument("model", nargs="?", choices=list(MODELS))
    run.add_argument("prompt", nargs="?")
    run.add_argument("-d", "--duration", type=int, default=5)
    run.add_argument("-r", "--resolution", default="720p")
    run.add_argument("-a", "--aspect-ratio", default="16:9")
    run.add_argument("--body", help="send this JSON file instead")
    run.add_argument("-o", "--output", default="seedance.mp4")
    run.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
