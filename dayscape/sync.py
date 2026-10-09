"""Git backup and sync functionality."""

import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

class SyncManager(QObject):
    syncStarted = Signal()
    syncFinished = Signal(bool, str)  # success, message

    def __init__(self, db_path: Path, get_url_cb, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.db_dir = self.db_path.parent
        self.get_url_cb = get_url_cb

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self._run_backup_async)

    def schedule_backup(self):
        self.timer.start()

    def _run_backup_async(self):
        url = self.get_url_cb()
        if not url:
            return
        self.syncStarted.emit()
        threading.Thread(target=self._backup_worker, args=(url,), daemon=True).start()

    def sync_manual(self):
        url = self.get_url_cb()
        if not url:
            self.syncFinished.emit(False, "No repository URL configured.")
            return
        self.syncStarted.emit()
        threading.Thread(target=self._sync_worker, args=(url,), daemon=True).start()

    def _run_git(self, *args) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.db_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=20
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            err = (e.stderr or "") + "\n" + (e.stdout or "")
            return False, err.strip() or str(e)
        except subprocess.TimeoutExpired as e:
            return False, f"Command timed out after {e.timeout}s. If using SSH, ensure your key doesn't require a passphrase prompt, or use a credential helper."
        except Exception as e:
            return False, str(e)

    def _init_repo_if_needed(self, url: str) -> bool:
        is_repo, _ = self._run_git("rev-parse", "--is-inside-work-tree")
        if not is_repo:
            success, err = self._run_git("init")
            if not success:
                return False
            # Set default branch to main
            self._run_git("branch", "-M", "main")
            
        # Update or set remote
        has_remote, remotes = self._run_git("remote")
        if not has_remote or "origin" not in remotes:
            self._run_git("remote", "add", "origin", url)
        else:
            self._run_git("remote", "set-url", "origin", url)
        return True

    def _backup_worker(self, url: str):
        if not self._init_repo_if_needed(url):
            self.syncFinished.emit(False, "Failed to initialize repository.")
            return

        # Add the db file
        self._run_git("add", self.db_path.name)
        
        # Check if there are changes
        has_changes, status = self._run_git("status", "--porcelain")
        if has_changes and status.strip():
            # Commit
            success, err = self._run_git("commit", "-m", "Auto backup")
            if not success:
                self.syncFinished.emit(False, f"Commit failed: {err}")
                return
                
        # Push
        success, err = self._run_git("push", "-u", "origin", "main")
        if success:
            self.syncFinished.emit(True, "Backup successful.")
        else:
            self.syncFinished.emit(False, f"Push failed: {err}")

    def _sync_worker(self, url: str):
        if not self._init_repo_if_needed(url):
            self.syncFinished.emit(False, "Failed to initialize repository.")
            return

        # Commit local changes first before pulling to avoid conflicts losing local data
        self._run_git("add", self.db_path.name)
        has_changes, status = self._run_git("status", "--porcelain")
        if has_changes and status.strip():
            self._run_git("commit", "-m", "Auto commit before sync")
            
        # Pull with rebase
        success, err = self._run_git("pull", "--rebase", "origin", "main")
        if not success:
            # Maybe the remote branch doesn't exist yet, try to fetch and check
            fetch_succ, _ = self._run_git("fetch", "origin")
            if not fetch_succ:
                self.syncFinished.emit(False, f"Sync failed: {err}")
                return
                
        # Push
        success, err = self._run_git("push", "-u", "origin", "main")
        if success:
            self.syncFinished.emit(True, "Sync successful.")
        else:
            self.syncFinished.emit(False, f"Sync (push) failed: {err}")
