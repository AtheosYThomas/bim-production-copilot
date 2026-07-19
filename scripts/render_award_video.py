"""Render the public 60-second award video only after every final Gate passes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import wave
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

NARRATION = (
    "Before thousands of BIM elements are modeled, which ones are actually ready? "
    "This role-separated agent workflow records traceable claims across an authorized plan, section, and structural detail. "
    "A separate readiness engine closes fourteen requirements. The matrix shows one thousand two hundred millimeter flight width "
    "from the architectural plan; four thousand two hundred floor height from its section; and one hundred fifty waist thickness "
    "from the structural detail. This is complementary closure; not every value is duplicated. The adjacent interface has no "
    "approved evidence: human clarification required. No evidence, no model. Only the ready item receives a controlled package in "
    "isolated Work. Independent checks follow. The stair passed thirty-four target checks, but full regression found five hundred "
    "eight non-target differences. The target was correct; integration was not. The Gate blocked promotion. After a Work-only repair, "
    "all two thousand three hundred thirty-four protected products matched. A separate read-only reviewer returned zero, zero, zero. "
    "The authority controller created a new revision; the original stayed unchanged. "
    "No agent can approve its own work."
)

ROLE_RESEARCH_SUBTITLE = (
    "One research role gathers traceable evidence across disciplines.\n"
    "A separate readiness engine decides what may proceed."
)
EVIDENCE_MATRIX_NOTE = "3 REPRESENTATIVE RECORDS SHOWN · 14 REQUIREMENTS EVALUATED"
RESULT_CARDS = [
    ("PROTECTED PRODUCTS", "0 / 2,334", "FULL-MODEL REGRESSION"),
    ("REGRESSION", "15 / 15 PASS", "REGRESSION GATE"),
    ("REVIEWER", "0 / 0 / 0", "READ-ONLY INDEPENDENT REVIEW"),
]


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
    image, draw = _base("00-08 / THE QUESTION", "Before thousands of BIM elements are modeled...", "Which ones are actually ready? Which are missing evidence? Which require coordination?")
    sources = [("ARCHITECTURAL", "PLAN"), ("STRUCTURAL", "DETAIL"), ("SECTION / DETAIL", "EVIDENCE")]
    for idx, (discipline, source_type) in enumerate(sources):
        x = 100 + idx * 580
        draw.rounded_rectangle((x, 390, x + 520, 790), 24, fill="white", outline="#A8B8B8", width=3)
        draw.text((x + 42, 455), discipline, font=_font(32, True), fill=INK)
        draw.text((x + 42, 545), source_type, font=_font(58, True), fill=GREEN)
        draw.text((x + 42, 700), "AUTHORIZED SOURCE", font=_font(23, True), fill=MONO)
    slides.append((image, 8))

    image, draw = _base("08-14 / ROLE-SEPARATED RESEARCH", "Separate roles decide what may proceed.", ROLE_RESEARCH_SUBTITLE)
    draw.rounded_rectangle((100, 350, 680, 855), 24, fill=INK)
    draw.text((155, 405), "EVIDENCE RESEARCH ROLE", font=_font(27, True), fill="#7FDEBF")
    draw.multiline_text((155, 495), "PLAN\nSTRUCTURE\nSECTION / DETAIL", font=_font(42, True), fill="white", spacing=18)
    draw.text((155, 770), "TRACEABLE CLAIMS", font=_font(22, True), fill="#9BB0B7")
    draw.text((740, 565), ">", font=_font(82, True), fill=GREEN)
    draw.rounded_rectangle((850, 350, 1820, 855), 24, fill="white", outline="#A8B8B8", width=3)
    draw.text((910, 405), "SEPARATE READINESS ENGINE", font=_font(27, True), fill=INK)
    draw.rounded_rectangle((910, 500, 1760, 620), 16, fill="#E0F1EA")
    draw.text((950, 540), "STAIR  /  14 OF 14  /  READY TO MODEL", font=_font(29, True), fill=GREEN)
    draw.rounded_rectangle((910, 655, 1760, 775), 16, fill="#F8E7D2")
    draw.text((950, 695), "INTERFACE  /  MISSING  /  HUMAN", font=_font(29, True), fill=AMBER)
    slides.append((image, 6))

    image, draw = _base("14-20 / REAL EVIDENCE MATRIX", "Cross-source evidence closes the bounded scope.", "Complementary requirement closure across authorized sources — not duplicate confirmation of every value.")
    columns = [(110, "REQUIREMENT"), (520, "AUTHORIZED SOURCE"), (1160, "ACCEPTED VALUE"), (1515, "DECISION")]
    draw.rounded_rectangle((100, 350, 1820, 840), 18, fill="white", outline="#A8B8B8", width=3)
    draw.rectangle((100, 350, 1820, 425), fill="#E4EAE6")
    for x, label in columns:
        draw.text((x, 375), label, font=_font(20, True), fill=MONO)
    rows = [
        ("FLIGHT WIDTH", "ARCHITECTURAL PLAN", "1,200 mm"),
        ("FLOOR HEIGHT", "ARCHITECTURAL SECTION", "4,200 mm"),
        ("WAIST THICKNESS", "STRUCTURAL DETAIL", "150 mm"),
    ]
    for idx, (requirement, source, value) in enumerate(rows):
        y = 445 + idx * 105
        if idx:
            draw.line((100, y - 20, 1820, y - 20), fill="#D7DEDA", width=2)
        draw.text((110, y), requirement, font=_font(25, True), fill=INK)
        draw.text((520, y), source, font=_font(25), fill=INK)
        draw.text((1160, y), value, font=_font(28, True), fill=INK)
        draw.text((1515, y), "ACCEPTED", font=_font(23, True), fill=GREEN)
    draw.text((110, 790), EVIDENCE_MATRIX_NOTE, font=_font(19, True), fill=MONO)
    draw.rounded_rectangle((100, 875, 1115, 965), 14, fill="#E0F1EA")
    draw.text((135, 905), "STAIR SCOPE  ·  14 / 14 CLOSED  ·  READY TO MODEL", font=_font(25, True), fill=GREEN)
    draw.rounded_rectangle((1145, 875, 1820, 965), 14, fill="#F8E7D2")
    draw.text((1180, 905), "INTERFACE  ·  NO APPROVED EVIDENCE  ·  HUMAN", font=_font(20, True), fill=AMBER)
    slides.append((image, 6))

    image, draw = _base("20-31 / CONTROLLED DISPATCH", "No evidence. No model.", "Only READY_TO_MODEL receives a bounded work package and isolated WORK access.")
    drawing_image = _contain(drawing, (100, 340, 770, 900))
    image.paste(drawing_image, (100, 340))
    draw.rounded_rectangle((825, 340, 1305, 900), 24, fill="#E0F1EA", outline=GREEN, width=3)
    draw.text((875, 400), "READY TO MODEL", font=_font(29, True), fill=GREEN)
    draw.multiline_text((875, 505), "CONTROLLED\nWORK PACKAGE", font=_font(48, True), fill=INK, spacing=12)
    draw.text((875, 725), "ISOLATED WORK ONLY", font=_font(25, True), fill=GREEN)
    draw.text((875, 790), "AUTHORITY: READ ONLY", font=_font(22, True), fill=MONO)
    draw.rounded_rectangle((1360, 340, 1820, 900), 24, fill="#2A1514")
    draw.text((1410, 400), "HUMAN CLARIFICATION", font=_font(25, True), fill="#F3A69B")
    draw.multiline_text((1410, 505), "NO PACKAGE\nNO IFC WRITE", font=_font(43, True), fill="white", spacing=15)
    draw.text((1410, 750), "ONE MINIMUM REQUEST", font=_font(21, True), fill="#D9A09A")
    slides.append((image, 11))

    image, draw = _base("31-44 / MODEL CROSS-CHECK", "The target passed. The integration failed.", "The modeler cannot approve its own result.")
    bim_image = _contain(bim, (100, 350, 780, 900))
    image.paste(bim_image, (100, 350))
    draw.rounded_rectangle((840, 350, 1270, 900), 24, fill="#E0F1EA", outline=GREEN, width=3)
    draw.text((890, 410), "TARGET AUDIT", font=_font(27, True), fill=INK)
    draw.text((890, 535), "34 / 34", font=_font(82, True), fill=GREEN)
    draw.text((890, 675), "PASS", font=_font(48, True), fill=GREEN)
    draw.rounded_rectangle((1325, 350, 1820, 900), 24, fill="#2A1514", outline=RED, width=4)
    draw.text((1375, 410), "FULL REGRESSION", font=_font(27, True), fill="#F3A69B")
    draw.text((1375, 505), "BLOCKED", font=_font(52, True), fill="white")
    draw.text((1375, 630), "508", font=_font(116, True), fill="#FF8E83")
    draw.text((1375, 780), "NON-TARGET DIFFERENCES", font=_font(21, True), fill="#D9A09A")
    slides.append((image, 13))

    image, draw = _base("44-54 / REPAIR + INDEPENDENT REVIEW", "The Gate blocked promotion. Every check reran.", "The shared context was repaired in isolated WORK only; the authority source remained unchanged.")
    for idx, (label, result, check_name) in enumerate(RESULT_CARDS):
        x = 100 + idx * 580
        draw.rounded_rectangle((x, 400, x + 520, 800), 24, fill="#E0F1EA", outline=GREEN, width=3)
        draw.text((x + 42, 455), label, font=_font(24, True), fill=INK)
        draw.text((x + 42, 570), result, font=_font(51, True), fill=GREEN)
        footer_font = _font(17 if len(check_name) > 24 else 21, True)
        draw.text((x + 42, 710), check_name, font=footer_font, fill=MONO)
    slides.append((image, 10))

    image, draw = _base("54-60 / CONTROLLED AUTHORITY", "WORK  ->  REVIEWED  ->  NEW REV", "Agents can research and model. No agent can approve its own work.")
    labels = [("WORK", "BOUNDED"), ("REVIEWED", "0 / 0 / 0"), (str(validation.get("new_rev") or "NEW REV"), "NEW PATH")]
    for idx, (label, sub) in enumerate(labels):
        x = 120 + idx * 600
        draw.rounded_rectangle((x, 430, x + 480, 760), 22, fill=INK if idx != 1 else GREEN)
        draw.text((x + 48, 510), label, font=_font(50, True), fill="white")
        draw.text((x + 48, 650), sub, font=_font(25, True), fill="#C7D4D8" if idx != 1 else "#D6F6EB")
        if idx < 2:
            draw.text((x + 530, 555), ">", font=_font(64, True), fill=GREEN)
    draw.text((100, 870), "ORIGINAL AUTHORITY SOURCE  /  UNCHANGED", font=_font(28, True), fill=GREEN)
    slides.append((image, 6))

    outputs: list[tuple[Path, int]] = []
    for idx, (slide, duration) in enumerate(slides, start=1):
        path = output_dir / f"slide-{idx:02d}.png"
        slide.save(path, format="PNG", optimize=True)
        outputs.append((path, duration))
    return outputs


def synthesize_narration(*, text: str, output: Path, voice: str = "Microsoft Zira Desktop") -> float:
    """Create a real spoken WAV track with the installed Windows speech engine."""
    if os.name != "nt":
        raise VideoGateError("automatic narration currently requires Windows System.Speech")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise VideoGateError("PowerShell is unavailable for narration synthesis")
    output.parent.mkdir(parents=True, exist_ok=True)
    text_path = output.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    environment = os.environ.copy()
    environment.update({
        "BIM_VIDEO_NARRATION_TEXT": str(text_path.resolve()),
        "BIM_VIDEO_NARRATION_WAV": str(output.resolve()),
        "BIM_VIDEO_VOICE": voice,
    })
    script = """
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voiceNames = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
if ($voiceNames -contains $env:BIM_VIDEO_VOICE) { $synth.SelectVoice($env:BIM_VIDEO_VOICE) }
$synth.Rate = 1
$synth.Volume = 100
$text = [System.IO.File]::ReadAllText($env:BIM_VIDEO_NARRATION_TEXT, [System.Text.Encoding]::UTF8)
$synth.SetOutputToWaveFile($env:BIM_VIDEO_NARRATION_WAV)
$synth.Speak($text)
$synth.Dispose()
"""
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if completed.returncode != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            raise VideoGateError(f"narration synthesis failed: {completed.stderr.strip()}")
    finally:
        text_path.unlink(missing_ok=True)
    with wave.open(str(output), "rb") as track:
        duration = track.getnframes() / float(track.getframerate())
    if duration < 10:
        output.unlink(missing_ok=True)
        raise VideoGateError("narration synthesis produced an invalid or effectively empty track")
    return duration


def render_video(*, slides: list[tuple[Path, int]], narration: Path, output: Path, ffmpeg: str) -> dict[str, Any]:
    if output.exists():
        raise VideoGateError("final video already exists; immutable output will not be overwritten")
    if not narration.is_file():
        raise VideoGateError("spoken narration track is missing")
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
        with wave.open(str(narration), "rb") as track:
            source_audio_seconds = track.getnframes() / float(track.getframerate())
        tempo = max(1.0, source_audio_seconds / 58.5)
        if tempo > 2.0:
            raise VideoGateError("narration is too long to fit the 60-second video")
        audio_filter = (
            f"atempo={tempo:.5f},highpass=f=70,lowpass=f=12000,"
            "volume=1.20,alimiter=limit=0.95,apad,atrim=duration=60"
        )
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-n", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-i", str(narration), "-vf", "fps=30,format=yuv420p", "-af", audio_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-t", "60",
            "-movflags", "+faststart", str(output),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            output.unlink(missing_ok=True)
            raise VideoGateError(f"ffmpeg failed: {completed.stderr.strip()}")
    finally:
        concat.unlink(missing_ok=True)
    return {
        "audio_content": "SPOKEN_ENGLISH_NARRATION",
        "voice": "Microsoft Zira Desktop",
        "source_audio_seconds": round(source_audio_seconds, 3),
        "tempo_adjustment": round(tempo, 5),
    }


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
        temp_dir = Path(temp)
        slides = compose_slides(workspace=args.workspace.resolve(), validation=validation, output_dir=temp_dir)
        narration = temp_dir / "spoken-narration.wav"
        synthesize_narration(text=NARRATION, output=narration)
        audio = render_video(slides=slides, narration=narration, output=args.output, ffmpeg=ffmpeg)
    print(json.dumps({**validation, **audio, "video": str(args.output), "duration_seconds": 60}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
