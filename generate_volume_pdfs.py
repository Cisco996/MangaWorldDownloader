#!/usr/bin/env python3
"""Generic script to convert downloaded manga chapters or volumes into PDF / CBZ files.

Scans the Downloads directory (or a specified folder), detects manga structures
(Volume folders, Chapter folders, or raw images), and compiles them into clean,
properly ordered PDF or CBZ files.

Works seamlessly on Windows, macOS, and Linux.
"""

# pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements,broad-exception-caught

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Sequence

from PIL import Image, UnidentifiedImageError

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

# Known volume mappings (optional presets for specific manga)
DEFAULT_KNOWN_MAPPINGS: dict[str, list[tuple[int, int, int]]] = {
    "vagabond": [
        (1, 1, 10),
        (2, 11, 21),
        (3, 22, 31),
        (4, 32, 40),
        (5, 41, 49),
        (6, 50, 59),
        (7, 60, 68),
        (8, 69, 78),
        (9, 79, 87),
        (10, 88, 97),
        (11, 98, 107),
        (12, 108, 117),
        (13, 118, 127),
        (14, 128, 136),
        (15, 137, 143),
        (16, 144, 150),
        (17, 151, 157),
        (18, 158, 164),
        (19, 165, 171),
        (20, 172, 179),
        (21, 180, 188),
        (22, 189, 197),
        (23, 198, 206),
        (24, 207, 215),
        (25, 216, 224),
        (26, 225, 233),
        (27, 234, 242),
        (28, 243, 251),
        (29, 252, 260),
        (30, 261, 269),
        (31, 270, 278),
        (32, 279, 287),
        (33, 288, 296),
        (34, 297, 303),
        (35, 304, 309),
        (36, 310, 315),
        (37, 316, 320),
    ],
}


def natural_sort_key(s: Path | str) -> list[int | str]:
    """Alphanumeric sort key for natural ordering (e.g., 'Chapter 2' < 'Chapter 10')."""
    text = str(s)
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", text)]


def extract_first_number(text: str) -> int:
    """Extract the first integer found in a string, or 0 if none found."""
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else 0


def collect_images_from_folder(folder: Path, recursive: bool = False) -> list[Path]:
    """Collect image paths from a folder, sorted numerically."""
    if not folder.is_dir():
        return []
    pattern = "**/*" if recursive else "*"
    images = [
        f
        for f in folder.glob(pattern)
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]
    images.sort(key=lambda p: (natural_sort_key(p.parent), natural_sort_key(p.name)))
    return images


def convert_images_to_pdf(image_paths: Sequence[Path], output_pdf_path: Path) -> bool:
    """Convert an ordered list of images to a single PDF file."""
    if not image_paths:
        return False

    pics: list[Image.Image] = []
    for img_path in image_paths:
        try:
            with Image.open(img_path) as img:
                pics.append(img.convert("RGB"))
        except (UnidentifiedImageError, OSError) as err:
            print(f"  [WARN] Skipping unreadable image {img_path.name}: {err}", flush=True)

    if not pics:
        return False

    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    temp_pdf = output_pdf_path.with_suffix(".tmp.pdf")
    try:
        pics[0].save(
            temp_pdf,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=pics[1:],
        )
        temp_pdf.replace(output_pdf_path)
        return True
    except Exception as err:
        print(f"  [ERROR] Failed to save PDF {output_pdf_path.name}: {err}", flush=True)
        if temp_pdf.exists():
            temp_pdf.unlink()
        return False


def convert_images_to_cbz(image_paths: Sequence[Path], output_cbz_path: Path) -> bool:
    """Convert an ordered list of images to a CBZ archive."""
    if not image_paths:
        return False

    output_cbz_path.parent.mkdir(parents=True, exist_ok=True)
    temp_cbz = output_cbz_path.with_suffix(".tmp.cbz")
    try:
        with zipfile.ZipFile(temp_cbz, "w", compression=zipfile.ZIP_DEFLATED) as cbz:
            for idx, img_path in enumerate(image_paths, 1):
                ext = img_path.suffix.lower()
                cbz.write(img_path, arcname=f"{idx:04d}{ext}")
        temp_cbz.replace(output_cbz_path)
        return True
    except Exception as err:
        print(f"  [ERROR] Failed to save CBZ {output_cbz_path.name}: {err}", flush=True)
        if temp_cbz.exists():
            temp_cbz.unlink()
        return False


def convert_images(image_paths: Sequence[Path], output_path: Path, output_format: str) -> bool:
    """Convert images to the requested format (PDF or CBZ)."""
    if output_format.lower() == "cbz":
        return convert_images_to_cbz(image_paths, output_path)
    return convert_images_to_pdf(image_paths, output_path)


def is_downloader_running(manga_name: str | None = None) -> bool:
    """Check across platforms if manga_downloader.py is currently active."""
    if sys.platform == "win32":
        try:
            filter_cmd = f"*{manga_name}*" if manga_name else "*manga_downloader.py*"
            ps_cmd = (
                f"Get-CimInstance Win32_Process | "
                f"Where-Object {{ $_.CommandLine -like '{filter_cmd}' }} | "
                f"Select-Object -ExpandProperty ProcessId"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            return bool(res.stdout.strip())
        except Exception:
            return False
    else:
        try:
            pattern = f"manga_downloader.py.*{manga_name}" if manga_name else "manga_downloader.py"
            res = subprocess.run(
                ["pgrep", "-f", pattern],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            return bool(res.stdout.strip())
        except Exception:
            return False


def load_custom_mappings(mapping_file: Path | None) -> dict[str, list[tuple[int, int, int]]]:
    """Load optional custom volume mapping from a JSON file."""
    mappings = dict(DEFAULT_KNOWN_MAPPINGS)
    if not mapping_file or not mapping_file.is_file():
        return mappings

    try:
        with mapping_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            for manga_key, vol_list in data.items():
                mappings[manga_key.lower()] = [
                    (int(v[0]), int(v[1]), int(v[2])) for v in vol_list
                ]
    except Exception as err:
        print(f"[WARN] Could not load volume mappings file {mapping_file}: {err}", flush=True)

    return mappings


def find_volume_and_chapter_dirs(manga_dir: Path) -> tuple[list[Path], list[Path]]:
    """Scan manga directory for volume folders and chapter folders."""
    ignore_names = {"pdf_volumi", "pdf", "cbz", "output", "temp", ".tmp", "dist", "build"}
    subdirs = [
        d
        for d in manga_dir.iterdir()
        if d.is_dir()
        and d.name.lower() not in ignore_names
        and not d.name.startswith(".")
    ]

    volume_dirs = [
        d
        for d in subdirs
        if re.search(r"\b(vol|volume)\b", d.name, re.I)
    ]
    chapter_dirs = [
        d
        for d in subdirs
        if re.search(r"\b(chapter|capitolo|ch)\b", d.name, re.I) or re.match(r"^\d+$", d.name)
    ]

    # If directories aren't explicitly named "chapter" but no volume directories exist,
    # treat all valid subdirs as chapters/units
    if not volume_dirs and not chapter_dirs and subdirs:
        chapter_dirs = subdirs

    volume_dirs.sort(key=natural_sort_key)
    chapter_dirs.sort(key=lambda d: extract_first_number(d.name))

    return volume_dirs, chapter_dirs


def process_manga(
    manga_dir: Path,
    *,
    output_format: str = "pdf",
    mode: str = "auto",
    chapters_per_volume: int = 10,
    output_subfolder: str = "PDF_Volumi",
    custom_mappings: dict[str, list[tuple[int, int, int]]] | None = None,
    force: bool = False,
    is_live: bool = False,
) -> int:
    """Process a single manga folder and generate PDFs/CBZs.

    Returns the number of generated files.
    """
    manga_name = manga_dir.name
    output_dir = manga_dir / output_subfolder
    output_dir.mkdir(parents=True, exist_ok=True)

    volume_dirs, chapter_dirs = find_volume_and_chapter_dirs(manga_dir)
    generated_count = 0
    ext = output_format.lower()

    # Determine execution strategy
    # 1. Volume folders already present (e.g. Manga/Volume 1/...)
    if (mode in {"auto", "volumes"}) and volume_dirs:
        print(f"\n[{manga_name}] Found {len(volume_dirs)} volume folder(s)...", flush=True)
        for vol_dir in volume_dirs:
            out_file = output_dir / f"{manga_name} - {vol_dir.name}.{ext}"
            if out_file.exists() and not force:
                continue

            images = collect_images_from_folder(vol_dir, recursive=True)
            if not images:
                continue

            print(f"  Generating {out_file.name} ({len(images)} images)...", flush=True)
            if convert_images(images, out_file, ext):
                size_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"  [OK] Created {out_file.name} ({size_mb:.1f} MB)", flush=True)
                generated_count += 1
        return generated_count

    # 2. Single output mode (all images across manga in one file)
    if mode == "single":
        out_file = output_dir / f"{manga_name}.{ext}"
        if out_file.exists() and not force:
            return 0
        images = collect_images_from_folder(manga_dir, recursive=True)
        if images:
            print(f"\n[{manga_name}] Generating single {ext.upper()}...", flush=True)
            if convert_images(images, out_file, ext):
                size_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"  [OK] Created {out_file.name} ({size_mb:.1f} MB)", flush=True)
                generated_count += 1
        return generated_count

    # 3. Chapter-by-chapter mode
    if mode == "chapters":
        print(f"\n[{manga_name}] Processing {len(chapter_dirs)} chapter(s)...", flush=True)
        for chap_dir in chapter_dirs:
            chap_num = extract_first_number(chap_dir.name)
            out_file = output_dir / f"{manga_name} - Chapter {chap_num:03d}.{ext}"
            if out_file.exists() and not force:
                continue
            images = collect_images_from_folder(chap_dir, recursive=False)
            if not images:
                continue
            print(f"  Generating {out_file.name} ({len(images)} images)...", flush=True)
            if convert_images(images, out_file, ext):
                generated_count += 1
        return generated_count

    # 4. Auto / Volumes mode with chapter folders
    if chapter_dirs:
        mapping_key = manga_name.lower().strip()
        mappings = custom_mappings or DEFAULT_KNOWN_MAPPINGS
        known_mapping = mappings.get(mapping_key)

        if known_mapping:
            print(
                f"\n[{manga_name}] Predefined volume mapping ({len(known_mapping)} volumes)...",
                flush=True,
            )
            volumes_to_process = known_mapping
        else:
            # Automatic grouping by chapters_per_volume
            chapter_numbers = [extract_first_number(d.name) for d in chapter_dirs]
            min_chap = min(chapter_numbers) if chapter_numbers else 1
            max_chap = max(chapter_numbers) if chapter_numbers else len(chapter_dirs)

            volumes_to_process = []
            vol_idx = 1
            cur_start = min_chap
            while cur_start <= max_chap:
                cur_end = cur_start + chapters_per_volume - 1
                volumes_to_process.append((vol_idx, cur_start, cur_end))
                vol_idx += 1
                cur_start = cur_end + 1

            print(
                f"\n[{manga_name}] Grouping {len(chapter_dirs)} chapters into volumes "
                f"({chapters_per_volume} chapters per volume)...",
                flush=True,
            )

        # Build chapter directory lookup
        chap_dir_map: dict[int, Path] = {}
        for d in chapter_dirs:
            num = extract_first_number(d.name)
            chap_dir_map[num] = d

        for vol_num, start_chap, end_chap in volumes_to_process:
            out_file = output_dir / f"{manga_name} - Volume {vol_num:02d}.{ext}"
            if out_file.exists() and not force:
                continue

            # In live monitoring mode, ensure the volume is fully downloaded
            if is_live:
                has_next = bool(end_chap + 1 in chap_dir_map)
                if not has_next:
                    # Still downloading this volume
                    continue

            # Gather all images for chapters belonging to this volume
            vol_images: list[Path] = []
            for c in range(start_chap, end_chap + 1):
                c_dir = chap_dir_map.get(c)
                if c_dir:
                    vol_images.extend(collect_images_from_folder(c_dir, recursive=False))

            if not vol_images:
                continue

            print(
                f"  Generating Volume {vol_num:02d} "
                f"(Chapters {start_chap}-{end_chap}, {len(vol_images)} pages)...",
                flush=True,
            )
            if convert_images(vol_images, out_file, ext):
                size_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"  [OK] Created {out_file.name} ({size_mb:.1f} MB)", flush=True)
                generated_count += 1

        return generated_count

    # 5. Fallback: Loose images in manga root
    root_images = collect_images_from_folder(manga_dir, recursive=False)
    if root_images:
        out_file = output_dir / f"{manga_name}.{ext}"
        if not out_file.exists() or force:
            print(f"\n[{manga_name}] Converting root images into {out_file.name}...", flush=True)
            if convert_images(root_images, out_file, ext):
                size_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"  [OK] Created {out_file.name} ({size_mb:.1f} MB)", flush=True)
                generated_count += 1

    return generated_count


def parse_cli_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert downloaded manga from MangaWorld into Volume PDFs or CBZs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        default=Path("Downloads"),
        help="Path to the directory containing downloaded manga.",
    )
    parser.add_argument(
        "-m",
        "--manga",
        type=str,
        default=None,
        help="Name of a specific manga directory to process (default: process all).",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["pdf", "cbz"],
        default="pdf",
        help="Output file format.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "volumes", "chapters", "single"],
        default="auto",
        help=(
            "Conversion mode: 'auto' (detects volume folders or groups chapters), "
            "'volumes' (group into volumes), 'chapters' (1 file per chapter), "
            "or 'single' (1 file for the entire manga)."
        ),
    )
    parser.add_argument(
        "-c",
        "--chapters-per-volume",
        type=int,
        default=10,
        help="Number of chapters per volume when grouping chapters automatically.",
    )
    parser.add_argument(
        "-o",
        "--output-subfolder",
        type=str,
        default="PDF_Volumi",
        help="Name of the subfolder inside each manga folder to store the generated files.",
    )
    parser.add_argument(
        "--mapping-file",
        type=Path,
        default=None,
        help="Optional JSON file defining custom volume mappings for manga.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate files even if the target PDF/CBZ already exists.",
    )
    parser.add_argument(
        "-w",
        "--monitor",
        action="store_true",
        help="Continuously monitor active downloads and generate volumes in real-time.",
    )
    return parser.parse_args()


def main() -> None:
    """Main execution function."""
    args = parse_cli_args()
    base_dir = args.input_dir

    if not base_dir.exists():
        print(f"[ERROR] Directory '{base_dir}' does not exist. Nothing to convert.")
        sys.exit(1)

    # Find manga directories to process
    if args.manga:
        target_dir = base_dir / args.manga
        if not target_dir.is_dir():
            print(f"[ERROR] Manga folder '{target_dir}' not found.")
            sys.exit(1)
        manga_dirs = [target_dir]
    else:
        manga_dirs = [
            d
            for d in base_dir.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and d.name.lower() not in {"pdf_volumi", "pdf", "cbz", "output", "temp"}
        ]

    if not manga_dirs:
        print(f"No manga folders found in '{base_dir}'.")
        return

    custom_mappings = load_custom_mappings(args.mapping_file)

    print("=" * 60)
    print("MangaWorld Downloader - Comic / Volume Generator")
    print(f"Base Directory: {base_dir.resolve()}")
    print(f"Format: {args.format.upper()} | Mode: {args.mode}")
    print(f"Target Manga: {[m.name for m in manga_dirs]}")
    print("=" * 60)

    # Continuous monitor mode
    if args.monitor:
        print("Monitoring active downloads (press Ctrl+C to stop)...", flush=True)
        try:
            while True:
                active = is_downloader_running(args.manga)
                for m_dir in manga_dirs:
                    process_manga(
                        m_dir,
                        output_format=args.format,
                        mode=args.mode,
                        chapters_per_volume=args.chapters_per_volume,
                        output_subfolder=args.output_subfolder,
                        custom_mappings=custom_mappings,
                        force=args.force,
                        is_live=active,
                    )
                if not active:
                    # Final pass when downloader finishes
                    print("\nDownloader finished. Running final completion pass...")
                    for m_dir in manga_dirs:
                        process_manga(
                            m_dir,
                            output_format=args.format,
                            mode=args.mode,
                            chapters_per_volume=args.chapters_per_volume,
                            output_subfolder=args.output_subfolder,
                            custom_mappings=custom_mappings,
                            force=args.force,
                            is_live=False,
                        )
                    print("\nAll conversions completed successfully.")
                    break
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")
        return

    # Standard one-shot conversion mode
    total_generated = 0
    for m_dir in manga_dirs:
        count = process_manga(
            m_dir,
            output_format=args.format,
            mode=args.mode,
            chapters_per_volume=args.chapters_per_volume,
            output_subfolder=args.output_subfolder,
            custom_mappings=custom_mappings,
            force=args.force,
            is_live=False,
        )
        total_generated += count

    print("\n" + "=" * 60)
    print(f"Done! Generated {total_generated} file(s).")
    print("=" * 60)


if __name__ == "__main__":
    main()
