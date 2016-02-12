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
import gosmart_sf_config
import shutil

# TODO: find a better way of integrating shared data locations
template_directory = os.path.join(os.path.dirname(__file__), 'data')
power_profiles_directory = os.path.join(os.path.dirname(__file__), 'data', 'power_profiles')
fortran_template_directory = os.path.join(os.path.dirname(__file__), 'data', 'elmer_modules')

# The location of the FORTRAN modules is decided at build time, so is in the
# CMake generated module
fortran_modules_directory = gosmart_sf_config.fortran_modules_dir
git_revision = gosmart_sf_config.git_revision
etc_location = gosmart_sf_config.etc_location

# Elmer properties (as GSSF => Elmer workflow)
elmer_binary_location = shutil.which("ElmerSolver_mpi")
if elmer_binary_location:
    elmer_prefix = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(elmer_binary_location)), os.pardir))
    elmer_home = os.path.join(elmer_prefix, "share", "elmersolver")

    # Find the Elmer revision with which we are working - this is important for the
    # log files, as it makes post hoc bisection possible
    with open(os.path.join(elmer_home, "gitrev")) as f:
            elmer_git_revision = f.read()
else:
    elmer_prefix = None
    elmer_home = None
    elmer_git_revision = None
