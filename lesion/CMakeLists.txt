cmake_minimum_required(VERSION 2.8)

find_package(CGAL COMPONENTS ImageIO)
include( ${CGAL_USE_FILE} )

find_package(VTK REQUIRED)
include(${VTK_USE_FILE})

find_path(TINYXML2_INCLUDE_DIR "tinyxml2.h" PATH_SUFFIXES "tinyxml2" REQUIRED)
find_library(TINYXML2_LIBRARIES NAMES "tinyxml2" PATH_SUFFIXES "tinyxml2" REQUIRED)
include_directories(${TINYXML2_INCLUDE_DIR})

if (IGNORE_ISO_VOLUME)
    add_definitions(-DIGNORE_ISO_VOLUME=${IGNORE_ISO_VOLUME})
else(IGNORE_ISO_VOLUME)
    add_subdirectory(vtkIsoVolume)
endif(IGNORE_ISO_VOLUME)

SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++0x")

add_executable(go-smart-lesion go-smart-lesion.cpp)
add_executable(go-smart-segmented-lesion-cleaner go-smart-segmented-lesion-cleaner.cpp PolyhedronUtils.cpp)

if (IGNORE_ISO_VOLUME)
    target_link_libraries(go-smart-lesion ${VTK_LIBRARIES} boost_program_options ${TINYXML2_LIBRARIES})
else(IGNORE_ISO_VOLUME)
    target_link_libraries(go-smart-lesion ${VTK_LIBRARIES} boost_program_options ${TINYXML2_LIBRARIES} vtkIsoVolume)
endif (IGNORE_ISO_VOLUME)

target_link_libraries(go-smart-segmented-lesion-cleaner ${VTK_LIBRARIES} boost_program_options ${CGAL_LIBRARIES} ${CGAL_3RD_PARTY_LIBRARIES})

INSTALL(TARGETS go-smart-lesion go-smart-segmented-lesion-cleaner RUNTIME DESTINATION "bin" LIBRARY DESTINATION "lib") 
