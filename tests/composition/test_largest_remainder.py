from backend.app.composer import allocate_largest_remainder


PERCENTAGES = {"选必二": 0.45, "选必一": 0.30, "必修": 0.20, "cross_book": 0.05}
TIE_ORDER = ["选必二", "选必一", "必修", "cross_book"]


def test_29_question_paper_rounding() -> None:
    assert allocate_largest_remainder(29, PERCENTAGES, TIE_ORDER) == {
        "选必二": 13,
        "选必一": 9,
        "必修": 6,
        "cross_book": 1,
    }


def test_30_question_paper_rounding() -> None:
    assert allocate_largest_remainder(30, PERCENTAGES, TIE_ORDER) == {
        "选必二": 14,
        "选必一": 9,
        "必修": 6,
        "cross_book": 1,
    }


def test_42_question_paper_rounding() -> None:
    assert allocate_largest_remainder(42, PERCENTAGES, TIE_ORDER) == {
        "选必二": 19,
        "选必一": 13,
        "必修": 8,
        "cross_book": 2,
    }
