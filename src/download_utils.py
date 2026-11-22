"""Utilities for handling file downloads with progress tracking."""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests import Response
from rich.progress import Progress

from .config import (
    CHUNK_SIZE,
    HEADERS,
    HTTP_STATUS_OK,
    MAX_RETRIES,
    MAX_WORKERS,
    PAGE_EXTENSIONS,
    SESSION,
    SESSION_LOG,
    TASK_COLOR,
    TIMEOUT,
    URL_FILENAME_REGEX,
)
from .file_utils import create_download_directory, write_file


def manage_running_tasks(futures: dict, job_progress: Progress) -> None:
    """Manage the status of running tasks and update their progress."""
    while futures:
        for future in list(futures.keys()):
            if future.running():
                task = futures.pop(future)
                job_progress.update(task, visible=True)


def run_in_parallel(
    func: callable,
    items: list,
    job_progress: Progress,
    *args: tuple,
) -> None:
    """Execute a function in parallel for a list of items, updating progress."""
    num_items = len(items)
    futures = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        overall_task = job_progress.add_task(
            f"[{TASK_COLOR}]Progress",
            total=num_items,
            visible=True,
        )
        for indx, item in enumerate(items):
            task = job_progress.add_task(
                f"[{TASK_COLOR}]Chapter {indx + 1}/{num_items}",
                total=100,
                visible=False,
            )
            task_info = job_progress, task, overall_task
            item_info = indx, item
            future = executor.submit(func, item_info, *args, task_info)
            futures[future] = task
            manage_running_tasks(futures, job_progress)


def download_page(
    response: Response,
    page: int,
    extension: str,
    download_path: str,
) -> None:
    """Download a single page of a chapter."""
    filename = f"{page}{extension}"
    final_path = Path(download_path) / filename

    try:
        with Path(final_path).open("wb") as file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk is not None:
                    file.write(chunk)

    except requests.exceptions.RequestException as req_err:
        log_message = f"Failed to download page {page}: {req_err}"
        logging.warning(log_message)
        write_file(SESSION_LOG, mode="a", content=log_message)


def download_direct_page(
    page: int,
    image_url: str,
    download_path: str,
) -> bool:
    """Download a single page using its direct image URL."""
    url_path = urlparse(image_url).path
    extension = Path(url_path).suffix or ".jpg"
    filename = f"{page}{extension}"
    final_path = Path(download_path) / filename

    for attempt in range(MAX_RETRIES):
        try:
            response = SESSION.get(
                image_url,
                stream=True,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            if response.status_code == HTTP_STATUS_OK:
                with Path(final_path).open("wb") as file:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk is not None:
                            file.write(chunk)
                return True
        except requests.exceptions.RequestException as req_err:
            logging.warning("Attempt %d failed for %s: %s", attempt + 1, image_url, req_err)

        if attempt < MAX_RETRIES - 1:
            time.sleep(1)

    log_message = f"Failed to download page {page} from {image_url}"
    logging.warning(log_message)
    write_file(SESSION_LOG, mode="a", content=log_message)
    return False


def attempt_download_page(
    page: int,
    base_download_link: str,
    download_path: str,
) -> bool:
    """Attempt downloading a page by testing all possible extensions.

    Returns True if download succeeded, False otherwise.
    """
    for extension in PAGE_EXTENSIONS:
        cleaned_base_link = re.sub(URL_FILENAME_REGEX, "", base_download_link)
        test_download_link = f"{cleaned_base_link}{page}{extension}"

        try:
            response = SESSION.get(
                test_download_link,
                stream=True,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            if response.status_code == HTTP_STATUS_OK:
                download_page(
                    response,
                    page,
                    extension,
                    download_path,
                )
                return True

        except requests.exceptions.RequestException as req_err:
            logging.warning("Failed attempt with %s: %s", test_download_link, req_err)
            continue

    # Every possible extension failed
    return False


def get_images_from_chapter_url(chapter_url: str) -> list[str]:
    """Fetch direct image URLs from a chapter reader page."""
    for attempt in range(MAX_RETRIES):
        try:
            response = SESSION.get(chapter_url, headers=HEADERS, timeout=TIMEOUT)
            if response.status_code == HTTP_STATUS_OK:
                soup = BeautifulSoup(response.text, "html.parser")
                img_items = soup.find_all("img", class_="reader-page")
                if not img_items:
                    stage = soup.find(class_="reader-stage")
                    if stage:
                        img_items = stage.find_all("img")
                if not img_items:
                    img_items = soup.find_all("img", attrs={"data-reader-image": True})

                image_urls = []
                for img in img_items:
                    src = img.get("src") or img.get("data-src")
                    if src and not src.startswith("data:") and "/chapters/" in src:
                        image_urls.append(src)

                if image_urls:
                    return image_urls

                legacy_imgs = soup.find_all("img", {"class": "img-fluid"})
                if legacy_imgs:
                    return [legacy_imgs[-1]["src"]]
        except requests.exceptions.RequestException as req_err:
            logging.warning("Error fetching chapter %s: %s", chapter_url, req_err)

        if attempt < MAX_RETRIES - 1:
            time.sleep(1)

    return []


def download_chapter(
    item_info: tuple,
    pages_per_chapter: list | None,
    manga_name: str,
    *extra_args: tuple,
) -> None:
    """Download all pages for a specific manga chapter and update the progress."""
    if len(extra_args) >= 2:
        chapter_start_index = int(extra_args[0])
        task_info = extra_args[1]
    elif len(extra_args) == 1:
        chapter_start_index = 1
        task_info = extra_args[0]
    else:
        raise ValueError("task_info is required")

    job_progress, task, overall_task = task_info
    indx_chapter, chapter_content = item_info

    real_chapter_num = indx_chapter + chapter_start_index
    download_path = create_download_directory(manga_name, real_chapter_num - 1)

    # If chapter_content is a chapter URL string, fetch image URLs dynamically
    if isinstance(chapter_content, str) and "/read/" in chapter_content:
        chapter_content = get_images_from_chapter_url(chapter_content)

    # Check if chapter_content is a list of direct image URLs
    if isinstance(chapter_content, list):
        image_urls = chapter_content
        num_pages = len(image_urls)
        for page, img_url in enumerate(image_urls, start=1):
            success = download_direct_page(page, img_url, download_path)
            if not success:
                logging.error(
                    "Chapter %d: Page %d could not be downloaded",
                    real_chapter_num,
                    page,
                )
            if num_pages > 0:
                progress_percentage = (page / num_pages) * 100
                job_progress.update(task, completed=progress_percentage)
    else:
        # Legacy fallback
        base_download_link = chapter_content
        num_pages = (
            int(pages_per_chapter[indx_chapter])
            if pages_per_chapter and indx_chapter < len(pages_per_chapter) and pages_per_chapter[indx_chapter]
            else 0
        )
        for page in range(1, num_pages + 1):
            success = attempt_download_page(page, base_download_link, download_path)
            if not success:
                logging.error(
                    "Chapter %d: Page %d could not be downloaded with any extension",
                    real_chapter_num,
                    page,
                )
            if num_pages > 0:
                progress_percentage = (page / num_pages) * 100
                job_progress.update(task, completed=progress_percentage)

    job_progress.update(task, completed=100, visible=False)
    job_progress.advance(overall_task)
