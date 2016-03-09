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
# pylint: disable=line-too-long
#
import os
import re
import errno
import shutil
import time
import json
from . import config
import socket
from distutils.version import StrictVersion
from lxml import etree as ET

from .lesion import GoSmartLesion
from .validation import GoSmartValidation
from .elmer import GoSmartElmer
from .elmergrid import GoSmartElmerGrid
from .logger_vigilant import GoSmartLoggerVigilant
from .mesh_optimizer import GoSmartMeshOptimizer
from .mesher import GoSmartMesher
from .mesher_2d_gmsh import GoSmartMesher2DGMSH
from .mesher_3d_cgal import GoSmartMesher3DCGAL
from .needlelibrary_interface import GoSmartNeedleLibraryInterface
from .preprocessor import GoSmartPreprocessorInterface
from .globals import colorama_imported, slugify
from .errors import GoSmartModelError

if colorama_imported:
    import colorama


# We use class members to give default values
# because there is exactly one instance and it
# is clear to read and adjust. Note however,
# that if, for some unknown reason, multiple instances
# of the class are required, special care should be
# taken
class GoSmartSimulationFramework:
    outfilename = "logger/go-smart-elmer-%d" % os.getpid()

    silent = False
    my_rank = None
    configfiles = []
    components = {}
    child_procs = None
    only = None
    elmer_binary = None

    _update_status_socket = None
    _update_status_callback = None

    header_width = None

    def __init__(self, runname='default', args=[], global_working_directory=None, observant=None, update_status=None):
        # This allows us to run GSSF from any location and use a passed working directory
        if global_working_directory is None:
            global_working_directory = os.getcwd()

        # We use observant (now known as vigilant) to monitor GSSF processes, if
        # possible. If not, this is a transparent wrapper around GoSmartLogger
        self.logger = GoSmartLoggerVigilant(
            runname=runname,
            logfile="%s.log" % self.outfilename,
            global_working_directory=global_working_directory,
            observant=observant)

        # Check through the command line arguments for any relevant settings
        self.parse_args(args)

        # Go through the GSSF-XML input
        self.parse_config_files()

        # If we have been given a status socket, then connect and store the
        # details for logging progress later
        if update_status is not None:
            self._update_status_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._update_status_socket.connect(update_status)

        # Make sure each component knows the process-specific logging prefix, so
        # they all match
        for component in self.components.values():
            if isinstance(component, list):
                for cpt in component:
                    cpt.set_outfile_prefix(self.outfilename)
            else:
                component.set_outfile_prefix(self.outfilename)

    # Write a percentage progress line to the status socket, if we have one
    def update_status(self, percentage, message):
        if self._update_status_socket is not None:
            bytestring = '%lf|%s\n' % (percentage, '\\n'.join(message.splitlines()))
            self._update_status_socket.sendall(bytestring.encode('utf-8'))

    # If a component is found in the top level of the GSSF-XML, we store it and
    # name it accordingly. We also add it as a member.
    def add_component(self, name, component):
        if self.only is not None and self.only != name:
            return component

        self.components[name] = component
        component.suffix = name
        setattr(self, name, component)
        return component

    # Output key information on each run
    def print_header(self):
        header = [
            "=",
            "GO-SMART SIMULATION ENVIRONMENT",
            "-",
            "",
            "https://github.com/numa-engineering/gosmart-gssa",
            ""
            "The Go-Smart project is co-funded by: European Commission under grant agreement no. 600641."
            "For further information, see http://gosmart-project.eu/",
            "=",
        ]

        self.header_width = len(max(*header, key=len)) + 2
        for idx, line in enumerate(header):
            pad = ' '
            if line in ("=", '-'):
                pad = line

            header[idx] = pad + line.ljust(self.header_width, pad)

        for line in header:
            self.logger.print_line('|' + line + '|', prefix='', color="MAGENTA", color_bright=True)

        self.logger.print_line()

    # Start off the GSSF workflow
    def launch(self, default_procs=1):
        if self.child_procs is None:
            self.child_procs = default_procs

        final_output = {}

        self.logger.init_time = time.time()
        self.logger.print_debug("Seconds since Unix epoch: %d " % self.logger.init_time)

        # Provide version strings to aid reproducibility. These repos should
        # be on Github, so it is possible to go back and check results.
        self.logger.print_line("Using GSSF version: %s" % config.git_revision)
        self.logger.print_line("Using Elmer (NUMA-modified) version: %s" % config.elmer_git_revision)

        # Start counting percentage progress
        overall_percentage = 0.0
        percentage_per_component = 100 / len(self.components)

        # By default, we use a analytically-defined extent
        extent_file = None
        needle_files = {}

        # Run the needle library if it is not supposed to be skipped
        if "needlelibrary" in self.components:
            self.update_status(overall_percentage, "Needlelibrary starting")
            overall_percentage = overall_percentage + percentage_per_component
            needle_files, extent_file = self.needlelibrary.launch()
            self.update_status(overall_percentage, "Needlelibrary complete")
        else:
            self.update_status(overall_percentage, "Skipped needlelibrary")

        msh_files = {}
        default_msh_file = GoSmartMesher.get_default_msh_outfile(os.path.join('mesher', self.logger.runname), "mesher")

        # Start the mesher. If we skip it, make a cursory attempt to find a
        # pre-existing mesh
        if "mesher" in self.components:
            self.update_status(overall_percentage, "Mesher starting")
            msh_files.update(self.mesher.launch(needle_files, extent_file,
                             self.preprocessor if "preprocessor" in self.components else None))
            overall_percentage = overall_percentage + percentage_per_component
            self.update_status(overall_percentage, "Mesher complete")
        elif os.path.exists(os.path.join(self.logger.get_cwd(), default_msh_file["-mesher"])):
            msh_files.update(default_msh_file)
            self.update_status(overall_percentage, "Skipped mesher (and copied existing)")
        else:
            self.update_status(overall_percentage, "Skipped mesher")

        # If we have an inner mesh, which will have been added when reading the
        # XML, then we run that too
        if hasattr(self, "mesher_inner"):
            for mesher_inner in self.mesher_inner:
                if mesher_inner.skip:
                    msh_files[mesher_inner.suffix] = "%s/%s.msh" % (mesher_inner.suffix, self.logger.runname)
                    self.update_status(overall_percentage, "Skipped mesher-inner")
                else:
                    self.update_status(overall_percentage, "Mesher-inner starting")
                    overall_percentage = overall_percentage + percentage_per_component
                    msh_files.update(mesher_inner.launch(needle_files, None))
                    self.update_status(overall_percentage, "Mesher-inner complete")

        # The optimizer comes next, cleaning any meshes produced above
        if hasattr(self, "optimizer"):
            self.update_status(overall_percentage, "Optimizer starting")
            overall_percentage = overall_percentage + percentage_per_component
            for k, v in msh_files.items():
                msh_files[k] = self.optimizer.launch(v, appendix=k)
            self.update_status(overall_percentage, "Optimizer complete")
        else:
            for k, v in msh_files.items():
                optimized_msh_file = "optimizer/%s%s-optimized.msh" % (self.logger.runname, k)
                if os.path.exists(os.path.join(self.logger.get_cwd(), optimized_msh_file)):
                    msh_files[k] = optimized_msh_file
            self.update_status(overall_percentage, "Optimizer complete")

        # Here, we renumber bodies to make sure that mesh indexing is
        # consecutive based on the presence of cells in the mesh - this is
        # required by Elmer. Turns out be kind of tricky.
        msh_files = self.renumber_bodies(msh_files)
        eg_trees = {}

        # ElmerGrid then converts to Elmer's mesh format
        if "elmergrid" in self.components:
            self.update_status(overall_percentage, "ElmerGrid starting")
            overall_percentage = overall_percentage + percentage_per_component
            for k, v in msh_files.items():
                eg_trees[k] = self.elmergrid.launch(v, self.child_procs, appendix=k)
            self.update_status(overall_percentage, "ElmerGrid complete")
        else:
            for k, v in msh_files.items():
                eg_trees[k] = "elmergrid/%s%s" % (self.logger.runname, k)

        # We run ElmerSolver
        if "elmer" in self.components:
            self.update_status(overall_percentage, "Elmer starting")
            self.elmer.set_update_status(lambda p, m: self.update_status(p / percentage_per_component + overall_percentage, m))
            overall_percentage = overall_percentage + percentage_per_component
            self.launch_elmer(mesh_locations=eg_trees)
            self.update_status(overall_percentage, "Elmer complete")

        # ... extract the lesion ...
        if "lesion" in self.components:
            self.update_status(overall_percentage, "Lesion starting")
            overall_percentage = overall_percentage + percentage_per_component
            lesion_surface, lesion_volume = self.lesion.launch(is_parallel=(self.child_procs is not None and self.child_procs > 1))
            self.update_status(overall_percentage, "Lesion complete")
            final_output["lesion_surface.vtp"] = lesion_surface
            final_output["lesion_volume.vtu"] = lesion_volume

        # ... and validate
        if "validation" in self.components:
            self.update_status(overall_percentage, "Validation starting")
            overall_percentage = overall_percentage + percentage_per_component
            validation_surface, validation_analysis = self.validation.launch(is_parallel=(self.child_procs is not None and self.child_procs > 1))
            if validation_surface is not None and validation_analysis is not None:
                self.update_status(overall_percentage, "Validation complete")
                final_output["validation_surface.vtp"] = validation_surface
                final_output["validation_analysis.xml"] = validation_analysis
                shutil.copyfile(validation_analysis, os.path.join(self.logger.get_cwd(), "validation.xml"))
            else:
                self.update_status(overall_percentage, "Could not perform validation (is AaltoTCV binary definitely present?)")

        # If we have output to amalgamate into a single handy location, copy it
        # there

        if len(final_output) > 0:
            os.makedirs(self.logger.make_cwd("output"), exist_ok=True)

        for k, f in final_output.items():
            shutil.copy(os.path.join(self.logger.get_cwd(), f), os.path.join(self.logger.get_cwd(), "output", "%s-%s" % (self.logger.runname, k)))
            shutil.copy(os.path.join(self.logger.get_cwd(), f), os.path.join(self.logger.get_cwd(), "output", k))

    # For Elmer usage, we need contiguous numbering of subdomains that actually
    # appear in the SIF file. This is not necessarily all of the numbered
    # domains that we have already been passed, so we must renumber the MSH
    # files, and our GSSF regions, accordingly.
    def renumber_bodies(self, msh_files):
        present_ids = {}

        msh_content = {}

        # Loop through the MSH files to work out which are 2D and which are 3D
        for k, v in msh_files.items():
            with open(os.path.join(self.logger.get_cwd(), v), 'r') as f:
                content = f.read()
                # If this MSH file contains volume elements, add it as the kth entry to msh_content,
                # marked as a 3D mesh
                if re.search(r"^\d+ 4 2 ", content, re.MULTILINE) is not None:
                    msh_content[k] = (True, content)
                # Otherwise, if this MSH file has a surface element, add it as the kth entry to msh_content,
                # marked as a 2D mesh
                elif re.search(r"^\d+ 2 2 ", content, re.MULTILINE) is not None:
                    msh_content[k] = (False, content)

        # At this point, msh_content is a list of meshes numbered from 1 to k

        # Note that this will break with more than ~26 zones
        #
        # Check which zones are and are not present and make sure they are
        # numbered consistently throughout the MSH files
        for zone, a in self.logger.zones.items():
            self.logger.print_debug(zone)
            for k, d in msh_content.items():
                is_3d_mesh, content = d
                elt_type = "4" if is_3d_mesh else "2"

                # If we have already come across this zone in a MSH make sure
                # that we use the same tag
                if zone not in present_ids:
                    new_id = len(present_ids) + 1
                else:
                    new_id = present_ids[zone]

                # Swap all lines that start like this (e.g. 143 4 2 6 6)
                from_sub = r"(?m)^(\d+) {1} 2 {0} \d+ ".format(a['id'], elt_type)
                # ...to be like this (e.g. 143 4 2 A A)
                to_sub = r"\1 {1} 2 {0} {0} ".format(chr(65 + new_id), elt_type)
                new_content, num_changes = re.subn(from_sub, to_sub, content)

                # If we changed anything, then this zone is officially present, so we
                # record the tag we used and update the MSH content array
                if num_changes > 0:
                    self.logger.print_line("%s: Found %d elements for %s" % (msh_files[k], num_changes, zone))
                    present_ids[zone] = new_id
                    msh_content[k] = (is_3d_mesh, new_content)

        self.logger.print_line(present_ids)
        # Go through all the present zones in all the MSH files
        for zone, i in present_ids.items():
            for k, d in msh_content.items():
                is_3d_mesh, content = d
                elt_type = "4" if is_3d_mesh else "2"
                # Turn the letters back into numbers
                from_sub = r"(?m)^(\d+) {1} 2 {0} {0} ".format(chr(65 + i), elt_type)
                to_sub = r"\1 {1} 2 {0} {0} ".format(i, elt_type)
                msh_content[k] = (is_3d_mesh, re.sub(from_sub, to_sub, content))
            # Store the updated zone tag with the zone in our Python zones array
            self.logger.zones[zone]['id'] = i

        # Strip out any zones from our records that appear in no MSH files. From now
        # on it is assumed that we have consecutively numbered zones, all appearing as
        # elements in some MSH, ready to be dropped into a SIF
        exclusion = [z for z in self.logger.zones if z not in present_ids]
        self.logger.print_debug(self.logger.zones_map)
        self.logger.print_debug(exclusion)
        for zone in exclusion:
            self.logger.zones_map.pop(self.logger.zones[zone]['id'])
            self.logger.zones_excluded[zone] = self.logger.zones.pop(zone)

        # Write out the MSH files to the filesystem
        if msh_content:
            try:
                os.makedirs(os.path.join(self.logger.get_cwd(), "meshes-reordered"))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    self.print_fatal("Could not create %s directory: %s" %
                                     (self.suffix, str(e)))

            for k, d in msh_content.items():
                output_mesh = os.path.join(self.logger.get_cwd(), "meshes-reordered", "%s%s.msh" % (self.logger.runname, k))
                with open(output_mesh, 'w') as f:
                    f.write(d[1])
                msh_files[k] = output_mesh

        return msh_files

    # This gives additional flexibility in choosing the number of processes for
    # running Elmer
    def launch_elmer(self, default_procs=1, **kwargs):
        if self.child_procs is None:
            self.child_procs = default_procs

        self.elmer.launch(self.child_procs, **kwargs)

    # Update internal asettings based on the command line arguments
    def parse_args(self, args):
        global colorama_imported

        # Suppress output
        self.logger.silent = args.silent

        # Debug output
        self.logger.debug = args.debug

        # Clean the working directory tree before overwriting
        self.logger.leavetree = args.leavetree

        # Location of logs
        if args.outfilename is not None:
            self.outfilename = args.outfilename

        # Add PID of main process to logs
        if args.addpid:
            self.outfilename += "-" + str(os.getpid())

        # Specific binary for ElmerSolver
        if args.elmer_binary is not None:
            self.elmer_binary = args.elmer_binary

        # Launch Elmer over N processors (with MPI)
        if args.nprocs is not None:
            self.child_procs = int(args.nprocs)

        # Only run one component (used when bootstrapping for multiple Elmer
        # processes)
        if args.only is not None:
            self.only = args.only

        # Output to terminal in colour
        if not args.baw and colorama_imported:
            colorama.init()
        else:
            # This overrides the first try-catch import test
            colorama_imported = False

        # Schedule all listed config files to be processed
        if len(args.configfilenames) > 0:
            self.configfiles = args.configfilenames

    # Process a GSSF-XML file
    def parse_config_file(self, filename):
        filename = os.path.join(self.logger.get_cwd(), filename)

        configtree = ET.parse(filename)
        root = configtree.getroot()

        # Make sure we have the right type of file
        if root.tag != "gosmart" and root.tag != "gssf":
            if root.tag == "simulationDefinition":
                self.logger.print_fatal("This settings file seems to be GSSA-XML, not GSSF-XML")
            else:
                self.logger.print_fatal("This settings file seems not to be for Go-Smart")

        if root.get('debug') == "true":
            self.logger.debug = True

        # This is the GSSF-XML version
        if root.get('version') is not None:
            self.logger.version = StrictVersion(root.get('version'))
        else:
            self.logger.version = StrictVersion("0.1.0")

        runname = root.get('name')
        if runname is not None:
            self.logger.runname = runname

        # The logger will get constants from this
        # FIXME: then why do we check for a constants section later?
        self.logger.parse_config(root)

        only_needle = None
        for section in root:
            skip = (section.get("skip") == "true")

            # Needle Library component
            if section.tag == 'needlelibrary' and not skip:
                needlelibrary = self.add_component('needlelibrary', GoSmartNeedleLibraryInterface(self.logger))
                needlelibrary.parse_config(section)
                # RMV Tidy up.
                for needle in section:
                    if needle.tag != 'needle':
                        continue
                    if only_needle is None:
                        only_needle = needle
                    else:
                        only_needle = None
                        break

                # If there is only one needle, and it has an offset, we store
                # its location as NEEDLE_X, etc. in the global space
                # This should be DEPRECATED
                if only_needle is not None and only_needle.get("offset"):
                    for c, o in zip(('x', 'y', 'z'), only_needle.get("offset").split(" ")):
                        self.logger.add_or_update_constant(c, self.logger.get_constant(c, group="needle") + float(o), group="needle", typ="float")

            # This is the official way of adding needles
            elif section.tag == 'needles':
                for needle in section:
                    if needle.tag != 'needle':
                        continue
                    if needle.get('name') is None:
                        raise GoSmartModelError("Missing needle name")

                    needle_name = needle.get('name')

                    for subsection in needle:
                        if subsection.tag == 'parameters':
                            if len(needle) == 1:
                                for parameter in needle[0]:
                                    self.logger.add_or_update_needle_constant(needle_name, parameter.get('name'), parameter.get('value'), parameter.get('type'))
                        else:
                            raise GoSmartModelError("There should be at most one node (parameters) inside needle section")

            # This is DEPRECATED
            elif section.tag == 'preprocessor':
                preprocessor = self.add_component('preprocessor', GoSmartPreprocessorInterface(self.logger))
                preprocessor.parse_config(section)
            # Core geometry facts
            elif section.tag == 'geometry':
                for setting in section:
                    # The focal point for the simulation (from where all offsets
                    # should be measured)
                    if setting.tag == 'centre':
                        for c in ('x', 'y', 'z'):
                            self.logger.geometry["centre"][c] = float(setting.get(c))
                            self.logger.add_or_update_constant(c, float(setting.get(c)), group="needle", typ="float")
                    # The dominant axis. This is not necessarily the axis of
                    # the/a needle, but it provides a default axis where one is
                    # needed
                    elif setting.tag == 'needleaxis':
                        self.logger.geometry["needleaxis"].append({})
                        for c in ('x', 'y', 'z'):
                            self.logger.geometry["needleaxis"][0][c] = float(setting.get(c))
                            self.logger.add_or_update_constant("axis " + c, float(setting.get(c)), group="needle", typ="float")
                    # Scaling difference between input meshes and simulation.
                    # In many cases, input STL will be in mm, whereas simulation
                    # is in m, to match SI constants
                    elif setting.tag == 'simulationscaling':
                        self.logger.geometry["simulationscaling"] = float(setting.get("ratio"))
                    else:
                        raise GoSmartModelError("Not understood geometry tag")
            # Geometrical regions within the simulation
            elif section.tag == 'regions' or section.tag == 'definitions':
                for region in section:
                    # 'region' is DEPRECATED (and equivalent to 'surface')
                    if region.tag in ('region', 'surface', 'zone', 'both'):
                        # Groups: these allow us to forget about individual
                        # regions in the SIF template, and describe possibly
                        # multiple subdomains as a collective
                        # Format: "group1; group2; ..."
                        if region.get("groups"):
                            groups = [s.strip() for s in region.get("groups").split(";")]
                        else:
                            groups = []

                        # Add a region - a zone (volumetric) or a surface
                        # (boundary) or both (embedded boundary of volumetric
                        # subdomain)
                        groups.append(region.tag)
                        if region.tag == "zone":
                            self.logger.add_region(region.get("name"), region.get("input"), groups, zone=True)
                        if region.tag == "both":
                            self.logger.add_region(region.get("name"), region.get("input"), groups, zone="both")
                        elif region.tag == "region" or region.tag == "surface":
                            self.logger.add_region(region.get("name"), region.get("input"), groups, zone=False)
                    # TODO: work out if this is still necessary
                    elif region.tag in ('cad',):
                        self.logger.add_file(region.tag, region.get("name"), region.get("input"))
                    else:
                        raise GoSmartModelError("Not understood region tag")
            # Meshing configuration
            elif section.tag == 'mesher':
                # This allows for meshes of embedded, e.g. axisymmetric,
                # problems
                inner = section.find("inner")
                self.has_inner = (inner is not None)

                type = section.get('type')

                # FIXME: skipping the entire meshing section does not pick up
                # extant 2D meshes. As a workaround, we allow skip="outer" to
                # re-use only 3D and regenerate 2D.
                skip_outer = (section.get("skip") == "outer")

                if type == "CGAL":
                    mesher = GoSmartMesher3DCGAL(self.logger)
                elif type == "axisymmetric":
                    mesher = GoSmartMesher2DGMSH(self.logger)
                else:
                    self.logger.print_fatal("Unknown mesher type %s in %s" % (type, filename))

                if not skip_outer and not skip:
                    self.add_component('mesher', mesher)

                # Load the mesher config
                mesher.parse_config(section)

                # If we have an inner section
                if self.has_inner:
                    self.mesher_inner = []

                    # FIXME: SURELY this shouldn't be hardcoded??
                    self.logger.add_region("catheter", None, ("zone",), zone=True)
                    self.logger.add_region("slot", None, ("zone",), zone=True)
                    self.logger.add_region("dielectric cable", None, ("zone",), zone=True)

                    # Make sure we know to run inner mesher later
                    self.components['mesher_inner'] = self.mesher_inner
                    for inner_node in section.iterfind('inner'):
                        inner_type = inner_node.get('type')
                        inner_name = inner_node.get('name')

                        # It is possible we have multiple inners, such as a fine
                        # and a coarse variant
                        if inner_name is None:
                            inner_name = "mesher_inner"
                        else:
                            inner_name = "mesher_inner-%s" % slugify(inner_name)

                        # This also has a type
                        if inner_type == "CGAL":
                            component = GoSmartMesher3DCGAL(self.logger)
                        elif inner_type == "axisymmetric":
                            component = GoSmartMesher2DGMSH(self.logger)
                        else:
                            self.logger.print_fatal("Unknown mesher type %s in %s" % (inner_type, filename))

                        component.suffix = inner_name

                        # Configure the specific meshing component
                        component.parse_config(section)

                        # This may have a template, a library layout that
                        # defines it
                        # TODO: find some way of making this sensibly includable
                        # in GSSF-XML (maybe as a separate input file).
                        # Moreover, should this be available on the outer level if
                        # that can be axisymmetric?
                        template_set = inner_node.get("template")
                        if template_set is not None:
                            template_filename = "templates/inner-%s.xml" % template_set
                            with open(os.path.join(self.logger.get_cwd(), config.template_directory, template_filename), "r") as template_file:
                                configtree = ET.parse(template_file)
                                root = configtree.getroot()
                                component.parse_config(root)

                        component.parse_config(inner_node)

                        # The inner mesh is constrained to this region
                        if inner_node.get("region") is not None:
                            component.alter_extent(inner_node.get("region"))

                        # Which mesh should the needle be (geometrically)
                        # embedded in? Inner/outer/both
                        if inner_node.get("needle") is not None:
                            if inner_node.get("needle") == "inner only":
                                if not skip_outer and not skip:
                                    mesher.skip_needle = True
                            elif inner_node.get("needle") == "outer only":
                                component.skip_needle = True
                            elif inner_node.get("needle") != "both":
                                self.logger.print_fatal("If supplied, 'needle' parameter to inner mesh should be 'inner only', 'outer only' or 'both'")

                        self.mesher_inner.append(component)
                        component.skip = skip

            # The optimizer cleans the mesh
            elif section.tag == 'optimizer' and not skip:
                self.add_component('optimizer', GoSmartMeshOptimizer(self.logger))
            # The lesion component extracts an isosurface from the Elmer
            # volumetric output
            elif section.tag == 'lesion' and not skip:
                lesion = self.add_component('lesion', GoSmartLesion(self.logger))
                lesion.parse_config(section)
            # The validation compares the lesion output to a reference STL surface
            elif section.tag == 'validation' and not skip:
                validation = self.add_component('validation', GoSmartValidation(self.logger))
                validation.parse_config(section)
            # ElmerGrid scales and converts to Elmer mesh format
            elif section.tag == 'elmergrid' and not skip:
                elmergrid = self.add_component('elmergrid', GoSmartElmerGrid(self.logger))
                elmergrid.parse_config(section)
            # Elmer solves the simulation problem
            elif section.tag == 'elmer' and not skip:
                elmer = self.add_component('elmer', GoSmartElmer(self.logger, elmer_binary=self.elmer_binary))
                elmer.parse_config(section)
            # Any constants that should end up in the global parameter
            # dictionary (for SIF template usage) should be placed here
            elif (section.tag == 'constants' or section.tag == 'parameters') and not skip:
                # DEPRECATED: use a library set of constants
                default_set = section.get("defaults")

                if default_set is not None:
                    self.logger._load_constant_set(default_set)

                # Loop through and add each constant listed. Note that we do not
                # check the tag name - we eventually want to migrate to calling
                # these parameters - this allows us to do so progressively
                for constant in section:
                    value = constant.get("value")
                    if value is None:
                        value = constant
                    try:
                        value = json.loads(value)
                    except:
                        pass
                    self.logger.add_or_update_constant(constant.get("name"), value, True, constant.tag, typ=constant.get("type"))
            elif not skip:
                self.logger.print_fatal("Unknown top-level section %s in %s" % (section.tag, filename))

            if skip:
                self.logger.print_line("* Skipping %s as indicated in settings file %s" % (section.tag, filename))

        # Output all regions loaded so far (this should include any generated by
        # the needle library)
        self.logger.print_debug(self.logger.zones)
        self.logger.print_debug(self.logger.surfaces)

        # Append this config file to the Elmer component list, as it may need to
        # bootstrap us if there are multiple processes to be fired off and we
        # are the first one
        if hasattr(self, "elmer"):
            self.elmer.configfiles.append(filename)

    # Parse all config files. This hasn't been tested properly
    # though for more than one.
    def parse_config_files(self):
        if len(self.configfiles) == 0:
            self.logger.print_fatal("No config files were supplied")

        for configfile in self.configfiles:
            self.parse_config_file(configfile)
