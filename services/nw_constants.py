"""Need/Want encoding — the single source of truth.

The transaction entry screen has always written these three values:

    0 = Not Set (untagged)
    1 = Need
    2 = Want

Readers elsewhere previously assumed ``1 = Need, 0 = Want``, which silently
counted every *untagged* transaction as a Want and made real Wants (2)
invisible. Import from here instead of hard-coding the integers.
"""

NW_NONE = 0
NW_NEED = 1
NW_WANT = 2
NW_NOT_APPLICABLE = 3

# Need/Want is a behavioural expense classification. Income, transfers and
# wealth/ledger movements are deliberately distinct from an untagged expense.
NW_LABELS = {
    NW_NONE: "Not Set",
    NW_NEED: "Need",
    NW_WANT: "Want",
    NW_NOT_APPLICABLE: "Not Applicable",
}

# Label -> value, for filter chips and combos.
NW_FROM_LABEL = {
    "Need": NW_NEED,
    "Want": NW_WANT,
    "Not Set": NW_NONE,
    "Not Applicable": NW_NOT_APPLICABLE,
    "None": NW_NONE,      # legacy chip label
}

# Values that mean "the user actually tagged this".
NW_TAGGED = (NW_NEED, NW_WANT)


def nw_label(value):
    """Human label for a stored neednwant value (None-safe)."""
    if value is None:
        return NW_LABELS[NW_NONE]
    return NW_LABELS.get(value, NW_LABELS[NW_NONE])


def is_need(value):
    return value == NW_NEED


def is_want(value):
    return value == NW_WANT


def is_untagged(value):
    """True for NULL or 0 — anything the user hasn't classified."""
    return value not in NW_TAGGED


def split_need_want(rows, amount_key="amount", nw_key="neednwant",
                    type_key="tx_type", debit_only=True):
    """Total DEBIT spend split into (need, want, untagged).

    Used by Home, Database, Audit and the PDF reports so every surface
    reports the same figures.
    """
    need = want = none = 0.0
    for r in rows:
        if debit_only and r.get(type_key) != "DEBIT":
            continue
        amt = r.get(amount_key) or 0
        nw = r.get(nw_key)
        if nw == NW_NOT_APPLICABLE:
            continue
        if nw == NW_NEED:
            need += amt
        elif nw == NW_WANT:
            want += amt
        else:
            none += amt
    return need, want, none
