from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from shakespy import translator


@dataclass
class FakeToken:
    i: int
    text: str
    dep_: str
    pos_: str
    lemma_: str
    whitespace_: str = ""
    is_alpha: bool = True
    head: "FakeToken | None" = None
    children: list["FakeToken"] = field(default_factory=list)


class FakeDoc:
    def __init__(self, tokens: list[FakeToken]):
        self._tokens = tokens

    def __iter__(self):
        return iter(self._tokens)

    def __getitem__(self, item):
        return self._tokens[item]


def make_doc(specs):
    tokens = [
        FakeToken(
            i=index,
            text=spec["text"],
            dep_=spec["dep"],
            pos_=spec["pos"],
            lemma_=spec.get("lemma", spec["text"].lower()),
            whitespace_=spec.get("ws", ""),
            is_alpha=spec.get("is_alpha", spec["text"].isalpha()),
        )
        for index, spec in enumerate(specs)
    ]

    for index, spec in enumerate(specs):
        head_index = spec.get("head", index)
        tokens[index].head = tokens[head_index]

    for token in tokens:
        if token.head is not token:
            token.head.children.append(token)

    return FakeDoc(tokens)


@pytest.fixture
def stub_nlp(monkeypatch):
    def set_doc(doc):
        monkeypatch.setattr(translator, "_get_nlp", lambda: (lambda _: doc))
        return doc

    return set_doc


def test_object_you_becomes_thee(stub_nlp):
    doc = make_doc(
        [
            {"text": "I", "dep": "nsubj", "pos": "PRON", "head": 1, "ws": " "},
            {"text": "love", "dep": "ROOT", "pos": "VERB", "head": 1, "ws": " "},
            {"text": "you", "dep": "dobj", "pos": "PRON", "head": 1},
        ]
    )
    stub_nlp(doc)

    assert translator.translate("I love you") == "I love thee"


def test_subject_you_becomes_thou_and_conjugates_verb(stub_nlp):
    doc = make_doc(
        [
            {
                "text": "You",
                "dep": "nsubj",
                "pos": "PRON",
                "lemma": "you",
                "head": 1,
                "ws": " ",
            },
            {
                "text": "love",
                "dep": "ROOT",
                "pos": "VERB",
                "lemma": "love",
                "head": 1,
                "ws": " ",
            },
            {"text": "me", "dep": "dobj", "pos": "PRON", "lemma": "me", "head": 1},
            {
                "text": ".",
                "dep": "punct",
                "pos": "PUNCT",
                "lemma": ".",
                "head": 1,
                "is_alpha": False,
            },
        ]
    )
    stub_nlp(doc)

    assert translator.translate("You love me.") == "Thou lovest me."


def test_case_and_punctuation_are_preserved(stub_nlp):
    doc = make_doc(
        [
            {
                "text": "Are",
                "dep": "ROOT",
                "pos": "AUX",
                "lemma": "are",
                "head": 0,
                "ws": " ",
            },
            {"text": "you", "dep": "nsubj", "pos": "PRON", "lemma": "you", "head": 0, "ws": " "},
            {"text": "ready", "dep": "acomp", "pos": "ADJ", "lemma": "ready", "head": 0},
            {"text": "?", "dep": "punct", "pos": "PUNCT", "lemma": "?", "head": 0, "is_alpha": False},
        ]
    )
    stub_nlp(doc)

    assert translator.translate("Are you ready?") == "Art thou ready?"


def test_possessive_pronouns_choose_thy_and_thine(stub_nlp):
    doc = make_doc(
        [
            {
                "text": "Your",
                "dep": "poss",
                "pos": "PRON",
                "lemma": "your",
                "head": 1,
                "ws": " ",
            },
            {"text": "apple", "dep": "ROOT", "pos": "NOUN", "lemma": "apple", "head": 1, "ws": " "},
            {"text": "and", "dep": "cc", "pos": "CCONJ", "lemma": "and", "head": 1, "ws": " "},
            {"text": "your", "dep": "poss", "pos": "PRON", "lemma": "your", "head": 4, "ws": " "},
            {"text": "book", "dep": "conj", "pos": "NOUN", "lemma": "book", "head": 1, "ws": " "},
            {"text": "are", "dep": "cop", "pos": "AUX", "lemma": "are", "head": 6, "ws": " "},
            {"text": "yours", "dep": "attr", "pos": "PRON", "lemma": "yours", "head": 1},
            {"text": ".", "dep": "punct", "pos": "PUNCT", "lemma": ".", "head": 1, "is_alpha": False},
        ]
    )
    stub_nlp(doc)

    assert translator.translate("Your apple and your book are yours.") == (
        "Thine apple and thy book are thine."
    )


def test_modal_auxiliary_is_conjugated_instead_of_main_verb(stub_nlp):
    doc = make_doc(
        [
            {"text": "You", "dep": "nsubj", "pos": "PRON", "lemma": "you", "head": 2, "ws": " "},
            {"text": "will", "dep": "aux", "pos": "AUX", "lemma": "will", "head": 2, "ws": " "},
            {"text": "find", "dep": "ROOT", "pos": "VERB", "lemma": "find", "head": 2, "ws": " "},
            {"text": "your", "dep": "poss", "pos": "PRON", "lemma": "your", "head": 4, "ws": " "},
            {"text": "answer", "dep": "dobj", "pos": "NOUN", "lemma": "answer", "head": 2, "ws": " "},
            {"text": "before", "dep": "prep", "pos": "ADP", "lemma": "before", "head": 2, "ws": " "},
            {"text": "night", "dep": "pobj", "pos": "NOUN", "lemma": "night", "head": 5},
            {"text": ".", "dep": "punct", "pos": "PUNCT", "lemma": ".", "head": 2, "is_alpha": False},
        ]
    )
    stub_nlp(doc)

    assert translator.translate("You will find your answer before night.") == (
        "Thou wilt find thine answer ere night."
    )


def test_second_person_want_uses_richer_verb_base(stub_nlp):
    doc = make_doc(
        [
            {"text": "You", "dep": "nsubj", "pos": "PRON", "lemma": "you", "head": 1, "ws": " "},
            {"text": "want", "dep": "ROOT", "pos": "VERB", "lemma": "want", "head": 1, "ws": " "},
            {"text": "to", "dep": "aux", "pos": "PART", "lemma": "to", "head": 3, "ws": " "},
            {"text": "help", "dep": "xcomp", "pos": "VERB", "lemma": "help", "head": 1, "ws": " "},
            {"text": "me", "dep": "dobj", "pos": "PRON", "lemma": "me", "head": 3},
            {"text": ".", "dep": "punct", "pos": "PUNCT", "lemma": ".", "head": 1, "is_alpha": False},
        ]
    )
    stub_nlp(doc)

    assert translator.translate("You want to help me.") == "Thou desirest to help me."


def test_phrase_and_word_replacements_expand_coverage(stub_nlp):
    doc = make_doc(
        [
            {"text": "Good", "dep": "amod", "pos": "ADJ", "lemma": "good", "head": 1, "ws": " "},
            {"text": "morning", "dep": "ROOT", "pos": "NOUN", "lemma": "morning", "head": 1},
            {"text": ",", "dep": "punct", "pos": "PUNCT", "lemma": ",", "head": 1, "is_alpha": False, "ws": " "},
            {"text": "please", "dep": "advmod", "pos": "INTJ", "lemma": "please", "head": 4, "ws": " "},
            {"text": "wait", "dep": "ROOT", "pos": "VERB", "lemma": "wait", "head": 4},
            {"text": ".", "dep": "punct", "pos": "PUNCT", "lemma": ".", "head": 4, "is_alpha": False},
        ]
    )
    stub_nlp(doc)

    assert translator.translate("Good morning, please wait.") == (
        "Good morrow, prithee bide."
    )


def test_non_second_person_want_still_gets_lexical_upgrade(stub_nlp):
    doc = make_doc(
        [
            {"text": "I", "dep": "nsubj", "pos": "PRON", "lemma": "I", "head": 1, "ws": " "},
            {"text": "want", "dep": "ROOT", "pos": "VERB", "lemma": "want", "head": 1, "ws": " "},
            {"text": "to", "dep": "aux", "pos": "PART", "lemma": "to", "head": 3, "ws": " "},
            {"text": "help", "dep": "xcomp", "pos": "VERB", "lemma": "help", "head": 1, "ws": " "},
            {"text": "you", "dep": "dobj", "pos": "PRON", "lemma": "you", "head": 3},
            {"text": ".", "dep": "punct", "pos": "PUNCT", "lemma": ".", "head": 1, "is_alpha": False},
        ]
    )
    stub_nlp(doc)

    assert translator.translate("I want to help you.") == "I desire to help thee."
