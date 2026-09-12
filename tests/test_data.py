# -*- coding: utf-8 -*-
"""
Deterministic synthetic K-line data generators for testing Chan Theory algorithms.
"""

from typing import List
from chan.kline.unit import CKLine_Unit
from tests.conftest import create_klu


def generate_monotone_up(count: int = 10, start_price: float = 10.0, step: float = 1.0) -> List[CKLine_Unit]:
    """Generates strictly upward K-lines with no inclusion relations."""
    result = []
    price = start_price
    for i in range(1, count + 1):
        # Day increment
        month = 1 + (i - 1) // 28
        day = (i - 1) % 28 + 1
        klu = create_klu(
            year=2024,
            month=month,
            day=day,
            open_p=price,
            high_p=price + step * 0.8,
            low_p=price - step * 0.2,
            close_p=price + step * 0.6,
            volume=1000.0 + i * 10,
        )
        result.append(klu)
        price += step
    return result


def generate_monotone_down(count: int = 10, start_price: float = 100.0, step: float = 1.0) -> List[CKLine_Unit]:
    """Generates strictly downward K-lines with no inclusion relations."""
    result = []
    price = start_price
    for i in range(1, count + 1):
        month = 1 + (i - 1) // 28
        day = (i - 1) % 28 + 1
        klu = create_klu(
            year=2024,
            month=month,
            day=day,
            open_p=price,
            high_p=price + step * 0.2,
            low_p=price - step * 0.8,
            close_p=price - step * 0.6,
            volume=1000.0 + i * 10,
        )
        result.append(klu)
        price -= step
    return result


def generate_included_sequence_up() -> List[CKLine_Unit]:
    """
    K-line sequence with upward inclusion:
    K1: [10, 15, 9, 14]
    K2: [11, 13, 10, 12] (included inside K1)
    K3: [12, 18, 11, 17] (breakout up)
    """
    return [
        create_klu(2024, 1, 1, open_p=10.0, high_p=15.0, low_p=9.0, close_p=14.0),
        create_klu(2024, 1, 2, open_p=11.0, high_p=13.0, low_p=10.0, close_p=12.0),
        create_klu(2024, 1, 3, open_p=12.0, high_p=18.0, low_p=11.0, close_p=17.0),
    ]


def generate_included_sequence_down() -> List[CKLine_Unit]:
    """
    K-line sequence with downward inclusion:
    K1: [15, 16, 10, 11]
    K2: [13, 14, 11, 12] (included inside K1)
    K3: [11, 12, 8, 9] (breakout down)
    """
    return [
        create_klu(2024, 1, 1, open_p=15.0, high_p=16.0, low_p=10.0, close_p=11.0),
        create_klu(2024, 1, 2, open_p=13.0, high_p=14.0, low_p=11.0, close_p=12.0),
        create_klu(2024, 1, 3, open_p=11.0, high_p=12.0, low_p=8.0, close_p=9.0),
    ]


def generate_top_fractal() -> List[CKLine_Unit]:
    """
    Clear top fractal (3 bars):
    K1: low 10, high 15
    K2: low 12, high 20 (peak)
    K3: low 9, high 14
    """
    return [
        create_klu(2024, 1, 1, open_p=11.0, high_p=15.0, low_p=10.0, close_p=14.0),
        create_klu(2024, 1, 2, open_p=14.0, high_p=20.0, low_p=12.0, close_p=18.0),
        create_klu(2024, 1, 3, open_p=13.0, high_p=14.0, low_p=9.0, close_p=10.0),
    ]


def generate_bottom_fractal() -> List[CKLine_Unit]:
    """
    Clear bottom fractal (3 bars):
    K1: low 15, high 20
    K2: low 8, high 14 (trough)
    K3: low 11, high 18
    """
    return [
        create_klu(2024, 1, 1, open_p=19.0, high_p=20.0, low_p=15.0, close_p=16.0),
        create_klu(2024, 1, 2, open_p=13.0, high_p=14.0, low_p=8.0, close_p=10.0),
        create_klu(2024, 1, 3, open_p=12.0, high_p=18.0, low_p=11.0, close_p=17.0),
    ]


def generate_single_up_bi() -> List[CKLine_Unit]:
    """
    Generates a valid upward stroke (Bottom Fractal -> intermediate bars -> Top Fractal):
    Bottom center at day 2 (low 10).
    Top center at day 6 (high 30).
    Span = 6 - 2 = 4 (strictly satisfies bi_span >= 4).
    Follow-up bar at day 7 confirms the top fractal.
    """
    return [
        create_klu(2024, 1, 1, open_p=15.0, high_p=18.0, low_p=14.0, close_p=16.0),
        create_klu(2024, 1, 2, open_p=14.0, high_p=15.0, low_p=10.0, close_p=12.0),  # Bottom center
        create_klu(2024, 1, 3, open_p=13.5, high_p=19.0, low_p=13.0, close_p=18.0),
        create_klu(2024, 1, 4, open_p=18.0, high_p=23.0, low_p=17.0, close_p=22.0),
        create_klu(2024, 1, 5, open_p=22.0, high_p=26.0, low_p=21.0, close_p=25.0),
        create_klu(2024, 1, 6, open_p=25.0, high_p=30.0, low_p=24.0, close_p=29.0),  # Top center
        create_klu(2024, 1, 7, open_p=28.0, high_p=28.0, low_p=22.0, close_p=23.0),
        create_klu(2024, 1, 8, open_p=23.0, high_p=23.0, low_p=18.0, close_p=19.0),  # Confirmation
    ]


def generate_bi_series_for_zs() -> List[CKLine_Unit]:
    """
    Generates a series of K-lines forming at least 3 strokes overlapping into a Zhongshu (ZS):
    Bi 1 (UP): 10 -> 30
    Bi 2 (DOWN): 30 -> 18 (lowers into 18, so overlap [18, 30])
    Bi 3 (UP): 18 -> 26 (oscillates within [18, 30])
    Bi 4 (DOWN): 26 -> 15 (breakout down)
    Each stroke has >= 5 bars to ensure clear fractals and valid span.
    """
    bars = []
    day = 1

    def add_bar(o, h, l, c):
        nonlocal day
        # Handle month rollover if day > 28
        month = 1 + (day - 1) // 28
        d = ((day - 1) % 28) + 1
        bars.append(create_klu(2024, month, d, o, h, l, c))
        day += 1

    # --- Bi 1: Bottom at 10 to Top at 30 ---
    # Bottom fractal
    add_bar(15, 17, 13, 14)  # 1
    add_bar(13, 14, 10, 11)  # 2: Trough = 10
    add_bar(12, 18, 12, 17)  # 3
    # Intermediates
    add_bar(17, 22, 16, 21)  # 4
    add_bar(21, 26, 20, 25)  # 5
    # Top fractal
    add_bar(25, 30, 24, 29)  # 6: Peak = 30
    add_bar(26, 27, 22, 23)  # 7

    # --- Bi 2: Top at 30 down to Bottom at 18 ---
    add_bar(23, 24, 20, 21)  # 8
    add_bar(21, 22, 18, 19)  # 9: Trough = 18
    add_bar(19, 21, 19, 21)  # 10

    # --- Bi 3: Bottom at 18 up to Top at 26 ---
    add_bar(21, 24, 20, 23)  # 11
    add_bar(23, 26, 22, 25)  # 12: Peak = 26
    add_bar(24, 24, 21, 22)  # 13

    # --- Bi 4: Top at 26 down to Bottom at 14 ---
    add_bar(21, 22, 17, 18)  # 14
    add_bar(18, 18, 14, 15)  # 15: Trough = 14
    add_bar(15, 17, 15, 16)  # 16

    return bars
