"""Token ledger. Voice stages spend it; a level adds to it when a token is collected.

Balance `None` means unlimited tokens — used for testing so charges still
log without ever rejecting a spend. A played level starts finite at zero.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Entry:
    reason: str
    amount: int
    stage: str


@dataclass(frozen=True)
class Ledger:
    """Token balance and spend log. `balance is None` means infinite."""

    balance: int | None
    spent: int = 0
    entries: tuple[Entry, ...] = ()


@dataclass(frozen=True)
class ChargeOk:
    ledger: Ledger


@dataclass(frozen=True)
class InsufficientCredits:
    need: int
    have: int


def testing_ledger() -> Ledger:
    """Infinite balance for local demos and hackathon testing."""
    return Ledger(balance=None)


def finite_ledger(balance: int) -> Ledger:
    return Ledger(balance=max(0, balance))


def charge(
    ledger: Ledger, amount: int, *, reason: str, stage: str
) -> ChargeOk | InsufficientCredits:
    if amount < 0:
        amount = 0
    if ledger.balance is not None and ledger.balance < amount:
        return InsufficientCredits(need=amount, have=ledger.balance)
    entry = Entry(reason=reason, amount=amount, stage=stage)
    new_balance = None if ledger.balance is None else ledger.balance - amount
    return ChargeOk(
        ledger=replace(
            ledger,
            balance=new_balance,
            spent=ledger.spent + amount,
            entries=ledger.entries + (entry,),
        )
    )


def grant(ledger: Ledger, amount: int, *, reason: str) -> Ledger:
    """Add tokens to a finite balance. An unlimited ledger stays unlimited."""
    if amount <= 0 or ledger.balance is None:
        return ledger
    entry = Entry(reason=reason, amount=amount, stage="grant")
    return replace(
        ledger,
        balance=ledger.balance + amount,
        entries=ledger.entries + (entry,),
    )


def remaining(ledger: Ledger) -> str:
    if ledger.balance is None:
        return "infinite"
    return str(ledger.balance)
