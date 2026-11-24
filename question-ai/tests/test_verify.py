import pytest

from qgen import verify
from qgen.schemas import Question, SourceRef
from qgen.schemas import Verification as V

V3 = ["A", "B", "C"]
V4 = ["A", "B", "C", "D"]


def b(expected, form="any", minimal=False, variables=V3, **kw):
    return verify.check_bool(V(kind="bool_expr", variables=variables, expected=expected, form=form,
                               minimal=minimal, **kw))


# ---------- 실제로 나온 사례 ----------

def test_11_21_q1_wrong_answer_is_caught():
    """112142 q1: F = A'B + BC + AC'에서 BC를 지운 오답. 실제 최소식은 B + AC'."""
    issues = b("A'B + AC'", "SOP", True, function="A'B + BC + AC'")
    assert len(issues) == 1 and "A=1, B=1, C=1" in issues[0]
    assert b("B + AC'", "SOP", True, function="A'B + BC + AC'") == []


def test_11_21_verified_q1_passes():
    """115412 q1 최종 정답 (코드 검산으로 맞음 확인했던 것)."""
    m = dict(minterms=[1, 3, 6, 7])
    assert b("A'C + AB", "SOP", True, **m) == []
    assert b("(A+C)(A'+B)", "POS", True, **m) == []
    assert b("(A+C)(A'+B)(B+C)", "POS", True, **m)[0].endswith("(리터럴 6개, 최소 POS 4개)")


def test_11_19_q1_attempts():
    """f = Σm(0,2,3,5,7,8,10,11) + d(4,15) — 11-19 보고서 §4.6 표와 같은 판정."""
    m = dict(minterms=[0, 2, 3, 5, 7, 8, 10, 11], dont_cares=[4, 15], variables=V4)
    assert b("B'D' + B'C + A'BD", "SOP", True, **m) == []                 # 참고 정답
    assert "A=1, B=1, C=0, D=1" in b("B'D' + B'C + BD", "SOP", True, **m)[0]   # m13에서 틀림
    assert b("(A'+B')(B'+D)(B+C+D')", "POS", True, **m) == []           # 참고 정답
    assert "A=1, B=1, C=0, D=1" in b("(B'+D)(B+C+D')", "POS", True, **m)[0]    # m13
    assert "최소가 아님" in b("(A'+B')(B+C+D')(B'+C'+D)", "POS", True, **m)[0]  # 맞지만 8리터럴


# ---------- 표기 ----------

@pytest.mark.parametrize("expr", [
    r"A'C + AB", r"$\bar{A}C+AB$", r"\overline{A}C + AB", r"¬A·C + A·B", r"F = A'C + AB",
    r"F(A,B,C) = A'C+AB", r"~A&C | A&B", r"A’C + AB", r"(A)'C + AB", r"\overline{A} \cdot C + A \cdot B",
])
def test_notations(expr):
    assert b(expr, minterms=[1, 3, 6, 7]) == []


def test_xor_nested_overline_and_long_names():
    assert b("A'B'C + A'BC' + AB'C' + ABC", function=r"A \oplus B \oplus C") == []
    assert b("x'y'z", function=r"\overline{x+y}z", variables=["x", "y", "z"]) == []
    assert b("x_1 x_0' + x_1' x_0", function="x_1 ⊕ x_0", variables=["x_1", "x_0"]) == []


def test_form_detection():
    assert b("A'C + AB", "POS", minterms=[1, 3, 6, 7])[0].endswith("POS 형태가 아님")
    assert b("(A+C)(A'+B)", "SOP", minterms=[1, 3, 6, 7])[0].endswith("SOP 형태가 아님")
    assert b("A", "SOP", minterms=[4, 5, 6, 7]) == [] and b("A", "POS", minterms=[4, 5, 6, 7]) == []


def test_min_literals():
    assert verify.min_sop_literals({1, 3, 6, 7}, set(), 3) == 4
    assert verify.min_sop_literals({2, 3, 4, 6, 7}, set(), 3) == 3   # B + AC'
    assert verify.min_sop_literals(set(range(8)), set(), 3) == 0
    assert verify.min_sop_literals({0, 3, 5, 6}, set(), 3) == 12        # XNOR류: 줄일 수 없음


def test_unreadable_is_reported_not_raised():
    q = Question(item_id="q1", qtype="계산형", stem="s", answer="a", sources=[SourceRef(file="a.pdf", page=1)],
                 verifications=[V(kind="bool_expr", variables=V3, minterms=[1], expected="A ? B"),
                                V(kind="bool_expr", variables=V3, minterms=[9], expected="A"),
                                V(kind="bool_expr", variables=V3, minterms=[1, 3, 6, 7], expected="A'C+AB", label="(1)")])
    r = verify.run(q)
    assert r.issues == [] and len(r.unreadable) == 2 and r.passed == ["(1) 불 식 F(A,B,C) = Σm(1, 3, 6, 7) → `A'C+AB`"]


# ---------- 수 표현 ----------

@pytest.mark.parametrize("value,expected", [
    ("-118.625", "0xC2ED4000"), ("-118.625", "C2ED4000_{16}"), ("-118.625", "$C2ED4000_{16}$"),
    ("-25.375", "1 10000011 10010110000000000000000"), ("-25.375", "0xC1CB0000"),
])
def test_ieee754_ok(value, expected):
    assert verify.check_ieee754(V(kind="ieee754", value=value, expected=expected)) == []


def test_ieee754_wrong():
    issues = verify.check_ieee754(V(kind="ieee754", value="-25.375", expected="0xC1CB8000", label="(1)"))
    assert issues and "C1CB0000" in issues[0]


@pytest.mark.parametrize("rep,expected,ok", [
    ("2s", "11111011", True), ("1s", "11111010", True), ("sm", "10000101", True),
    ("2s", "11111010", False), ("2s", "0xFB", True),
])
def test_int_repr(rep, expected, ok):
    issues = verify.check_int(V(kind="int_repr", value="-5", bits=8, repr=rep, expected=expected))
    assert (issues == []) == ok


def test_trivial_check_is_flagged():
    with pytest.raises(verify.ParseError):
        b("C", function="C", variables=["C"])


def test_constant_is_both_sop_and_pos():
    """2026-11-21 162212 q4-r1: 정답 `1`을 'SOP 형태가 아님'으로 잘못 판정했던 것."""
    assert b("1", "SOP", True, minterms=list(range(8))) == []
    assert b("0", "POS", True, minterms=[]) == []
