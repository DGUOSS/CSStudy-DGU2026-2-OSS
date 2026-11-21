"""기계적으로 확인할 수 있는 정답을 코드로 검산한다 (LLM 미사용, 비용 0).

LLM은 불 대수 간소화를 안정적으로 하지 못했다 (문제사항 G-04, V-03):
- 11-19 q1: 출제 정답 SOP·POS 모두 틀림, solver POS 3번 모두 틀림
- 11-21 `112142` q1: `A'B + BC + AC'`에서 BC를 중복 항으로 보고 지움 (실제로는 필요한 항)
그래서 generator가 `Question.verifications`에 검산 거리를 적고, 여기서 확인한다.

지원:
- bool_expr: 변수 목록 + 함수(민텀·don't care 또는 식) + 정답 식. 같은 함수인지(don't care 제외 전부 대입),
  form(SOP/POS) 형태인지, minimal이면 리터럴 수가 최소인지 (Quine-McCluskey + 최소 덮개 탐색)
- ieee754: 10진수 → 단정밀도/배정밀도 비트열(16진수 또는 2진수)
- int_repr: 10진 정수 → n비트 부호-크기 / 1의 보수 / 2의 보수
"""
from __future__ import annotations

import itertools
import re
import struct
from dataclasses import dataclass

from .schemas import Question, Verification

MAX_VARS = 8  # 이보다 변수가 많으면 최소 여부는 검사하지 않는다 (계산량)


class ParseError(ValueError):
    pass


# ---------- 불 식 읽기 ----------

def _normalize(expr: str, variables: list[str]) -> str:
    """LaTeX·여러 표기를 한 가지로: 부정은 ~X, 그리고 &, 또는 |, XOR ^."""
    s = expr.strip().strip("$").strip()
    s = re.sub(r"^[A-Za-z]\w*\s*(\([^()]*\))?\s*=", "", s)  # 앞의 'F =' / 'F(A,B,C) =' 제거
    s = s.replace("\\left", "").replace("\\right", "").replace("\\,", "").replace("\\;", "").replace("\\ ", "")
    s = s.replace("\\cdot", "&").replace("·", "&").replace("*", "&").replace("\\times", "&")
    s = s.replace("\\oplus", "^").replace("⊕", "^")
    s = s.replace("\\lor", "|").replace("\\vee", "|").replace("∨", "|").replace("+", "|")
    s = s.replace("\\land", "&").replace("\\wedge", "&").replace("∧", "&")
    s = s.replace("\\neg", "~").replace("¬", "~").replace("!", "~")
    s = s.replace("’", "'").replace("′", "'").replace("‘", "'")
    # \overline{...} / \bar{...} → ~(...)  (중첩 괄호 처리)
    while True:
        m = re.search(r"\\(?:overline|bar)\s*\{", s)
        if not m:
            break
        depth, i = 1, m.end()
        while i < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[i], 0)
            i += 1
        if depth:
            raise ParseError("\\overline/\\bar 중괄호 짝이 맞지 않음")
        s = s[:m.start()] + "~(" + s[m.end():i - 1] + ")" + s[i:]
    s = re.sub(r"\\(?:overline|bar)\s*([A-Za-z]\w*)", r"~(\1)", s)
    s = s.replace("{", "(").replace("}", ")")
    # 변수 위 결합 문자 (A̅)
    s = s.replace("\u0305", "'")
    s = re.sub(r"\s+", "", s)
    return s


def _tokenize(s: str, variables: list[str]) -> list[str]:
    names = sorted(variables, key=len, reverse=True)
    toks, i = [], 0
    while i < len(s):
        c = s[i]
        if c in "()~'&|^01":
            toks.append(c)
            i += 1
            continue
        for v in names:
            if s.startswith(v, i):
                toks.append(v)
                i += len(v)
                break
        else:
            raise ParseError(f"알 수 없는 글자 '{s[i:i + 8]}' (변수: {variables})")
    return toks


@dataclass
class _Node:
    op: str  # "var" "const" "not" "and" "or" "xor"
    args: tuple = ()
    name: str = ""
    value: int = 0

    def eval(self, env: dict[str, int]) -> int:
        if self.op == "var":
            return env[self.name]
        if self.op == "const":
            return self.value
        vals = [a.eval(env) for a in self.args]
        if self.op == "not":
            return 1 - vals[0]
        if self.op == "and":
            return int(all(vals))
        if self.op == "or":
            return int(any(vals))
        out = 0
        for v in vals:
            out ^= v
        return out


class _Parser:
    """우선순위: 부정(~, 뒤 ') > 그리고(&, 붙여 쓰기) > XOR(^) > 또는(|)."""

    def __init__(self, toks: list[str], variables: list[str]):
        self.t, self.i, self.vars = toks, 0, set(variables)

    def peek(self) -> str | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> str:
        tok = self.t[self.i]
        self.i += 1
        return tok

    def parse(self) -> _Node:
        if not self.t:
            raise ParseError("식이 비어 있음")
        n = self.or_()
        if self.peek() is not None:
            raise ParseError(f"식 끝에 남은 글자: {''.join(self.t[self.i:])}")
        return n

    def or_(self) -> _Node:
        args = [self.xor()]
        while self.peek() == "|":
            self.take()
            args.append(self.xor())
        return args[0] if len(args) == 1 else _Node("or", tuple(args))

    def xor(self) -> _Node:
        args = [self.and_()]
        while self.peek() == "^":
            self.take()
            args.append(self.and_())
        return args[0] if len(args) == 1 else _Node("xor", tuple(args))

    def and_(self) -> _Node:
        args = [self.unary()]
        while self.peek() is not None and (self.peek() == "&" or self.peek() in self.vars or self.peek() in "(~01"):
            if self.peek() == "&":
                self.take()
            args.append(self.unary())
        return args[0] if len(args) == 1 else _Node("and", tuple(args))

    def unary(self) -> _Node:
        if self.peek() == "~":
            self.take()
            n = _Node("not", (self.unary(),))
        else:
            n = self.atom()
        while self.peek() == "'":
            self.take()
            n = _Node("not", (n,))
        return n

    def atom(self) -> _Node:
        tok = self.peek()
        if tok is None:
            raise ParseError("식이 중간에 끝남")
        self.take()
        if tok == "(":
            n = self.or_()
            if self.peek() != ")":
                raise ParseError("괄호 짝이 맞지 않음")
            self.take()
            return n
        if tok in "01":
            return _Node("const", value=int(tok))
        if tok in self.vars:
            return _Node("var", name=tok)
        raise ParseError(f"예상하지 못한 '{tok}'")


def parse_bool(expr: str, variables: list[str]) -> _Node:
    return _Parser(_tokenize(_normalize(expr, variables), variables), variables).parse()


def truth(node: _Node, variables: list[str]) -> list[int]:
    """민텀 번호 순서(첫 변수가 최상위 비트)의 진리표."""
    n = len(variables)
    return [node.eval({v: (m >> (n - 1 - k)) & 1 for k, v in enumerate(variables)}) for m in range(2 ** n)]


# ---------- 형태·리터럴 ----------

def _flatten(node: _Node, op: str) -> list[_Node]:
    if node.op == op:
        return [x for a in node.args for x in _flatten(a, op)]
    return [node]


def _is_literal(node: _Node) -> bool:
    return node.op == "var" or (node.op == "not" and node.args[0].op == "var")


def form_of(node: _Node) -> set[str]:
    """식이 SOP/POS 형태인지. 상수(0·1), 리터럴 하나, 곱 하나, 합 하나는 둘 다."""
    if node.op == "const":
        return {"SOP", "POS"}
    out = set()
    terms = _flatten(node, "or")
    if all(all(_is_literal(f) for f in _flatten(t, "and")) for t in terms):
        out.add("SOP")
    factors = _flatten(node, "and")
    if all(all(_is_literal(x) for x in _flatten(f, "or")) for f in factors):
        out.add("POS")
    return out


def literal_count(node: _Node) -> int:
    if _is_literal(node):
        return 1
    if node.op == "const":
        return 0
    return sum(literal_count(a) for a in node.args)


# ---------- 최소 SOP (Quine-McCluskey + 최소 덮개) ----------

def _prime_implicants(ones: set[int], dcs: set[int], n: int) -> set[tuple[int, int]]:
    """(값, 마스크) 쌍. 마스크 비트 1 = 그 변수 없음."""
    terms = {(m, 0) for m in ones | dcs}
    primes: set[tuple[int, int]] = set()
    while terms:
        merged, used = set(), set()
        tl = sorted(terms)
        for a, b in itertools.combinations(tl, 2):
            if a[1] == b[1]:
                diff = a[0] ^ b[0]
                if diff and diff & (diff - 1) == 0:
                    merged.add((a[0] & ~diff, a[1] | diff))
                    used.update((a, b))
        primes |= terms - used
        terms = merged
    return primes


def _covers(pi: tuple[int, int], m: int) -> bool:
    return (m & ~pi[1]) == pi[0]


def min_sop_literals(ones: set[int], dcs: set[int], n: int) -> int:
    """don't care를 쓸 수 있을 때 최소 SOP의 리터럴 수."""
    if not ones:
        return 0
    if len(ones | dcs) == 2 ** n:
        return 0  # 항상 1
    pis = sorted(_prime_implicants(ones, dcs, n), key=lambda p: bin(p[1]).count("1"), reverse=True)
    cost = {p: n - bin(p[1]).count("1") for p in pis}
    cover = {p: frozenset(m for m in ones if _covers(p, m)) for p in pis}
    best = [sum(cost.values()) + 1]

    def search(left: frozenset, chosen_cost: int, cand: list) -> None:
        if chosen_cost >= best[0]:
            return
        if not left:
            best[0] = chosen_cost
            return
        m = min(left, key=lambda x: sum(1 for p in cand if x in cover[p]))  # 덮는 항이 가장 적은 민텀부터
        for p in cand:
            if m in cover[p]:
                search(left - cover[p], chosen_cost + cost[p], [q for q in cand if q != p])

    search(frozenset(ones), 0, pis)
    return best[0]


# ---------- 검산 ----------

def _minterm_str(m: int, variables: list[str]) -> str:
    n = len(variables)
    return ", ".join(f"{v}={(m >> (n - 1 - k)) & 1}" for k, v in enumerate(variables))


def check_bool(v: Verification) -> list[str]:
    vars_ = v.variables
    if not vars_:
        raise ParseError("variables가 비어 있음")
    n = len(vars_)
    dcs = set(v.dont_cares)
    if v.minterms is not None:
        bad = [m for m in [*v.minterms, *dcs] if not 0 <= m < 2 ** n]
        if bad:
            raise ParseError(f"민텀 번호 {bad}가 변수 {n}개 범위(0~{2 ** n - 1}) 밖")
        ones = set(v.minterms) - dcs
    elif v.function:
        if _normalize(v.function, vars_) == _normalize(v.expected, vars_):
            raise ParseError("원래 함수(function)와 정답이 같은 식이라 검산 의미 없음 — 문제에서 준 함수를 적을 것")
        ones = {m for m, y in enumerate(truth(parse_bool(v.function, vars_), vars_)) if y} - dcs
    else:
        raise ParseError("minterms나 function 중 하나가 있어야 함")
    node = parse_bool(v.expected, vars_)
    got = truth(node, vars_)
    wrong = [m for m in range(2 ** n) if m not in dcs and got[m] != (m in ones)]
    label = f"{v.label} " if v.label else ""
    if wrong:
        ex = ", ".join(f"({_minterm_str(m, vars_)}) 원래 {int(m in ones)} → 식 {got[m]}" for m in wrong[:3])
        return [f"코드 검산 실패 {label}`{v.expected}`: 원래 함수와 다른 입력 {len(wrong)}개 — {ex}"]
    issues = []
    if v.form in ("SOP", "POS") and v.form not in form_of(node):
        issues.append(f"코드 검산 실패 {label}`{v.expected}`: {v.form} 형태가 아님")
    if v.minimal and n <= MAX_VARS:
        zeros = set(range(2 ** n)) - ones - dcs
        need = min_sop_literals(zeros, dcs, n) if v.form == "POS" else min_sop_literals(ones, dcs, n)
        have = literal_count(node)
        if have > need:
            issues.append(f"코드 검산 실패 {label}`{v.expected}`: 같은 함수지만 최소가 아님 "
                          f"(리터럴 {have}개, 최소 {v.form if v.form != 'any' else 'SOP'} {need}개)")
    return issues


def _bits(s: str) -> str:
    """'0xC2ED4000', 'C2ED 4000', '1100 0010 …', '$11000010…_2$' → 2진 문자열."""
    t = s.strip().strip("$").lower()
    base = None
    m = re.search(r"(?:_\{?|\()(2|16)\}?\)?$", t)  # 끝의 _2, _{16}, (16)
    if m:
        base = int(m.group(1))
        t = t[:m.start()]
    t = re.sub(r"[\s{}\\]|\\text|\\mathrm", "", t)
    if t.startswith("0x"):
        base, t = 16, t[2:]
    elif t.startswith("0b"):
        base, t = 2, t[2:]
    if base is None:
        base = 2 if re.fullmatch(r"[01]+", t) else 16
    if base == 2:
        if not re.fullmatch(r"[01]+", t):
            raise ParseError(f"2진수로 읽을 수 없음: {s}")
        return t
    if not re.fullmatch(r"[0-9a-f]+", t):
        raise ParseError(f"16진수로 읽을 수 없음: {s}")
    return "".join(f"{int(c, 16):04b}" for c in t)


def check_ieee754(v: Verification) -> list[str]:
    fmt = {"single": (">f", 32), "double": (">d", 64)}[v.precision]
    want = "".join(f"{b:08b}" for b in struct.pack(fmt[0], float(v.value)))
    got = _bits(v.expected)
    if got != want:
        hexw = f"{int(want, 2):0{fmt[1] // 4}X}"
        return [f"코드 검산 실패 {v.label + ' ' if v.label else ''}{v.value}의 IEEE 754 {v.precision}: "
                f"정답 `{v.expected}`, 계산 결과 {hexw} ({want[0]} {want[1:1 + (8 if fmt[1] == 32 else 11)]} …)"]
    return []


def check_int(v: Verification) -> list[str]:
    n, x = v.bits, int(v.value)
    if not n:
        raise ParseError("bits가 없음")
    if v.repr == "2s":
        if not -(2 ** (n - 1)) <= x < 2 ** (n - 1):
            raise ParseError(f"{x}는 {n}비트 2의 보수 범위 밖")
        want = format(x & (2 ** n - 1), f"0{n}b")
    else:
        if not abs(x) < 2 ** (n - 1):
            raise ParseError(f"{x}는 {n}비트 범위 밖")
        mag = format(abs(x), f"0{n - 1}b")
        if v.repr == "sm":
            want = ("1" if x < 0 else "0") + mag
        else:  # 1s
            want = "0" + mag if x >= 0 else "".join("1" if c == "0" else "0" for c in "0" + mag)
    got = _bits(v.expected)
    if got != want:
        return [f"코드 검산 실패 {v.label + ' ' if v.label else ''}{x}의 {n}비트 {v.repr}: 정답 `{v.expected}`, 계산 결과 {want}"]
    return []


def describe(v: Verification) -> str:
    """무엇을 검산했는지 (reviewer가 문제 본문과 맞는지 볼 수 있게 원래 함수·값까지)."""
    if v.kind == "bool_expr":
        if v.minterms is not None:
            src = f"Σm{tuple(v.minterms)}" + (f" + d{tuple(v.dont_cares)}" if v.dont_cares else "")
        else:
            src = f"{v.function}" + (f" + d{tuple(v.dont_cares)}" if v.dont_cares else "")
        extra = "".join([f", {v.form}" if v.form != "any" else "", ", 최소" if v.minimal else ""])
        return f"불 식 F({','.join(v.variables)}) = {src} → `{v.expected}`{extra}"
    if v.kind == "ieee754":
        return f"{v.value}의 IEEE 754 {v.precision} → `{v.expected}`"
    return f"{v.value}의 {v.bits}비트 {v.repr} → `{v.expected}`"


CHECKERS = {"bool_expr": check_bool, "ieee754": check_ieee754, "int_repr": check_int}


@dataclass
class VerifyResult:
    issues: list[str]  # 틀림 → 수정 요청
    passed: list[str]  # 맞음 (reviewer에게 알림)
    unreadable: list[str]  # 검산 거리를 읽지 못함 (기록만, 수정 요청 안 함)


def run(q: Question) -> VerifyResult:
    res = VerifyResult([], [], [])
    for v in q.verifications:
        desc = f"{v.label + ' ' if v.label else ''}{describe(v)}"
        try:
            found = CHECKERS[v.kind](v)
        except (ParseError, ValueError, KeyError, struct.error) as e:
            res.unreadable.append(f"{desc}: {e}")
            continue
        if found:
            res.issues += found
        else:
            res.passed.append(desc)
    return res
