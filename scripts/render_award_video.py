"""Render the public 60-second award video only after every final Gate passes."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


class VideoGateError(RuntimeError):
    pass


WIDTH, HEIGHT = 1920, 1080
BG = "#F2EFE7"
INK = "#071C24"
GREEN = "#087D62"
AMBER = "#C0701A"
RED = "#B84035"
MONO = "#5E6A6E"


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise VideoGateError(f"required final artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_final_video_gates(
    *, review_path: Path, promotion_path: Path, readiness_index_path: Path, sanitization_report_path: Path
) -> dict[str, Any]:
    review = _read(review_path)
    promotion = _read(promotion_path)
    index = _read(readiness_index_path)
    public = _read(sanitization_report_path)
    counts = review.get("issue_counts", {})
    if review.get("status") != "PASS" or counts != {"B0": 0, "B1": 0, "B2": 0} or review.get("findings") != []:
        raise VideoGateError("independent review is not a verified 0/0/0 PASS")
    if review.get("review_policy") != "READ_ONLY":
        raise VideoGateError("independent review was not read-only")
    if promotion.get("status") != "PROMOTED_TO_NEW_AUTHORITY_REV":
        raise VideoGateError("controlled promotion record is missing or incomplete")
    if promotion.get("review_findings") != {"B0": 0, "B1": 0, "B2": 0}:
        raise VideoGateError("promotion is not bound to the 0/0/0 review")
    if promotion.get("source_authority_unchanged") is not True or promotion.get("overwrite_permitted") is not False:
        raise VideoGateError("promotion did not preserve the source authority")
    gates = promotion.get("gates", {})
    required_gate_values = {
        "readiness": "READY_TO_MODEL",
        "regression": "PASS",
        "non_target_difference": 0,
        "bonsai": "PASS",
        "independent_review": "0/0/0",
    }
    for name, expected in required_gate_values.items():
        if gates.get(name) != expected:
            raise VideoGateError(f"promotion Gate is not PASS: {name}")
    if public.get("result") != "PASS" or public.get("confidentiality_findings") != []:
        raise VideoGateError("public sanitization Gate did not pass")
    readiness_counts = index.get("counts", {})
    if index.get("real_project_item_count") != 2 or readiness_counts.get("READY_TO_MODEL") != 1:
        raise VideoGateError("readiness index does not match the verified two-item demonstration")
    if sum(int(readiness_counts.get(state, 0)) for state in (
        "READY_TO_MODEL", "CROSSCHECK_REQUIRED", "HUMAN_CLARIFICATION_REQUIRED", "COORDINATION_REQUIRED", "BLOCKED"
    )) != 2:
        raise VideoGateError("readiness counts are not exhaustive")
    return {
        "status": "FINAL_VIDEO_GATES_PASS",
        "review_findings": counts,
        "new_rev": promotion.get("new_authority", {}).get("rev"),
        "authority_source_unchanged": True,
        "readiness_counts": readiness_counts,
    }


def _font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _base(kicker: str, title: str, subtitle: str = ""):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 26), fill=GREEN)
    draw.text((100, 72), kicker.upper(), font=_font(30, True), fill=GREEN)
    draw.text((100, 130), title, font=_font(76, True), fill=INK)
    if subtitle:
        draw.multiline_text((104, 235), subtitle, font=_font(34), fill=MONO, spacing=14)
    draw.text((100, 1010), "BIM PRODUCTION COPILOT  /  AUTHORIZED REAL-PROJECT DEMO", font=_font(22, True), fill=MONO)
    return image, draw


def _contain(path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    source = Image.open(path).convert("RGB")
    target_w, target_h = box[2] - box[0], box[3] - box[1]
    source.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), "white")
    x = (target_w - source.width) // 2
    y = (target_h - source.height) // 2
    canvas.paste(source, (x, y))
    return canvas


def compose_slides(*, workspace: Path, validation: dict[str, Any], output_dir: Path) -> list[tuple[Path, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    drawing = workspace / "judge-ui/public/authorized-drawing-evidence.png"
    bim = workspace / "judge-ui/public/authorized-bim-oblique.png"
    blocked = workspace / "submission/screenshots/03-safe-block.png"
    for asset in (drawing, bim, blocked):
        if not asset.is_file():
            raise VideoGateError(f"approved public visual is missing: {asset}")

    slides: list[tuple[Image.Image, int]] = []
    image, draw = _base("00—07 / THE QUESTION", "What is actually safe to model?", "Before AI produces thousands of BIM elements, evidence must decide what may proceed — and why.")
    draw.rounded_rectangle((100, 430, 1820, 840), 26, fill=INK)
    draw.text((170, 520), "GOVERNANCE", font=_font(42, True), fill="#7FDEBF")
    draw.text((170, 590), "BEFORE GEOMETRY", font=_font(112, True), fill="white")
    draw.text((170, 735), "Authority BIM remains read-only.", font=_font(34), fill="#C7D4D8")
    slides.append((image, 7))

    image, draw = _base("07—18 / REAL READINESS", "Every item ends in exactly one state.")
    state_order = ["READY_TO_MODEL", "CROSSCHECK_REQUIRED", "HUMAN_CLARIFICATION_REQUIRED", "COORDINATION_REQUIRED", "BLOCKED"]
    colors = [GREEN, "#688393", AMBER, "#926B53", RED]
    for index, (state, color) in enumerate(zip(state_order, colors)):
        x = 100 + index * 350
        draw.rounded_rectangle((x, 330, x + 300, 810), 20, fill="white", outline=color, width=5)
        draw.text((x + 32, 370), state.replace("_", "\n"), font=_font(31, True), fill=INK, spacing=8)
        draw.text((x + 32, 650), str(validation["readiness_counts"].get(state, 0)), font=_font(104, True), fill=color)
    slides.append((image, 11))

    image, draw = _base("18—28 / SAFE FAILURE", "Missing evidence means no model is written.", "The product blocks unsafe work and returns one precise next action.")
    proof = ImageOps.fit(Image.open(blocked).convert("RGB"), (1040, 585), method=Image.Resampling.LANCZOS)
    image.paste(proof, (780, 330))
    draw.rounded_rectangle((100, 390, 690, 820), 24, fill="#2A1514")
    draw.text((160, 475), "NO MODEL", font=_font(72, True), fill="#FFD5CE")
    draw.text((160, 565), "WRITTEN", font=_font(72, True), fill="#FFD5CE")
    draw.text((160, 705), "WORK PACKAGE  /  NOT ISSUED", font=_font(25, True), fill="#F3A69B")
    slides.append((image, 10))

    image, draw = _base("28—40 / CONTROLLED PACKAGE", "Evidence closes the scope — not the authority BIM.")
    drawing_image = _contain(drawing, (100, 315, 920, 930))
    image.paste(drawing_image, (100, 315))
    draw.rounded_rectangle((1010, 315, 1820, 930), 24, fill="white", outline="#C9C8C0", width=3)
    facts = [("14", "accepted evidence records"), ("0", "unresolved assumptions"), ("1", "controlled work package"), ("ONLY", "isolated WORK modeling")]
    for idx, (value, label) in enumerate(facts):
        y = 360 + idx * 135
        draw.text((1080, y), value, font=_font(58, True), fill=GREEN)
        draw.text((1300, y + 12), label, font=_font(29), fill=INK)
    slides.append((image, 12))

    image, draw = _base("40—51 / ISOLATED WORK + GATES", "The candidate is tested before promotion.")
    bim_image = _contain(bim, (100, 315, 990, 920))
    image.paste(bim_image, (100, 315))
    gates = [("DATA", "34 / 34"), ("REGRESSION", "15 / 15"), ("NON-TARGET DIFF", "0 / 2,334"), ("BONSAI GUI", "PASS"), ("INDEPENDENT REVIEW", "0 / 0 / 0")]
    for idx, (label, result) in enumerate(gates):
        y = 330 + idx * 112
        draw.rounded_rectangle((1080, y, 1820, y + 84), 16, fill="#E0F1EA")
        draw.text((1120, y + 25), label, font=_font(27, True), fill=INK)
        draw.text((1660, y + 24), result, anchor="ra", font=_font(30, True), fill=GREEN)
    slides.append((image, 11))

    image, draw = _base("51—58 / CONTROLLED PROMOTION", "WORK  →  APPROVED  →  NEW REV", "Only the controlling authority role may promote. The prior authority source remains unchanged.")
    labels = [("WORK", "HASH LOCKED"), ("APPROVED", "REVIEW 0 / 0 / 0"), (str(validation.get("new_rev") or "NEW REV"), "NEW PATH — NO OVERWRITE")]
    for idx, (label, sub) in enumerate(labels):
        x = 120 + idx * 600
        draw.rounded_rectangle((x, 450, x + 480, 780), 22, fill=INK if idx != 1 else GREEN)
        draw.text((x + 50, 535), label, font=_font(54, True), fill="white")
        draw.text((x + 50, 665), sub, font=_font(25, True), fill="#C7D4D8" if idx != 1 else "#D6F6EB")
        if idx < 2:
            draw.text((x + 530, 575), "→", font=_font(64, True), fill=GREEN)
    slides.append((image, 7))

    image, draw = _base("58—60 / THE RULE", "AI can research and model.")
    draw.text((100, 385), "No agent can approve its own work.", font=_font(72, True), fill=GREEN)
    draw.text((100, 545), "Know what is safe to model before BIM production begins.", font=_font(44), fill=INK)
    slides.append((image, 2))

    outputs: list[tuple[Path, int]] = []
    for idx, (slide, duration) in enumerate(slides, start=1):
        path = output_dir / f"slide-{idx:02d}.png"
        slide.save(path, format="PNG", optimize=True)
        outputs.append((path, duration))
    return outputs


def render_video(*, slides: list[tuple[Path, int]], output: Path, ffmpeg: str) -> None:
    if output.exists():
        raise VideoGateError("final video already exists; immutable output will not be overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    concat = output.parent / f".{output.stem}-concat.txt"
    lines: list[str] = []
    for path, duration in slides:
        safe = str(path.resolve()).replace("'", "'\\''")
        lines.extend([f"file '{safe}'", f"duration {duration}"])
    safe_last = str(slides[-1][0].resolve()).replace("'", "'\\''")
    lines.append(f"file '{safe_last}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-n", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "128k", "-t", "60",
            "-movflags", "+faststart", str(output),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            output.unlink(missing_ok=True)
            raise VideoGateError(f"ffmpeg failed: {completed.stderr.strip()}")
    finally:
        concat.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--promotion", type=Path, required=True)
    parser.add_argument("--readiness-index", type=Path, required=True)
    parser.add_argument("--sanitization-report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validation = validate_final_video_gates(
        review_path=args.review,
        promotion_path=args.promotion,
        readiness_index_path=args.readiness_index,
        sanitization_report_path=args.sanitization_report,
    )
    if args.check:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0
    if not args.output:
        raise VideoGateError("--output is required unless --check is used")
    ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise VideoGateError("ffmpeg is unavailable") from exc
    with tempfile.TemporaryDirectory(prefix="bim-award-video-") as temp:
        slides = compose_slides(workspace=args.workspace.resolve(), validation=validation, output_dir=Path(temp))
        render_video(slides=slides, output=args.output, ffmpeg=ffmpeg)
    print(json.dumps({**validation, "video": str(args.output), "duration_seconds": 60}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
