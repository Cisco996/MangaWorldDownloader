# MangaWorld Downloader

> A Python-based tool for downloading and organizing manga content from MangaWorld.

![Demo](https://github.com/Lysagxra/MangaWorldDownloader/blob/a8dca98cb0fece9d7eab672ea30fea5ab50bcf34/assets/demo.gif)

## Features

- Downloads multiple chapters concurrently.
- Downloads chapters by volume (if available).
- Supports [batch downloading](https://github.com/Lysagxra/MangaWorldDownloader?tab=readme-ov-file#batch-download) via a list of URLs.
- Supports downloading a [specified range of chapters](https://github.com/Lysagxra/MangaWorldDownloader?tab=readme-ov-file#single-manga-download).
- Supports the [generation of PDF and CBZ files](https://github.com/Lysagxra/MangaWorldDownloader?tab=readme-ov-file#comic-files-generation) from the downloaded chapters.
- Track and display download progress.
- Organize and format manga chapters.

## Dependencies

- Python 3
- `aiohttp` - for asynchronous HTTP requests
- `requests` - for HTTP requests
- `beautifulsoup4` (bs4) - for HTML parsing
- `Pillow` - for image processing
- `rich` - for progress display in terminal

<details>

<summary>Show directory structure</summary>

```
project-root/
├── helpers/
│ ├── config.py          # Manages constants and settings used across the project
│ ├── download_utils.py  # Utilities for managing the download process
│ ├── file_utils.py      # Utilities for managing file operations
│ ├── format_utils.py    # Functions for formatting manga data
│ ├── general_utils.py   # Miscellaneous utility functions
│ ├── pdf_generator.py   # Tools for generating PDF files from manga chapters
│ └── progress_utils.py  # Utilities for tracking and displaying progress
├── manga_downloader.py  # Core functionality for managing manga downloads
├── main.py              # Main script to run the downloader
└── URLs.txt             # Text file containing manga URLs
```

</details>

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Lysagxra/MangaWorldDownloader.git
```
   
2. Navigate to the project directory: 

```bash
cd MangaWorldDownloader
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Single Manga Download

To download a single manga, you can use the `manga_downloader.py` script.

### Usage

Run the script followed by the manga URL you want to download:

```bash
python3 manga_downloader.py <manga_url> [--start <start_index>] [--end <end_index>] [--volume]
```

- `<manga_url>`: The URL of the manga.
- `--start <start_index>`: The starting chapter (or volume) number (optional).
- `--end <end_index>`: The ending chapter (or volume) number (optional).
- `--volume --v`: Enable download by volume (optional).

### Example

```bash
python3 manga_downloader.py https://www.mangaworld.ac/manga/2754/sayonara-eri
```

### Examples

To download all chapters:
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison
```

To download a specific range of chapters (e.g., chapters 5 to 10):
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison --start 5 --end 10
```

To download chapters starting from a specific chapter:
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison --start 5
```
In this case, the script will download all chapters starting from the `--start` chapter to the last chapter.

To download chapters up to a certain chapter:
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison --end 10
```
In this case, the script will download all chapters starting from the first chapter to the `--end` chapter.

### Download chapters by volume

To download chapters by volume (if available) you can use the `--volume` argument from the command line to enable this functionality and select volume(s) to retrive:
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison --volume
```

To download a specific range of volumes (e.g., volumes 5 to 10):
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison --volume --start 5 --end 10
```

To download chapters starting from a specific volume:
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison --volume --start 5
```
In this case, the script will download all volumes starting from the `--start` volume to the last volume.

To download chapters up to a certain volume:
```bash
python3 manga_downloader.py https://www.mangaworld.cx/manga/2472/soloist-of-the-prison --volume --end 10
```
In this case, the script will download all volumes starting from the first volume to the `--end` volume.

## Batch Download

### Usage

1. Create a `URLs.txt` file in the project root and list the manga URLs you want to download.

- Example of `URLs.txt`:

```
https://www.mangaworld.ac/manga/2754/sayonara-eri
https://www.mangaworld.ac/manga/2378/bibliomania
https://www.mangaworld.ac/manga/2472/soloist-of-the-prison
```

- Ensure that each URL is on its own line without any extra spaces.
- You can add as many URLs as you need, following the same format.

2. Run the main script via the command line:

```bash
python3 main.py
```

The downloaded files will be saved in the `Downloads` directory.

## Comic & Volume File Generation

This tool includes functionality to generate comic files (PDF and CBZ) from downloaded manga, both during download and for already downloaded manga.

### Converting Already Downloaded Manga (Volumes & Chapters)

You can convert any manga present in the `Downloads/` directory into volume PDFs or CBZs using `generate_volume_pdfs.py` (or `convert_to_pdf.py`).

The script automatically detects the directory structure:
- **Volume folders already present**: Converts each volume folder into a volume PDF.
- **Chapter folders**: Automatically groups chapters into volumes (default: 10 chapters per volume, or uses custom/predefined volume mappings).
- **Loose images**: Compiles images into a single comic file.

#### Basic Usage (Convert everything in `Downloads/`)

```bash
python3 generate_volume_pdfs.py
```

#### Advanced Options

- **Specify chapters per volume:**
  ```bash
  python3 generate_volume_pdfs.py --chapters-per-volume 10
  ```

- **Convert a specific manga only:**
  ```bash
  python3 generate_volume_pdfs.py --manga "MangaName"
  ```

- **Select conversion mode:**
  - `--mode auto` (default): Groups chapters into volumes or converts volume folders.
  - `--mode chapters`: Generates a separate PDF/CBZ for each chapter.
  - `--mode single`: Combines the entire manga into one single PDF/CBZ.
  - `--mode volumes`: Groups into volumes.
  ```bash
  python3 generate_volume_pdfs.py --mode chapters
  ```

- **Output format (PDF or CBZ):**
  ```bash
  python3 generate_volume_pdfs.py --format cbz
  ```

- **Real-time download monitor:**
  Continuously monitors downloads in progress and generates volume files as soon as each volume completes:
  ```bash
  python3 generate_volume_pdfs.py --monitor
  ```

- **Custom volume mapping file (JSON):**
  If you have specific chapter-to-volume ranges for a manga, pass a JSON file:
  ```bash
  python3 generate_volume_pdfs.py --mapping-file custom_mapping.json
  ```
  *Example `custom_mapping.json`:*
  ```json
  {
    "my-manga": [
      [1, 1, 10],
      [2, 11, 20]
    ]
  }
  ```

### Converting During Download

To generate PDF files automatically during download, use `--format pdf` with `main.py` or `manga_downloader.py`:

```bash
python3 main.py --format pdf
```

Or for a single manga:

```bash
python3 manga_downloader.py <manga_url> --format pdf
```

## Logging

The application logs any issues encountered during the download process in a file named `session.log`. Check this file for any URLs that may have been blocked or had errors.
