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

# TODO: this file needs quite a bit of tidying and crud-removal, once PythonOCC
# is Py3 compatible

import os
import sys
import argparse

from . import manipulator
from . import spherebuilder
from . import cuboidbuilder

from lxml import etree as ET
from distutils.version import StrictVersion


# Simple logger class to be superseded by the Py3 logger when PythonOCC
# compatible
class GoSmart2Logger:
    def __init__(self, runname):
        self.runname = runname

    def print_line(self, line='', prefix=''):
        print(prefix + line)

    def print_fatal(self, line):
        self.print_line(line)
        sys.exit(line)


# We use class members to give default values
# because there is exactly one instance and it
# is clear to read and adjust. Note however,
# that if, for some unknown reason, multiple instances
# of the class are required, special care should be
# taken
class NeedleLibrary:
    logfilename = "/tmp/go-smart-needle-library-%d" % os.getpid()
    outfile = "needle.stl"
    extentfile = "extent.stl"
    silent = False
    my_rank = None
    configfiles = []
    components = {}
    child_procs = None
    only = None
    scaling = None
    offset = (0., 0., 0.)
    extent_type = None

    header_width = None

    def __init__(self, runname='default'):
        self.logger = GoSmart2Logger(runname)

        self.needles = {}

        self.parse_args()
        self.parse_config_files()

    def print_header(self):
        header = [
            "=",
            "GO-SMART NEEDLE LIBRARY",
            "-",
            "",
            "For information, see http://gosmart-project.eu/",
            "=",
        ]

        self.header_width = len(max(*header, key=len)) + 2
        for idx, line in enumerate(header):
            pad = ' '
            if line in ("=", '-'):
                pad = line

            header[idx] = pad + line.ljust(self.header_width, pad)

        for line in header:
            self.logger.print_line('{' + line + '|', prefix='')

        self.logger.print_line()

    def launch(self):
        # Loop through the needles, outputting transformed STL surfaces for each
        for name, needle in self.needles.items():
            needle_manipulator = None
            needle_target = [self.target[i] + needle["offset"][i] for i in (0, 1, 2)]

            # TODO: tidy all this into the logger
            print(self.target)
            print(needle["offset"])
            print(needle_target)

            # If we have an ID, then the manipulator should be able to find it
            # in the library (TODO: this is a separate job; shouldn't be in the
            # manipulator). Otherwise, we should have a STEP file given to us to
            # define it.
            if needle["id"] != 'none' and needle["id"] is not None:
                self.logger.print_line("Using needle: %s (axis: %s; target: %s)" % (needle["id"], str(needle["axis"]), str(needle_target)))
                needle_manipulator = manipulator.Manipulator(self.logger, needle_id=needle["id"])
            elif needle["stepfile"] is not None:
                self.logger.print_line("Using needle: %s (axis: %s; target: %s)" % (needle["stepfile"], str(needle["axis"]), str(needle_target)))
                needle_manipulator = manipulator.Manipulator(self.logger, filename=needle["stepfile"])

            # TODO: should this error our if a needle cannot be output? Is there
            # a reason that it doesn't?
            if needle_manipulator is not None:
                scaling = self.scaling
                self.logger.print_line("Simulation Scaling: %lf" % scaling)
                if "scaling" in needle:
                    scaling *= float(needle["scaling"])
                    self.logger.print_line("Total Scaling: %lf" % scaling)
                needle_manipulator.scale(scaling)
                needle_manipulator.reorient(needle["axis"])
                needle_manipulator.translate(needle_target)
                needle_manipulator.write_stl("%s-%s" % (self.outfile, needle["file"]))

        # The domain extent, if specified as a primitive for STL output, rather
        # than being left for analytic definition in the mesher (i.e. a maximal radius)
        extent_target = [self.target[i] + self.offset[i] for i in (0, 1, 2)]
        if self.extent_type == 'sphere':
            self.logger.print_line("Extent is %s; target %s, radius %lf" % (self.extent_type, str(extent_target), self.radius))
            extent_builder = spherebuilder.SphereBuilder(self.logger, extent_target, self.radius)
            extent_builder.build()
            extent_builder.write_stl(self.extentfile)
        elif self.extent_type == 'cuboid':
            self.logger.print_line("Extent is %s; target %s, dims %lf x %lf x %lf" % (self.extent_type, str(extent_target), self.height, self.width, self.length))
            cuboid_builder = cuboidbuilder.CuboidBuilder(self.logger, extent_target, 1.0, height=self.height, width=self.width, length=self.length)
            cuboid_builder.build()
            cuboid_builder.write_stl(self.extentfile)
        elif self.extent_type is None:
            pass
        else:
            self.logger.print_fatal("Extent type not recognized")

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Management tool for Go-Smart ablation needle geometry library')
        parser.add_argument('--logfile', dest='logfilename', help='Name of the log file')
        parser.add_argument('--logfile-addpid', dest='addpid',
                            action='store_true', help='Whether the PID should be appended to the given logfile name')
        parser.add_argument('--silent', dest='silent', action='store_true', help='Prevent wrapper output')
        parser.add_argument('--debug', dest='debug', action='store_true', help='Additional, debug output (overridden by --silent)')
        parser.add_argument('--output', dest='outfile', help='Destination STL file for needle')
        parser.add_argument('--output-extent', dest='extentfile', help='Destination STL file for extent')
        parser.add_argument(dest='configfilenames', nargs=argparse.REMAINDER, help='Locations of configuration file (latter override former)')

        args = parser.parse_args()

        self.logger.silent = args.silent
        self.logger.debug = args.debug
        if args.logfilename is not None:
            self.logfilename = args.logfilename
        if args.addpid:
            self.logfilename += "-" + str(os.getpid())
        if args.outfile is not None:
            self.outfile = args.outfile
        if args.extentfile is not None:
            self.extentfile = args.extentfile

        if len(args.configfilenames) > 0:
            self.configfiles = args.configfilenames

    def parse_config_file(self, filename):
        configtree = ET.parse(filename)
        root = configtree.getroot()

        self.scaling = root.get("scaling")
        if self.scaling is not None:
            self.scaling = float(self.scaling)
        else:
            self.scaling = 1.0
        version = root.get("version")
        # FIXME: remove alternative - this has been deprecated long enough
        if version is not None and StrictVersion(version) >= StrictVersion("1.0.1"):
            if root.tag != "needlelibrary":
                self.logger.print_fatal("This settings file seems not to be for Go-Smart Needle Library (or is for the wrong version)")

            for section in root:
                if section.get("skip") == "true":
                    self.logger.print_line("* Skipping %s as indicated in settings file %s" % (section.tag, filename))
                    continue

                if section.tag == "needle":
                    needle_id = section.get('id')
                    stepfile = section.get('stepfile')
                    name = section.get('name')
                    scaling = section.get('scaling')
                    if (needle_id is not None or stepfile is not None) and name is not None:
                        needle = {}
                        needle["id"] = needle_id
                        needle["stepfile"] = stepfile
                        needle["name"] = name
                        needle["scaling"] = scaling

                        axis = section.get('axis')
                        needle["axis"] = list(map(float, axis.split(' ')))

                        offset = section.get('offset')
                        if offset is not None:
                            needle["offset"] = list(map(float, offset.split(' ')))
                        else:
                            needle["offset"] = (0.0, 0.0, 0.0)

                        file = section.get('file')
                        if file is not None:
                            needle["file"] = file

                        self.needles[name] = needle
                elif section.tag == 'target':
                    self.target = list(map(float, (section.get('x'), section.get('y'), section.get('z'))))
                elif section.tag == 'extent':
                    self.extent_type = section.get('shape')
                    if self.extent_type == 'sphere':
                        self.radius = float(section.get('radius'))
                    elif self.extent_type == 'cuboid':
                        self.height = float(section.get('height'))
                        self.width = float(section.get('width'))
                        self.length = float(section.get('length'))
                    if section.get('offset'):
                        self.offset = tuple(map(float, section.get('offset').split(',')))
                else:
                    self.logger.print_fatal("Unknown top-level section %s in %s" % (section.tag, filename))
        else:
            if root.tag != "needle":
                self.logger.print_fatal("This settings file seems not to be for Go-Smart Needle Library")

            needle_id = root.get('id')
            if needle_id is not None:
                self.needle_id = needle_id

            for section in root:
                if section.get("skip") == "true":
                    self.logger.print_line("* Skipping %s as indicated in settings file %s" % (section.tag, filename))
                    continue

                # Reorientation of x-z axis
                if section.tag == 'axis':
                    self.axis = list(map(float, (section.get('x'), section.get('y'), section.get('z'))))
                elif section.tag == 'target':
                    self.target = list(map(float, (section.get('x'), section.get('y'), section.get('z'))))
                elif section.tag == 'extent':
                    self.extent_type = section.get('shape')
                    if self.extent_type == 'sphere':
                        self.radius = float(section.get('radius'))
                    elif self.extent_type == 'cuboid':
                        self.height = float(section.get('height'))
                        self.width = float(section.get('width'))
                        self.length = float(section.get('length'))
                    if section.get('offset'):
                        self.offset = tuple(map(float, section.get('offset').split(',')))
                else:
                    self.logger.print_fatal("Unknown top-level section %s in %s" % (section.tag, filename))

    def parse_config_files(self):
        if len(self.configfiles) == 0:
            self.logger.print_fatal("No config files were supplied")

        for configfile in self.configfiles:
            self.parse_config_file(configfile)
