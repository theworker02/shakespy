from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ReplacementRule:
    source: str
    replacement: str


PHRASE_REPLACEMENTS = (
    ReplacementRule("good morning", "good morrow"),
    ReplacementRule("good evening", "good e'en"),
    ReplacementRule("thank you", "i thank thee"),
    ReplacementRule("excuse me", "prithee pardon me"),
    ReplacementRule("come here", "come hither"),
    ReplacementRule("go away", "get thee gone"),
)

WORD_REPLACEMENTS = (
    ReplacementRule("hello", "hail"),
    ReplacementRule("hi", "hail"),
    ReplacementRule("hey", "hail"),
    ReplacementRule("goodbye", "fare thee well"),
    ReplacementRule("bye", "fare thee well"),
    ReplacementRule("please", "prithee"),
    ReplacementRule("before", "ere"),
    ReplacementRule("why", "wherefore"),
    ReplacementRule("perhaps", "perchance"),
    ReplacementRule("maybe", "perchance"),
    ReplacementRule("often", "oft"),
    ReplacementRule("soon", "anon"),
    ReplacementRule("between", "betwixt"),
    ReplacementRule("among", "amongst"),
    ReplacementRule("around", "about"),
    ReplacementRule("yes", "aye"),
    ReplacementRule("no", "nay"),
    ReplacementRule("nothing", "naught"),
    ReplacementRule("everything", "all"),
    ReplacementRule("never", "ne'er"),
    ReplacementRule("over", "o'er"),
    ReplacementRule("listen", "harken"),
    ReplacementRule("listen to", "harken unto"),
    ReplacementRule("wait", "bide"),
    ReplacementRule("stop", "cease"),
    ReplacementRule("friend", "companion"),
    ReplacementRule("enemy", "foe"),
    ReplacementRule("strange", "passing strange"),
    ReplacementRule("wrong", "amiss"),
    ReplacementRule("near", "nigh"),
    ReplacementRule("away", "afar"),
    ReplacementRule("house", "manor"),
    ReplacementRule("boy", "lad"),
    ReplacementRule("girl", "lass"),
    ReplacementRule("man", "sirrah"),
    ReplacementRule("woman", "lady"),
    ReplacementRule("child", "bairn"),
    ReplacementRule("children", "bairns"),
    ReplacementRule("old", "aged"),
    ReplacementRule("young", "youthful"),
    ReplacementRule("want", "desire"),
)

VERB_BASE_REPLACEMENTS = {
    "want": "desire",
}

IRREGULAR_SECOND_PERSON = {
    "am": "art",
    "are": "art",
    "be": "art",
    "have": "hast",
    "has": "hast",
    "do": "dost",
    "does": "dost",
    "will": "wilt",
    "shall": "shalt",
    "can": "canst",
    "could": "couldst",
    "would": "wouldst",
    "should": "shouldst",
    "may": "mayest",
    "might": "mightst",
    "need": "needest",
    "must": "must",
}

SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj", "expl"}
OBJECT_DEPS = {"dobj", "obj", "pobj", "iobj", "dative"}
POSSESSIVE_TRIGGER_DEPS = {"poss", "det"}
VOWELS = set("aeiou")


def _compile_replacement_patterns(rules: tuple[ReplacementRule, ...]) -> list[tuple[ReplacementRule, re.Pattern[str]]]:
    compiled: list[tuple[ReplacementRule, re.Pattern[str]]] = []
    for rule in sorted(rules, key=lambda item: len(item.source), reverse=True):
        pattern = re.compile(rf"\b{re.escape(rule.source)}\b", re.IGNORECASE)
        compiled.append((rule, pattern))
    return compiled


PHRASE_PATTERNS = _compile_replacement_patterns(PHRASE_REPLACEMENTS)
WORD_PATTERNS = _compile_replacement_patterns(WORD_REPLACEMENTS)


@lru_cache(maxsize=1)
def _get_nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "spaCy is required to use ShakesPy. Install it with: pip install spacy"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "The spaCy model 'en_core_web_sm' is required. "
            "Install it with: python -m spacy download en_core_web_sm"
        ) from exc


def _match_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement.capitalize()
    return replacement


def _next_word_text(doc, index: int) -> str | None:
    for token in doc[index + 1 :]:
        if token.is_alpha:
            return token.text
    return None


def _normalized_lemma(lemma: str) -> str:
    lower_lemma = lemma.lower()
    return VERB_BASE_REPLACEMENTS.get(lower_lemma, lower_lemma)


def _second_person_form(word: str, lemma: str) -> str:
    lower_word = word.lower()
    lower_lemma = _normalized_lemma(lemma)

    if lower_word in IRREGULAR_SECOND_PERSON:
        return _match_case(word, IRREGULAR_SECOND_PERSON[lower_word])

    if lower_lemma in IRREGULAR_SECOND_PERSON:
        return _match_case(word, IRREGULAR_SECOND_PERSON[lower_lemma])

    stem = lower_lemma if lower_lemma else lower_word
    if stem.endswith("e"):
        conjugated = f"{stem}st"
    else:
        conjugated = f"{stem}est"
    return _match_case(word, conjugated)


def _should_use_object_pronoun(token) -> bool:
    return token.dep_ in OBJECT_DEPS


def _should_use_subject_pronoun(token) -> bool:
    return token.dep_ in SUBJECT_DEPS


def _is_modal_or_auxiliary(token) -> bool:
    return token.pos_ == "AUX" or token.lemma_.lower() in IRREGULAR_SECOND_PERSON


def _apply_second_person_verb_overrides(token, overrides: dict[int, str]) -> None:
    head = token.head

    if head.i == token.i:
        if head.pos_ in {"VERB", "AUX"}:
            overrides[head.i] = _second_person_form(head.text, head.lemma_)
        return

    aux_children = [
        child
        for child in head.children
        if child.dep_ in {"aux", "auxpass", "cop"} and _is_modal_or_auxiliary(child)
    ]

    if aux_children:
        for child in aux_children:
            overrides[child.i] = _second_person_form(child.text, child.lemma_)
        return

    if head.pos_ in {"VERB", "AUX"}:
        overrides[head.i] = _second_person_form(head.text, head.lemma_)


def _replacement_for_your(token, doc) -> str:
    next_word = _next_word_text(doc, token.i) or ""
    replacement = "thine" if next_word[:1].lower() in VOWELS else "thy"
    return _match_case(token.text, replacement)


def _collect_overrides(doc) -> dict[int, str]:
    overrides: dict[int, str] = {}

    for token in doc:
        lower = token.text.lower()

        if lower == "you":
            if _should_use_subject_pronoun(token):
                overrides[token.i] = _match_case(token.text, "thou")
                _apply_second_person_verb_overrides(token, overrides)
            elif _should_use_object_pronoun(token):
                overrides[token.i] = _match_case(token.text, "thee")

        elif lower == "your" and token.dep_ in POSSESSIVE_TRIGGER_DEPS:
            overrides[token.i] = _replacement_for_your(token, doc)

        elif lower == "yours":
            overrides[token.i] = _match_case(token.text, "thine")

        elif lower == "yourself":
            overrides[token.i] = _match_case(token.text, "thyself")

        elif lower == "yourselves":
            overrides[token.i] = _match_case(token.text, "thy selves")

        elif lower == "my" and token.dep_ in POSSESSIVE_TRIGGER_DEPS:
            next_word = _next_word_text(doc, token.i) or ""
            if next_word[:1].lower() in VOWELS:
                overrides[token.i] = _match_case(token.text, "mine")

    return overrides


def _apply_rule_set(text: str, rules: list[tuple[ReplacementRule, re.Pattern[str]]]) -> str:
    updated = text
    for rule, pattern in rules:
        updated = pattern.sub(
            lambda match: _match_case(match.group(0), rule.replacement),
            updated,
        )
    return updated


def _apply_lexical_replacements(text: str) -> str:
    updated = _apply_rule_set(text, PHRASE_PATTERNS)
    updated = _apply_rule_set(updated, WORD_PATTERNS)
    return updated


def translate(text: str) -> str:
    doc = _get_nlp()(text)
    overrides = _collect_overrides(doc)

    translated = "".join(
        overrides.get(token.i, token.text) + token.whitespace_
        for token in doc
    )
    return _apply_lexical_replacements(translated)
