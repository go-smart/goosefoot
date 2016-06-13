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
from distutils.version import StrictVersion
from lxml import etree as ET
import os.path

from .component import GoSmartComponent
from .globals import defaults, slugify


# This wraps the Python2 go-smart-needle-library command
class GoSmartNeedleLibraryInterface(GoSmartComponent):
    suffix = 'needlelibrary'
    use_zones = False
    use_extent = False

    def __init__(self, logger):
        super().__init__(logger)

        # Almost certainly `go-smart-needle-library`
        self.command = defaults["needle library command"]
        self.needles = {}

    def parse_config(self, config_node):
        super().parse_config(config_node)

        # DEPRECATED
        if self.logger.version < StrictVersion("1.0.1"):
            for section in config_node:
                if section.tag == "needle":
                    self.needle_id = section.get('id')
                    target = section.find('target')
                    centre = self.logger.geometry["centre"]
                    for c in ('x', 'y', 'z'):
                        if target is not None:
                            centre[c] += float(target.get(c))
                            target.set(c, str(centre[c]))
                        self.add_or_update_constant(c, centre[c], group="needle")
                    self.config = section
                else:
                    self.logger.print_fatal("Unknown element %s in needle configuration" % section.tag)
        else:
            self.config = ET.Element("needlelibrary")

            # Whether needles should be treated as zones
            if config_node.get("zones") == "true":
                self.use_zones = True

            # Make sure the needlelibrary command receives the overall scaling
            if 'simulationscaling' in self.logger.geometry:
                scaling = self.logger.geometry["simulationscaling"]
                self.config.set("scaling", str(scaling))

            # Transfer the version of GSSF-XML to needlelibrary's XML (they
            # should be in lock-step)
            self.config.set("version", str(self.logger.version))

            target = None
            for section in config_node:
                # Add in a needle
                if section.tag == "needle":
                    needle = ET.SubElement(self.config, "needle")

                    # Which needle? Does it have a library ID?
                    needle_id = section.get('id')
                    # ... or a CAD definition?
                    stepfile = self.logger.get_file('cad', needle_id)

                    # This is the preferred way to identify a library needle,
                    # although we would really rather move the whole needle
                    # definition to GSSA
                    if needle_id.startswith('stock:'):
                        needle.set('id', needle_id[len('stock:'):])
                    elif stepfile is not None:
                        needle.set('stepfile', stepfile)
                    else:
                        needle.set('id', needle_id)

                    if section.get('scaling'):
                        needle.set('scaling', str(section.get('scaling')))

                    # This allows a consistent name to be used for identifying
                    # this needle throughout the simulation
                    needle_name = section.get('name')

                    # If it doesn't have one, we give it a unique integer as a
                    # name
                    if needle_name is None:
                        needle_name = str(len(self.needles))

                    # And update if necessary
                    needle.set("name", needle_name)

                    # If the needle has no axis given, we take the global one
                    axis = section.get("axis")
                    if axis is not None:
                        needle.set("axis", axis)
                    else:
                        if len(self.logger.geometry["needleaxis"]) == 0:
                            self.logger.print_fatal("If no per-needle axis, must have a needleaxis in geometry to define a needle")
                        axis = " ".join([str(self.logger.geometry["needleaxis"][0][c]) for c in ('x', 'y', 'z')])
                        needle.set("axis", axis)

                    # If the needle has no offset, it will be set with tip at
                    # the global centre
                    offset = section.get("offset")
                    if offset is not None:
                        needle.set("offset", offset)

                    # Prepare the data for sending to needle library
                    sname = slugify(needle_name)
                    needle.set("file", sname)
                    self.needles[needle_name] = {
                        "id": needle_id,
                        "name": needle_name,
                        "file": sname,
                        "axis": axis,
                        "offset": offset
                    }
                elif section.tag == "target":
                    # Indicate we have an offset from the simulation centre for
                    # the entire needle-set
                    target = section.find('target')
                elif section.tag == "extent":
                    # We should produce an STL extent
                    if self.use_extent:
                        self.use_extent = True
                    self.config.append(section)
                else:
                    self.logger.print_fatal("Unknown element %s in needle configuration" % section.tag)

            # Calculate the centre of the needle-set
            centre = self.logger.geometry["centre"]
            target_node = ET.SubElement(self.config, "target")
            for c in ('x', 'y', 'z'):
                if target is not None:
                    centre[c] += float(target.get(c))
                self.add_or_update_constant(c, centre[c], group="needle")
                target_node.set(c, str(centre[c]))

        target_stl = "%s" % self.logger.runname
        # Add each needle to the Needle Library XML
        for name, n in self.needles.items():
            sname = n['file']
            target_path = os.path.join(self.cwd, self.suffix, target_stl)
            self.logger.add_region('needle-%s' % n['file'], "%s-%s.stl" % (target_path, sname), ("needles", "surface"), zone=("both" if self.use_zones else False))

    def launch(self):
        super().launch()

        # Generate the Needle Library XML
        target_xml = "%s.xml" % self.logger.runname
        with open(os.path.join(self.logger.get_cwd(), self.suffix, target_xml), 'wb') as f:
            f.write(ET.tostring(self.config))

            target_stl = "%s" % self.logger.runname

        args = [
            "--output", target_stl,
            target_xml
        ]

        # Indicate the output name for the extent if required
        if self.use_extent:
            extent_stl = "%s-extent.stl" % self.logger.runname
            args["--output-extent"] = extent_stl

        self.cwd = self.suffix

        self._launch_subprocess(self.command, args)

        # If we have an extent, add it as a region for the rest of the
        # simulation components to see
        if self.use_extent:
            extent_path = os.path.join(self.cwd, extent_stl)
            if 'extent' not in self.logger.surfaces:
                self.logger.add_region('extent', extent_path, ("boundary", "surface"), primary=True)
        else:
            extent_path = None

        target_paths = None if len(self.needles) == 0 else {}

        print(self.needles)
        # Add an any inactive regions to the global list
        for name, n in self.needles.items():
            target_path = os.path.join(self.cwd, target_stl)
            sname = n['file']
            target_paths[sname] = "%s-%s.stl" % (target_path, sname)
            inactive_path = "%s-%s.inactive.stl" % (target_path, sname)
            if os.path.exists(inactive_path):
                target_paths[sname + "-inactive"] = inactive_path
                self.logger.add_region('needle-%s-inactive' % n['file'], "%s-%s.inactive.stl" % (target_path, sname), ("needles-inactive", "surface"), zone=("both" if self.use_zones else False))
        print(self.logger.surfaces)

        return target_paths, extent_path
