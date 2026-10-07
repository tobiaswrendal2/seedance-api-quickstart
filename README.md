# Seedance API Quickstart — 2.0 Mini from $0.026/s, 2.5 from $0.0874/s (480p)

**ByteDance Seedance 2.0 and 2.5 are live on [ArgoLink](https://argolink.io/gh-seedance-api-quickstart)**: Seedance 2.5 from $0.0874/s, 15% below the official price, and the Seedance 2.0 family from $0.026/s (2.0 Mini), $0.042/s (2.0 Fast) and $0.053/s (2.0), about 25% below, all at 480p. Four models share one endpoint and one request shape, so switching is a change of `model`; this quickstart shows which one to pick, what each accepts and what the same job costs on each.

[Model coverage](#model-coverage) · [Which model](#which-model-should-you-use) · [Prices](#prices) · [Quick start](#quick-start) · [Per-model notes](#per-model-notes) · [FAQ](#faq)

<sub>Last checked: 2026-10-07 against the four model pages and the API guide's Seedance chapter.</sub>

## Model coverage

| Model ID | Clip length | Resolutions | First-frame ratio | References (images / videos / audio) | Audio alone | Edits video | From |
|---|---|---|---|---|---|---|---:|
| `seedance-2.5` | 4–30 s | 480p · 720p · 1080p | `adaptive` only | 30 / 10 / 10, 50 in total | yes | yes | $0.0874/s |
| `seedance-2.0` | 4–15 s | 480p · 720p · 1080p · 4K | `adaptive` or a fixed ratio | 9 / 3 / 3, 15 in total | no | no | $0.053/s |
| `seedance-2.0-fast` | 4–15 s | 480p · 720p | `adaptive` or a fixed ratio | 9 / 3 / 3, 15 in total | no | no | $0.042/s |
| `seedance-2.0-mini` | 4–15 s | 480p · 720p | `adaptive` or a fixed ratio | 9 / 3 / 3, 15 in total | no | no | $0.026/s |

What all four share: `POST /v1/videos/generations` → `GET /v1/videos/{request_id}` (`pending`, `done`, `failed`, `expired`) → `GET /v1/videos/{request_id}/content`; a prompt in every mode; text, first frame, first + last frame and reference modes; one 24 fps H.264 MP4 per request with a generated AAC soundtrack (`generate_audio: false` turns it off); no `seed` or `watermark`; media as HTTPS URLs; failed and expired jobs free.

## Which model should you use?

- **One clip longer than 15 seconds, more than 9 reference images, a song or voice as the only reference, or a change to footage you already have**: `seedance-2.5`. It is the only model that does any of these.
- **4K**: `seedance-2.0`, the only Seedance route that renders it ($0.58/s).
- **The lowest price, for drafts, storyboards and batches**: `seedance-2.0-mini`, $0.026/s at 480p.
- **The quickest preview**: `seedance-2.0-fast`, the Seedance model with the shortest turnaround.
- **A final 1080p clip of up to 15 s**: compare `seedance-2.0` at $0.28/s with `seedance-2.5` at $0.483/s.

A common split is drafting on 2.0 Mini at 480p, then rendering the keeper on 2.5 or 2.0 at full resolution with the same prompt.

## Prices

Per second of output without video input:

| Model | 480p | 720p | 1080p | 4K | Below the BytePlus list price |
|---|---:|---:|---:|---:|---|
| `seedance-2.5` | $0.0874 | $0.196 | $0.483 | — | 15% |
| `seedance-2.0` | $0.053 | $0.11 | $0.28 | $0.58 | 25% (27% at 720p) |
| `seedance-2.0-fast` | $0.042 | $0.091 | — | — | 25% |
| `seedance-2.0-mini` | $0.026 | $0.057 | — | — | 25–26% |

The rates are 85% (2.5) and 75% (2.0 family) of the BytePlus ModelArk list price, rounded to three and two significant figures, which is why 2.0 at 720p is $0.11 against $0.1512. The same 720p second elsewhere:

| 720p, no video input | ArgoLink | BytePlus list | Replicate | fal.ai |
|---|---:|---:|---:|---:|
| Seedance 2.5 | **$0.196** | $0.2311 | $0.2312 | $0.4730 |
| Seedance 2.0 | **$0.11** | $0.1512 | $0.18 | $0.3034 |
| Seedance 2.0 Fast | **$0.091** | $0.121 | $0.15 | $0.2419 |
| Seedance 2.0 Mini | **$0.057** | $0.0756 | $0.09 | $0.1547 |

<sub>Read 2026-10-07: [ArgoLink model pages](https://argolink.io/en/models/seedance-2.5), [BytePlus ModelArk pricing](https://docs.byteplus.com/en/docs/modelark/model-pricing) (token prices for a 16:9 frame; BytePlus has run time-limited, enterprise-only discounts on 2.0 Fast and Mini that are not shown), Replicate's [2.5](https://replicate.com/bytedance/seedance-2.5), [2.0](https://replicate.com/bytedance/seedance-2.0), [2.0 Fast](https://replicate.com/bytedance/seedance-2.0-fast) and [2.0 Mini](https://replicate.com/bytedance/seedance-2.0-mini) pages, and fal's [2.5](https://fal.ai/models/bytedance/seedance-2.5/text-to-video), [2.0](https://fal.ai/models/bytedance/seedance-2.0/text-to-video), [2.0 Fast](https://fal.ai/models/bytedance/seedance-2.0/fast/text-to-video) and [2.0 Mini](https://fal.ai/models/bytedance/seedance-2.0/mini/text-to-video) pages.</sub>

Billing is the same on all four: the output's seconds plus any reference videos' seconds (fractions dropped), times the rate of the resolution. Reference images, audio and uploads are free, and a request without `duration` bills 5 seconds.

## Quick start

You need a key from [argolink.io/app/keys](https://argolink.io/app/keys), `curl` and `jq`, and Python 3.9+ for the helper script (standard library only).

```bash
git clone https://github.com/tobiaswrendal2/seedance-api-quickstart
cd seedance-api-quickstart
export SEEDANCE_API_KEY=your-key
```

### 1. List the Seedance models (no key needed)

```bash
curl -s https://argolink.io/v1/models | jq -r '.data[].id | select(startswith("seedance"))'
# seedance-2.0-fast
# seedance-2.0
# seedance-2.0-mini
# seedance-2.5
```

### 2. Price the job on each model

```bash
python seedance.py compare -d 10 -r 720p
# 10 s at 720p (rates checked 2026-10-07):
#   seedance-2.5       $1.9600
#   seedance-2.0       $1.1000
#   seedance-2.0-fast  $0.9100
#   seedance-2.0-mini  $0.5700
```

`--ref-seconds 3.5` adds a reference video; models that cannot run the job (too long, no such resolution) are marked.

### 3. Upload local files (only if you have them)

```bash
FILE=./logo.png
TICKET=$(curl -fsS https://argolink.io/v1/media/uploads \
  -H "Authorization: Bearer $SEEDANCE_API_KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"seedance-2.5\",\"type\":\"image\",\"content_type\":\"image/png\",\"size_bytes\":$(wc -c < "$FILE" | tr -d ' ')}")
curl -fsS -X PUT "$(jq -r .upload_url <<<"$TICKET")" -H "Content-Type: image/png" --data-binary @"$FILE"
jq -r .media_url <<<"$TICKET"   # use it as start_image.url; it stays readable for seven days
```

The API guide's own example requests the ticket as `seedance-2.5` and uses the `media_url` in a `seedance-2.0-mini` job, as here. Tickets are free and create no job.

### 4. Create the job

The body is the same for every model; only the limits differ.

```bash
curl -fsS https://argolink.io/v1/videos/generations \
  -H "Authorization: Bearer $SEEDANCE_API_KEY" -H "Content-Type: application/json" \
  -d '{"model": "seedance-2.0-mini", "prompt": "A paper plane glides across a sunlit desk", "duration": 5, "resolution": "720p"}'
# {"request_id": "…"}  (HTTP 202)
```

### 5. Poll and download

```bash
curl -fsS https://argolink.io/v1/videos/$REQUEST_ID -H "Authorization: Bearer $SEEDANCE_API_KEY" | jq '{status, progress}'
curl -fsSL https://argolink.io/v1/videos/$REQUEST_ID/content -H "Authorization: Bearer $SEEDANCE_API_KEY" -o plane.mp4
```

Poll every 10–15 seconds until `status` is `done`. Or let a script do steps 4 and 5 for any body in [`examples/`](./examples):

```bash
./examples/run.sh examples/seedance-2.0-mini-draft.json logo.mp4
python seedance.py run seedance-2.0-fast "A tram crosses a rainy bridge at dusk" -d 6 -r 480p -o tram.mp4
```

## Same request, different limits

| Field | `seedance-2.5` | `seedance-2.0` | `seedance-2.0-fast`, `-mini` |
|---|---|---|---|
| `duration` | 4–30 | 4–15 | 4–15 |
| `resolution` | `480p`, `720p`, `1080p` | adds `1080p` and `4k` to 480p/720p | `480p`, `720p` |
| `aspect_ratio` with `start_image` | `adaptive` only | `adaptive` or a fixed ratio, which crops the frame | as 2.0 |
| `reference_images` | up to 30 | up to 9 | up to 9 |
| `reference_videos` | up to 10; 2–30 s each, 30 s total; MP4/MOV ≤ 100 MiB | up to 3; 2–15 s each, 15 s total; ≤ 50 MB | as 2.0 |
| `reference_audios` | up to 10; may be the only reference | up to 3; needs an image or a video beside it | as 2.0 |
| `omni_reference_task_type: "edit"` | edits one 4–30 s video | rejected | rejected |
| `size` (`WIDTHxHEIGHT`) | short side 480, 720 or 1080 | also 2160 for 4K | 480 or 720 |

`python seedance.py check BODY.json` applies these rules for the body's model before you spend a request.

## Per-model notes

### `seedance-2.5`

The newest generation and the only one with 30-second clips, 50 references, audio-only references and video editing. Frame jobs follow the first frame (`adaptive`). An edit keeps the source's length and ratio and bills the source twice, as output and as reference: an 8-second edit at 1080p bills 16 s, $7.73. Examples: [audio-only reference, 20 s](./examples/seedance-2.5-audio-only.json), [edit](./examples/seedance-2.5-edit.json).

### `seedance-2.0`

The sharpest 2.0 model and the only 4K route, at $0.58/s. In frame modes it also takes a fixed ratio and crops the first frame to it. Example: [6 s of 4K between two frames](./examples/seedance-2.0-4k-frames.json), which bills 6 × $0.58 = $3.48.

### `seedance-2.0-fast`

The quickest Seedance turnaround, for previewing an idea before a full render; 480p and 720p. Example: [a reference-image and song preview](./examples/seedance-2.0-fast-preview.json). Reference audio on a 2.0 model needs an image or a video next to it, which is why this one sends both.

### `seedance-2.0-mini`

The lowest per-second price of any Seedance model: a 5-second 480p draft costs $0.13. Same inputs as 2.0, 480p and 720p. Example: [a first-frame logo draft](./examples/seedance-2.0-mini-draft.json).

## Errors you meet when switching models

A body that is valid for one model can be refused by another. The submit call answers `400` with `request_unsupported` and a message that names the cause, for example `seedance-2.0-mini does not support video resolution 1080p`. The usual ones:

| Sent to a 2.0 model | Why it fails |
|---|---|
| `duration` above 15 | the 2.0 family stops at 15 s |
| `reference_audios` without images or videos | 2.0 needs a visual reference beside audio |
| `omni_reference_task_type: "edit"` | only 2.5 edits video |
| more than 9 images, 3 videos or 3 audio clips | 2.0 limits |
| `1080p` or `4k` on Fast or Mini | they render 480p and 720p |

Nothing is charged for a rejected request, or for a job that later ends `failed` or `expired`.

## The helper script

| Command | What it does |
|---|---|
| `python seedance.py models` | each model's limits and starting price, plus the live list from `/v1/models` |
| `python seedance.py compare -d N -r RES [--ref-seconds S]` | the same job priced on every model, offline |
| `python seedance.py check BODY.json` | the per-model rules above; exit code 1 on a problem |
| `python seedance.py run MODEL "PROMPT" [-d N] [-r RES] [-a RATIO] [-o FILE]` | submit, poll every 12 s, download |
| `python seedance.py run --body BODY.json [-o FILE]` | the same for a JSON body |

It sends its own `User-Agent` header: the API's Cloudflare front answers urllib's default `Python-urllib/3.x` agent with `403` (error code 1010), so do the same in your own urllib code.

## FAQ

**Is Seedance 2.5 better than Seedance 2.0?**
It does more: clips up to 30 s instead of 15, more than three times the reference images, audio-only references and video editing. Seedance 2.0 still renders 4K, which 2.5 does not, and costs less per second at every shared resolution.

**Can I switch models without changing code?**
Yes. Every model takes the same fields at the same endpoint and returns the same job object, so only `model` changes, as long as the request fits the new model's limits (see the table above).

**What is the cheapest way to try Seedance?**
`seedance-2.0-mini` at 480p for 4 seconds: 4 × $0.026 = $0.104. On Seedance 2.5 the cheapest clip is 4 × $0.0874 ≈ $0.35.

**How long does a job take?**
For Seedance 2.5, about 2–5 minutes for a 4–10 second clip; the 2.0 models also usually finish in a few minutes, Fast the soonest. A busy queue makes any of them slower, so poll instead of assuming a deadline.

**Which Seedance model supports 4K?**
Only `seedance-2.0`, at $0.58/s. Seedance 2.5 tops out at 1080p.

**Is the API stable?**
Yes. A job that cannot find capacity within 10 minutes fails with the retryable code `capacity_unavailable` and is not billed, so clients never wait on a job that will not start.

## Tests

```bash
pip install pytest
pytest
```

28 offline tests: the per-model rules (including that every body in `examples/` passes), the prices and rounding rule, and the submit, poll and download flow against a fake HTTP layer.

## License

MIT. Seedance is a ByteDance model; this repository is not affiliated with ByteDance.
