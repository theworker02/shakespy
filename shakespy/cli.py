from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import __version__
from .translator import PHRASE_REPLACEMENTS
from .translator import WORD_REPLACEMENTS
from .translator import ReplacementRule
from .translator import _get_nlp
from .translator import translate


PROGRAM_NAME = "shakespy"
DEFAULT_ENCODING = "utf-8"
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_TRANSLATION_ERROR = 3

REPL_BANNER = """
ShakesPy interactive mode
Type modern English and press Enter to translate it.
Use /help to see commands, /quit to leave, and /rules to inspect the glossary.
""".strip()

EXAMPLE_TEXTS = (
    "You are making a mistake.",
    "You will find your answer before night.",
    "Good morning, please wait.",
    "I want to help you before the evening ends.",
    "Thank you, my friend. Please come here soon.",
)

SUBCOMMAND_NAMES = {"translate", "batch", "repl", "glossary", "examples", "doctor"}
PASSTHROUGH_FLAGS = {"-h", "--help", "--version"}
TRANSLATE_FLAGS = {
    "--stdin",
    "--input-file",
    "--output-file",
    "--json",
    "--pretty",
    "--show-source",
    "--show-header",
    "--number-lines",
    "--repeat",
    "--separator",
    "--strip",
    "--fail-on-empty",
    "--dump-metadata",
}


@dataclass(frozen=True)
class TranslationRecord:
    source: str
    translated: str
    source_name: str = "inline"
    index: int = 1


@dataclass(frozen=True)
class CliContext:
    stdout: object
    stderr: object


@dataclass(frozen=True)
class RenderOptions:
    as_json: bool = False
    pretty: bool = False
    show_header: bool = False
    number_lines: bool = False
    show_source: bool = False
    separator: str = "\n"


@dataclass(frozen=True)
class BatchOptions:
    recursive: bool = False
    glob: str = "*.txt"
    skip_empty: bool = False
    include_source: bool = True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description=(
            "Translate Modern English text into playful Early Modern English. "
            "Use the default translate command for direct text, or one of the "
            "subcommands for files, batches, glossary inspection, and REPL mode."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            examples:
              shakespy "You are making a mistake."
              shakespy translate --stdin
              shakespy translate --input-file note.txt --output-file note.eme.txt
              shakespy batch speeches/ --recursive --json
              shakespy repl
              shakespy glossary --phrases
              shakespy doctor
            """
        ).strip(),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--encoding",
        default=DEFAULT_ENCODING,
        help="Text encoding to use for reading and writing files. Default: %(default)s",
    )

    subparsers = parser.add_subparsers(dest="command")

    _add_translate_parser(subparsers)
    _add_batch_parser(subparsers)
    _add_repl_parser(subparsers)
    _add_glossary_parser(subparsers)
    _add_examples_parser(subparsers)
    _add_doctor_parser(subparsers)

    parser.set_defaults(command="translate", handler=handle_translate)
    return parser


def _add_translate_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "translate",
        help="Translate direct text, stdin, or a single file.",
        description=(
            "Translate one input source. You can pass text as positional "
            "arguments, pipe content through stdin, or read a file."
        ),
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="Text to translate. If omitted, use --stdin or --input-file.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read the full source text from standard input.",
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Read source text from a file.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Write translated text to a file instead of stdout.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output for readability.",
    )
    parser.add_argument(
        "--show-source",
        action="store_true",
        help="Include the original source text in rendered output.",
    )
    parser.add_argument(
        "--show-header",
        action="store_true",
        help="Show a decorative header in plain-text output.",
    )
    parser.add_argument(
        "--number-lines",
        action="store_true",
        help="Number output lines in plain-text mode.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Translate and emit the same input multiple times. Default: %(default)s",
    )
    parser.add_argument(
        "--separator",
        default="\n",
        help="Separator between repeated outputs in plain-text mode.",
    )
    parser.add_argument(
        "--strip",
        action="store_true",
        help="Trim leading and trailing whitespace from the input before translation.",
    )
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="Exit with an error if the resolved input is empty.",
    )
    parser.add_argument(
        "--dump-metadata",
        action="store_true",
        help="Include source metadata such as character counts and encoding hints.",
    )
    parser.set_defaults(handler=handle_translate)


def _add_batch_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "batch",
        help="Translate multiple text files from one or more directories.",
        description=(
            "Translate every matching file under one or more input paths. "
            "Use this for release prep, corpus conversion, or regression sampling."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to process.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Walk directories recursively.",
    )
    parser.add_argument(
        "--glob",
        default="*.txt",
        help="Glob used when scanning directories. Default: %(default)s",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write translated files to a separate directory tree.",
    )
    parser.add_argument(
        "--suffix",
        default=".eme",
        help="Suffix inserted before the original file extension. Default: %(default)s",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON array describing every translated file.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without writing files.",
    )
    parser.add_argument(
        "--skip-empty",
        action="store_true",
        help="Skip files that resolve to empty content after trimming.",
    )
    parser.add_argument(
        "--strip",
        action="store_true",
        help="Trim leading and trailing whitespace before translation.",
    )
    parser.add_argument(
        "--print-output",
        action="store_true",
        help="Print translated content to stdout in addition to writing files.",
    )
    parser.add_argument(
        "--show-source",
        action="store_true",
        help="Include the original file content in console output.",
    )
    parser.set_defaults(handler=handle_batch)


def _add_repl_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "repl",
        help="Start an interactive translation shell.",
        description=(
            "Enter interactive mode for ad hoc translations. "
            "Use slash commands such as /help, /examples, and /rules."
        ),
    )
    parser.add_argument(
        "--prompt",
        default="modern> ",
        help="Prompt used for source text. Default: %(default)s",
    )
    parser.add_argument(
        "--translated-prompt",
        default="bard> ",
        help="Prefix used when printing translated output. Default: %(default)s",
    )
    parser.add_argument(
        "--show-header",
        action="store_true",
        help="Print the interactive banner before starting.",
    )
    parser.add_argument(
        "--number-lines",
        action="store_true",
        help="Number translated lines in REPL output.",
    )
    parser.set_defaults(handler=handle_repl)


def _add_glossary_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "glossary",
        help="Inspect built-in phrase and vocabulary replacements.",
        description=(
            "List the built-in phrase and word replacements used by the translator."
        ),
    )
    parser.add_argument(
        "--phrases",
        action="store_true",
        help="Show only phrase replacements.",
    )
    parser.add_argument(
        "--words",
        action="store_true",
        help="Show only word replacements.",
    )
    parser.add_argument(
        "--contains",
        help="Filter rules to those whose source or replacement contains this substring.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit glossary data as JSON.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.set_defaults(handler=handle_glossary)


def _add_examples_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "examples",
        help="Print built-in examples and sample translations.",
        description="Show a curated set of sample inputs and outputs.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit examples as JSON.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--translate-only",
        action="store_true",
        help="Print only the translated results in plain-text mode.",
    )
    parser.set_defaults(handler=handle_examples)


def _add_doctor_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "doctor",
        help="Check whether the runtime environment looks healthy.",
        description=(
            "Inspect Python, spaCy, and the English model configuration used by ShakesPy."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit environment information as JSON.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.set_defaults(handler=handle_doctor)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    normalized_argv = normalize_argv(argv)
    args = parser.parse_args(normalized_argv)
    context = CliContext(stdout=sys.stdout, stderr=sys.stderr)
    return args.handler(args, context)


def normalize_argv(argv: Sequence[str] | None) -> list[str]:
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw:
        return raw
    first = raw[0]
    if first in SUBCOMMAND_NAMES or first in PASSTHROUGH_FLAGS:
        return raw
    if first in TRANSLATE_FLAGS:
        return ["translate", *raw]
    if not first.startswith("-"):
        return ["translate", *raw]
    return raw


def handle_translate(args: argparse.Namespace, context: CliContext) -> int:
    try:
        source_text, source_name = resolve_single_input(args, context)
        if args.strip:
            source_text = source_text.strip()
        if args.fail_on_empty and not source_text:
            raise CliUsageError("Resolved input is empty.")

        record = TranslationRecord(
            source=source_text,
            translated=translate(source_text),
            source_name=source_name,
            index=1,
        )
        rendered = render_single_record(
            record,
            RenderOptions(
                as_json=args.json,
                pretty=args.pretty,
                show_header=args.show_header,
                number_lines=args.number_lines,
                show_source=args.show_source,
                separator=args.separator,
            ),
            dump_metadata=args.dump_metadata,
            repeat=max(1, args.repeat),
        )

        if args.output_file:
            write_text_file(args.output_file, rendered, encoding=args.encoding)
        else:
            write_output(context.stdout, rendered)
        return EXIT_OK
    except CliUsageError as exc:
        write_error(context.stderr, str(exc))
        return EXIT_USAGE
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        write_error(context.stderr, f"Translation failed: {exc}")
        return EXIT_TRANSLATION_ERROR


def handle_batch(args: argparse.Namespace, context: CliContext) -> int:
    try:
        batch_options = BatchOptions(
            recursive=args.recursive,
            glob=args.glob,
            skip_empty=args.skip_empty,
            include_source=args.show_source,
        )
        input_files = collect_input_files(args.paths, batch_options)
        records: list[TranslationRecord] = []

        for index, input_path in enumerate(input_files, start=1):
            source_text = read_text_file(input_path, encoding=args.encoding)
            if args.strip:
                source_text = source_text.strip()
            if batch_options.skip_empty and not source_text:
                continue

            translated = translate(source_text)
            record = TranslationRecord(
                source=source_text,
                translated=translated,
                source_name=str(input_path),
                index=index,
            )
            records.append(record)

            if args.output_dir and not args.dry_run:
                destination = build_batch_output_path(
                    source_path=input_path,
                    root_paths=args.paths,
                    output_dir=args.output_dir,
                    suffix=args.suffix,
                )
                write_text_file(destination, translated, encoding=args.encoding)

        if args.json:
            rendered = render_batch_json(records, pretty=args.pretty, show_source=args.show_source)
            write_output(context.stdout, rendered)
            return EXIT_OK

        if args.print_output or not args.output_dir or args.dry_run:
            rendered = render_batch_plaintext(
                records,
                show_source=args.show_source,
                dry_run=args.dry_run,
                output_dir=args.output_dir,
            )
            write_output(context.stdout, rendered)

        if args.dry_run and args.output_dir:
            preview = render_batch_destinations(
                input_files=input_files,
                root_paths=args.paths,
                output_dir=args.output_dir,
                suffix=args.suffix,
            )
            write_output(context.stdout, preview)

        return EXIT_OK
    except CliUsageError as exc:
        write_error(context.stderr, str(exc))
        return EXIT_USAGE
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        write_error(context.stderr, f"Batch translation failed: {exc}")
        return EXIT_TRANSLATION_ERROR


def handle_repl(args: argparse.Namespace, context: CliContext) -> int:
    if args.show_header:
        write_output(context.stdout, REPL_BANNER)

    while True:
        try:
            raw = input(args.prompt)
        except EOFError:
            write_output(context.stdout, "")
            return EXIT_OK
        except KeyboardInterrupt:
            write_output(context.stdout, "\nFare thee well.")
            return EXIT_OK

        if not raw.strip():
            continue
        if raw.startswith("/"):
            should_exit = process_repl_command(raw, args, context)
            if should_exit:
                return EXIT_OK
            continue

        try:
            translated = translate(raw)
        except Exception as exc:  # pragma: no cover - interactive boundary
            write_error(context.stderr, f"Translation failed: {exc}")
            continue

        if args.number_lines:
            translated = number_lines(translated)
        write_output(context.stdout, f"{args.translated_prompt}{translated}")


def handle_glossary(args: argparse.Namespace, context: CliContext) -> int:
    rules = resolve_glossary_rules(args)
    if args.contains:
        needle = args.contains.casefold()
        rules = [
            rule for rule in rules
            if needle in rule.source.casefold() or needle in rule.replacement.casefold()
        ]

    if args.json:
        payload = [
            {"source": rule.source, "replacement": rule.replacement}
            for rule in rules
        ]
        write_output(context.stdout, dump_json(payload, pretty=args.pretty))
        return EXIT_OK

    rendered = render_glossary_plaintext(rules)
    write_output(context.stdout, rendered)
    return EXIT_OK


def handle_examples(args: argparse.Namespace, context: CliContext) -> int:
    records = [
        TranslationRecord(
            source=sample,
            translated=translate(sample),
            source_name="example",
            index=index,
        )
        for index, sample in enumerate(EXAMPLE_TEXTS, start=1)
    ]

    if args.json:
        payload = [asdict(record) for record in records]
        write_output(context.stdout, dump_json(payload, pretty=args.pretty))
        return EXIT_OK

    if args.translate_only:
        write_output(context.stdout, "\n".join(record.translated for record in records))
        return EXIT_OK

    sections = []
    for record in records:
        sections.append(
            "\n".join(
                [
                    f"[Example {record.index}]",
                    f"Modern: {record.source}",
                    f"Bardic: {record.translated}",
                ]
            )
        )
    write_output(context.stdout, "\n\n".join(sections))
    return EXIT_OK


def handle_doctor(args: argparse.Namespace, context: CliContext) -> int:
    status = gather_environment_status()
    if args.json:
        write_output(context.stdout, dump_json(status, pretty=args.pretty))
        return EXIT_OK

    lines = [
        "ShakesPy environment report",
        f"- package version: {status['package_version']}",
        f"- python: {status['python']}",
        f"- spaCy available: {status['spacy_available']}",
        f"- model available: {status['model_available']}",
        f"- model name: {status['model_name']}",
    ]
    if status["error"]:
        lines.append(f"- error: {status['error']}")
    write_output(context.stdout, "\n".join(lines))
    return EXIT_OK


def resolve_single_input(args: argparse.Namespace, context: CliContext) -> tuple[str, str]:
    explicit_sources = int(bool(args.text)) + int(bool(args.stdin)) + int(bool(args.input_file))
    if explicit_sources == 0:
        raise CliUsageError(
            "No input provided. Pass text, use --stdin, or specify --input-file."
        )
    if explicit_sources > 1:
        raise CliUsageError(
            "Choose exactly one input source: positional text, --stdin, or --input-file."
        )

    if args.text:
        return " ".join(args.text), "inline"
    if args.stdin:
        return context.stdin.read() if hasattr(context, "stdin") else sys.stdin.read(), "stdin"
    if args.input_file:
        return read_text_file(args.input_file, encoding=args.encoding), str(args.input_file)
    raise CliUsageError("Unable to resolve input source.")


def collect_input_files(paths: Sequence[Path], options: BatchOptions) -> list[Path]:
    collected: list[Path] = []
    for raw_path in paths:
        path = raw_path.expanduser()
        if not path.exists():
            raise CliUsageError(f"Input path does not exist: {path}")
        if path.is_file():
            collected.append(path)
            continue
        if path.is_dir():
            iterator = path.rglob(options.glob) if options.recursive else path.glob(options.glob)
            collected.extend(candidate for candidate in iterator if candidate.is_file())
            continue
        raise CliUsageError(f"Unsupported path type: {path}")

    unique = sorted({item.resolve() for item in collected})
    if not unique:
        raise CliUsageError("No input files matched the provided paths.")
    return unique


def build_batch_output_path(
    source_path: Path,
    root_paths: Sequence[Path],
    output_dir: Path,
    suffix: str,
) -> Path:
    output_dir = output_dir.expanduser()
    matched_root = choose_root_for_path(source_path, root_paths)
    if matched_root.is_file():
        relative = Path(source_path.name)
    else:
        relative = source_path.relative_to(matched_root)

    destination = output_dir / relative
    new_name = f"{destination.stem}{suffix}{destination.suffix}"
    return destination.with_name(new_name)


def choose_root_for_path(source_path: Path, root_paths: Sequence[Path]) -> Path:
    resolved_source = source_path.resolve()
    candidates = sorted(
        (path.resolve() for path in root_paths if path.exists()),
        key=lambda path: len(str(path)),
        reverse=True,
    )
    for candidate in candidates:
        if candidate.is_file() and candidate == resolved_source:
            return candidate
        if candidate.is_dir():
            try:
                resolved_source.relative_to(candidate)
                return candidate
            except ValueError:
                continue
    return source_path.parent


def render_single_record(
    record: TranslationRecord,
    options: RenderOptions,
    dump_metadata: bool = False,
    repeat: int = 1,
) -> str:
    if options.as_json:
        payload: list[dict[str, object]] = []
        for index in range(repeat):
            item: dict[str, object] = {
                "index": index + 1,
                "translated": record.translated,
                "source_name": record.source_name,
            }
            if options.show_source:
                item["source"] = record.source
            if dump_metadata:
                item["metadata"] = build_record_metadata(record)
            payload.append(item)
        return dump_json(payload[0] if repeat == 1 else payload, pretty=options.pretty)

    sections: list[str] = []
    for index in range(repeat):
        translated = number_lines(record.translated) if options.number_lines else record.translated
        block_lines: list[str] = []
        if options.show_header:
            block_lines.append(render_header(f"Translation {index + 1}"))
        if options.show_source:
            block_lines.append(f"Source ({record.source_name}): {record.source}")
        block_lines.append(translated)
        if dump_metadata:
            metadata = build_record_metadata(record)
            block_lines.append(f"[chars: {metadata['translated_characters']}]")
        sections.append("\n".join(block_lines))
    return options.separator.join(sections)


def render_batch_json(
    records: Sequence[TranslationRecord],
    pretty: bool = False,
    show_source: bool = False,
) -> str:
    payload = []
    for record in records:
        item: dict[str, object] = {
            "index": record.index,
            "source_name": record.source_name,
            "translated": record.translated,
            "metadata": build_record_metadata(record),
        }
        if show_source:
            item["source"] = record.source
        payload.append(item)
    return dump_json(payload, pretty=pretty)


def render_batch_plaintext(
    records: Sequence[TranslationRecord],
    show_source: bool = False,
    dry_run: bool = False,
    output_dir: Path | None = None,
) -> str:
    lines: list[str] = []
    if dry_run:
        lines.append(render_header("Dry Run"))
    elif output_dir:
        lines.append(render_header("Batch Translation"))

    for record in records:
        lines.append(f"[{record.index}] {record.source_name}")
        if show_source:
            lines.append(f"source: {record.source}")
        lines.append(f"translated: {record.translated}")
        lines.append("")

    return "\n".join(lines).rstrip()


def render_batch_destinations(
    input_files: Sequence[Path],
    root_paths: Sequence[Path],
    output_dir: Path,
    suffix: str,
) -> str:
    lines = [render_header("Planned Outputs")]
    for path in input_files:
        destination = build_batch_output_path(path, root_paths, output_dir, suffix)
        lines.append(f"{path} -> {destination}")
    return "\n".join(lines)


def render_glossary_plaintext(rules: Sequence[ReplacementRule]) -> str:
    if not rules:
        return "No glossary entries matched."

    width = max(len(rule.source) for rule in rules)
    lines = [render_header("Glossary")]
    for rule in rules:
        lines.append(f"{rule.source.ljust(width)} -> {rule.replacement}")
    return "\n".join(lines)


def resolve_glossary_rules(args: argparse.Namespace) -> list[ReplacementRule]:
    if args.phrases and args.words:
        return list(PHRASE_REPLACEMENTS) + list(WORD_REPLACEMENTS)
    if args.phrases:
        return list(PHRASE_REPLACEMENTS)
    if args.words:
        return list(WORD_REPLACEMENTS)
    return list(PHRASE_REPLACEMENTS) + list(WORD_REPLACEMENTS)


def process_repl_command(raw: str, args: argparse.Namespace, context: CliContext) -> bool:
    command = raw.strip().lower()
    if command in {"/quit", "/exit"}:
        write_output(context.stdout, "Fare thee well.")
        return True
    if command == "/help":
        write_output(context.stdout, render_repl_help())
        return False
    if command == "/rules":
        write_output(context.stdout, render_glossary_plaintext(resolve_glossary_rules(_GlossaryArgs())))
        return False
    if command == "/examples":
        for sample in EXAMPLE_TEXTS:
            write_output(context.stdout, f"{args.translated_prompt}{translate(sample)}")
        return False
    if command == "/banner":
        write_output(context.stdout, REPL_BANNER)
        return False
    write_error(context.stderr, f"Unknown REPL command: {raw}")
    return False


def render_repl_help() -> str:
    return "\n".join(
        [
            render_header("REPL Commands"),
            "/help      Show this help message",
            "/rules     Show the built-in glossary",
            "/examples  Translate the built-in examples",
            "/banner    Reprint the interactive banner",
            "/quit      Exit the REPL",
        ]
    )


def gather_environment_status() -> dict[str, object]:
    status = {
        "package_version": __version__,
        "python": sys.version.split()[0],
        "spacy_available": False,
        "model_available": False,
        "model_name": "en_core_web_sm",
        "error": None,
    }

    try:
        nlp = _get_nlp()
        status["spacy_available"] = True
        status["model_available"] = True
        status["pipeline"] = list(nlp.pipe_names)
    except Exception as exc:  # pragma: no cover - depends on environment
        message = str(exc)
        status["error"] = message
        if "spaCy is required" in message:
            status["spacy_available"] = False
        else:
            status["spacy_available"] = True
            status["model_available"] = False
    return status


def build_record_metadata(record: TranslationRecord) -> dict[str, object]:
    return {
        "source_characters": len(record.source),
        "translated_characters": len(record.translated),
        "source_lines": record.source.count("\n") + 1 if record.source else 0,
        "translated_lines": record.translated.count("\n") + 1 if record.translated else 0,
    }


def number_lines(text: str) -> str:
    lines = text.splitlines() or [text]
    width = len(str(len(lines)))
    return "\n".join(f"{str(index).rjust(width)} | {line}" for index, line in enumerate(lines, start=1))


def render_header(title: str) -> str:
    underline = "=" * len(title)
    return f"{title}\n{underline}"


def dump_json(payload: object, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    return json.dumps(payload, ensure_ascii=False)


def read_text_file(path: Path, encoding: str = DEFAULT_ENCODING) -> str:
    try:
        return path.expanduser().read_text(encoding=encoding)
    except FileNotFoundError as exc:
        raise CliUsageError(f"File not found: {path}") from exc
    except OSError as exc:
        raise CliUsageError(f"Could not read file {path}: {exc}") from exc


def write_text_file(path: Path, content: str, encoding: str = DEFAULT_ENCODING) -> None:
    try:
        target = path.expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
    except OSError as exc:
        raise CliUsageError(f"Could not write file {path}: {exc}") from exc


def write_output(stream, content: str) -> None:
    if content.endswith("\n"):
        stream.write(content)
    else:
        stream.write(f"{content}\n")


def write_error(stream, message: str) -> None:
    write_output(stream, f"error: {message}")


class CliUsageError(ValueError):
    """Raised when CLI input is invalid or incomplete."""


@dataclass(frozen=True)
class _GlossaryArgs:
    phrases: bool = False
    words: bool = False


if __name__ == "__main__":
    raise SystemExit(main())
