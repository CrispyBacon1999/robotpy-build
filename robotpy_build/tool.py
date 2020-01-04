import argparse
import glob
import inspect
from os.path import basename, exists, join, relpath, splitext
import subprocess

from .setup import Setup
from .generator_data import MissingReporter


def get_setup() -> Setup:
    s = Setup()
    s.prepare()
    return s


class GenCreator:
    @classmethod
    def add_subparser(cls, parent_parser, subparsers):
        parser = subparsers.add_parser(
            "create-gen",
            help="Create YAML files from parsed header files",
            parents=[parent_parser],
        )
        parser.add_argument(
            "--write", help="Write to files if they don't exist", action="store_true"
        )
        parser.add_argument("--strip-prefixes", action="append")

        return parser

    def run(self, args):

        pfx = ""
        if args.strip_prefixes:
            pfx = "strip_prefixes:\n- " + "\n- ".join(args.strip_prefixes) + "\n\n"

        s = get_setup()
        for wrapper in s.wrappers:
            reporter = MissingReporter()
            wrapper.on_build_gen("", reporter)

            nada = True
            for name, report in reporter.as_yaml():
                report = f"---\n\n{pfx}{report}"

                nada = False
                if args.write:
                    if not exists(name):
                        print("Writing", name)
                        with open(name, "w") as fp:
                            fp.write(report)
                    else:
                        print(name, "already exists!")

                print("===", name, "===")
                print(report)

            if nada:
                print("Nothing to do!")


class HeaderScanner:
    @classmethod
    def add_subparser(cls, parent_parser, subparsers):
        parser = subparsers.add_parser(
            "scan-headers",
            help="Generate a list of headers in TOML form",
            parents=[parent_parser],
        )
        return parser

    def run(self, args):
        s = get_setup()
        for wrapper in s.wrappers:
            for incdir in wrapper.get_include_dirs():
                files = list(
                    sorted(
                        relpath(f, incdir) for f in glob.glob(join(incdir, "**", "*.h"))
                    )
                )

                print("generate = [")
                for f in files:
                    if "rpygen" not in f:
                        base = splitext(basename(f))[0]
                        print(f'    {{ {base} = "{f}" }},')
                print("]")


class ImportCreator:
    @classmethod
    def add_subparser(cls, parent_parser, subparsers):
        parser = subparsers.add_parser(
            "create-imports",
            help="Generate suitable imports for a module",
            parents=[parent_parser],
        )
        parser.add_argument("base", help="Ex: wpiutil")
        parser.add_argument("compiled", help="Ex: wpiutil._impl.wpiutil")
        return parser

    def run(self, args):
        # TODO: could probably generate this from parsed code, but seems hard
        ctx = {}
        exec(f"from {args.compiled} import *", {}, ctx)

        relimport = "." + ".".join(
            args.compiled.split(".")[len(args.base.split(".")) :]
        )

        stmt = inspect.cleandoc(
            f"""

            # autogenerated by 'robotpy-build create-imports {args.base} {args.compiled}'
            from {relimport} import {','.join(sorted(ctx.keys()))}
            __all__ = ["{'", "'.join(sorted(ctx.keys()))}"]
        
        """
        )

        print(
            subprocess.check_output(
                ["black", "-", "-q"], input=stmt.encode("utf-8")
            ).decode("utf-8")
        )


def main():

    parser = argparse.ArgumentParser(prog="robotpy-build")
    parent_parser = argparse.ArgumentParser(add_help=False)
    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True

    for cls in (GenCreator, HeaderScanner, ImportCreator):
        cls.add_subparser(parent_parser, subparsers).set_defaults(cls=cls)

    args = parser.parse_args()
    cmd = args.cls()
    retval = cmd.run(args)

    if retval is False:
        retval = 1
    elif retval is True:
        retval = 0
    elif isinstance(retval, int):
        pass
    else:
        retval = 0

    exit(retval)
