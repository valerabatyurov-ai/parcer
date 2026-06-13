from __future__ import annotations

from schemas import StakePlan


def implied_sum(odds_1: float, odds_2: float) -> float:
    return (1 / odds_1) + (1 / odds_2)


def profit_percent(odds_1: float, odds_2: float) -> float:
    total = implied_sum(odds_1, odds_2)
    return (1 / total - 1) * 100


def calculate_stakes(bankroll_rub: float, odds_1: float, odds_2: float) -> StakePlan:
    total = implied_sum(odds_1, odds_2)
    stake_1 = bankroll_rub * (1 / odds_1) / total
    stake_2 = bankroll_rub * (1 / odds_2) / total
    payout_1 = stake_1 * odds_1
    payout_2 = stake_2 * odds_2
    expected_payout = min(payout_1, payout_2)
    return StakePlan(
        stake_1=stake_1,
        stake_2=stake_2,
        expected_payout=expected_payout,
        profit_rub=expected_payout - bankroll_rub,
    )
