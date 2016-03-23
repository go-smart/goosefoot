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
import select
import threading
import socket
import string
import shutil
import re
import uuid
import numpy as N
import json
import jinja2
import jinja2.sandbox

from . import config
from .component import GoSmartComponent
from .globals import \
    defaults, \
    _sif_calculations, \
    _elmer_modules_required, \
    launcher_command, \
    slugify
from .elmer_probelocation import GoSmartElmerProbeLocationFactory, probe_location_factories
from .errors import GoSmartClientError


# This utility attempts to convert a variable to a string including the Elmer
# SIF type prefix
def _type_to_sif_type(typ, var):
    # Floats are Reals
    if (typ == 'float' or typ == 'array(float)'):
        return 'Real %s' % _type_to_sif_string(typ, var)
    # Ints are Integers
    elif (typ == 'int' or typ == 'array(int)'):
        return 'Integer %s' % _type_to_sif_string(typ, var)
    # Float-over-time uses time as a variable
    # TODO: this should not be here - Time is an argument, so this should
    # probably be an algorithm
    elif (typ == 'array(Time,float)'):
        ret = "Variable Time\nReal \n%s\nEnd" % "\n".join(map(lambda row: " ".join(map(str, row)), sorted(json.loads(var).items())))
        return ret

    # Otherwise it is assumed to be something without a type required
    var = _type_to_sif_string(typ, var)

    return var


# Simple conversion to a string for the benefit of Elmer SIF templating
def _type_to_sif_string(typ, var):
    # If an array, we use space-separated notation, as required for a SIF
    # Usually this will need to be prefixed by the type when embedded
    if (typ in ('array(float)', 'array(int)')):
        return " ".join(map(str, json.loads(var)))
    return str(var)


# This class allows us to maintain a number of important properties of our
# parameter without complicating life for the templater (who may even be an
# online user). It is what appears in SIF usage.
#
# We try to make it as like a normal Python primitive as possible, but still
# with the name and value able to be explicitly retrieved
class Parameter:
    def __init__(self, attr, value, type_callback):
        self._attr = attr
        self._value = value
        self._type_callback = type_callback

    def __float__(self):
        return float(self._value)

    def __int__(self):
        return int(self._value)

    def __str__(self):
        return str(self.render())

    def __bool__(self):
        return bool(self._value)

    def get_name(self):
        return self._attr

    # The typed parameter lets the user indicate whether this is being used
    # directly on the RHS of a SIF assignment (so type prefix is fine) or
    # whether it is being dropped in / used for a Python calculation / otherwise
    # and should appear with no preceding type string
    def render(self, typed=False):
        renderer = _type_to_sif_type if typed else _type_to_sif_string

        rendered = renderer(self._type_callback(self._attr), self._value)

        return rendered

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value

    # Convenience notation as laconic approach required
    def __getattr__(self, attr):
        if attr == 'name':
            return self.get_name()
        elif attr == 'value':
            return self.get_value()

        super().__getattr__(attr)


# This class is an extension of dict that allows us to refer to parameters as
# members, saving a little syntax, and allowing specification of a type callback
# for all parameters.
#
# Note that this class is not ready to replace dict entirely (that
# requires more method overriding than here)
class ParameterDict(dict):
    def __init__(self, type_callback, *args, **kwargs):
        self._type_callback = type_callback

        super().__init__(*args, **kwargs)

    def __getattr__(self, attr):
        return self.__getitem__(attr)

    def __setitem__(self, attr, value):
        super().__setitem__(attr, Parameter(attr, value, self._type_callback))

    def update(self, *args, **kwargs):
        update_dict = dict(*args, **kwargs)
        super().update({k: Parameter(k, v, self._type_callback) for k, v in update_dict.items()})


# This class is used similarly to the ParameterDict, but will dynamically start
# a counter when a member is does not have is requested. If the member is
# prefixed with an underscore, the counter is not incremented.
#
# E.g.
#   C = CounterDict()
#   C.BODY (first usage returns 1)
#   C.BODY (second usage returns 2)
#   C._BODY (third usage returns 2, as underscore used)
#   C.BODY (fourth usage returns 3)
class CounterDict(dict):
    def __getitem__(self, attr):
        if attr[0] == '_':
            increment = False
            attr = attr[1:]
        else:
            increment = True

        try:
            p = super().__getitem__(attr)
        except KeyError:
            self[attr] = 1
            p = super().__getitem__(attr)

        if increment:
            self[attr] = p + 1

        return p


# Class to hold settings specific to the Go-Smart/Elmer solver
class GoSmartElmer(GoSmartComponent):
    suffix = 'elmer'
    _startinfo = 'ELMERSOLVER_STARTINFO'
    # For restarts, a separate binary is needed to convert the results if on
    # different grids
    restart_binary = 'ResultToResult'

    # (DEPRECATED) If the SIF in not supplied in the XML it may be found as a
    # library file - this provides a translation from model names to template
    # file suffices
    _sif_suffices = {
        "rfa point sources": "_ps",
        "rfa point sources (modified bioheat)": "_ps-modbioheat",
        "rfa point sources (new elmer)": "_ps-newelmer",
        "rfa joule heating": "_jh",
        "mwa": "_mwa",
        "mwa (nonlinear)": "_mwa-nl",
        "cryoablation": "_cryo",
        "ire": "_ire"
    }

    # Time spent in these pairs will be reported on successful exit
    logpick_pairs = (("NumaCellStateSolve: Starting Assembly", "NumaCellStateSolve: Assembly done", "Assembly [cell]"),
                     ("HeatSolve: Starting Assembly", "HeatSolve:: Dirichlet boundary conditions set", "Assembly [heat]"),
                     ("NumaStatCurrentSolve: Starting Assembly", "NumaStatCurrentSolve: Assembly done", "Assembly [jh]"),
                     ("CRS_IncompleteLU: ILU(0) (Real), Starting Factorization", "ComputeChange:", "Solver"))

    # RMV: check these
    todos = ("PTW: Conversion from ml to g in perfusion rate at 1:1!!",
             "PTW: Basic alphabetization to rotate indices means that this will break with more than ~26 zones - switch letters to (slugified?) suitably escaped zone names",
             "PTW: Double check that the missing boundary conditions don't default to somewhere else - use non-existent target boundaries if absolutely ness.",
             "PTW: Check correct inclusion of perfusion coefficient in JH",
             "PTW: Ignoring segfaults and other signals (negative codes indicate terminated by a given Unix signal",
             "PTW: MWA not using variable power",
             "PTW: Not currently using intersection and (in-)trocar points")

    # point sources or excised
    needle_type = "excised"

    probe_location_factory = None

    _restarting = None

    def __init__(self, logger, elmer_binary=None, elmer_mpi_binary=None, probe_location_factory=None):
        super().__init__(logger)

        # elmer_binary is usually ``ElmerSolver_mpi`` or ``ElmerSolver``
        if elmer_binary is None:
            elmer_binary = defaults["elmer binary"]
        # elmer_mpi_binary is normally ``ElmerSolver_mpi``
        if elmer_mpi_binary is None:
            elmer_mpi_binary = defaults["elmer mpi binary"]
        if probe_location_factory is None:
            probe_location_factory = GoSmartElmerProbeLocationFactory()

        # This is used to compile Fortran - for security reasons we only use
        # this with library Fortran. The runtime compilation allows for use of
        # XML parameters in the code
        self.fortran_binary = defaults["fortran binary"]

        self.elmer_binary = elmer_binary
        self.elmer_mpi_binary = elmer_mpi_binary

        # This will form the main parameter dictionary
        self._sif_mapping = ParameterDict(type_callback=self.logger.get_constant_type)
        self._sif_mapping["RUNNAME"] = self.logger.runname

        self._probe_location_factory = probe_location_factory

        self._sif_variant = "default"
        self._sif = None
        self._elmer_modules_required = []
        self._algorithms = {}

        self.configfiles = []

    # This allows the calculation of the perpendicular distance between two needles, for use
    # in the SIF template.
    # dist_from_tip : fixed length down the shaft where comparison should take
    #                 place
    # reference_needle : on which needle should the dist_from_tip measurement take
    #                    place
    def _needle_distance(self, needle1, needle2, dist_from_tip=None, reference_needle=None):
        needle1 = str(needle1)
        needle2 = str(needle2)

        if "simulationscaling" in self.logger.geometry:
            scaling = self.logger.geometry["simulationscaling"]
        else:
            scaling = 1.0

        n1t = N.array(json.loads(self.logger.get_needle_constant(needle1, "NEEDLE_TIP_LOCATION"))) * scaling
        n2t = N.array(json.loads(self.logger.get_needle_constant(needle2, "NEEDLE_TIP_LOCATION"))) * scaling
        n1e = N.array(json.loads(self.logger.get_needle_constant(needle1, "NEEDLE_ENTRY_LOCATION"))) * scaling
        n2e = N.array(json.loads(self.logger.get_needle_constant(needle2, "NEEDLE_ENTRY_LOCATION"))) * scaling
        print(n1t, n2t, n1e, n2e)

        # If not given a distance from needle1 ti
        if dist_from_tip is None:
            p = N.cross(n1t - n1e, n2t - n2e)
            print(p)
            if p.dot(p) < 1e-10:
                return N.sqrt(N.dot(n2t - n1t, n2t - n1t))

            return abs(N.dot(n2e - n1e, p)) / N.sqrt(p.dot(p))

        if reference_needle is None:
            reference_needle = needle1

        n1 = n1t - n1e
        c = n1t - (float(dist_from_tip) * scaling) * n1 / N.sqrt(n1.dot(n1))
        l = (n2t - n2e).dot(n1)
        if abs(l) < 1e-10:
            raise GoSmartClientError("Needle %s and needle %s are perpendicular!" % (needle1, needle2))

        k = (c - n2e).dot(n1) / l
        v = c - n2e - k * (n2t - n2e)
        print(v)

        return N.sqrt(v.dot(v))

    # If this is a string, try and cast to a float, otherwise leave it as it is.
    def _maybefloat(self, c):
        if isinstance(c, str):
            try:
                c = float(c)
            except:
                pass
        return c

    # Return a list of possibly-numeric values from a list of constant-names
    def _get_requirements(self, requirements):
        inp = [self.get_constant(x) for x in requirements]
        return list(map(self._maybefloat, inp))

    def _check_sif_mapping_set(self, sif_template):
        # If a lambda function calculation is required, get the values from its
        # input requirements and run the function on them. Save as
        # CALCULATED_CONSTNAME. This is DEPRECATED and should be replaced with
        # algorithms
        for name, definition in _sif_calculations.items():
            if all(v in self.get_constants() for v in definition['requirements']):
                value = definition['formula'](*self._get_requirements(definition['requirements']))
                self.add_or_update_constant(name, str(value), False, "CALCULATED")
            else:
                self.logger.print_debug("SIF Generation - Skipping %s as missing parameters (requires %s)" % (name, ", ".join(definition['requirements'])))

        # Give up if constants marked for warning are not present in the SIF
        # file
        for name, info in self.get_mapping_warn().items():
            if not sif_template.find(name):
                self.logger.print_error("SIF Generation - Missing %s" % info)

        # If we are requested to debug, tell the logger what all the values of
        # all constants (so far) is
        if self.logger.debug:
            for name, value in self.get_constants().items():
                self.logger.print_debug("%s set to %s" % (name, value))

    # Put each algorithm's MATC function into file and prepare a string that
    # references it from the main SIF. This will be planted wherever the Result
    # appears.
    def _prepare_algorithms(self):
        for result, algorithm in self._algorithms.items():
            filename = str(uuid.uuid4()) + '.matc'
            with open(os.path.join(self.logger.make_cwd(self.cwd), filename), 'w') as f:
                f.write(algorithm["definition"])
            algorithm["sources"] = "$ source(\"%s\")\n" % filename
            algorithm["call"] = "Variable %s\n\t\tReal MATC \"%s(%s)\"" % (
                ", ".join(algorithm["arguments"]),
                result,
                ", ".join("tx(%d)" % i for i in range(len(algorithm["arguments"])))
            )

    # Prepare the actual SIF from the input template
    def _generate_sif(self):
        # This approach is DEPRECATED, but certain templates are available as
        # library files
        if self._sif_variant is not None:
            sif_suffix = self._sif_suffices[self._sif_variant]
            sif_filename = os.path.join(config.template_directory, "templates", "go-smart-template%s.sif" % sif_suffix)
            self.logger.print_debug("SIF template filename %s" % sif_filename)
            sif_template_stream = open(sif_filename, "r")
            sif_definition = sif_template_stream.read()
            sif_template_stream.close()
        # Else we should have a definition already supplied from the XML in the _sif member
        else:
            sif_definition = self._sif

        # Get the mesh IDs of all geometric regions - surfaces and volumes
        region_ids = self.logger.get_region_ids()

        needle_constants = self.logger.get_needle_constants()

        self.logger.print_debug(needle_constants)

        # Loop through the needles and add region constants to the
        # needle-specific parameters without needle ID
        for needle, constants in needle_constants.items():
            root = "REGIONS_NEEDLE_%s" % slugify(needle)
            generic_root = "REGIONS_NEEDLE"
            for prefix in ("BODIES_", "BOUNDARIES_", ""):
                for suffix in ("_ACTIVE", "_INACTIVE", ""):
                    entry = "%s%s%s" % (prefix, root, suffix)
                    generic_entry = "%s%s%s" % (prefix, generic_root, suffix)
                    if entry in region_ids:
                        constants[generic_entry] = region_ids[entry]
                        self.logger.print_debug("%s: %s" % (entry, region_ids[entry]))

        # Sandbox for some extra security
        sif_environment = jinja2.sandbox.SandboxedEnvironment()
        sif_environment.filters['typed'] = lambda p: p.render(True)
        sif_environment.filters['totyped'] = lambda v, t: _type_to_sif_type(t, json.dumps(v))
        sif_environment.filters['discretize'] = lambda v, r: (float if r < 1 else int)(round(v / r) * r)
        sif_environment.globals['zip'] = zip
        sif_environment.globals['list'] = list
        sif_environment.globals['map'] = map
        sif_environment.globals['str'] = str
        sif_environment.globals['needle_distance'] = self._needle_distance
        sif_template = sif_environment.from_string(sif_definition)

        # If we are restarting, we can dynamically add a restart section
        # TODO: restarting needs further work
        if self._restarting:
            self._sif_mapping["RESTART_SECTION"] = """
                Restart File = File \"Result.dat\"
                Restart Position = Integer %d
                Restart Time = Real %lf
            """ % (self._restarting['position'], self._restarting['time'])
            self._sif_mapping["RESTART_FILEINDEX_OFFSET"] = "Fileindex Offset = %d" % (self._restarting['position'] + 1)
        # Otherwise, we can save progress as we go
        else:
            self._sif_mapping["RESTART_FILEINDEX_OFFSET"] = ""
            self._sif_mapping["RESTART_SECTION"] = """
                Output File = 'Restart.dat'
            """

        self._prepare_algorithms()
        self._check_sif_mapping_set(sif_definition)

        constants = self.get_constants()

        # Add the component and global constants into our constants dictionary
        self._sif_mapping.update(constants)

        # Add in the region IDs
        self._sif_mapping.update(region_ids)

        # Add in the algorithms by result
        self._sif_mapping.update(dict((r, a["call"]) for r, a in self._algorithms.items()))

        # Add the sources section for pulling in the MATC algorithm definitions
        sources = "\n".join(a["sources"] for a in self._algorithms.values())
        self._sif_mapping["SOURCES"] = sources

        # Find regions in SIF and mark them as empty if they are not in the
        # dictionary, as they are assumed to be optional by default.
        for regions in re.finditer(r'((BOUNDARIES_|BODIES_|)REGIONS_[A-Z0-9_]*)', sif_definition):
            regions = regions.group(1)
            if regions not in self._sif_mapping:
                self._sif_mapping[regions] = None
                self.logger.print_debug("%s empty" % regions)

        # p and c are ParameterDicts, that is, you can get an item by using object syntax: p.KEY
        # c is also a CounterDict, that is, if you look for a key, it will return 1 the first time and
        # an incrementing number for each look-up. To get the current value, without incrementing, prefix
        # the key with an underscore: c.KEY gives an incremented value, c._KEY gives the current value
        # without incrementing
        counter_dict = CounterDict(type_callback=self.logger.get_constant)

        # Render and write the SIF file
        sif_string = sif_template.render(p=self._sif_mapping, needles=needle_constants, c=counter_dict)
        sif_stream = open(os.path.join(self.logger.make_cwd(self.cwd), self._sif_file), "w")
        sif_stream.write(sif_string)
        sif_stream.close()

    # Create the ELMERSOLVER_STARTINFO file (not essential as detail passed in
    # arguments)
    def _generate_startinfo(self, nprocs, sif=None):
        if sif is None:
            sif = self._sif_file

        with open(os.path.join(self.logger.make_cwd(self.cwd), self._startinfo), "w") as startinfo_file:
            startinfo_file.write("%s\n" % sif)
            startinfo_file.write("%d\n" % nprocs)

    # In the point source case, we will need to supply files of heating point
    # locations to be processed by an Elmer module
    def _generate_probe_locations(self):
        # Request the pre-defined factory generates the locations (this should
        # already be configured from the GSSF-XML)
        probe_locations = self.probe_location_factory.generate_locations()

        if probe_locations is None:
            self.logger.print_fatal("Failed to generate probe locations")

        # Add the locations into the SIF file
        # Note that time can also (should) be phase
        self._sif_mapping.update({
            "PROBELOCATIONS_COUNT": len(probe_locations),
            "PROBELOCATIONS": " ".join(str(l) for l in sorted(l.time for l in probe_locations.values())),
        })

        # This file gives the template for probe locations as the relevant
        # module expects to receive them
        probe_location_template_file = open(os.path.join(config.template_directory, "go-smart-probe-location-template.txt"), "r")
        probe_location_template = string.Template(probe_location_template_file.read())
        probe_location_template_file.close()

        # For each phase, go through the probe locations
        for idx, probe_location in probe_locations.items():
            for segment in ('ends', 'middles', 'thermocouples'):
                probe_location_filename = os.path.join(self.logger.make_cwd(self.cwd), self.logger.runname.lower() + "-probe-locations_" + str(idx + 1) + "-" + segment + ".txt")
                with open(probe_location_filename, "w") as probe_location_file:
                    points = probe_location[segment]
                    point_template_map = {"POINTCOUNT": len(points), "POINTTABLE": "\n".join(" ".join(map(str, list(row[0]) + [row[1]])) for row in points)}
                    probe_location_file.write(probe_location_template.substitute(point_template_map))

    # FIXME: this is suboptimal, intermediary solution to not passing data
    # between simulations. Certain simulations, esp. MWA, require pre-calculated
    # data - here it is supplied as a library. At the least, this should only
    # copy what's necessary
    def _copy_power_profiles(self):
        for profile in os.listdir(config.power_profiles_directory):
            shutil.copy(os.path.join(config.power_profiles_directory, profile), self.logger.make_cwd(self.cwd))

    # Compile any runtime-compiled Fortran modules
    def _build_elmer_modules(self):
        elmer_modules = self._elmer_modules_required

        # Certain pre-known SIF templates have dependent modules (however, this
        # approach is DEPRECATED)
        if self._sif_variant is not None:
            elmer_modules += _elmer_modules_required[self._sif_variant]

        for mod in elmer_modules:
            shutil.copy(os.path.join(config.fortran_template_directory, "%s.f90" % mod), self.logger.make_cwd(self.cwd))
            # This gets launched as a normal subprocess, albeit preceding the Elmer one
            self._launch_subprocess(self.fortran_binary, [
                "%s.f90" % mod,
                "-o", "%s.so" % mod,
                "-I", config.fortran_modules_directory,
                "-fPIC", "-shared",
            ])

    # If restarting, we will need the old SIF moved for the interpolation binary
    # to find. Run the interpolation binary
    def _interpolate_restart(self, nprocs):
        restart = self._restarting
        self._generate_startinfo(nprocs, "%s.sif" % restart["old"])
        cwd = self.logger.make_cwd(self.suffix)
        shutil.copy(os.path.join(cwd, "%s.sif" % self.logger.runname), os.path.join(cwd, "Interpolation.sif"))

        # This is an Elmer utility
        self._launch_subprocess(self.restart_binary, [])
        self._generate_startinfo(nprocs)

    # This allows the governing routine to provide us with a callback for
    # updated status
    def set_update_status(self, update_status):
        self._update_status = update_status

    # To communicate the status as the simulation proceeds, we create a socket
    # for the solver to connect to and monitor it
    def _percentage_server(self):
        cwd = self.logger.make_cwd(self.suffix)

        # Define a Unix socket the main Python directory
        address = os.path.join(cwd, "percentage.sock")

        # If we have a pre-existing socket, remove it
        try:
            os.remove(address)
        except OSError:
            if os.path.exists(address):
                return

        # Unix stream
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(address)
        s.listen(1)
        self._monitoring_status = True

        while self._monitoring_status:
            inp, out, exc = select.select([s], [], [], 1)

            # If we have input, a process has connected...
            if len(inp):
                conn, client = s.accept()
                client_file = conn.makefile("r")

                # Keep looking until we run out of lines - the process has
                # exited
                while True:
                    data = client_file.readline()
                    if data:
                        # Simplistic but should be improved if user is
                        # eventually allowed to set status text
                        percentage, status = data.split('||')
                        self.logger.print_line("[status]: %s%% --- %s" % (percentage, status))

                        if self._update_status is not None:
                            try:
                                self._update_status(float(percentage), status)
                            except:
                                pass
                    else:
                        # Stop watching; we should only look after one process in a run
                        self.stop_monitoring_status()
                        break
                conn.close()

    def stop_monitoring_status(self):
        self._monitoring_status = False

    # Set up the status socket in a different thread and return
    def _setup_percentage_socket(self):
        self._percentage_thread = threading.Thread(target=self._percentage_server)
        self._percentage_thread.start()

    # Start the simulation
    def launch(self, nprocs=1, mesh_locations=None):
        super().launch()

        # Guess the mesh_locations are under the elmergrid directory if not
        # given
        if not mesh_locations:
            mesh_locations = {"-mesher": "elmergrid/%s-mesher" % self.logger.runname}

        self.cwd = self.suffix

        # Move all the necessary meshes into place. The appendix allows multiple
        # meshes to be handled within one simulation - a case in point is the
        # combination of 3D and axisymmetric 2D meshes for MWA
        for appendix, mesh_location in mesh_locations.items():
            mesh_target = os.path.join(self.logger.make_cwd(self.cwd), self.logger.runname + appendix)

            # Only tidy up if we are allowed to
            if not self.logger.leavetree:
                if os.path.exists(mesh_target):
                    shutil.rmtree(mesh_target)
                shutil.copytree(os.path.join(self.logger.get_cwd(), mesh_location), mesh_target)

            mesh_location_slug = slugify(appendix)
            self._sif_mapping["MESHLOCATION" + mesh_location_slug] = self.logger.runname + appendix

        self._sif_file = self.logger.runname + ".sif"

        # Prepare the SIF file, modules and any other necessary config
        # If we have multiple processes, then we actually re-run GSSF with MPI.
        if nprocs < 2:
            self.logger.print_line(" [in serial]")
            if not self.logger.leavetree:
                if self.probe_location_factory:
                    self._generate_probe_locations()

                self._copy_power_profiles()
                self._build_elmer_modules()

                self._generate_sif()
                if self._restarting:
                    self._interpolate_restart(nprocs)
                self._generate_startinfo(nprocs)
                try:
                    self._setup_percentage_socket()
                    return_code = self._launch_subprocess(self.elmer_binary, [])
                finally:
                    self.stop_monitoring_status()
            else:
                return_code = self._launch_subprocess(self.elmer_binary, [])
        else:

            if self.probe_location_factory:
                self._generate_probe_locations()

            self._copy_power_profiles()
            self._build_elmer_modules()

            if self._restarting:
                self._interpolate_restart(nprocs)
            self._generate_sif()
            self._generate_startinfo(nprocs)
            self.cwd = '.'
            self.logger.print_line(" [using MPI with %d processes]" % nprocs)
            args = ["-np", str(nprocs),
                    launcher_command,
                    "--nprocs", "1",
                    "--silent",
                    "--only", "elmer",
                    "--leavetree",
                    "--elmer", self.elmer_mpi_binary,
                    "--elmer-logfile", self.outfilename,
                    "--logfile-addpid"] + self.configfiles
            return_code = self._launch_subprocess("mpirun", args, mute=True)

        self.logger.print_debug("Return code [%d]" % int(return_code))
        self.stop_monitoring_status()

        # Wait for the percentage server to exit
        self._percentage_thread.join()

    # Load the configuration from the XML node
    def parse_config(self, config_node):
        super().parse_config(config_node)

        for element in config_node:
            # DEPRECATED: see pointsources instead
            if element.tag == 'probelocations':
                if element.get('type') not in probe_location_factories.keys():
                    self.logger.print_fatal("Could not find probe location type")

                self.probe_location_factory = probe_location_factories[element.get('type')]()
                self.probe_location_factory.parse_config(element)
            # TODO: make sure this all still works correctly
            elif element.tag == 'restart':
                self._restarting = {'time': float(element.get('time')), 'position': int(element.get('position')), 'old': element.get('old')}
            # If we need to handle heating points, instantiate a factory and
            # pass it the configuration
            elif element.tag == 'pointsources':
                self.needle_type = 'point sources'
                generation_system = element.get('system')
                if generation_system is None:
                    generation_system = 'straight tines'
                self.probe_location_factory = probe_location_factories[generation_system]()
                self.probe_location_factory.parse_config(element, logger=self.logger)
            # This is the actual SIF template
            elif element.tag == 'variant':
                modules_required = element.get('modules')

                if modules_required is not None:
                    self._elmer_modules_required += modules_required.split('; ')

                # We now prefer the SIF template to be embedded - providing a
                # variant name is DEPRECATED
                name = element.get('name')
                if name is None:
                    self._sif = element.text
                    self._sif_variant = None
                elif name.lower() in ("rfa point sources", "mwa", "mwa (nonlinear)", "cryoablation", "ire", "rfa joule heating", "rfa point sources (new elmer)"):
                    self._sif_variant = name.lower()
                    self._load_constant_set("variant-%s" % slugify(self._sif_variant))

                    for jh_element in config_node:
                        pass
                else:
                    self.logger.print_fatal("Unknown variant: %s" % name)
            # This is actually just a constants section - this could possibly be
            # removed as a ``constants`` element should achieve the same effect.
            # However, it does add entries in group SETTING
            elif element.tag == 'settings':
                for constant in element:
                    value = constant.get("value")
                    if value is None:
                        value = constant
                    self.add_or_update_constant(constant.get("name"), value, True, "SETTING", typ=constant.get("type"))
            # Add in any MATC algorithms
            elif element.tag == 'algorithms':
                for algorithm in element:
                    # Pull all the argument names out of the arguments node
                    arguments = map(lambda a: a.get("name"), algorithm.find("arguments"))

                    # Actual code definition is in the content node
                    definition = algorithm.find("content").text

                    if definition is not None:
                        self._algorithms[algorithm.get("result")] = {
                            "definition": definition,
                            "arguments": list(arguments)
                        }
            else:
                self.logger.print_error("Unknown element %s in %s" %
                                        (element.tag, config_node.tag))
