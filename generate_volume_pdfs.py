#!/usr/bin/env python3
"""Script to monitor download of Vagabond and generate a PDF for each Volume."""

import os
import re
import sys
import time
from pathlib import Path
from PIL import Image, UnidentifiedImageError

VOLUMES_MAPPING = [
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
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def extract_page_number(file_path: Path) -> int:
    match = re.search(r"(\d+)", file_path.stem)
    return int(match.group(1)) if match else 0


def collect_volume_images(base_dir: Path, start_chap: int, end_chap: int) -> list[Path]:
    """Collect image paths for all chapters in a volume, sorted numerically."""
    all_images = []
    for chap in range(start_chap, end_chap + 1):
        chap_dir = base_dir / f"Chapter {chap}"
        if not chap_dir.is_dir():
            return []
        chap_images = [
            f for f in chap_dir.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not chap_images:
            return []
        chap_images.sort(key=extract_page_number)
        all_images.extend(chap_images)
    return all_images


def convert_images_to_pdf(image_paths: list[Path], output_pdf_path: Path) -> bool:
    """Convert images to PDF."""
    pics = []
    for img_path in image_paths:
        try:
            with Image.open(img_path) as img:
                pics.append(img.convert("RGB"))
        except (UnidentifiedImageError, OSError) as err:
            print(f"Warning: skipping {img_path}: {err}", flush=True)

    if not pics:
        return False

    temp_pdf = output_pdf_path.with_suffix(".tmp.pdf")
    pics[0].save(
        temp_pdf,
        "PDF",
        resolution=100.0,
        save_all=True,
        append_images=pics[1:],
    )
    temp_pdf.replace(output_pdf_path)
    return True


def is_downloader_running() -> bool:
    """Check if manga_downloader.py process is still running."""
    import subprocess
    res = subprocess.run(
        ["pgrep", "-f", "manga_downloader.py.*vagabond"],
        stdout=subprocess.PIPE,
        text=True,
    )
    return bool(res.stdout.strip())


def main():
    base_dir = Path("Downloads/Vagabond")
    base_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = base_dir / "PDF_Volumi"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    print(f"Monitoring download in {base_dir} and generating PDFs in {pdf_dir}...", flush=True)

    completed_volumes = set()

    while True:
        downloader_active = is_downloader_running()

        for vol_num, start_chap, end_chap in VOLUMES_MAPPING:
            if vol_num in completed_volumes:
                continue

            pdf_file = pdf_dir / f"Vagabond - Volume {vol_num:02d}.pdf"
            if pdf_file.exists():
                completed_volumes.add(vol_num)
                continue

            # Check if all chapters up to end_chap are ready
            # If downloader is still running, check that the next chapter exists too,
            # to be confident end_chap is completely downloaded.
            next_chap_dir = base_dir / f"Chapter {end_chap + 1}"
            volume_ready = False

            if not downloader_active:
                volume_ready = True
            elif end_chap == 320:
                volume_ready = not downloader_active
            elif next_chap_dir.is_dir() and any(next_chap_dir.iterdir()):
                volume_ready = True

            if volume_ready:
                images = collect_volume_images(base_dir, start_chap, end_chap)
                if images:
                    print(
                        f"Generating Volume {vol_num:02d} (Capitoli {start_chap}-{end_chap}, {len(images)} pagine)...",
                        flush=True,
                    )
                    success = convert_images_to_pdf(images, pdf_file)
                    if success:
                        completed_volumes.add(vol_num)
                        print(
                            f"[OK] Generato {pdf_file.name} ({pdf_file.stat().st_size / (1024*1024):.1f} MB)",
                            flush=True,
                        )

        if len(completed_volumes) == len(VOLUMES_MAPPING):
            print("Tutti i 37 volumi sono stati generati con successo!", flush=True)
            break

        if not downloader_active:
            # Downloader finished, make one more check
            time.sleep(2)
            downloader_active = is_downloader_running()
            if not downloader_active:
                # One last attempt for remaining volumes
                for vol_num, start_chap, end_chap in VOLUMES_MAPPING:
                    if vol_num not in completed_volumes:
                        pdf_file = pdf_dir / f"Vagabond - Volume {vol_num:02d}.pdf"
                        images = collect_volume_images(base_dir, start_chap, end_chap)
                        if images:
                            print(f"Final pass: Generating Volume {vol_num:02d}...", flush=True)
                            if convert_images_to_pdf(images, pdf_file):
                                completed_volumes.add(vol_num)
                print(f"Completato! Generati {len(completed_volumes)}/37 volumi in {pdf_dir}", flush=True)
                break

        time.sleep(5)


if __name__ == "__main__":
    main()
