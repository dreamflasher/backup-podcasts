# backup podcasts

[![wemake-python-styleguide](https://img.shields.io/badge/style-wemake-000000.svg)](https://github.com/wemake-services/wemake-python-styleguide)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

Most feature-complete Podcast backup/archive software. Download all available data for all your podcasts, including metadata (RSS, shownote, cover) and supplementary files (transcripts, videos etc.). Intended to be run as a cron-job, skips existing files and never deletes any previous data, even if it's removed from the online podcast.

Insallation:

`pip install backup-podcasts`

Features:

* OPML import
* RSS pagination
* Backup metadata (RSS, shownotes, cover)
* Graceful interruption behaviour (no half-downloaded files, even when killed)
* File-system compatible filename sanization (format: `pubdate - title`)
* Download all related files (transcripts, videos, etc.)

Usage:

`python -m backup_podcasts --opml "path_to.opml" --destination "/target/backup/location"`

Destination is optional, defaults to cwd.
