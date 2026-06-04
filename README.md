# ShakesPy

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Build](https://img.shields.io/badge/build-flit-orange.svg)
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)

ShakesPy is a lightweight Python library and CLI for translating Modern English
into a playful Early Modern English style inspired by Shakespeare and the King
James Bible.

ShakesPy combines spaCy-powered grammatical analysis with phrase and vocabulary
remapping to produce translations that feel more intentionally Shakespearean
than a simple word-for-word replacer.

## Features

- spaCy-powered grammatical rewrites for subject/object pronouns
- Smarter second-person verb conjugation such as `you are` -> `thou art`
- Auxiliary handling for forms such as `you will find` -> `thou wilt find`
- Expanded lexical and phrase replacements such as `good morning` -> `good morrow`
- Simple command-line interface

## Why ShakesPy

- Distinguishes subject and object `you` so `You know me` and `I know you` do not translate the same way
- Uses dependency parsing to conjugate second-person verbs more naturally
- Supports both programmatic use and a small CLI for quick translations
- Ships as a single Flit-packaged Python library with a focused API

## Installation

Install from source for local development:

```bash
pip install -e .
python -m spacy download en_core_web_sm
```

Or install the project with Flit:

```bash
flit install --symlink
python -m spacy download en_core_web_sm
```

## Usage

```python
from shakespy import translate

print(translate("You are making a mistake."))
print(translate("You will find your answer before night."))
print(translate("Good morning, please wait."))
```

```bash
shakespy "You are making a mistake."
python -m shakespy.cli "Hello! I want to help you."
python -m shakespy.cli "Good morning, please wait."
```

Example outputs:

- `You are making a mistake.` -> `Thou art making a mistake.`
- `You will find your answer before night.` -> `Thou wilt find thine answer ere night.`
- `I want to help you.` -> `I desire to help thee.`
- `Good morning, please wait.` -> `Good morrow, prithee bide.`

## Development

```bash
pip install -e .[dev]
python -m spacy download en_core_web_sm
python -m pytest
flit build
```

## Notes

The translator uses a two-tier pipeline:

1. spaCy dependency parsing for grammatical rules
2. Regex-based phrase and lexical replacements for broader stylistic coverage

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## Main Link

[Visit shakespy](https://pypi.org/project/theworker02-shakespy)
