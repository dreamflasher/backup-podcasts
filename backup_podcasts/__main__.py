#!/bin/env python3
"""Backup/archive all episodes of your podcast subscriptions locally."""
import fire
from backup_podcasts.backup_podcasts import backup_opml

if __name__ == "__main__":
	fire.Fire(backup_opml)
