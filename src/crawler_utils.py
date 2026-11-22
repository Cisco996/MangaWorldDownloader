"""Asynchronous utility functions for crawling manga chapters and extracting metadata.

This module provides high-level helpers to:
    - Retrieve chapter URLs and the corresponding number of pages.
    - Normalize chapter URLs depending on manga type (e.g., Manga, Manhwa).
    - Extract the manga type from embedded metadata or script data.
    - Fetch direct download links for chapter pages.
    - Collect download links for multiple chapters.

Intended to be used in combination with download utilities to provide a complete
pipeline for scraping and downloading manga content.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re

import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup

from .config import (
    FETCH_HEADERS,
    FIRST_PAGE_SUFFIX_REGEX,
    MANGA_LIKE,
    MANGA_TYPE_REGEX,
    MAX_RETRIES,
    TIMEOUT,
    WAIT_TIME_RETRIES,
)
from .general_utils import check_real_page


async def fetch_chapter_images(
    chapter_url: str,
    session: ClientSession,
    manga_type: str | None = None,
) -> list[str]:
    """Fetch direct image URLs for all pages in a chapter."""
    url_to_fetch = chapter_url
    if manga_type and manga_type == "Manhwa" and "?style=list" not in url_to_fetch:
        url_to_fetch = f"{url_to_fetch}?style=list"

    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(
                url_to_fetch,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                soup = BeautifulSoup(await response.text(), "html.parser")
                validated_soup = await check_real_page(soup, session, TIMEOUT)

                # Modern MangaWorld: all images are in <img class="reader-page">
                img_items = validated_soup.find_all("img", class_="reader-page")
                if not img_items:
                    stage = validated_soup.find(class_="reader-stage")
                    if stage:
                        img_items = stage.find_all("img")
                if not img_items:
                    img_items = validated_soup.find_all(
                        "img", attrs={"data-reader-image": True},
                    )

                image_urls = []
                for img in img_items:
                    src = img.get("src") or img.get("data-src")
                    if src and not src.startswith("data:") and "/chapters/" in src:
                        image_urls.append(src)

                if image_urls:
                    return image_urls

                # Legacy fallback: single image with class img-fluid
                legacy_imgs = validated_soup.find_all("img", {"class": "img-fluid"})
                if legacy_imgs:
                    return [legacy_imgs[-1]["src"]]

                # Check if there is a page select
                page_item = validated_soup.find("select", {"class": "page custom-select"})
                if page_item and legacy_imgs:
                    return [legacy_imgs[-1]["src"]]

        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass

        if attempt < MAX_RETRIES - 1:
            delay = random.uniform(1, min(WAIT_TIME_RETRIES, 3))  # noqa: S311
            await asyncio.sleep(delay)

    logging.error("Failed to fetch chapter images for %s", chapter_url)
    return []


async def fetch_chapter_data(chapter_url: str, session: ClientSession) -> tuple:
    """Fetch the number of pages for a given chapter URL, retrying if necessary."""
    session.headers.update(FETCH_HEADERS)
    images = await fetch_chapter_images(chapter_url, session)
    if images:
        return chapter_url, str(len(images))
    return None, None


def extract_chapter_urls(soup: BeautifulSoup) -> list[str]:
    """Extract chapter URLs from the manga page in ascending order."""
    chapters_panel = soup.find(class_=re.compile(r"manga-chapters|chapters", re.I))
    container = chapters_panel if chapters_panel else soup

    chapter_items = container.find_all(
        "a",
        class_=lambda c: c and any(cls in {"ch", "chap"} for cls in c.split()),
        href=re.compile(r"/read/"),
    )
    if not chapter_items:
        chapter_items = container.find_all(
            "a",
            class_=lambda c: c and ("ch" in c or "chap" in c),
            href=re.compile(r"/read/"),
        )

    seen = set()
    chapter_urls = []
    for item in chapter_items:
        url = item.get("href")
        if url and url not in seen and "/read/" in url:
            seen.add(url)
            chapter_urls.append(url)

    # In MangaWorld, chapters are listed descending (latest chapter first).
    # Reversing gives ascending order (Chapter 1 to Chapter N).
    return chapter_urls[::-1]


async def extract_chapters_info(soup: BeautifulSoup) -> tuple[list[str], list]:
    """Extract chapter URLs from the manga page."""
    chapter_urls = extract_chapter_urls(soup)
    return chapter_urls, []


def generate_chapter_url(chapter_url: str, manga_type: str) -> str | None:
    """Return the normalized chapter URL based on manga type, or None if unsupported."""
    if manga_type in MANGA_LIKE:
        return f"{chapter_url}/1"

    if manga_type == "Manhwa":
        return chapter_url.replace("?style=list", "/1?style=pages")

    logging.warning("Manga type '%s' is not supported", manga_type)
    return None


async def fetch_download_link(
    chapter_url: str,
    session: ClientSession,
    manga_type: str | None = None,
) -> list[str] | str | None:
    """Fetch the download links or first image link for a chapter page."""
    images = await fetch_chapter_images(chapter_url, session, manga_type=manga_type)
    if images:
        if len(images) > 1:
            return images
        return images[0]
    return None


async def extract_download_links(
    chapter_urls: list[str],
    start_index: int,
    end_index: int,
    manga_type: str | None = None,
) -> list:
    """Extract download links for the selected range of chapter URLs."""
    selected_urls = chapter_urls[start_index:end_index]
    async with aiohttp.ClientSession(headers=FETCH_HEADERS) as session:
        tasks = [
            fetch_download_link(chapter_url, session, manga_type=manga_type)
            for chapter_url in selected_urls
        ]
        results = await asyncio.gather(*tasks)

        cleaned_results = []
        for res in results:
            if isinstance(res, list):
                cleaned_results.append(res)
            elif isinstance(res, str):
                cleaned_results.append(re.sub(FIRST_PAGE_SUFFIX_REGEX, "", res))
            else:
                cleaned_results.append([])
        return cleaned_results


def extract_manga_type(soup: BeautifulSoup, manga_slug: str) -> str | None:
    """Extract the type of manga (e.g., 'Manga', 'Manhwa') from the page."""
    # 1. Search in DOM definition list (modern layout)
    for dt in soup.find_all("dt"):
        text = dt.get_text().strip().lower()
        if "tipo" in text or "type" in text:
            dd = dt.find_next_sibling("dd") or (dt.parent.find("dd") if dt.parent else None)
            if dd:
                manga_type = dd.get_text(strip=True)
                if manga_type:
                    return manga_type

    # 2. Search in script tags
    for script in soup.find_all("script"):
        script_text = script.get_text()
        if "typeT" in script_text:
            manga_slug_pattern = rf'"slug":"{manga_slug}".*?"typeT":\s*"[^"]*"'
            slug_match = re.search(manga_slug_pattern, script_text)
            if slug_match:
                type_match = re.search(MANGA_TYPE_REGEX, slug_match.group(0))
                if type_match:
                    return type_match.group(1)

    # 3. Default to Manga
    return "Manga"


def extract_volume_number(name: str) -> int:
    """Extract volume number by title."""
    match = re.search(r"\d+", name)
    return int(match.group()) if match else 0


def extract_volume_info(soup: BeautifulSoup) -> list[dict]:
    """Extract the volume list and relative list of chapter URLs.

    Output:
        [
            {"name": "Volume 1", "chapters": [{"title": ..., "url": ...}, ...]},
            ...
        ]
    """
    volumes = []
    # Check modern volume elements first
    volume_elements = soup.find_all("div", class_="volume")
    if not volume_elements:
        volume_elements = soup.find_all("div", {"class": "volume-element"})

    if volume_elements:
        for vol in volume_elements:
            # Volume name
            name_tag = (
                vol.find(class_="volume-name")
                or vol.find("button", class_="volume-head")
                or vol.find("p", class_="volume-name")
            )
            volume_name = name_tag.get_text(strip=True) if name_tag else "Volume"

            # Volume chapters
            chapters = []
            chap_links = vol.find_all(
                "a",
                class_=lambda c: c and any(cls in {"ch", "chap"} for cls in c.split()),
                href=re.compile(r"/read/"),
            )
            if not chap_links:
                chap_links = vol.find_all(
                    "a",
                    class_=lambda c: c and ("ch" in c or "chap" in c),
                    href=re.compile(r"/read/"),
                )

            for chap in chap_links:
                title = chap.get("title") or chap.get_text(strip=True)
                url = chap.get("href")
                if url:
                    chapters.append({"title": title, "url": url})

            # In DOM, chapters inside a volume are in descending order
            if chapters:
                volumes.append({
                    "name": volume_name,
                    "chapters": chapters[::-1],
                })
    else:
        logging.error("The selected link doesn't have available volumes.")
        return []

    # Return sorted volumes by number
    volumes.sort(key=lambda v: extract_volume_number(v["name"]))
    return volumes
