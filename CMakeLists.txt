# 
# Experimental CMake configuration script for Elmer
# 
# Authors:
#  Sami Ilvonen, CSC - IT Center for Science, Ltd.
#  Phil Weir, NUMA Engineering Services, Ltd.
#
# First public beta release 11th of October, 2013
#
# Note that this version is highly experimental and includes
# only a very limited subset of features that are supported
# by the original autotools scripts.
#

PROJECT(Elmer Fortran C CXX)
CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

SET(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${PROJECT_SOURCE_DIR}/cmake/Modules")
# This is GNU/Linux only for the mo (although *BSD should work fine?)
INCLUDE(GNUInstallDirs)

SET(ETC_LOCATION ${CMAKE_INSTALL_SYSCONFDIR}/gosmart)
SET(ETC_FULL_LOCATION ${CMAKE_INSTALL_FULL_SYSCONFDIR}/gosmart)

ENABLE_TESTING()

SET(ELMER_FEM_MAJOR_VERSION 7)
SET(ELMER_FEM_MINOR_VERSION 0)
SET(ELMER_FEM_VERSION
  ${ELMER_FEM_MAJOR_VERSION}.${ELMER_FEM_MINOR_VERSION})

SET(VERSION ${ELMER_FEM_VERSION})
SET(CMAKE_POSITION_INDEPENDENT_CODE TRUE)

FIND_PACKAGE(MPI REQUIRED)
ADD_DEFINITIONS(${MPI_Fortran_COMPILE_FLAGS})
INCLUDE_DIRECTORIES(${MPI_Fortran_INCLUDE_PATH})
LINK_DIRECTORIES(${MPI_Fortran_LIBRARIES})

#FIND_PACKAGE(CUDA)
#SET(HAVE_CUDA ${CUDA_FOUND})
#IF(HAVE_CUDA)
#   ADD_SUBDIRECTORY(cuda_hutiter)
#ENDIF(HAVE_CUDA)

FIND_PACKAGE(BLAS REQUIRED)
FIND_PACKAGE(LAPACK REQUIRED)

#FIND_PACKAGE(Trilinos)
#SET(HAVE_TRILINOS ${Trilinos_FOUND})
FIND_PACKAGE(Mumps)
SET(HAVE_MUMPS ${Mumps_FOUND})
MESSAGE(${HAVE_MUMPS})

# Check if Fortran compiler supports contiguous keyword
INCLUDE(testContiguous)
IF(CMAKE_Fortran_COMPILER_SUPPORTS_CONTIGUOUS)
  ADD_DEFINITIONS(-DCONTIG=,CONTIGUOUS)
ELSE()
  ADD_DEFINITIONS(-DCONTIG=)
ENDIF()

EXEC_PROGRAM(
    "git"
    ${CMAKE_CURRENT_SOURCE_DIR}
    ARGS "describe" "--tags" "--always"
    OUTPUT_VARIABLE GIT_REVISION)

SET(FC_STDCALLBULL " ")
SET(FC_FUNC FC_GLOBAL)
SET(FC_FUNC_ FC_GLOBAL_)

INCLUDE(FortranCInterface)
FortranCInterface_HEADER(FCMangle.h MACRO_NAMESPACE "FC_")
FortranCInterface_VERIFY(CXX)

SET(CMAKE_Fortran_MODULE_DIRECTORY
    ${PROJECT_BINARY_DIR}/bin/fortran CACHE PATH "Build directory for Fortran modules."
)
SET(CMAKE_Fortran_MODULE_DESTINATION
    ${CMAKE_INSTALL_PREFIX}/include/elmer/f90 CACHE PATH "Destination for Fortran modules."
)

ADD_SUBDIRECTORY(lesion)
ADD_SUBDIRECTORY(gssf)

MESSAGE(STATUS "------------------------------------------------")
MESSAGE(STATUS "  BLAS library:   " ${BLAS_LIBRARIES})
MESSAGE(STATUS "  LAPACK library: " ${LAPACK_LIBRARIES})
MESSAGE(STATUS "------------------------------------------------")
