set(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")
project(sigmond) #CMAKE_CXX_COMPILER set this using python
cmake_minimum_required(VERSION 3.4...3.18)
set(CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}" ${CMAKE_MODULE_PATH})

#set(CMAKE_BUILD_TYPE Debug)

find_package(Python COMPONENTS Interpreter Development)

# Find HDF5 - optimized for conda/docker environments
find_package(HDF5 COMPONENTS C)
if(HDF5_FOUND)
    # In conda environments, CMake often finds HDF5 but variables may be empty
    # because conda uses compiler wrappers
    if(NOT HDF5_INCLUDE_DIRS AND DEFINED ENV{CONDA_PREFIX})
        set(HDF5_INCLUDE_DIRS "$ENV{CONDA_PREFIX}/include")
    endif()
    if(NOT HDF5_LIBRARIES AND DEFINED ENV{CONDA_PREFIX})
        if(APPLE)
            set(HDF5_LIBRARIES "$ENV{CONDA_PREFIX}/lib/libhdf5.dylib")
        else()
            set(HDF5_LIBRARIES "$ENV{CONDA_PREFIX}/lib/libhdf5.so")
        endif()
    endif()
    message(STATUS "Found HDF5 - includes: ${HDF5_INCLUDE_DIRS}, libs: ${HDF5_LIBRARIES}")
    add_definitions(${HDF5_DEFINITIONS})
else()
    # Fallback for conda environments
    if(DEFINED ENV{CONDA_PREFIX})
        set(HDF5_INCLUDE_DIRS "$ENV{CONDA_PREFIX}/include")
        if(APPLE)
            set(HDF5_LIBRARIES "$ENV{CONDA_PREFIX}/lib/libhdf5.dylib")
        else()
            set(HDF5_LIBRARIES "$ENV{CONDA_PREFIX}/lib/libhdf5.so")
        endif()
        message(STATUS "Using conda HDF5: ${HDF5_LIBRARIES}")
    else()
        message(FATAL_ERROR "HDF5 not found!")
    endif()
endif()

# Set HDF5 includes globally for this project since multiple modules need it
include_directories(${HDF5_INCLUDE_DIRS})

#check this as a directory and also include other directories.
set(WINDOWS_LIB_DIRS "${Python_LIBRARY_DIRS}")
string(REPLACE "miniconda3/libs" "miniconda3/Lib" WINDOWS_LIB_DIRS "${WINDOWS_LIB_DIRS}")

message("${Python_LIBRARY_DIRS}")
find_package(pybind11 REQUIRED 
                      HINTS "${Python_LIBRARY_DIRS}/python${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}/site-packages"
                            "${WINDOWS_LIB_DIRS}/site-packages"
			    "/usr/local/lib/python${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}/dist-packages"
			)

include_directories("${Python_INCLUDE_DIRS}")

include_directories("${PROJECT_BINARY_DIR}")
include_directories("${PROJECT_SOURCE_DIR}/tasks")
include_directories("${PROJECT_SOURCE_DIR}/observables")
include_directories("${PROJECT_SOURCE_DIR}/analysis")
include_directories("${PROJECT_SOURCE_DIR}/data_handling")
include_directories("${PROJECT_SOURCE_DIR}/fitting")
include_directories("${PROJECT_SOURCE_DIR}/plotting")
include_directories("${PROJECT_SOURCE_DIR}/pysigmond")

set(SCALAR_TYPE $ENV{SIGMOND_SCALAR_TYPE})

if (NOT DEFINED SCALAR_TYPE) # default to complex numbers
    set(SCALAR_TYPE "COMPLEXNUMBERS")
endif()

message(STATUS "Compiling sigmond with scalar type: ${SCALAR_TYPE}")

#set cxx compiler
add_compile_definitions(DOUBLEPRECISION ${SCALAR_TYPE} DEFAULT_HDF5 NOGRACE NO_MINUIT NOXML HDF5 LAPACK)

# set the project name
project(Sigmond VERSION 1.0)

add_subdirectory(analysis)
add_subdirectory(data_handling)
add_subdirectory(fitting)
add_subdirectory(observables)
add_subdirectory(plotting)
add_subdirectory(tasks)

#link_libraries(tasks_libs data_handling_lib analysis_libs fitting_libs observables_libs plotting_libs)

set_target_properties(analysis PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(data_handling PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(fitting PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(observables PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(plotting PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(tasks PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)

pybind11_add_module(sigmond pysigmond/pysigmond.cc)

# target_link_libraries(sigmond PUBLIC data_handling_libs analysis_libs tasks_libs fitting_libs observables_libs plotting_libs) 
target_link_libraries(sigmond PUBLIC data_handling )
target_link_libraries(sigmond PUBLIC analysis )
target_link_libraries(sigmond PUBLIC tasks )
target_link_libraries(sigmond PUBLIC fitting )
target_link_libraries(sigmond PUBLIC observables )
target_link_libraries(sigmond PUBLIC plotting)

# Set up library dependencies
target_link_libraries(data_handling ${HDF5_LIBRARIES})
target_link_libraries(tasks PUBLIC data_handling analysis fitting observables plotting)

# Link math libraries - use different approach for macOS
if(APPLE)
    # On macOS, link to conda libraries explicitly and allow undefined symbols
    target_link_libraries(tasks PRIVATE "$ENV{CONDA_PREFIX}/lib/liblapack.dylib")
    target_link_libraries(tasks PRIVATE "$ENV{CONDA_PREFIX}/lib/libblas.dylib") 
    target_link_libraries(tasks PRIVATE "$ENV{CONDA_PREFIX}/lib/libgfortran.dylib")
    set_target_properties(data_handling PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(analysis PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(fitting PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(observables PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(plotting PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(tasks PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
else()
    target_link_libraries(tasks PRIVATE -llapack -lblas -lgfortran)
endif()

# HDF5 includes are now set globally above

target_compile_definitions(sigmond PRIVATE VERSION_INFO=${VERSION_INFO})

# --- Build sigmond_query executable (unless skipped) ---
option(SKIP_SIGMOND_QUERY "Skip building sigmond_query executable" OFF)
if(NOT SKIP_SIGMOND_QUERY)
    # Source files for sigmond_query
    set(SIGQUERY_SRCS
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/sigmond_query.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/basic_laph_operator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/byte_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/correlator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/correlator_matrix_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/encoder.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/gen_irrep_operator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/io_handler_fstream.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/io_handler_hdf5.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/analysis/matrix.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/mcobs_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/momenta.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/operator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/scalar_defs.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/xml_handler.cc
    )

    add_executable(sigmond_query ${SIGQUERY_SRCS})
    target_include_directories(sigmond_query PRIVATE ${HDF5_INCLUDE_DIRS})
    
    # Link sigmond_query with proper libraries for each platform
    if(APPLE)
        target_link_libraries(sigmond_query PRIVATE 
            "$ENV{CONDA_PREFIX}/lib/liblapack.dylib"
            "$ENV{CONDA_PREFIX}/lib/libblas.dylib" 
            "$ENV{CONDA_PREFIX}/lib/libgfortran.dylib"
            ${HDF5_LIBRARIES})
        set_target_properties(sigmond_query PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    else()
        target_link_libraries(sigmond_query -llapack -lblas -lgfortran ${HDF5_LIBRARIES})
    endif()
    
    install(TARGETS sigmond_query DESTINATION bin)
endif()
