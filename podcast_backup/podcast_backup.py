#!/bin/env python3
"""Backup/archive all episodes of your podcast subscriptions locally."""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import fire
from aiohttp import ClientSession
from defusedxml import ElementTree
from tqdm import tqdm

from parfive import Downloader, SessionConfig


def _aiohttp_session(config: SessionConfig) -> ClientSession:
	"""
	Create aiohttp session, ignore config.

	Args:
		config: Session config, will be ignored.
	"""
	return ClientSession(headers={'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0"}, requote_redirect_url=False)


cwd = Path().absolute()
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
dl = Downloader(max_splits=1, overwrite=True, config=SessionConfig(aiohttp_session_generator=_aiohttp_session))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[
	logging.FileHandler("backup.log", "w", "utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)


def sanitize_filename(filename: str, max_file_length_byte: int = 255) -> str:
	"""
	Replace illegal characters in filename.

	Args:
		filename: Filename.
		max_file_length_byte: Maximum filename length in bytes (default for most file systems is 255).

	Returns:
		Sanitized filename.
	"""
	filename = " ".join(filename.split())  # replace multiple (non-standard) whitespaces by space
	replacements = {
		"/": "\N{division slash}", "\\": "\N{reverse solidus operator}", ":": "\N{ratio}", "*": "\N{low asterisk}", "?": "\N{interrobang}", "\"": "'", "<":
		"\N{canadian syllabics pa}", ">": "\N{canadian syllabics po}", "|": "\N{vertical line extension}"}
	for old, new in replacements.items():
		filename = filename.replace(old, new)
	filename = filename.translate(dict.fromkeys(range(2**5)))  # strip non-printable (<32)

	if "." in filename:
		stem, extension = filename.rsplit(".", 1)
		filename = f"{stem.strip().strip('. ')}.{extension.strip()}"

	if len(filename.encode('utf8')) > max_file_length_byte:
		max_length_in_str = len(filename.encode('utf8', errors="replace")[:max_file_length_byte].decode('utf8', errors="ignore"))
		if "." in filename:
			extension = filename.split(".")[-1]
			filename = f"{filename[:max_length_in_str-len(extension)]}.{extension}"
		else:
			filename = filename[:max_length_in_str]

	return filename


def parse_opml(opml: Path) -> List[str]:
	"""
	Parse OPML file.

	Args:
		opml: Path to OPML file.

	Returns:
		List of podcast urls.
	"""
	log.info(f"Parsing OPML file: {opml}")

	xml_root = ElementTree.parse(opml).getroot()

	return [node.get("xmlUrl") for node in xml_root.findall("*/outline/[@type='rss']") if node.get("xmlUrl") is not None]


def backup_metadata(feed_url: str, rss: Dict, destination: Path) -> None:
	"""
	Backup metadata from RSS feed.

	Args:
		feed_url: Feed URL.
		rss: feedparser parsed feed.
		destination: Path to destination folder.
	"""
	dl.enqueue_file(feed_url, destination, "podcast.rss")

	feed_metadata = {}

	for field in rss["feed"].keys():
		if (field == 'image') and (rss["feed"].get('image', None)):
			v = rss["feed"].image.href
			dl.enqueue_file(v, destination, "cover.jpg")
		else:
			v = rss["feed"][field]
		feed_metadata[field] = v

	feed_metadata['episode_count'] = len(rss["entries"])

	(destination / "meta.json").write_text(json.dumps(feed_metadata))

	dl.download()


def download_episode(episode: Dict, backup_path: Path, backup_meta_path: Path) -> int:
	"""
	Download episode from URL.

	Args:
		episode: Parsed episode.
		backup_path: Path for audio.
		backup_meta_path: Path for metadata.

	Returns:
		1 if episode is new, else 0.
	"""
	episode_metadata = {}
	for field in episode.keys():
		episode_metadata[field] = episode.get(field, None)

	if episode_metadata.get('links', None):
		for link in episode_metadata['links']:
			if link.get('type', None):
				if 'audio' in link.get('type', None):
					episode_metadata['link'] = link.get('href', None)
					break

		episode_metadata.pop('links', None)

	date_string = time.strftime("%Y-%m-%d", episode_metadata['published_parsed'])
	extension = episode_metadata['link'].rsplit(".", 1)[1].split("?")[0]
	episode_name = sanitize_filename(f'{date_string} {episode_metadata["title"]}.{extension}')

	if not (backup_path / episode_name).exists():
		try:
			(backup_meta_path / sanitize_filename(episode_name + ".json")).write_text(json.dumps(episode_metadata))
			# download to meta folder and move later in case download was succesful, to avoid partial files
			dl.enqueue_file(episode_metadata['link'], backup_meta_path, episode_name)
		except Exception as e:
			log.error(f"Failed to download episode: {(backup_path / episode_name)}")
			log.error(e)
			return 0
		return 1
	return 0


def backup_feed(feed_url: str, destination: Path) -> None:
	"""
	Backup podcast from feed url.

	Args:
		feed_url: Feed URL.
		destination: Path to destination folder.
	"""
	rss: Dict = feedparser.parse(feed_url)
	title = rss["feed"]["title"]
	log.info(f'Backup feed: {title} ({feed_url})')
	backup_path = destination / sanitize_filename(title)
	backup_path.mkdir(parents=True, exist_ok=True)
	backup_meta_path = backup_path / "meta"
	backup_meta_path.mkdir(parents=True, exist_ok=True)

	new_episodes = 0
	feed_url_next_page: Optional[str] = feed_url
	while feed_url_next_page:
		episodes = rss.get('entries', False) or rss.get('items', False)
		if episodes:
			new_episodes += sum(download_episode(episode, backup_path, backup_meta_path) for episode in episodes)
		next_pages = [link['href'] for link in rss['feed']['links'] if link['rel'] == 'next']
		if len(next_pages) > 0:
			feed_url_next_page = next_pages[0]
			rss = feedparser.parse(feed_url)
		else:
			feed_url_next_page = None

	if new_episodes > 0:
		download_results = dl.download()
		for error in download_results.errors:
			log.error(error)
		for completed in download_results:
			Path(completed).rename(backup_path / Path(completed).name)
		backup_metadata(feed_url, rss, backup_meta_path)


def tqdm_updater(progress_bar: Any) -> None:
	"""
	Update tqdm progress bar every second.

	Args:
		progress_bar: tqdm progress bar.
	"""
	while True:  # noqa: WPS457
		time.sleep(1000)
		progress_bar.refresh()


def backup_opml(opml: Path, destination: Path = cwd) -> None:
	"""
	Backup podcasts from opml file.

	Args:
		opml: Path to OPML file.
		destination: Path to destination folder, defaults to cwd.
	"""
	log.info(f"Backing podcasts from: {opml} to: {destination}")
	for feed_url in tqdm(parse_opml(Path(opml)), desc="Feeds"):
		try:
			backup_feed(feed_url, Path(destination))
		except Exception as e:
			log.error(f"Failed to backup feed: {feed_url}")
			log.error(e)


if __name__ == "__main__":
	fire.Fire(backup_opml)
