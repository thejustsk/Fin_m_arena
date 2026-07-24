"""Finance Manager v3 — Entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Fix WebEngine OpenGL warning — must be set BEFORE QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

from db.connection import Database
from db.schema import run_migrations
from db.repositories import (
    AccountsRepo, TransactionsRepo, LookupsRepo, SecurityRepo,
    LoansRepo, BorrowedRepo, DepositsRepo, FDRepo, MFRepo,
    NotesRepo, CardsRepo, DebitCardsRepo, AuditRepo, BudgetsRepo, RecurringRepo
)
from services.balance_service import BalanceService
from services.security_service import SecurityService
from services.audit_service import AuditService
from services.email_service import EmailService


# Module-level references — prevents garbage collection
_app_windows = {}


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    db = Database()
    db.connect()
    run_migrations(db)

    repos = {
        "accounts": AccountsRepo(db), "transactions": TransactionsRepo(db),
        "lookups": LookupsRepo(db), "security": SecurityRepo(db),
        "audit": AuditRepo(db), "loans": LoansRepo(db),
        "borrowed": BorrowedRepo(db), "deposits": DepositsRepo(db),
        "fd": FDRepo(db), "mf": MFRepo(db), "notes": NotesRepo(db),
        "cards": CardsRepo(db), "debit_cards": DebitCardsRepo(db), "budgets": BudgetsRepo(db),
        "recurring": RecurringRepo(db),
    }
    services = {
        "balance": BalanceService(repos["accounts"]),
        "security": SecurityService(repos["security"]),
        "audit": AuditService(repos["audit"], repos["transactions"], db),
        "email": EmailService(db),
    }

    from ui.theme import QSS
    app.setStyleSheet(QSS)

    def show_main_window(show_walkthrough_prompt=False):
        from ui.loading_dialog import LoadingDialog
        from PyQt5.QtCore import QTimer

        splash = LoadingDialog()
        splash.show()
        app.processEvents()

        def _step1():
            splash.set_status("Loading accounts & categories...")
            app.processEvents()
            QTimer.singleShot(50, _step2)

        def _step2():
            splash.set_status("Building interface...")
            app.processEvents()
            from ui.main_window import MainWindow
            mw = MainWindow(db, repos, services)
            _app_windows["main"] = mw
            QTimer.singleShot(50, lambda: _step3(mw))

        def _step3(mw):
            splash.set_status("Preparing home page...")
            app.processEvents()
            mw.showMaximized()
            mw.raise_()
            mw.activateWindow()
            # Close splash once window is visible — home page is ready
            QTimer.singleShot(300, lambda: _close_splash(splash))
            # Continue pre-loading wealth + notes in background (non-blocking)
            QTimer.singleShot(500, lambda: _preload_pages(mw, 0))
            # Show walkthrough prompt after setup wizard
            if show_walkthrough_prompt:
                QTimer.singleShot(800, lambda: _ask_walkthrough(mw))

        def _close_splash(splash):
            splash.close()
            splash.deleteLater()

        def _ask_walkthrough(mw):
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
            from ui.theme import C

            dlg = QDialog(mw)
            dlg.setWindowTitle("Welcome!")
            dlg.setMinimumWidth(440)
            dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(28, 24, 28, 24)
            lay.setSpacing(16)

            icon = QLabel("\U0001f9ed")
            icon.setStyleSheet("font-size:48px;background:transparent;border:none;")
            icon.setAlignment(Qt.AlignCenter)
            lay.addWidget(icon)

            title = QLabel("Welcome to Finance Manager!")
            title.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['text']};background:transparent;border:none;")
            title.setAlignment(Qt.AlignCenter)
            lay.addWidget(title)

            desc = QLabel("Setup complete! Would you like to take a quick walkthrough\nto learn how the app works?")
            desc.setStyleSheet(f"font-size:13px;color:{C['text2']};background:transparent;border:none;")
            desc.setAlignment(Qt.AlignCenter)
            desc.setWordWrap(True)
            lay.addWidget(desc)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)

            skip_btn = QPushButton("Skip")
            skip_btn.setStyleSheet(
                f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};"
                f"border-radius:8px;padding:10px 24px;font-size:13px;font-weight:600;}}"
                f"QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}")
            skip_btn.setCursor(Qt.PointingHandCursor)
            skip_btn.setMinimumHeight(42)
            skip_btn.clicked.connect(dlg.reject)
            btn_row.addWidget(skip_btn)

            go_btn = QPushButton("\U0001f9ed  Take Walkthrough")
            go_btn.setStyleSheet(
                f"QPushButton{{background:{C['accent']};color:white;border:none;"
                f"border-radius:8px;padding:10px 24px;font-size:13px;font-weight:700;}}"
                f"QPushButton:hover{{background:#4338CA;}}")
            go_btn.setCursor(Qt.PointingHandCursor)
            go_btn.setMinimumHeight(42)
            go_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(go_btn)

            lay.addLayout(btn_row)

            if dlg.exec_() == QDialog.Accepted:
                mw._nav("settings")
                settings_tab = mw._tabs.get("settings")
                if settings_tab and hasattr(settings_tab, "go_to_walkthrough"):
                    settings_tab.go_to_walkthrough()

        def _preload_pages(mw, idx):
            """Pre-load wealth + notes pages in background after splash closes."""
            pages_to_load = []
            wealth = mw._tabs.get("wealth")
            if wealth and hasattr(wealth, '_pages'):
                for p in wealth._pages:
                    pages_to_load.append(p)
            notes = mw._tabs.get("notes")
            if notes:
                pages_to_load.append(notes)

            if idx >= len(pages_to_load):
                return  # all done

            page = pages_to_load[idx]
            page.load_list()
            # Continue with next page after a short delay (keeps UI responsive)
            QTimer.singleShot(100, lambda: _preload_pages(mw, idx + 1))

        QTimer.singleShot(50, _step1)

    if not services["security"].is_setup():
        from ui.login.setup_wizard import SetupWizard
        wizard = SetupWizard(services["security"], repos["accounts"])
        _app_windows["wizard"] = wizard  # prevent GC

        def on_setup_done():
            wizard.close()
            wizard.deleteLater()
            show_main_window(show_walkthrough_prompt=True)

        wizard.done.connect(on_setup_done)
        wizard.show()
    else:
        from ui.login.login_screen import LoginScreen
        screen = LoginScreen(services["security"])
        _app_windows["login"] = screen  # prevent GC

        def on_login_success():
            screen.close()
            screen.deleteLater()
            show_main_window()

        screen.success.connect(on_login_success)
        screen.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
