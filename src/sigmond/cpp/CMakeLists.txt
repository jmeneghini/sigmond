set(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")
project(sigmond) #CMAKE_CXX_COMPILER set this using python
cmake_minimum_required(VERSION 3.13)
set(CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}" ${CMAKE_MODULE_PATH})

#set(CMAKE_BUILD_TYPE Debug)

set(BUILD_SHARED_LIBS OFF)
# Enable Position Independent Code for static libraries
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Add conda root dir to CMAKE_PREFIX_PATH to aid find_package
if(DEFINED ENV{CONDA_PREFIX} AND NOT "$ENV{CONDA_PREFIX}" STREQUAL "")
    set(_conda_prefix "$ENV{CONDA_PREFIX}")
    set(_conda_lib     "${_conda_prefix}/lib")
    message(STATUS "Conda detected at: ${_conda_prefix}")
    # Help CMake discover packages installed in the environment
    list(APPEND CMAKE_PREFIX_PATH "${_conda_prefix}")

    if(APPLE)
        # Embed conda's lib directory as an RPATH on macOS so that @rpath references
        # inside HDF5 / LAPACK / etc. resolve correctly at runtime.
        set(CMAKE_INSTALL_RPATH "${_conda_lib}")
        set(CMAKE_BUILD_RPATH   "${_conda_lib}")
        set(CMAKE_INSTALL_RPATH_USE_LINK_PATH ON)
        set(CMAKE_MACOSX_RPATH ON)
        # Force CMake to actually use the rpath settings
        set(CMAKE_BUILD_WITH_INSTALL_RPATH ON)
    endif()
endif()


# Use the specific Python executable passed from setup.py
if(PYTHON_EXECUTABLE)
    set(Python_EXECUTABLE "${PYTHON_EXECUTABLE}")
endif()

find_package(Python COMPONENTS Interpreter Development)

find_package(pybind11 REQUIRED 
                      HINTS "${Python_LIBRARY_DIRS}/python${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}/site-packages"
			    "/usr/local/lib/python${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}/dist-packages"
			)

if(pybind11_FOUND)
    message(STATUS "Found pybind11: ${pybind11_VERSION}")
    if(pybind11_INCLUDE_DIR)
        message(STATUS "pybind11 include directory: ${pybind11_INCLUDE_DIR}")
    endif()
    get_target_property(pybind11_includes pybind11::headers INTERFACE_INCLUDE_DIRECTORIES)
    if(pybind11_includes)
        message(STATUS "pybind11 interface includes: ${pybind11_includes}")
    endif()
endif()

include_directories("${Python_INCLUDE_DIRS}")

include_directories("${PROJECT_BINARY_DIR}")
include_directories("${PROJECT_SOURCE_DIR}/tasks")
include_directories("${PROJECT_SOURCE_DIR}/observables")
include_directories("${PROJECT_SOURCE_DIR}/analysis")
include_directories("${PROJECT_SOURCE_DIR}/data_handling")
include_directories("${PROJECT_SOURCE_DIR}/fitting")
include_directories("${PROJECT_SOURCE_DIR}/plotting")
include_directories("${PROJECT_SOURCE_DIR}/pysigmond")


# === LIBRARY DETECTION ===

# HDF5 (required) - Use find_package with HDF5_ROOT support
find_package(HDF5 COMPONENTS C REQUIRED)
if(HDF5_FOUND)
    message(STATUS "HDF5 include dirs: ${HDF5_INCLUDE_DIRS}")
    if(DEFINED HDF5_ROOT)
        message(STATUS "HDF5_ROOT was set to: ${HDF5_ROOT}")
    endif()
else()
    message(FATAL_ERROR "HDF5 not found. Please specify root_dir in sigmond.toml or install HDF5 development packages.")
endif()

# Set HDF5 includes globally for this project since multiple modules need it
include_directories(${HDF5_INCLUDE_DIRS})

# LAPACK (required)
if(APPLE)
    # Try Accelerate framework first on macOS
    find_library(ACCELERATE_FRAMEWORK Accelerate HINTS ${SIGMOND_ACCELERATE_FRAMEWORK_DIR})
    if(ACCELERATE_FRAMEWORK)
        set(LAPACK_FOUND TRUE)
        set(LAPACK_LIBRARIES ${ACCELERATE_FRAMEWORK})
        set(BLAS_LIBRARIES   ${ACCELERATE_FRAMEWORK})
        add_library(LAPACK::LAPACK INTERFACE IMPORTED)
        set_target_properties(LAPACK::LAPACK PROPERTIES
            INTERFACE_LINK_LIBRARIES "${ACCELERATE_FRAMEWORK}")
        message(STATUS "Found LAPACK via Accelerate framework: ${ACCELERATE_FRAMEWORK}")
    endif()
endif()

if(NOT LAPACK_FOUND)
    # Find BLAS first since LAPACK depends on it
    set(BLA_VENDOR OpenBLAS)
    find_package(BLAS REQUIRED)
    find_package(LAPACK REQUIRED)
endif()

# MINUIT2 (optional) 
# check_manual_paths(MINUIT2)
if(ENABLE_MINUIT)
    find_path(MINUIT2_INCLUDE_DIR
        NAMES Minuit2/FCNBase.h
        HINTS ${SIGMOND_MINUIT2_INCLUDE_DIR}
        PATH_SUFFIXES Minuit2
    )
    find_library(MINUIT2_LIBRARY
        NAMES Minuit2 minuit2
        HINTS ${SIGMOND_MINUIT2_LIBRARY_DIR}
    )
    if(MINUIT2_INCLUDE_DIR AND MINUIT2_LIBRARY)
        set(MINUIT2_FOUND TRUE)
        add_library(Minuit2::Minuit2 UNKNOWN IMPORTED)
        set_target_properties(Minuit2::Minuit2 PROPERTIES
            IMPORTED_LOCATION             "${MINUIT2_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${MINUIT2_INCLUDE_DIR}"
        )
        message(STATUS "Found standalone Minuit2: ${MINUIT2_LIBRARY}")
        message(STATUS "Minuit2 include dirs: ${MINUIT2_INCLUDE_DIR}")
    else()
        find_package(ROOT QUIET COMPONENTS Minuit2)
        if(TARGET ROOT::Minuit2)
            set(MINUIT2_FOUND TRUE)
            add_library(Minuit2::Minuit2 ALIAS ROOT::Minuit2)
            message(STATUS "Using Minuit2 from ROOT (ROOT::Minuit2)")
        endif()
    endif()
    if(NOT MINUIT2_FOUND)
        message(FATAL_ERROR "Minuit2 not found. Please specify include_dir and library_dir in sigmond.toml or install Minuit2 development packages.")
    endif()
endif()

# GRACE (optional)
if(ENABLE_GRACE)
    find_path(GRACE_INCLUDE_DIR
        NAMES grace_np.h grace.h
        HINTS
            ${SIGMOND_GRACE_INCLUDE_DIR}
    )
    find_library(GRACE_LIBRARY
        NAMES grace_np grace
        HINTS
            ${SIGMOND_GRACE_LIBRARY_DIR}
    )
    if(GRACE_LIBRARY AND GRACE_INCLUDE_DIR)
        set(GRACE_FOUND TRUE)
        add_library(Grace::Grace UNKNOWN IMPORTED)
        set_target_properties(Grace::Grace PROPERTIES
            IMPORTED_LOCATION             "${GRACE_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${GRACE_INCLUDE_DIR}"
        )
        message(STATUS "Found GRACE: ${GRACE_LIBRARY}")
        message(STATUS "GRACE include dirs: ${GRACE_INCLUDE_DIR}")
    else()
        message(FATAL_ERROR "GRACE not found. Please specify include_dir and library_dir in sigmond.toml or install GRACE development packages.")
    endif()
endif()

# === LINKING FUNCTIONS ===

# Standard library linking function
function(sigmond_link_libraries target_name)
    # Required libraries
    target_link_libraries(${target_name} PRIVATE HDF5::HDF5)
    
    # If we have an imported LAPACK target, it should carry what’s needed (e.g., Accelerate)
    if(TARGET LAPACK::LAPACK)
        target_link_libraries(${target_name} PRIVATE LAPACK::LAPACK)
    else()
        # Otherwise, add BLAS then LAPACK from variables or fall back
        if(BLAS_LIBRARIES)
        target_link_libraries(${target_name} PRIVATE ${BLAS_LIBRARIES})
        elseif(TARGET BLAS::BLAS)
        target_link_libraries(${target_name} PRIVATE BLAS::BLAS)
        else()
        target_link_libraries(${target_name} PRIVATE -lblas)
        endif()

        if(LAPACK_LIBRARIES)
        target_link_libraries(${target_name} PRIVATE ${LAPACK_LIBRARIES})
        else()
        target_link_libraries(${target_name} PRIVATE -llapack)
        endif()
    endif()

    if(MINUIT2_FOUND)
        target_link_libraries(${target_name} PRIVATE Minuit2::Minuit2)
    endif()
    
    # Platform-specific linking for Fortran runtime
    # if(NOT APPLE)
    #     target_link_libraries(${target_name} PRIVATE -lgfortran)
    # endif()
endfunction()

add_subdirectory(analysis)
add_subdirectory(data_handling)
add_subdirectory(fitting)
add_subdirectory(observables)
add_subdirectory(plotting)
add_subdirectory(tasks)

# Apply external library linking to all component libraries
sigmond_link_libraries(analysis)
sigmond_link_libraries(data_handling)
sigmond_link_libraries(observables)
sigmond_link_libraries(tasks)
sigmond_link_libraries(fitting)
sigmond_link_libraries(plotting)

if(GRACE_FOUND)
    target_link_libraries(plotting PRIVATE Grace::Grace)
    target_include_directories(plotting PRIVATE ${GRACE_INCLUDE_DIR})
endif()


#link_libraries(tasks_libs data_handling_lib analysis_libs fitting_libs observables_libs plotting_libs)

set_target_properties(analysis PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(data_handling PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(fitting PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(observables PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(plotting PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)
set_target_properties(tasks PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)

if(APPLE)
    set_target_properties(analysis PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(data_handling PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(fitting PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(observables PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(plotting PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(tasks PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
endif()

pybind11_add_module(sigmond pybind/pysigmond.cc)

# target_link_libraries(sigmond PUBLIC data_handling_libs analysis_libs tasks_libs fitting_libs observables_libs plotting_libs) 
target_link_libraries(sigmond PUBLIC data_handling )
target_link_libraries(sigmond PUBLIC analysis )
target_link_libraries(sigmond PUBLIC tasks )
target_link_libraries(sigmond PUBLIC fitting )
target_link_libraries(sigmond PUBLIC observables )
target_link_libraries(sigmond PUBLIC plotting)

# Link external libraries
sigmond_link_libraries(sigmond)

target_compile_definitions(sigmond PRIVATE VERSION_INFO=${VERSION_INFO})

# Set output directory for the pybind11 module
set_target_properties(sigmond PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/sigmond)

# Build executables (optional)
option(SKIP_SIGMOND_BATCH "Skip building sigmond batch executable" OFF)
option(SKIP_SIGMOND_QUERY "Skip building sigmond_query executable" OFF)

if(NOT SKIP_SIGMOND_BATCH)
    add_executable(sigmond_batch apps/sigmond.cc)
    target_link_libraries(sigmond_batch PRIVATE 
        tasks analysis data_handling fitting observables plotting)
    sigmond_link_libraries(sigmond_batch)
    install(TARGETS sigmond_batch DESTINATION bin)
endif()

if(NOT SKIP_SIGMOND_QUERY)
    add_executable(sigmond_query apps/sigmond_query.cc)
    target_link_libraries(sigmond_query PRIVATE 
        data_handling observables tasks analysis)
    sigmond_link_libraries(sigmond_query)
    install(TARGETS sigmond_query DESTINATION bin)
endif()
