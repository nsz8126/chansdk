# -*- coding: utf-8 -*-
"""
Layer 5 Tests: chan.seg module
Covers: CSeg construction, invariants (min 3 strokes, price direction),
CEigen characteristic sequence, and CSegList.
"""

import pytest
from chan.common.enum import BI_DIR, KLINE_DIR, FX_TYPE
from chan.common.exception import CChanException, ErrCode
from chan.bi.bi import CBi
from chan.kline.kline import CKLine
from chan.seg.seg import CSeg
from chan.seg.eigen import CEigen
from tests.conftest import create_klu


def make_mock_bi(idx: int, _dir: BI_DIR, begin_price: float, end_price: float) -> CBi:
    """Creates a standalone CBi object for segment testing."""
    k1 = create_klu(2024, 1, 1, begin_price, max(begin_price, end_price), min(begin_price, end_price), begin_price)
    k2 = create_klu(2024, 1, 5, end_price, max(begin_price, end_price), min(begin_price, end_price), end_price)
    klc1 = CKLine(k1, idx * 5, KLINE_DIR.UP if _dir == BI_DIR.UP else KLINE_DIR.DOWN)
    klc2 = CKLine(k2, idx * 5 + 4, KLINE_DIR.UP if _dir == BI_DIR.UP else KLINE_DIR.DOWN)
    if _dir == BI_DIR.UP:
        klc1.set_fx(FX_TYPE.BOTTOM)
        klc2.set_fx(FX_TYPE.TOP)
    else:
        klc1.set_fx(FX_TYPE.TOP)
        klc2.set_fx(FX_TYPE.BOTTOM)
    bi = CBi(klc1, klc2, idx=idx, is_sure=True)
    return bi


class TestCSegInvariants:
    """Tests for Segment invariants and validation rules."""

    def test_valid_up_segment(self):
        """Upward segment: bi0(UP, 10->20), bi1(DOWN, 20->15), bi2(UP, 15->30)."""
        bi0 = make_mock_bi(0, BI_DIR.UP, 10.0, 20.0)
        bi1 = make_mock_bi(1, BI_DIR.DOWN, 20.0, 15.0)
        bi2 = make_mock_bi(2, BI_DIR.UP, 15.0, 30.0)
        seg = CSeg(idx=0, start_bi=bi0, end_bi=bi2, is_sure=True)
        assert seg.is_up() is True
        assert seg.dir == BI_DIR.UP
        assert seg.get_begin_val() == 10.0
        assert seg.get_end_val() == 30.0

    def test_valid_down_segment(self):
        """Downward segment: bi0(DOWN, 50->30), bi1(UP, 30->40), bi2(DOWN, 40->20)."""
        bi0 = make_mock_bi(0, BI_DIR.DOWN, 50.0, 30.0)
        bi1 = make_mock_bi(1, BI_DIR.UP, 30.0, 40.0)
        bi2 = make_mock_bi(2, BI_DIR.DOWN, 40.0, 20.0)
        seg = CSeg(idx=0, start_bi=bi0, end_bi=bi2, is_sure=True)
        assert seg.is_down() is True
        assert seg.dir == BI_DIR.DOWN
        assert seg.get_begin_val() == 50.0
        assert seg.get_end_val() == 20.0

    def test_segment_violating_price_direction_raises(self):
        """Upward segment where end price is lower than begin price must raise SEG_END_VALUE_ERR."""
        bi0 = make_mock_bi(0, BI_DIR.UP, 100.0, 110.0)  # Start price 100
        bi2 = make_mock_bi(2, BI_DIR.UP, 40.0, 50.0)    # End price 50
        with pytest.raises(CChanException) as exc_info:
            CSeg(idx=0, start_bi=bi0, end_bi=bi2, is_sure=True)
        assert exc_info.value.errcode == ErrCode.SEG_END_VALUE_ERR


class TestCEigenCharacteristicSequence:
    """Tests for CEigen characteristic sequence element merging and gap tracking."""

    def test_eigen_creation_and_gap_detection(self):
        bi0 = make_mock_bi(0, BI_DIR.DOWN, 20.0, 10.0)
        bi1 = make_mock_bi(1, BI_DIR.DOWN, 35.0, 25.0)  # Gap up from bi0 (25 > 20)
        bi2 = make_mock_bi(2, BI_DIR.DOWN, 28.0, 18.0)

        e0 = CEigen(bi0, _dir=KLINE_DIR.UP)
        e1 = CEigen(bi1, _dir=KLINE_DIR.UP)
        e2 = CEigen(bi2, _dir=KLINE_DIR.DOWN)

        # Wire pre and next
        e0.set_next(e1)
        e1.set_pre(e0); e1.set_next(e2)
        e2.set_pre(e1)

        # Update fx for e1
        e1.update_fx(e0, e2)
        assert e1.fx == FX_TYPE.TOP
        # There was a gap because e0.high (20) < e1.low (25)
        assert e1.gap is True
