"""Walkthrough — Full-page guided tour with detailed content database."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor
from ui.theme import C


# ═══════════════════════════════════════════════
# WALKTHROUGH CONTENT DATABASE
# Each entry has: title, icon, tab_key, sections (list of sub-topics)
# ═══════════════════════════════════════════════

WALKTHROUGH_DB = [
    {
        "title": "Home",
        "icon": "\U0001f3e0",
        "tab_key": "home",
        "sections": [
            {
                "heading": "Dashboard Overview",
                "body": "The Home page is your financial command center. It shows a quick summary of your finances at a glance with period-based KPI cards and quick access tiles."
            },
            {
                "heading": "KPI Period Cards",
                "body": "Four clickable period cards:\n\u2022  Today \u2014 Today's income and expenses\n\u2022  This Week \u2014 Current week totals\n\u2022  This Month \u2014 Current month totals\n\u2022  This Year \u2014 Year-to-date totals\n\nEach card shows Credits, Debits, Net, and Transaction count. The selected card is highlighted with an indigo border. Click any card to switch the view."
            },
            {
                "heading": "Account Summary",
                "body": "Below the KPIs, account cards show your balances grouped by type (Bank, Cash, Wallet, Credit Card). Each card displays:\n\u2022  Net amount for the selected period\n\u2022  Credits and Debits breakdown\n\u2022  Start and End balance for the period"
            },
            {
                "heading": "Quick Access Tiles",
                "body": "Tiles provide one-click access to every tab:\n\u2022  Transactions, Database, Balances (Daily)\n\u2022  Credit Cards, Debit Cards (Cards)\n\u2022  Audit, Wealth (Review & Planning)\n\u2022  Notes, Settings, Gmail (Tools)"
            },
            {
                "heading": "How to Use",
                "body": "Start your day by checking the Today card. Switch between periods by clicking different KPI cards. Use quick access tiles to jump to specific sections. The Home page refreshes automatically when you make changes in other tabs."
            },
        ],
    },
    {
        "title": "Transactions",
        "icon": "\U0001f4dd",
        "tab_key": "transaction_entry",
        "sections": [
            {
                "heading": "Recording Transactions",
                "body": "This is where you record every income and expense. Fill in the fields and click 'Add Transaction'. The form supports keyboard-only navigation."
            },
            {
                "heading": "Fields Explained",
                "body": "\u2022  Account \u2014 Which account this transaction belongs to (searchable dropdown)\n\u2022  Category \u2014 What type of expense/income (Food, Transport, etc.)\n\u2022  Method \u2014 How you paid (UPI, Cash, Card, etc.)\n\u2022  Type \u2014 DEBIT (money out) or CREDIT (money in) \u2014 toggle button\n\u2022  Amount \u2014 How much\n\u2022  Person/Org \u2014 Who you paid or received from\n\u2022  Description \u2014 What it was for\n\u2022  Need/Want \u2014 Budgeting tag (Need = essential, Want = optional)\n\u2022  PF Category \u2014 Auto-set from category (Commitment, Consumption, Growth, Safety, NC)"
            },
            {
                "heading": "DEBIT/CREDIT Toggle",
                "body": "Click the DEBIT/CREDIT button to switch the transaction type. DEBIT = money going out (expense). CREDIT = money coming in (income). The button color changes to indicate the current type."
            },
            {
                "heading": "Need/Want Buttons",
                "body": "Three buttons for budgeting:\n\u2022  Need \u2014 Essential expenses (rent, groceries, bills)\n\u2022  Want \u2014 Non-essential expenses (entertainment, shopping)\n\u2022  (empty) \u2014 Not classified\n\nThis helps track spending patterns in the Audit tab insights."
            },
            {
                "heading": "Auto-Create",
                "body": "If you type a payment method or category that doesn't exist, the app will create it automatically. No need to pre-configure everything."
            },
            {
                "heading": "Transfer Tab",
                "body": "Switch to the Transfer tab to move money between your own accounts:\n\u2022  Select From and To accounts (searchable)\n\u2022  Swap button to reverse direction\n\u2022  Enter amount, method, date\n\u2022  Creates two linked transactions (DEBIT from source, CREDIT to destination)\n\u2022  Both transactions share a transfer_group_id for tracking"
            },
            {
                "heading": "Recent Transactions",
                "body": "Below the form, recent transactions for the selected account appear. Click any transaction to view details. The list updates when you change the date or account."
            },
            {
                "heading": "Tips",
                "body": "\u2022  Use Tab key to move between fields quickly\n\u2022  Enter key submits the form\n\u2022  Category icons appear in transaction cards throughout the app\n\u2022  Amount starts at \u20b91 (not 0) to prevent accidental zero-amount entries"
            },
        ],
    },
    {
        "title": "Database",
        "icon": "\U0001f5c4\ufe0f",
        "tab_key": "database",
        "sections": [
            {
                "heading": "Three Views",
                "body": "The Database tab shows all your transactions in three different formats, each optimized for different use cases."
            },
            {
                "heading": "Complete View",
                "body": "Shows every transaction with:\n\u2022  Running balance per account (computed via SQL window function)\n\u2022  Search bar (person, description, amount, category, account)\n\u2022  Lazy scroll (loads in batches, configurable page size in Settings)\n\u2022  Month and date headers\n\u2022  Category icons and colors on each transaction card\n\u2022  Transaction kind badges (\U0001f517 for wealth-linked, Updated for recently modified)"
            },
            {
                "heading": "Monthly View",
                "body": "Select a month and year to see:\n\u2022  Transaction list grouped by date\n\u2022  5 KPI cards: Transactions, Credits, Debits, Net, Transfers\n\u2022  Account summary grouped by type (Bank, Cash, Wallet, Credit Card)\n\u2022  Each account card shows: Credits, Debits, Start Balance, End Balance\n\u2022  Print to PDF with full statement"
            },
            {
                "heading": "Filtered View",
                "body": "Advanced filtering with:\n\u2022  Date range selector (From/To)\n\u2022  Exact or Sequential filter mode toggle\n\u2022  Field selector (Account, Category, Method, Type, Kind, Need/Want, PF Category, Person, Description, Min/Max Amount)\n\u2022  Multi-value chip filters (add multiple values per field)\n\u2022  Stats bar: transaction count, Credits, Debits, Net\n\u2022  Print to PDF"
            },
        ],
    },
    {
        "title": "Credit Cards",
        "icon": "\U0001f4b3",
        "tab_key": "cards",
        "sections": [
            {
                "heading": "3D Carousel",
                "body": "Your credit cards are displayed in a 3D carousel with smooth animation:\n\u2022  Drag or scroll to browse cards\n\u2022  Left/Right arrow keys scroll\n\u2022  Space bar flips the nearest card\n\u2022  Cards show: bank name, brand, utilization bar, network, class"
            },
            {
                "heading": "Card Front & Back",
                "body": "Front of card shows:\n\u2022  Bank name and co-brand\n\u2022  Chip graphic\n\u2022  Utilization bar (color-coded: green < 30%, amber < 70%, red > 70%)\n\u2022  Network name (VISA, Mastercard, etc.)\n\u2022  Card class (Platinum, Signature, etc.)\n\nBack of card shows:\n\u2022  'VIEW ACCOUNT DETAILS' stripe (click to open)\n\u2022  Cardholder name\n\u2022  Card number (masked)\n\u2022  Expiry date"
            },
            {
                "heading": "Active & Closed Cards",
                "body": "Two sub-tabs:\n\u2022  Active Cards \u2014 Currently in use\n\u2022  Closed Cards \u2014 Deactivated or expired cards\n\nCards auto-close when their expiry date passes. Add new cards with the '+ Add Card' button."
            },
            {
                "heading": "Account Details",
                "body": "Click 'VIEW ACCOUNT DETAILS' on a card back to see:\n\u2022  Header: card name, network, class, edit button\n\u2022  Billing info: Limit, Statement date, Amount Due, Due Date, Current Outstanding\n\u2022  Transactions grouped by billing cycle (FIFO allocation)\n\u2022  Each cycle header: cycle name, Spent, Paid, Remaining\n\u2022  Editable due dates per cycle (click to change)"
            },
            {
                "heading": "FIFO Billing",
                "body": "Credit card billing uses FIFO (First-In-First-Out) payment allocation:\n\u2022  Payments are allocated to the oldest unpaid cycle first\n\u2022  Each cycle tracks: Debits, Paid, Remaining\n\u2022  Amount Due = sum of remaining from all previous cycles\n\u2022  Current Outstanding = total balance on the card"
            },
            {
                "heading": "Settlement",
                "body": "Use the footer to record credit card payments:\n\u2022  Select Amount Due or Current Outstanding (or Custom)\n\u2022  Choose source account and payment method\n\u2022  Settlement creates two linked transactions (DEBIT from source, CREDIT to card)\n\u2022  FIFO cycles are recalculated after settlement"
            },
            {
                "heading": "Reminders",
                "body": "The right panel shows:\n\u2022  Upcoming statement dates (5 days before)\n\u2022  Due date reminders with amount\n\u2022  Overdue warnings (red)\n\u2022  High-value transaction alerts (configurable threshold in Settings)"
            },
        ],
    },
    {
        "title": "Debit Cards",
        "icon": "\U0001f4b3",
        "tab_key": "debit_cards",
        "sections": [
            {
                "heading": "Card Management",
                "body": "Manage debit cards linked to your current accounts. Each debit card is connected to a bank account (CURRENT type). A current account can have multiple debit cards."
            },
            {
                "heading": "3D Carousel",
                "body": "Same 3D carousel as credit cards with metallic gradient themes:\n\u2022  Drag or scroll to browse cards\n\u2022  Click to flip (shows card back with number, expiry)\n\u2022  Click stripe to view account details\n\u2022  20 metallic gradient themes (Titanium, Gunmetal, Platinum, Chrome, Carbon, etc.)"
            },
            {
                "heading": "Account Details",
                "body": "Click a card to view:\n\u2022  Header: card name, network, connected account name, edit button\n\u2022  Transactions from the connected current account\n\u2022  Monthly grouping with Debits, Credits, Surplus/Deficit"
            },
            {
                "heading": "Smart Lazy Scroll",
                "body": "Transactions use smart lazy loading:\n\u2022  Loads 1 month initially\n\u2022  If < 4 transactions, auto-loads next month (up to 6)\n\u2022  On scroll, loads 1-3 more months\n\u2022  Monthly headers show accurate totals (pre-computed)\n\u2022  Colors: green for surplus, red for deficit"
            },
            {
                "heading": "Auto-Close on Expiry",
                "body": "Cards automatically move to 'Closed' when their expiry month passes. No manual action needed."
            },
            {
                "heading": "Adding a Debit Card",
                "body": "Click '+ Add Card' to add:\n\u2022  Card Name \u2014 e.g., 'SBI Debit Card'\n\u2022  Bank \u2014 Select from your CURRENT accounts only\n\u2022  Network \u2014 VISA, Mastercard, RuPay, AMEX\n\u2022  Last 4 Digits, Cardholder Name, Expiry\n\u2022  Annual Fee\n\u2022  Card Style \u2014 Choose from 20 metallic gradient themes"
            },
            {
                "heading": "Edit & Deactivate",
                "body": "Edit card details or deactivate:\n\u2022  Same fields as Add Card\n\u2022  Activate/Deactivate toggle button\n\u2022  Deactivated cards move to 'Closed Cards' view"
            },
        ],
    },
    {
        "title": "Audit",
        "icon": "\U0001f50d",
        "tab_key": "audit",
        "sections": [
            {
                "heading": "Transaction Review",
                "body": "The Audit tab lets you review and edit ALL transactions (regular + wealth-linked) in one place. Two sub-tabs: Records and Insights."
            },
            {
                "heading": "Filters",
                "body": "Advanced filter system:\n\u2022  Date range (From/To)\n\u2022  Field filters (Account, Category, Method, Type, Kind, Need/Want, PF Category, Person, Description, Min/Max Amount)\n\u2022  Multi-value chips (add multiple values per field)\n\u2022  Stats bar: transaction count, Credits, Debits, Net"
            },
            {
                "heading": "Editing Transactions",
                "body": "Click the Edit button on any transaction:\n\u2022  Edit all fields (date, account, type, amount, category, method, person, description, need/want, PF)\n\u2022  Changes to amount/date cascade to linked wealth records\n\u2022  Password/TOTP verification required before saving\n\u2022  Updating popup with progress indicator"
            },
            {
                "heading": "Field Locking",
                "body": "Some fields are locked for wealth-linked transactions:\n\u2022  Type (DEBIT/CREDIT) \u2014 locked for all wealth-linked\n\u2022  Amount and Date \u2014 locked for closed wealth records\n\u2022  Person/Org \u2014 locked for all wealth-linked (auto-generated)"
            },
            {
                "heading": "Bulk Update",
                "body": "Select multiple transactions using checkboxes (Select/Done toggle buttons):\n\u2022  Change Category, Need/Want, or PF Category in bulk\n\u2022  Verification required before applying\n\u2022  Progress popup shows 'Updating X/Y...'\n\u2022  Done popup shows count of updated transactions"
            },
            {
                "heading": "Delete & Transfer",
                "body": "Delete transactions with safety:\n\u2022  Transfer detection \u2014 warns that both related transactions will be deleted\n\u2022  Warning shows details of related transaction\n\u2022  Verification required\n\u2022  Wealth-linked transactions cannot be deleted from audit\n\u2022  Audit log entries cleaned up before delete"
            },
            {
                "heading": "Wealth Linking",
                "body": "Transactions linked to wealth records show:\n\u2022  \U0001f517 badge with link type (Loan Given, FD Deposit, FD Withdrawal, etc.)\n\u2022  'Updated' badge when recently modified\n\u2022  Changes cascade to the linked wealth record\n\u2022  Status recalculation after amount/date changes\n\u2022  Badge sync between audit and wealth tabs"
            },
            {
                "heading": "Insights",
                "body": "The Insights sub-tab shows:\n\u2022  Total Credits, Debits, Net, Transaction count\n\u2022  Expense by Category (doughnut chart)\n\u2022  Spending by Account (horizontal bar)\n\u2022  Daily Cash Flow (line chart)\n\u2022  Need vs Want breakdown\n\u2022  Monthly aggregation for ranges > 90 days"
            },
        ],
    },
    {
        "title": "Wealth",
        "icon": "\U0001f4c8",
        "tab_key": "wealth",
        "sections": [
            {
                "heading": "Five Sub-Tabs",
                "body": "Wealth tracks five types of financial instruments, each with Entry and List views:\n\u2022  Loans I Give \u2014 Money lent to others\n\u2022  Loans I Take \u2014 Money borrowed from others (EMI and Non-EMI)\n\u2022  FD I Deposit \u2014 Fixed deposits you hold\n\u2022  FD Others \u2014 Deposits received from others\n\u2022  Mutual Funds \u2014 MF investments with live NAV tracking"
            },
            {
                "heading": "Expandable Cards",
                "body": "Each item is an expandable card:\n\u2022  Click to expand \u2192 shows details, edit button, repayment history\n\u2022  Click again to collapse\n\u2022  Color-coded by status (Active=indigo, Overdue=red, Repaid=green, Closed=gray)\n\u2022  Progress bar shows repayment percentage\n\u2022  'Updated' badge when recently modified"
            },
            {
                "heading": "Performance & Search",
                "body": "Each sub-tab has optimized performance:\n\u2022  Batch database queries (single query for all items instead of per-item)\n\u2022  Sort by: Status, Name, Amount, Due Date\n\u2022  Ascending/Descending toggle\n\u2022  Search by name\n\u2022  Print PDF for pending items"
            },
            {
                "heading": "Status Tracking",
                "body": "Status is auto-calculated based on date and amount:\n\u2022  ACTIVE \u2014 No payments yet\n\u2022  PARTIALLY_PAID \u2014 Some payments made\n\u2022  OVERDUE \u2014 Past due date\n\u2022  REPAID \u2014 Fully paid (amount-based check)\n\u2022  CLOSED \u2014 Manually closed"
            },
            {
                "heading": "Repayment Editing",
                "body": "Click a repayment card to expand and edit:\n\u2022  Change amount, date, description\n\u2022  Changes cascade to linked transactions\n\u2022  Status recalculated after edit\n\u2022  Verification required\n\u2022  Not available for closed items"
            },
            {
                "heading": "Mark as Closed",
                "body": "For REPAID items, click 'Mark as Closed' to archive. Closed items:\n\u2022  Cannot be edited\n\u2022  Repayments cannot be edited\n\u2022  Move to 'Closed' view"
            },
            {
                "heading": "Mutual Funds",
                "body": "MF sub-tab has special features:\n\u2022  Live NAV fetch from MFAPI (background thread)\n\u2022  Current value calculation (units \u00d7 NAV)\n\u2022  Return percentage\n\u2022  Transaction history per scheme\n\u2022  Scheme editing with re-link to API"
            },
            {
                "heading": "FD Features",
                "body": "FD sub-tab has:\n\u2022  Maturity amount calculation (simple/compound interest)\n\u2022  Progress bar showing time elapsed\n\u2022  Mark as Matured when past maturity date\n\u2022  Withdrawal with interest calculation and fee deduction"
            },
        ],
    },
    {
        "title": "Notes",
        "icon": "\U0001f4cb",
        "tab_key": "notes",
        "sections": [
            {
                "heading": "Three Views",
                "body": "Notes tab has three sub-views:\n\u2022  All Notes \u2014 Active notes with search and tag filtering\n\u2022  Trash \u2014 Deleted notes for recovery\n\u2022  Composer (hidden) \u2014 For creating/editing notes"
            },
            {
                "heading": "Note Cards",
                "body": "Each note is a card showing:\n\u2022  Title (bold)\n\u2022  Content preview (truncated)\n\u2022  Tag chips (color-coded based on tag name)\n\u2022  Created/updated date\n\u2022  Pin indicator for pinned notes"
            },
            {
                "heading": "Tag System",
                "body": "Tags help organize notes:\n\u2022  Predefined tags: Personal, Business, Tax, Recurring, Important\n\u2022  Add custom tags in Settings \u2192 Note Tags\n\u2022  Color-coded chip display\n\u2022  Filter notes by tag in the search bar"
            },
            {
                "heading": "Creating & Editing Notes",
                "body": "Click '+ New Note' to create:\n\u2022  Title (required)\n\u2022  Content (rich text)\n\u2022  Tags (select from available tags)\n\u2022  Click note card to edit\n\u2022  Notes auto-save as you type"
            },
            {
                "heading": "Pin & Search",
                "body": "\u2022  Pin important notes to keep them at the top\n\u2022  Search by title or content\n\u2022  Filter by tags using chip selection\n\u2022  Lazy scroll for large note collections"
            },
            {
                "heading": "Trash & Recovery",
                "body": "Deleted notes go to Trash:\n\u2022  Recover notes from trash\n\u2022  Permanently delete from trash\n\u2022  Trash shows deletion date"
            },
        ],
    },
    {
        "title": "Balances",
        "icon": "\U0001f4b0",
        "tab_key": "balances",
        "sections": [
            {
                "heading": "Account Cards",
                "body": "Each account is displayed as a card showing:\n\u2022  Account name and type badge\n\u2022  Current balance (large, prominent)\n\u2022  Account type icon (Bank, Cash, Wallet, Credit Card)\n\u2022  Color-coded by type"
            },
            {
                "heading": "Credit Card Details",
                "body": "Credit card accounts show additional info:\n\u2022  Credit limit\n\u2022  Utilization percentage with color bar\n\u2022  Statement balance vs current balance"
            },
            {
                "heading": "Account Transactions",
                "body": "Click an account card to view:\n\u2022  Recent transactions for that account\n\u2022  Lazy scroll for large transaction lists\n\u2022  Transaction cards with category icons"
            },
            {
                "heading": "Net Worth",
                "body": "Total net worth displayed at the top, calculated from all account balances."
            },
        ],
    },
    {
        "title": "Settings",
        "icon": "\u2699\ufe0f",
        "tab_key": "settings",
        "sections": [
            {
                "heading": "Accounts",
                "body": "Manage your accounts:\n\u2022  Add/edit bank accounts, cash, wallets\n\u2022  Grouped by type (Bank, Cash, Wallet)\n\u2022  Single-line rows with type badge, opening balance, edit/activate buttons\n\u2022  'OPENING BALANCE' label for clarity\n\u2022  Credit card accounts managed from Credit Cards tab"
            },
            {
                "heading": "Categories",
                "body": "Manage expense/income categories:\n\u2022  Icon selector with emoji palette (96 icons in 8 categories: Food, Transport, Shopping, Home, Health, Entertainment, Objects, Nature)\n\u2022  Color picker with 24-color disc palette\n\u2022  PF Category (Commitment, Consumption, Growth, Safety, NC)\n\u2022  Tax deductible flag\n\u2022  Edit button per category with instant update"
            },
            {
                "heading": "Payment Methods",
                "body": "Manage payment methods:\n\u2022  Add new payment methods\n\u2022  Activate/Deactivate toggle (deactivated methods hidden from dropdowns)\n\u2022  Deactivated methods still show in historical transactions\n\u2022  Status indicator (Active/Inactive)"
            },
            {
                "heading": "Security",
                "body": "Protect your data:\n\u2022  2FA (TOTP) with authenticator app \u2014 compact toggle button\n\u2022  Google account linking for alternative login\n\u2022  Password change\n\u2022  Tab-level security with toggle buttons (Wealth, Audit, Database, Credit Cards, Notes, Gmail, Settings)\n\u2022  Password/TOTP verification when enabling/disabling tab protection"
            },
            {
                "heading": "Preferences",
                "body": "Customize behavior:\n\u2022  Pagination: Transactions (min 30), Wealth (min 10), Notes (min 10)\n\u2022  Scroll trigger distance\n\u2022  High-value transaction alert threshold\n\u2022  Display settings (Theme, Currency)"
            },
            {
                "heading": "Data Management",
                "body": "Backup and storage:\n\u2022  Manual backup with one click\n\u2022  Backup location, retention count, last backup date\n\u2022  Database size and total backup size\n\u2022  Coming soon: Data export (CSV/Excel), import, take down, cloud sync"
            },
            {
                "heading": "User Guide",
                "body": "Documentation and walkthrough:\n\u2022  Walk Through \u2014 Interactive topic-based guide with 'Go to tab' navigation\n\u2022  Functions \u2014 Detailed feature descriptions\n\u2022  Working Scheme \u2014 Technical architecture and data flow\n\u2022  UI Details \u2014 Interface component descriptions"
            },
        ],
    },
    {
        "title": "Gmail",
        "icon": "\U0001f4e7",
        "tab_key": "gmail",
        "sections": [
            {
                "heading": "Gmail Integration",
                "body": "Gmail integration for transaction suggestions:\n\u2022  Parse bank notification emails\n\u2022  Suggest transactions based on email content\n\u2022  Auto-fill transaction fields from email data\n\nNote: Gmail sync requires configuration. Contact support for setup."
            },
        ],
    },
    {
        "title": "Security System",
        "icon": "\U0001f512",
        "tab_key": None,
        "sections": [
            {
                "heading": "Authentication",
                "body": "Two authentication methods:\n\u2022  Password \u2014 Traditional password login\n\u2022  TOTP (2FA) \u2014 6-digit code from authenticator app\n\nToggle between them in Settings \u2192 Security."
            },
            {
                "heading": "Google Login",
                "body": "Alternative login method:\n\u2022  Link your Google account in Settings\n\u2022  Click 'Sign in with Google' on login screen\n\u2022  Google verifies your identity each time\n\u2022  Useful if you forget your password"
            },
            {
                "heading": "Tab Security",
                "body": "Protect specific tabs:\n\u2022  Enable in Settings \u2192 Security \u2192 Tab Security\n\u2022  Choose which tabs to protect (Wealth, Audit, etc.)\n\u2022  Password/TOTP required when navigating to protected tabs\n\u2022  Toggle buttons with verification for each tab"
            },
            {
                "heading": "Edit Verification",
                "body": "All edits require verification:\n\u2022  Wealth tab edits \u2192 TOTP/password popup\n\u2022  Audit tab edits \u2192 TOTP/password popup\n\u2022  Delete operations \u2192 Confirmation + verification\n\u2022  Bulk updates \u2192 Verification before applying"
            },
        ],
    },
    {
        "title": "Data & Backup",
        "icon": "\U0001f4e6",
        "tab_key": None,
        "sections": [
            {
                "heading": "Local Storage",
                "body": "All data is stored locally:\n\u2022  SQLite database (finance.db)\n\u2022  No internet required\n\u2022  No data sent to external servers\n\u2022  Complete privacy"
            },
            {
                "heading": "Automatic Backups",
                "body": "Backups happen automatically:\n\u2022  On app close (via closeEvent)\n\u2022  Location: finance_data/backups/\n\u2022  Retention: Last 14 backups\n\u2022  Format: finance_YYYYMMDD_HHMMSS.db"
            },
            {
                "heading": "Manual Backup",
                "body": "Create backups manually:\n\u2022  Settings \u2192 Data Management \u2192 Backup Now\n\u2022  Shows backup location and count\n\u2022  Shows storage size"
            },
            {
                "heading": "Recovery",
                "body": "To restore from backup:\n\u2022  Close the app\n\u2022  Replace finance.db with a backup file\n\u2022  Restart the app\n\nComing soon: In-app restore, cloud backup, data export/import"
            },
        ],
    },
]


# ═══════════════════════════════════════════════
# WALKTHROUGH PAGE WIDGET
# ═══════════════════════════════════════════════

class WalkthroughPage(QWidget):
    """Full-page walkthrough with topic list and detail view."""
    navigate_to = pyqtSignal(str)  # emits tab key to navigate

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_topic = 0
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Left: Topic list ──
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet(f"background:{C['surface2']};border-right:1px solid {C['border2']};")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(8, 12, 8, 12)
        left_lay.setSpacing(2)

        header = QLabel("\U0001f9ed Topics")
        header.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['text']};padding:8px 8px 12px;")
        left_lay.addWidget(header)

        self.topic_btns = []
        for i, topic in enumerate(WALKTHROUGH_DB):
            btn = QPushButton(f"  {topic['icon']}  {topic['title']}")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setMinimumHeight(36)
            btn.setStyleSheet(self._topic_btn_css(i == 0))
            btn.clicked.connect(lambda _, idx=i: self._select_topic(idx))
            left_lay.addWidget(btn)
            self.topic_btns.append(btn)

        left_lay.addStretch()
        lay.addWidget(left)

        # ── Right: Detail area ──
        right = QWidget()
        right.setStyleSheet("background:transparent;")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(32, 20, 32, 20)
        right_lay.setSpacing(16)

        # Topic title
        self.title_label = QLabel()
        self.title_label.setStyleSheet(f"font-size:24px;font-weight:800;color:{C['text']};")
        right_lay.addWidget(self.title_label)

        # Go to tab button
        self.goto_btn = QPushButton("\U0001f517  Go to this tab")
        self.goto_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;border:none;"
            f"border-radius:8px;padding:8px 20px;font-size:13px;font-weight:600;}}"
            f"QPushButton:hover{{background:#4338CA;}}")
        self.goto_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.goto_btn.clicked.connect(self._go_to_tab)
        self.goto_btn.setFixedHeight(36)
        right_lay.addWidget(self.goto_btn, alignment=Qt.AlignLeft)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C['border2']};")
        right_lay.addWidget(sep)

        # Scrollable content
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background:transparent;")
        self.content_lay = QVBoxLayout(self.content_widget)
        self.content_lay.setSpacing(20)
        self.content_lay.setContentsMargins(0, 0, 8, 0)
        self.content_scroll.setWidget(self.content_widget)
        right_lay.addWidget(self.content_scroll, 1)

        # Navigation buttons
        nav_row = QHBoxLayout()
        nav_row.setSpacing(12)
        self.prev_btn = QPushButton("\u2190  Previous")
        self.prev_btn.setStyleSheet(
            f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:8px 20px;font-size:13px;font-weight:600;}}"
            f"QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}")
        self.prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.prev_btn.clicked.connect(self._prev_topic)
        nav_row.addWidget(self.prev_btn)
        nav_row.addStretch()
        self.next_btn = QPushButton("Next  \u2192")
        self.next_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;border:none;"
            f"border-radius:8px;padding:8px 24px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:#4338CA;}}")
        self.next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.next_btn.clicked.connect(self._next_topic)
        nav_row.addWidget(self.next_btn)
        right_lay.addLayout(nav_row)

        lay.addWidget(right, 1)

        # Show first topic
        self._select_topic(0)

    def _topic_btn_css(self, active):
        if active:
            return (f"QPushButton{{background:{C['accent']};color:white;border:none;"
                    f"border-radius:8px;padding:8px 12px;text-align:left;font-size:12px;font-weight:700;}}")
        return (f"QPushButton{{background:transparent;color:{C['text2']};border:none;"
                f"border-radius:8px;padding:8px 12px;text-align:left;font-size:12px;font-weight:500;}}"
                f"QPushButton:hover{{background:{C['surface']};color:{C['text']};}}")

    def _select_topic(self, idx):
        """Select and display a topic."""
        self._current_topic = idx
        topic = WALKTHROUGH_DB[idx]

        # Update topic button styles
        for i, btn in enumerate(self.topic_btns):
            btn.setStyleSheet(self._topic_btn_css(i == idx))

        # Update title
        self.title_label.setText(f"{topic['icon']}  {topic['title']}")

        # Show/hide go-to-tab button
        self.goto_btn.setVisible(topic.get("tab_key") is not None)

        # Clear content
        while self.content_lay.count():
            itm = self.content_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()

        # Build sections
        for section in topic["sections"]:
            frame = QFrame()
            frame.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};"
                f"border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(16, 12, 16, 12)
            fl.setSpacing(6)

            heading = QLabel(section["heading"])
            heading.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
            fl.addWidget(heading)

            body = QLabel(section["body"])
            body.setStyleSheet(f"font-size:12px;color:{C['text2']};line-height:1.5;")
            body.setWordWrap(True)
            fl.addWidget(body)

            self.content_lay.addWidget(frame)

        self.content_lay.addStretch()

        # Update nav buttons
        self.prev_btn.setVisible(idx > 0)
        self.next_btn.setText("Finish  \u2713" if idx == len(WALKTHROUGH_DB) - 1 else "Next  \u2192")

        # Scroll to top
        self.content_scroll.verticalScrollBar().setValue(0)

    def _next_topic(self):
        if self._current_topic < len(WALKTHROUGH_DB) - 1:
            self._select_topic(self._current_topic + 1)

    def _prev_topic(self):
        if self._current_topic > 0:
            self._select_topic(self._current_topic - 1)

    def _go_to_tab(self):
        topic = WALKTHROUGH_DB[self._current_topic]
        if topic.get("tab_key"):
            self.navigate_to.emit(topic["tab_key"])
