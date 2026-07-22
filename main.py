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
    NotesRepo, CardsRepo, AuditRepo, BudgetsRepo, RecurringRepo
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
        "cards": CardsRepo(db), "budgets": BudgetsRepo(db),
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

    def show_main_window():
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
            splash.set_status("Preparing data...")
            app.processEvents()
            mw.showMaximized()
            mw.raise_()
            mw.activateWindow()
            QTimer.singleShot(300, splash.close)

        QTimer.singleShot(50, _step1)

    if not services["security"].is_setup():
        from ui.login.setup_wizard import SetupWizard
        wizard = SetupWizard(services["security"], repos["accounts"])
        _app_windows["wizard"] = wizard  # prevent GC

        def on_setup_done():
            wizard.close()
            wizard.deleteLater()
            show_main_window()

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
