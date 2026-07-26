"""Assemble every positive example with the official MARS 4.5 CLI."""

from argparse import ArgumentParser
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codegen import generate_ir
from lexer import lex
from mips import generate_mips
from parser_rd import parse_rd
from semantic import analyse


def compile_text(source: str, name="source") -> str:
    tokens, lex_errors = lex(source)
    if lex_errors:
        raise RuntimeError(f"{name}: lexical errors: {lex_errors}")
    ast, parse_errors = parse_rd(tokens)
    if parse_errors:
        raise RuntimeError(f"{name}: syntax errors: {parse_errors}")
    sem_errors = analyse(ast)
    if sem_errors:
        raise RuntimeError(f"{name}: semantic errors: {sem_errors}")
    return generate_mips(generate_ir(ast))


def compile_source(path: Path) -> str:
    return compile_text(path.read_text(encoding="utf-8"), path.name)


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("mars_jar", type=Path)
    args = parser.parse_args()

    failures = []
    examples = [
        path
        for path in sorted((ROOT / "examples").glob("*.rs"))
        if not path.name.startswith("err.")
    ]
    output_dir = ROOT / "tmp"
    output_dir.mkdir(exist_ok=True)
    generated = []
    try:
        for source_path in examples:
            asm_path = output_dir / f"verify_{source_path.stem}.asm"
            generated.append(asm_path)
            asm_path.write_text(compile_source(source_path), encoding="utf-8")
            result = subprocess.run(
                [
                    "java",
                    "-jar",
                    str(args.mars_jar.resolve()),
                    "nc",
                    "a",
                    "ae1",
                    str(asm_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode:
                failures.append((source_path.name, result.stdout, result.stderr))

        smoke_path = output_dir / "verify_runtime.asm"
        generated.append(smoke_path)
        smoke_path.write_text(
            compile_text(
                "fn factorial(n:i32)->i32{"
                "if n<=1{return 1;}return n*factorial(n-1);}"
                "fn main()->i32{factorial(5)}",
                "runtime smoke test",
            ),
            encoding="utf-8",
        )
        smoke = subprocess.run(
            [
                "java",
                "-jar",
                str(args.mars_jar.resolve()),
                "nc",
                "sm",
                "se1",
                "100000",
                "s0",
                str(smoke_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if smoke.returncode or "0x00000078" not in smoke.stdout:
            failures.append(("runtime smoke test", smoke.stdout, smoke.stderr))
    finally:
        for asm_path in generated:
            asm_path.unlink(missing_ok=True)

    if failures:
        for name, stdout, stderr in failures:
            print(f"[FAIL] {name}\n{stdout}{stderr}")
        return 1
    print(
        f"MARS assembled {len(examples)} positive examples and "
        "executed factorial(5)=120 successfully."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
