import os
import sys
import tempfile

import asciinema.asciicast.raw as raw
import asciinema.asciicast.v2 as v2
import asciinema.notifier as notifier
import asciinema.recorder as recorder
from asciinema.api import APIError
from asciinema.commands.command import Command


class RecordCommand(Command):
    def __init__(self, args, config, env):
        Command.__init__(self, args, config, env)
        self.quiet = args.quiet
        self.filename = args.filename
        self.rec_stdin = args.stdin
        self.command = args.command
        self.env_whitelist = args.env
        self.title = args.title
        self.assume_yes = args.yes or args.quiet
        self.idle_time_limit = args.idle_time_limit
        self.append = args.append
        self.overwrite = args.overwrite
        self.raw = args.raw
        self.writer = raw.writer if args.raw else v2.writer
        self.notifier = notifier.get_notifier(
            config.notifications_enabled, config.notifications_command
        )
        self.env = env
        self.key_bindings = {
            "prefix": config.record_prefix_key,
            "pause": config.record_pause_key,
        }

    def execute(self):
        upload = False
        append = self.append

        if self.filename == "":
            if self.raw:
                self.print_error(
                    "filename required when recording in raw mode"
                )
                return 1
            else:
                self.filename = _tmp_path()
                upload = True

        if os.path.exists(self.filename):
            if not os.access(self.filename, os.W_OK):
                self.print_error(f"can't write to {self.filename}")
                return 1

            if os.stat(self.filename).st_size > 0 and self.overwrite:
                os.remove(self.filename)
                append = False

            elif os.stat(self.filename).st_size > 0 and not append:
                self.print_error(f"{self.filename} already exists, aborting")
                self.print_error(
                    "use --overwrite option if you want to overwrite existing recording"
                )
                self.print_error(
                    "use --append option if you want to append to existing recording"
                )
                return 1

        if append:
            self.print_info(f"appending to asciicast at {self.filename}")
        else:
            self.print_info(f"recording asciicast to {self.filename}")

        if self.command:
            self.print_info("""exit opened program when you're done""")
        else:
            self.print_info(
                """press <ctrl-d> or type "exit" when you're done"""
            )

        vars = filter(
            None, map((lambda var: var.strip()), self.env_whitelist.split(","))
        )

        try:
            recorder.record(
                self.filename,
                command=self.command,
                append=append,
                title=self.title,
                idle_time_limit=self.idle_time_limit,
                command_env=self.env,
                capture_env=vars,
                rec_stdin=self.rec_stdin,
                writer=self.writer,
                notifier=self.notifier,
                key_bindings=self.key_bindings,
            )
        except v2.LoadError:
            self.print_error(
                "can only append to asciicast v2 format recordings"
            )
            return 1

        self.print_info("recording finished")

        if upload:
            if not self.assume_yes:
                self.print_info(
                    f"press <enter> to upload to {self.api.hostname()}"
                    ", <ctrl-c> to save locally"
                )
                try:
                    sys.stdin.readline()
                except KeyboardInterrupt:
                    self.print("\r", end="")
                    self.print_info(f"asciicast saved to {self.filename}")
                    return 0

            try:
                result, warn = self.api.upload_asciicast(self.filename)

                if warn:
                    self.print_warning(warn)

                os.remove(self.filename)
                self.print(result.get("message") or result["url"])

            except APIError as e:
                self.print("\r\x1b[A", end="")
                self.print_error(f"upload failed: {str(e)}")
                self.print_error(
                    f"retry later by running: asciinema upload {self.filename}"
                )
                return 1
        else:
            self.print_info(f"asciicast saved to {self.filename}")

        return 0


def _tmp_path():
    fd, path = tempfile.mkstemp(suffix="-ascii.cast")
    os.close(fd)
    return path
