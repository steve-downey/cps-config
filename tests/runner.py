#!/usr/bin/env python
# SPDX-License-Identifier: MIT
# Copyright © 2024 Dylan Baker

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import os
import sys
import tomllib
import typing

if typing.TYPE_CHECKING:

    class Arguments(typing.Protocol):

        runner: str
        cases: str

    class TestCase(typing.TypedDict):

        name: str
        cps: str
        args: list[str]
        expected: str
        mode: typing.NotRequired[typing.Literal['pkgconf']]

    class TestDescription(typing.TypedDict):

        case: list[TestCase]


SOURCE_DIR = os.path.dirname(os.path.dirname(__file__))
PREFIX = os.path.join(SOURCE_DIR, 'tests/cases')
_PRINT_LOCK = asyncio.Lock()


@dataclasses.dataclass
class Result:

    name: str
    success: bool
    stdout: str
    stderr: str
    returncode: int
    expected: str
    command: list[str]


async def test(runner: str, case_: TestCase) -> Result:
    cmd = [runner, case_['cps']] + case_['args']
    if 'mode' in case_:
        cmd.extend([f"--format={case_['mode']}"])
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    bout, berr = await proc.communicate()
    out = bout.decode().strip()

    expected = case_['expected'].format(prefix=PREFIX)

    success = proc.returncode == 0 and out == expected
    async with _PRINT_LOCK:
        print('ok' if success else 'not ok', '-', case_['name'])

    return Result(case_['name'], success, out, berr.decode().strip(), proc.returncode, expected, cmd)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('runner', help="The compiled cps-config binary")
    parser.add_argument('cases', help="A toml file containing case descriptions")
    args: Arguments = parser.parse_args()

    with open(os.path.join(SOURCE_DIR, args.cases), 'rb') as f:
        tests = typing.cast('TestDescription', tomllib.load(f))

    print(f'1..{len(tests["case"])}')

    results = typing.cast(
        'list[Result]',
        await asyncio.gather(*[test(args.runner, c) for c in tests['case']]))

    for r in results:
        if not r.success:
            print(f'{r.name}:', file=sys.stderr)
            print('  returncode:', r.returncode, file=sys.stderr)
            print('  stdout:  ', r.stdout, file=sys.stderr)
            print('  expected:', r.expected, file=sys.stderr)
            print('  stderr:', r.stderr, file=sys.stderr)
            print('  command:', ' '.join(r.command), file=sys.stderr)
            print('\n')


if __name__ == "__main__":
    asyncio.run(main())