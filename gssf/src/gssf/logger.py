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
import re
import os
import errno

from .component import GoSmartComponent
from .globals import debug, slugify, colorama_imported
from .errors import exceptions

if colorama_imported:
    import colorama


# This is the class of the main application-level logging object and,
# unfortunately, the catch-all singleton for application-wide data
# TODO: switch to logging module
# TODO: reduce singletonness
class GoSmartLogger(GoSmartComponent):
    suffix = 'logger'
    version = None
    _global_working_directory = None

    def __init__(self, runname, silent=False, debug=debug, logfile=None, global_working_directory=None):
        super().__init__(self)

        # Name of this particular simulation used in various file prefices
        self.runname = runname

        # Verbosity
        self.silent = silent
        self.debug = debug

        # Remove colour commands from output
        self._colour_stripper = re.compile(r'\x1b[^m]*m')

        self._global_working_directory = global_working_directory

        # Zones are volumetric subdomains
        # Note that these _may_ get renumbered partway through!
        self.zones = {}
        self.zones_map = {}
        self.zones_excluded = {}

        # Surfaces are boundary subdomains
        self.surfaces = {}
        self.surfaces_map = {}

        self.files = {}

        # Needles each have their own constants dictionary
        self._constant_needle_mapping = {}
        self._constant_needle_mapping_types = {}

        # Track the surface and zone numbers to assign separate indices to each
        # (not necessarily final)
        self._current_i = {
            "surfaces": 0,
            "zones": 0
        }

        # Default values for the geometry, although these should always be
        # overridden
        self.geometry = {
            "centre": {'x': 0, 'y': 0, 'z': 0},
            "needleaxis": [],
            "simulationscaling": 1.,
        }

        # Only place loading a library set may make sense (elsewhere
        # deprecated), as this provides for universal constants and so forth
        # that will be the same in all simulations (e.g. pi, vac perm could go here)
        self._load_constant_set("default")

        # Create the logging directory
        absolute_path = os.path.join(self.logger.get_cwd(), self.suffix)
        try:
            os.makedirs(absolute_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                self.print_fatal("Could not create %s directory: %s" %
                                 (absolute_path, str(e)))

        # Open the primary logfile
        self.logfile = open(os.path.join(self.get_cwd(), logfile), "w") if logfile is not None else None

        # Make sure we have one region at least - a catch-all volume (ideally, this
        # should not be necessary)
        self.add_region("tissue", None, ("zone", "tissues", "background"), primary=True, zone=True)

    # Push out anything that hasn't gone
    def flush_logfile(self):
        if self.logfile is not None:
            self.logfile.flush()

    def find_regions_by_group(self, group):
        return [r for r in self.regions.values() if group in r["groups"]]

    # Create a dictionary mapping SIF template parameter names to SIF-rendered
    # lists of IDs
    def get_region_ids(self):
        regions = {}

        # Call surfaces "Boundaries" and zones "Bodies"
        for lregions, sifregion in ((self.surfaces, "Boundaries"), (self.zones, "Bodies")):
            region_groups = {}
            # Go through each surface/zone and add relevant SIF parameters
            for name, region in lregions.items():
                self.print_debug(("REGION %s: " % name) + str(region["groups"]))

                # Firstly, we have the simple REGION_X - 1-to-1 mapping of
                # surfaces/zones to IDs
                regions["REGION_%s" % slugify(name)] = region["id"]

                # Then we have groups
                for group in region["groups"]:
                    # For each group, we create its entries with a generic
                    # REGION_ prefix and with a BOUNDARIES_ or BODIES_ prefix,
                    # so that the user does not /need/ to know whether the
                    # region is a boundary or body, but can specify where
                    # required (e.g. needles may have distinct boundary and body
                    # region IDs of the same suffix - _NEEDLE_N)
                    for grouptype in ("REGIONS", sifregion.upper()):
                        group = "%s_%s" % (grouptype, slugify(group))
                        if group not in region_groups:
                            region_groups[group] = []
                        if region["id"] >= 0:
                            region_groups[group].append(region["id"])

            # Space-separate the region IDs in the groups and prefix the
            # template string with the actual declaration line, so this can be
            # put into the SIF wholesale and, if the group is not present, the
            # omission does not cause an Elmer error (desirable for optional
            # groups)
            regions.update(dict((g, "Target %s(%d) = Integer %s" % (sifregion, len(set(l)), " ".join(str(i) for i in set(l)))) for g, l in region_groups.items()))

        return regions

    # Used for other components to find the working directory (singleton
    # behaviour)
    def get_cwd(self):
        if self._global_working_directory is not None:
            return os.path.abspath(self._global_working_directory)

        return os.path.abspath(".")

    # Convenience routine to take a GSSF subdirectory name and do any necessary
    # prefixing to make sure it lies in the GSSF working directory
    def make_cwd(self, cwd):
        if self._global_working_directory is not None:
            return os.path.join(self._global_working_directory, cwd)

        return cwd

    # Store an actual filename for a file that can be retrieved later (e.g.
    # region->STL surface) (singleton behaviour)
    def add_file(self, nature, name, filename):
        if nature not in self.files:
            self.files[nature] = {}
        if filename[0] != '/':
            filename = os.path.realpath(os.path.join(self.logger.get_cwd(), filename))
        self.files[nature][name] = filename

    # Retrieve an actual filename for a file (see self.add_file)
    def get_file(self, nature, name):
        if nature in self.files and name in self.files[nature]:
            return self.files[nature][name]
        return None

    # Record a region and all the gory details (singleton behaviour)
    # name: name of region (string)
    # filename: any STL/etc. definition file (string)
    # groups: region groups that this should be attached to (list of strings)
    # primary: this should end up as Region 1, swapping if necessary (bool)
    # unnumbered: this is just recorded but does not appear in the ID list
    #             (bool)
    # zone: this is volumetric (True), boundary (False) or both ("both")
    # i: ID to use; "max" uses the first free index (int/"max")
    def add_region(self, name, filename, groups, primary=False, unnumbered=False, zone=False, i="max"):
        # If this region should appear as both a volumetric subdomain and an
        # embedded boundary, re-run this function once for each. Ensure that,
        # for the moment, their IDs match (this could be changed by the
        # preconversion renumbering)
        if zone == "both":
            num = self.add_region(name, filename, groups, primary, unnumbered, True, i="max")
            self.add_region(name, filename, groups, primary, unnumbered, False, i=num)
            return num

        # If we have no specific ID to use, we go for the first clash-free
        # example (checking both zones and surfaces). Any gaps will be rectified
        # on renumbering.
        if i == "max":
            i = max(self._current_i["zones"], self._current_i["surfaces"]) + 1

        # Pick out zones or surfaces structures
        if zone:
            regions = self.zones
            regions_map = self.zones_map
            if i is None:
                i = self._current_i["zones"] + 1
            self._current_i["zones"] = i
        else:
            regions = self.surfaces
            regions_map = self.surfaces_map
            if i is None:
                i = self._current_i["surfaces"] + 1
            self._current_i["surfaces"] = i

        if primary and unnumbered:
            self.debug_fatal("Primary region must be numbered")

        # If this is not an official, numbered region, we do still have to keep
        # track of it, but we can signify the fact with a negative. This allows
        # components to use a unique identifier, but still have a transparent
        # numbered-zone identifier list (positives) if they only want marked
        # regions
        if unnumbered:
            i = -i

        # Swap the primary with this region, if it is the new primary
        if primary and (1 in regions_map):
            regions[regions_map[1]]["id"] = i
            regions_map[i] = regions_map[1]
            i = 1

        # Add the region to the appropriate zone/surface structure
        regions[name] = {"id": i, "filename": filename, "groups": ["all", name] + list(groups)}
        self.print_debug("%s : %d" % (name, i))
        regions_map[i] = name

        return i

    # Get details for the given region
    def get_region(self, name):
        if name in self.zones:
            return self.zones[name]
        elif name in self.surfaces:
            return self.surfaces[name]
        else:
            self.print_error("Can't find region %s" % name)

    # Add a constant if it is missing
    def ensure_constant(self, name, value, warn=False, group="CONSTANT", typ=None):
        self.add_or_update_constant(name, value, warn, group, override=False, typ=typ)

    # Make sure there is a (possibly blank) needle parameter dictionary for this needle
    def ensure_needle(self, needle):
        if needle not in self._constant_needle_mapping:
            self._constant_needle_mapping[needle] = {}
            self._constant_needle_mapping_types[needle] = {}

    # Add a constant to a given needle parameter dictionary
    def add_or_update_needle_constant(self, needle, name, value, typ=None):
        self.ensure_needle(needle)
        name = slugify(name)
        self._constant_needle_mapping[needle][name] = value
        self._constant_needle_mapping_types[needle][name] = {}

    # Add a constant to the global parameter dictionary
    def add_or_update_constant(self, name, value, warn=False, group="CONSTANT", override=True, typ=None):
        # TODO:PTW:THIS SHOULD BE REPLACED WITH SLUGIFY!!! However, matching
        # behaviour must first be confirmed
        if slugify(group) == "PARAMETER":
            mangled_name = slugify(name)
        else:
            mangled_name = "%s_%s" % (slugify(group), slugify(name))

        # Add to our structure
        if override or mangled_name not in self._constant_mapping:
            self._constant_mapping[mangled_name] = value
            self._constant_mapping_types[mangled_name] = typ

        # Certain constants should generate a user-visible warning if they are
        # not used in the SIF template
        if warn:
            self._constant_mapping_warn[mangled_name] = "constant : %s" % name

    # Retrieve a constant - note that the name does /not/ need to include the
    # group, if it is provided, but it should also work with the full slugified
    # name.
    def get_constant(self, name, group="CONSTANT"):
        mangled_name = "%s_%s" % (slugify(group), slugify(name))

        if name in self._constant_mapping:
            return self._constant_mapping[name]
        elif mangled_name in self._constant_mapping:
            return self._constant_mapping[mangled_name]
        return None

    # Get parameter dictionaries for the needles
    def get_needle_constants(self):
        constants = self._constant_needle_mapping.copy()
        return constants

    # Get a parameter for a specific needle
    def get_needle_constant(self, needle, name):
        if needle not in self._constant_needle_mapping:
            self.print_fatal(
                "Needle {needle} missing - asked for parameter {name} (NB: needles start from 0)".format(needle=needle, name=name),
                "E_MODEL"
            )
        if name in self._constant_needle_mapping[needle]:
            return self._constant_needle_mapping[needle][name]

        return None

    # Get a copy of the whole parameter dictionary
    def get_constants(self):
        constants = self._constant_mapping.copy()
        return constants

    # Copy of constants that must appear in the SIF template
    def get_mapping_warn(self):
        warn = self._constant_mapping_warn.copy()
        return warn

    def print_debug(self, line='', prefix='| '):
        if self.debug:
            self.print_line(line, prefix, color="CYAN")

    # Generic log printing
    # prefix: start of line (string)
    # color: colorama colour (string)
    # color_text: monochrome/colour (bool)
    # color_bright: normal or bold/bright (bool)
    def print_line(self, line='', prefix='| ', color="GREEN", color_text=True, color_bright=False):
        line_plain = self._colour_stripper.sub('', str(line))

        if not self.silent:
            if colorama_imported:
                color = getattr(colorama.Fore, color)
                reset = colorama.Fore.RESET

                if color_bright:
                    color += colorama.Style.BRIGHT
                    reset = colorama.Style.RESET_ALL + reset

                if color_text:
                    print(color + prefix + str(line) + reset)
                else:
                    print(color + prefix + reset + str(line))
            else:
                print(prefix + line_plain)

        self.logfile_print(prefix + line_plain)

    # Log something serious, but not enough to exit
    def print_error(self, error, color="RED"):
        if colorama_imported:
            color = getattr(colorama.Fore, color)
            print(colorama.Fore.GREEN + error + colorama.Fore.RESET)
        else:
            print(error)

        self.logfile_print("***ERROR*** : %s" % error)

    # Workhorse ensuring all logfile writing goes through a single, overloadable
    # point
    def logfile_print(self, line):
        if self.logfile is not None:
            self.logfile.write(str(line).strip() + "\n")

    # Something serious enough to exit, raise a GSSF exception (see .errors)
    def print_fatal(self, error, code="E_UNKNOWN"):
        self.print_error(error)

        raise exceptions[code](error)
