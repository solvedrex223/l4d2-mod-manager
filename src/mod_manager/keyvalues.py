from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(text)
    line = 1
    while i < n:
        c = text[i]
        if c == "\n":
            tokens.append(Token("nl", "", line))
            line += 1
            i += 1
        elif c in " \t\r":
            i += 1
        elif c == "/" and text[i : i + 2] == "//":
            while i < n and text[i] != "\n":
                i += 1
        elif c == "{":
            tokens.append(Token("lbrace", "", line))
            i += 1
        elif c == "}":
            tokens.append(Token("rbrace", "", line))
            i += 1
        elif c == '"':
            i += 1
            buf: list[str] = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n and text[i + 1] in '"\\':
                    buf.append(text[i + 1])
                    i += 2
                else:
                    if text[i] == "\n":
                        line += 1
                    buf.append(text[i])
                    i += 1
            i += 1
            tokens.append(Token("str", "".join(buf), line))
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n"{}':
                if text[j : j + 2] == "//":
                    break
                j += 1
            tokens.append(Token("str", text[i:j], line))
            i = j
    return tokens


def _parse_node(tokens: list[Token], i: int, top: bool = False) -> tuple[dict, int]:
    out: dict = {}
    while i < len(tokens):
        t = tokens[i]
        if t.kind == "nl":
            i += 1
            continue
        if t.kind == "rbrace":
            if top:
                i += 1
                continue
            return out, i + 1
        if t.kind == "lbrace":
            i += 1
            continue
        key = t.value.lower()
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if nxt is not None and nxt.kind == "str" and nxt.line == t.line:
            out[key] = nxt.value
            i += 2
        elif nxt is not None and nxt.kind == "lbrace":
            child, i = _parse_node(tokens, i + 2)
            out[key] = child
        elif (
            nxt is not None
            and nxt.kind == "nl"
            and i + 2 < len(tokens)
            and tokens[i + 2].kind == "lbrace"
        ):
            child, i = _parse_node(tokens, i + 3)
            out[key] = child
        else:
            out[key] = ""
            i += 1
    return out, i


def parse(text: str) -> dict:
    tokens = tokenize(text)
    result, _ = _parse_node(tokens, 0, top=True)
    return result
