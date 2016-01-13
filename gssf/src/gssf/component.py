# This file is part of the Go-Smart Simulation Architecture (GSSA).
# Go-Smart is an EU-FP7 project, funded by the European Commission.
#
# Copyright (C) 2013-  NUMA Engineering Ltd. (see AUTHORS file)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from lxml import etree as ET
import time
import errno
import subprocess
import math
import threading
import re
import json

from .globals import slugify, colorama_imported
from . import config
from .errors import Error as ErrorCode

if colorama_imported:
    import colorama


# Note that derived classes should account for the possibility
# that parse_config is not called due to missing information in
# the settings file (intentionally or otherwise)
class GoSmartComponent:
    suffix = 'unknown'

    # This is just a convenience member allowing us to put in TODOs that the
    # user should be prompted about (in some sense, temporary caveats)
    todos = ()

    logpick_pairs = ()
    error_regex = None
    last_error = None
    manual_return_code_handling = False

    # Tuplet - number of consecutive triggered seconds before suppressing; number of lines per second to trigger
    suppress_logging_over_per_second = None

    def __init__(self, logger):
        self.logger = logger
        self.mute = None  # This _overrides_ value passed to _launch_subprocess
        self.cwd = "."

        self._constant_mapping = {}
        self._constant_mapping_types = {}
        self._constant_mapping_warn = {}

        self._timings = {}
        self._timings_tmp = {}

        # Timings in contrasting colour
        self.print_timing = lambda t: self.logger.print_line(t, color="BLUE", color_bright=True)

        # Error regexes pick anything containing the words ERROR or FATAL (any
        # case)
        self.error_regex = re.compile(r'(error|fatal)', re.IGNORECASE)

        for todo in self.todos:
            self.logger.print_line("TODO (%s): %s" % (self.suffix, todo), color_bright=True)

    # This monitors the log with pairs of regexes to find start/end of timings of interest (e.g. FE assembly)
    def logpick(self, offset, logline):
        sym = " "

        if not self.logpick_pairs:
            return sym

        # Annotate lines matching the logpick regexes: > for start timing, | for
        # in timing, < for end of timing
        for pair in self.logpick_pairs:
            if pair[0] in self._timings_tmp and logline.startswith(pair[1]):
                if pair[0] not in self._timings:
                    self._timings[pair[0]] = 0
                self._timings[pair[0]] += offset - self._timings_tmp[pair[0]]
                del self._timings_tmp[pair[0]]
                sym = ">"
            if pair[0] not in self._timings_tmp and logline.startswith(pair[0]):
                self._timings_tmp[pair[0]] = offset
                sym = "|" if sym in (">", "|") else "<"

        return sym

    # Output the final logpick detail
    def print_logpick(self, total):
        self.print_timing("Timings (sec resolution):")
        total_counted = 0
        for timing in self.logpick_pairs:
            if timing[0] in self._timings:
                self.print_timing(" -- %4d %s <'%s' - '%s'>" % (self._timings[timing[0]], timing[2], timing[0], timing[1]))
                total_counted += self._timings[timing[0]]

        self.print_timing(" -- %4d [other]" % (total - total_counted))
        self.print_timing("    ====")
        self.print_timing(" -- %d" % total)

    # Attach a constant (attribute)
    def add_or_update_constant(self, name, value, warn=False, group="CONSTANT", typ=None):
        # Create a name that is a legitimate template slug and is unique even
        # outside the group
        mangled_name = "%s_%s" % (slugify(group), slugify(name))

        self._constant_mapping[mangled_name] = value
        self._constant_mapping_types[mangled_name] = typ

        if warn:
            self._constant_mapping_warn[mangled_name] = "constant : %s" % name

        # Make sure this is known globally also
        self.logger.add_or_update_constant(name, value, False, group, typ=typ)

    # Return a constant's type - preferably from this component's map, or global
    # if not
    def get_constant_type(self, name, group="CONSTANT"):
        mangled_name = "%s_%s" % (slugify(group), slugify(name))

        if name in self._constant_mapping_types:
            return self._constant_mapping_types[name]
        elif mangled_name in self._constant_mapping_types:
            return self._constant_mapping_types[mangled_name]

        return self.logger.get_constant(name, group)

    # Return a constant - preferably from this component's map, or global if not
    def get_constant(self, name, group="CONSTANT"):
        mangled_name = "%s_%s" % (slugify(group), slugify(name))

        if name in self._constant_mapping:
            return self._constant_mapping[name]
        elif mangled_name in self._constant_mapping:
            return self._constant_mapping[mangled_name]

        return self.logger.get_constant(name, group)

    # Get a merged copy of constants for this component and the global space
    def get_constants(self):
        constants = self._constant_mapping.copy()
        constants.update(self.logger.get_constants())

        return constants

    # Get all (this component's and global) constants marked for warning
    def get_mapping_warn(self):
        warn = self._constant_mapping_warn.copy()
        warn.update(self.logger.get_mapping_warn())

        return warn

    # Load relevant values from the XML node (normally most of this is done in
    # the subclass, we just handle the generic aspects here)
    def parse_config(self, config_node):
        # Should log output be suppressed?
        if config_node.get('mute') == "true":
            self.mute = True
        if config_node.get('mute') == "false":
            self.mute = False

        # If there are component-specific constants, load them (note that they
        # will also get fed up to the global constant space)
        element = config_node.find('constants')
        if element is not None:
            # Default_set allows us to specify a library of constants
            default_set = element.get("defaults")

            if default_set is not None:
                self._load_constant_set(default_set)

            # Try and set this constant
            for constant in element:
                value = constant.get("value")
                if value is None:
                    # FIXME: should this be constant.text?
                    value = constant
                # Try and rehydrate this constant if possible
                try:
                    value = json.loads(value)
                except:
                    pass
                self.add_or_update_constant(constant.get("name"), value, True, constant.tag, typ=constant.get("type"))

    # Grab a set of constants from standard config
    def _load_constant_set(self, setname):
        constant_filename = "constants/constants-%s.xml" % slugify(setname).lower()
        with open(os.path.join(config.template_directory, constant_filename), "r") as constant_file:
            configtree = ET.parse(constant_file)
            root = configtree.getroot()

            for constant in root:
                value = constant.get("value")
                if value is None:
                    value = constant
                try:
                    value = json.loads(value)
                except:
                    pass
                self.add_or_update_constant(constant.get('name'), value, (constant.get('warn') == 'yes'), typ=constant.get("type"))

    # Set the filename prefix to be used for output from this component
    def set_outfile_prefix(self, outfile):
        self.outfilename = os.path.join(self.logger.get_cwd(), outfile)

    # Get name of an output log file
    def get_outfile(self):
        return self.outfilename + '-' + self.suffix + '.log'

    # Process the output of the subprocess - logging to disk and doing any
    # necessary analysis
    def _log_thread(self, process_stdout, outstream, mute):
        current_second = -1
        current_per_second = 0
        consecutive_overrun = 0

        # Step line by line through child's STDOUT
        for line in iter(process_stdout.readline, ''):
            outstream.write(line)

            offset = time.time() - self._start_time

            # Check this line for logpick entries
            sym = self.logpick(offset, line)

            # Check if there is any error here
            if self.error_regex and self.error_regex.search(line):
                self.last_error = line

            suppress = mute
            # If the rate of output is too high, then do not print the log
            # messages
            if self.suppress_logging_over_per_second is not None:
                if math.floor(offset) == current_second:
                    current_per_second += 1
                else:
                    if current_per_second == -1:
                        consecutive_overrun = 0
                    else:
                        current_per_second = -1
                        consecutive_overrun += 1

                    current_second = math.floor(offset)

                if consecutive_overrun >= self.suppress_logging_over_per_second[0]:
                    if current_per_second == self.suppress_logging_over_per_second[1]:
                        line = "......"
                    elif current_per_second > self.suppress_logging_over_per_second[1]:
                        suppress = True

            if not suppress:
                # If we can print in colour, do so
                if colorama_imported:
                    line = "%s  + %8d %s[%s %s" % (colorama.Fore.YELLOW, offset, sym, colorama.Fore.RESET, line.strip())
                else:
                    line = "  + %8d %s[ %s" % (offset, sym, line.strip())

                # Now send this to the global logger
                self.logger.print_line(line, color_text=False)

    # Actually fire off the subprocess
    def _launch_subprocess(self, executable, args, mute=False, environment={}):
        if self.mute is not None:
            mute = self.mute

        # Open the logging file for logging - we do component-specific logging
        # from here, global goes to the global logger
        outfile = self.get_outfile()
        outstream = open(outfile, "w")

        self.logger.print_line("  (output to %s)" % outfile)

        if not mute and not self.logger.silent:
            self.logger.print_error(outfile)

        # Print full command string - usually, this can be copy-pasted to the
        # shell directly (if environment matches) to reproduce what you see here
        args = [str(a) for a in args]
        args.insert(0, executable)
        self.logger.print_line("  Command: " + " ".join(args) + " [" + self.cwd + "]")

        outstream_line = "GOSMART: Output for " + " ".join(args) + " [" + self.cwd + "]"
        outstream.write(outstream_line + "\n")
        outstream.write("=" * len(outstream_line))
        outstream.write("\n")

        self._start_time = time.time()
        self.logger.print_line("  Starting %d s after launcher" % (self._start_time - self.logger.init_time))

        # Make sure everything is written
        self.logger.flush_logfile()
        outstream.flush()

        # Fire off the subprocess based on the arguments and working directory
        # above. Do not buffer output, as we will take care of it immediately
        # and pipe output back to us (except STDERR)
        self._process = subprocess.Popen(args, cwd=self.logger.make_cwd(self.cwd), stderr=subprocess.STDOUT,
                                         stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)

        # Set up the logging thread and get it started, processing output from
        # the subprocess above
        thread = threading.Thread(target=self._log_thread, args=[self._process.stdout, outstream, mute])
        thread.daemon = True
        thread.start()

        # Let the subprocess go about its business, output handled by the
        # logging thread, while we in the main thread wait
        return_code = self._process.wait()

        self._end_time = time.time()
        self.logger.print_line("  Stopping %d s after launcher" % (self._end_time - self.logger.init_time))

        # If the return code is non-zero we crash out
        # FIXME: Ignoring segfaults and other signals (negative codes indicate terminated by a given Unix signal)
        if not self.manual_return_code_handling and return_code != 0:
            # If there is no manual return code handling, we assume this is our indicator for the Go-Smart code
            try:
                code = ErrorCode(return_code).name
            except ValueError:
                if return_code < 0:
                    code = "E_SERVER"
                else:
                    code = "E_UNKNOWN"

            message = "%s did not exit cleanly - returned %d (%s)" % (executable, return_code, self.suffix)
            if self.last_error:
                message += ": %s" % self.last_error
            self.logger.print_fatal(message, code)

        # Just in case the thread gets stuck for some reason
        thread.join(timeout=1)

        self._end_time = time.time()

        # Output the logpick entries
        self.print_logpick(self._end_time - self._start_time)

        return return_code

    # This is primarily a placeholder for derived classes
    def launch(self):
        self.logger.print_line("Launching %s..." % self.suffix)

        self.logger.flush_logfile()

        absolute_path = os.path.join(self.logger.get_cwd(), self.suffix)
        try:
            os.makedirs(absolute_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                self.print_fatal("Could not create %s directory: %s" %
                                 (absolute_path, str(e)))
