"""Storage and sync settings."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLineEdit, QPushButton

from dayscape.store import Store
from dayscape.widgets.common import Card, label, caps

class StorageView(QWidget):
    def __init__(self, store: Store, sync_mgr=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.sync_mgr = sync_mgr

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 32)
        root.setSpacing(18)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("Storage", "h1"))
        titles.addWidget(label("Manage your local and remote backups", "muted"))
        head.addLayout(titles)
        head.addStretch(1)
        root.addLayout(head)

        scard = Card(margins=20)

        h = QHBoxLayout()
        h.addWidget(caps("Git Remote Backup"))
        h.addStretch(1)
        scard.body.addLayout(h)

        sdesc = label("Set a remote Git repository URL to automatically backup your journal. Changes are debounced and pushed 5 seconds after a save. Local git credentials (e.g., SSH keys) will be used.", "muted")
        sdesc.setStyleSheet("font-size: 14px;")
        scard.body.addWidget(sdesc)
        sdesc.setWordWrap(True)

        scard.body.addSpacing(10)

        self.git_url = QLineEdit()
        self.git_url.setPlaceholderText("git@github.com:user/repo.git")
        self.git_url.setText(self.store.get_setting("git_url", ""))
        self.git_url.textChanged.connect(lambda t: self.store.set_setting("git_url", t))
        self.git_url.setStyleSheet("font-size: 14px; padding: 8px; border-radius: 6px;")
        scard.body.addWidget(self.git_url)

        scard.body.addSpacing(24)

        sync_head = QHBoxLayout()
        sync_head.addWidget(caps("Manual Sync"))
        sync_head.addStretch(1)
        scard.body.addLayout(sync_head)

        sync_desc = label("Sync with the remote repository in case the local version is not up to date.", "muted")
        sync_desc.setStyleSheet("font-size: 14px;")
        scard.body.addWidget(sync_desc)
        sync_desc.setWordWrap(True)

        scard.body.addSpacing(10)

        self.sync_btn = QPushButton("Sync Now")
        self.sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_btn.setStyleSheet("font-size: 14px; padding: 8px 20px;")
        if self.sync_mgr:
            self.sync_btn.clicked.connect(self.sync_mgr.sync_manual)
            self.sync_mgr.syncStarted.connect(lambda: self.sync_btn.setText("Syncing..."))
        else:
            self.sync_btn.setEnabled(False)
            self.sync_btn.setToolTip("Not available in demo mode")

        h_sync = QHBoxLayout()
        h_sync.addWidget(self.sync_btn, 0)

        self.sync_status = label("", "statHint")
        self.sync_status.setStyleSheet("font-size: 13px;")
        self.sync_status.setWordWrap(True)
        if self.sync_mgr:
            def on_finished(ok: bool, msg: str):
                self.sync_btn.setText("Sync Now")
                self.sync_status.setStyleSheet("font-size: 13px; color: {};".format("#6CC67C" if ok else "#C93752"))
                self.sync_status.setText(msg)
                
            self.sync_mgr.syncFinished.connect(on_finished)
        h_sync.addWidget(self.sync_status, 1, Qt.AlignmentFlag.AlignVCenter)
        h_sync.addStretch(1)

        scard.body.addLayout(h_sync)

        root.addWidget(scard)
        root.addStretch(1)
