# Wealth → Dashboard: Bug Fixes

**Only ONE source file changed:** `ui/tabs/wealth_tab.py`
**Patch file (apply to your local repo):** `wealth_dashboard_fixes.patch`

---

## How to get these changes into your local repo

### Option A — apply the patch file (recommended)

Copy `wealth_dashboard_fixes.patch` into your local repo root, then:

```bash
cd /path/to/your/Fin_m_arena
git apply --check wealth_dashboard_fixes.patch   # dry run, prints nothing if OK
git apply wealth_dashboard_fixes.patch
```

If `git apply` complains because your copy has drifted:

```bash
patch -p1 --fuzz=3 < wealth_dashboard_fixes.patch
```

### Option B — copy the whole file

Just overwrite your local `ui/tabs/wealth_tab.py` with the one from this
branch. Nothing else in the project was touched, so there is no risk of a
half-applied change.

### Option C — review first, then hand-edit

```bash
git diff ui/tabs/wealth_tab.py          # full diff
git diff --stat ui/tabs/wealth_tab.py   # 382 insertions, 101 deletions
```

**Note:** no database file was changed. During testing some `finance_data/*.db`
files got touched and were restored with `git checkout --`, so your data is
untouched.

---

## Where the changes are (line numbers in the fixed file)

| Lines | What |
|---|---|
| 97–200 | **New** shared helpers: `_months_between`, `_is_overdue`, `_days_since`, `_batch_sum_db`, `_batch_rows_db`, `borrowed_outstanding`, `deposit_outstanding` |
| 2946 | `FDOthersPage.load_list` — interest-bearing "fully paid" check |
| 3244, 3269 | `MFPage` — new `_nav_updated` signal, emitted after live NAVs arrive |
| 4601–4640 | `DashboardPage.__init__` / `set_nav` / `_bind_click` / `_navigate` |
| 4725 | `_go_to_split` — parent-chain fallback |
| 4811 | **New** `_sync_statuses()` |
| 4843–5100 | `refresh()` — rewritten |
| 5179–5199 | `WealthTab._on_mf_navs_updated`, `_goto` |

---

## The bugs that were fixed

### 1. Every KPI card and quick-access tile was dead (nothing happened on click)

`_kpi_card()` and `_tile()` attached their click handler behind
`elif self._nav_cb:`. But `_build()` runs inside `__init__`, and `set_nav()`
is only called by `WealthTab` *afterwards* — so `_nav_cb` was still `None`
and the branch never ran. 10 of 12 cards had no handler at all.

Fixed by recording the clickable widgets during build and binding them in
`set_nav()`. Verified: 12/12 now carry a handler, 10 navigate and 2 route to
the Split tab.

### 2. "Loans I Take" total contradicted the Loans I Take page

Dashboard did `principal - repaid`, ignoring interest, EMI vs non-EMI, and
compounding. The sub-page runs a full `LoanService` analysis.

On your real data: dashboard said **₹949.67**, the page said **₹966.67**.

Both now call the shared `borrowed_outstanding()` helper and agree.

### 3. FD Others was counted as an asset — it's a liability

"FD Others" is money *other people deposited with you*, which you owe back
(its ledger entry is a CREDIT, same direction as a loan you take). The
dashboard added it to **Receivable**.

With ₹5,00,056 of deposits this flipped the headline figure from
**+₹6,13,915** to the correct **−₹3,86,213**. Net position is now
`investments + receivable − payable + split`, with deposits in payable.
The card and tile were also recoloured red (they were green) and the
net-bar labels got tooltips explaining what feeds each number.

### 4. Matured FDs silently vanished from net worth

KPI 3 summed only `status='ACTIVE'`. An FD that matured but hasn't been
withdrawn is still your money, and it was counted nowhere — the detail line
said "1 active / 0 matured" while the value ignored matured rows entirely.
Matured value is now included.

### 5. Dashboard showed "0 overdue" until you opened a sub-tab

Each sub-page calls `sync_overdue()` in its own `load_list()`. The dashboard
never did, so it read stale statuses. Demonstrated with a loan 30 days past
due: dashboard said `0 overdue / 1 active` and **0 alerts**, then after
merely *visiting* the Loans page the same untouched data became
`1 overdue / 1 active` with **2 alerts**.

Added `_sync_statuses()`, which now runs at the top of `refresh()`.

### 6. Crash: `TypeError: '>' not supported between 'NoneType' and 'int'`

The next-EMI loop did `r["emi_amount"] > 0` with no null guard. Any borrowed
loan with a future due date and a NULL `emi_amount` took the whole dashboard
down. Reproduced, then fixed with `(r.get("emi_amount") or 0)`.

### 7. Alerts leaked widgets on every refresh

Alert rows were added with `addLayout()`, but the cleanup loop only called
`deleteLater()` on `itm.widget()` — which is `None` for a nested layout. The
labels stayed parented to the frame forever: 25 → 50 → 75 → 100 labels after
four refreshes, invisibly stacking behind each other.

Rows are now real `QWidget`s cleared via the existing recursive
`_clear_layout()`. Verified flat at 25 across repeated refreshes.

### 8. Overdue alerts showed the original amount, not what's still owed

A ₹10,000 loan with ₹9,500 repaid displayed "₹10,000 overdue". Alerts now
show true outstanding.

### 9. FDs with no linked bank account never raised a maturity alert

The alert query used an inner `JOIN accounts`, so any FD whose
`bank_account_id` is NULL was dropped. Changed to `LEFT JOIN` with a
"Fixed Deposit" fallback label.

### 10. Bogus "EMI ₹0.00 due …" alert rows

The EMI-due query had no `emi_amount > 0` filter, so non-EMI loans produced
meaningless zero-rupee reminders. Filtered out.

### 11. Deposits you owe back had no alerts at all

Every other wealth category raised alerts; deposits from others raised none.
Added overdue and due-within-30-days alerts for them.

### 12. Dashboard used stale mutual-fund NAVs

`MFPage` fetches live NAVs in a background thread and caches them, but the
dashboard always recomputed from the last transaction's NAV. It now reads
the MF page's cache and refreshes when the new signal fires.

### 13. Smaller items

- `FDOthersPage.load_list` had `fully_paid = total >= principal  # simplified
  for batch` in the interest-bearing branch, so an interest-bearing deposit
  was marked REPAID once the principal was covered, while accrued interest
  was still outstanding. Now uses the real analysis.
- KPI 4's detail line counted *all* non-closed deposits as "active".
- `_go_to_split()` did nothing when `window()` wasn't the MainWindow; it now
  walks the parent chain.
- `_goto()` had no bounds check.
- N+1 repayment queries replaced with batched lookups.
- KPI 3 tile/card relabelled "FD Deposits" → "FD I Deposit" to match the nav
  button, and "1 unsettled groups" → "1 unsettled group".

---

## Verification

- All **99** existing tests in `test_suite.py` pass.
- Every KPI now matches its sub-page exactly on your real database:

| KPI | Sub-page | Dashboard |
|---|---|---|
| Loans I Give | ₹92,422.40 | ₹92,422.40 |
| Loans I Take | ₹966.67 | ₹966.67 |
| FD I Deposit | ₹151.50 | ₹151.50 |
| FD Others | ₹5,00,056.00 | ₹5,00,056.00 |
| Mutual Funds | ₹21,869.47 | ₹21,869.47 |

- No crash on an empty database, or on rows with NULL due dates, NULL EMI
  amounts, NULL maturity amounts and unlinked accounts.
