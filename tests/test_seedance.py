"""Offline tests for seedance.py: per-model rules, prices, and the HTTP flow against a
fake opener. No key, network or job is involved.

    pip install pytest
    pytest
"""
import io
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import seedance  # noqa: E402

IMG = {"url": "https://example.com/a.png"}
VID = {"url": "https://example.com/a.mp4"}
AUD = {"url": "https://example.com/a.mp3"}


def body(model, **fields):
    return {"model": model, "prompt": "a lighthouse in a storm", **fields}


@pytest.mark.parametrize("path", sorted((ROOT / "examples").glob("*.json")), ids=lambda p: p.name)
def test_every_example_body_is_valid_for_its_model(path):
    assert seedance.problems(json.loads(path.read_text())) == []


@pytest.mark.parametrize("request_body, fragment", [
    (body("seedance-2.0", duration=16), "4-15"),
    (body("seedance-2.5", duration=31), "4-30"),
    (body("seedance-2.0-fast", resolution="1080p"), "does not support 1080p"),
    (body("seedance-2.0-mini", resolution="4k"), "does not support 4k"),
    (body("seedance-2.5", resolution="4k"), "does not support 4k"),
    (body("seedance-2.0", reference_audios=[AUD]), "needs an image or a video"),
    (body("seedance-2.0", reference_images=[IMG] * 10), "up to 9 reference images"),
    (body("seedance-2.0-mini", omni_reference_task_type="edit", reference_videos=[VID]), "only seedance-2.5"),
    (body("seedance-2.5", start_image=IMG, aspect_ratio="16:9"), "use adaptive"),
    (body("seedance-2.5", aspect_ratio="adaptive"), "not accepted"),
    (body("seedance-2.0", start_image=IMG, reference_images=[IMG]), "cannot be combined"),
    (body("seedance-2.5", seed=3), "seed"),
    (body("seedance-3.0"), "unknown model"),
])
def test_rules_differ_by_model(request_body, fragment):
    assert any(fragment in problem for problem in seedance.problems(request_body)), seedance.problems(request_body)


@pytest.mark.parametrize("request_body", [
    body("seedance-2.0", start_image=IMG, aspect_ratio="16:9", resolution="4k"),  # 2.0 frames may crop to a fixed ratio
    body("seedance-2.5", reference_audios=[AUD]),                                 # 2.5 takes audio on its own
    body("seedance-2.0", reference_images=[IMG] * 9, reference_videos=[VID] * 3, reference_audios=[AUD] * 3),
    body("seedance-2.5", omni_reference_task_type="edit", reference_videos=[VID]),
])
def test_documented_differences_are_accepted(request_body):
    assert seedance.problems(request_body) == []


def test_the_same_job_priced_on_each_model():
    costs = {name: seedance.price(name, "720p", 10) for name in seedance.MODELS}
    assert costs == {"seedance-2.5": 1.96, "seedance-2.0": 1.1, "seedance-2.0-fast": 0.91, "seedance-2.0-mini": 0.57}


def test_reference_video_seconds_are_billed_without_fractions():
    # documented example: 5 s of 720p seedance-2.0 with a 3 s reference video bills 8 s, $0.88
    assert seedance.billed_seconds(5, 3) == 8 and seedance.price("seedance-2.0", "720p", 5, 3) == 0.88
    assert seedance.billed_seconds(5, 2.4) == 7


def test_rates_follow_the_published_rounding_rule():
    # API guide: 85% of the BytePlus list price for seedance-2.5, rounded to three significant
    # figures; 75% for the 2.0 family, rounded to two (so 720p 2.0 is $0.11, 27% under $0.1512)
    for name, spec in seedance.MODELS.items():
        share, figures = (0.85, 3) if name == "seedance-2.5" else (0.75, 2)
        for tier, rate in spec.rates.items():
            assert rate == float(f"{spec.official[tier] * share:.{figures}g}"), (name, tier)


class FakeOpener:
    def __init__(self, answers):
        self.answers, self.requests = list(answers), []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        return io.BytesIO(self.answers.pop(0))


def test_submit_poll_and_download(tmp_path):
    opener = FakeOpener([
        b'{"request_id": "r1"}',
        b'{"request_id": "r1", "status": "pending", "progress": 30}',
        b'{"request_id": "r1", "status": "done", "usage": {"billed_seconds": 5}}',
        b"MP4BYTES",
    ])
    api = seedance.Api(api_key="k", base_url="https://api.test/v1", opener=opener, sleep=lambda s: None)
    request_id = api.submit(body("seedance-2.0-mini", duration=5))
    job = api.wait(request_id)
    api.download(request_id, str(tmp_path / "out.mp4"))

    submit = opener.requests[0]
    assert submit.full_url == "https://api.test/v1/videos/generations"
    assert json.loads(submit.data)["model"] == "seedance-2.0-mini"
    assert submit.get_header("Authorization") == "Bearer k"
    assert submit.get_header("User-agent").startswith("seedance-api-quickstart/")  # urllib's default agent gets a 403
    assert [r.full_url.rsplit("/v1", 1)[1] for r in opener.requests[1:]] == ["/videos/r1", "/videos/r1", "/videos/r1/content"]
    assert job["usage"]["billed_seconds"] == 5
    assert (tmp_path / "out.mp4").read_bytes() == b"MP4BYTES"


def test_a_failed_job_raises_with_its_error():
    opener = FakeOpener([b'{"request_id": "r2", "status": "failed", "error": {"code": "capacity_unavailable", "retryable": true}}'])
    api = seedance.Api(api_key="k", base_url="https://api.test/v1", opener=opener, sleep=lambda s: None)
    with pytest.raises(RuntimeError, match="capacity_unavailable"):
        api.wait("r2")


def test_run_refuses_an_invalid_body_before_any_request(monkeypatch, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(body("seedance-2.0-fast", resolution="1080p")))
    monkeypatch.setenv("SEEDANCE_API_KEY", "k")
    with pytest.raises(SystemExit) as exited:
        seedance.main(["run", "--body", str(bad)])
    assert "refusing to send" in str(exited.value)
