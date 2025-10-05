set(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")
cmake_minimum_required(VERSION 3.15)
project(sigmond)

set(BUILD_SHARED_LIBS OFF)
# Enable Position Independent Code for static libraries
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ccache for faster compilation
find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE ${CCACHE_PROGRAM})
    message(STATUS "Using ccache for compilation: ${CCACHE_PROGRAM}")
else()
    message(STATUS "ccache not found, not using it.")
endif()

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
include_directories("src/sigmond/cpp/tasks")
include_directories("src/sigmond/cpp/observables")
include_directories("src/sigmond/cpp/analysis")
include_directories("src/sigmond/cpp/data_handling")
include_directories("src/sigmond/cpp/fitting")
include_directories("src/sigmond/cpp/plotting")
include_directories("src/sigmond/cpp/pybind")

# Load configuration from sigmond.toml
set(_sigmond_cache "${CMAKE_CURRENT_SOURCE_DIR}/_sigmond_cache_init.cmake")
execute_process(
        COMMAND "${Python_EXECUTABLE}" -m configure write-cache -o "${_sigmond_cache}"
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        RESULT_VARIABLE _sigmond_rc
)
if(NOT _sigmond_rc EQUAL 0)
    message(FATAL_ERROR "configure.py write-cache failed (rc=${_sigmond_rc})")
endif()

include("${_sigmond_cache}")  # seeds cache before find_package calls

# Apply compiler definitions based on CMake variables from configuration

# Precision setting
if(NOT DEFINED PRECISION OR PRECISION STREQUAL "double")
    add_compile_definitions(DOUBLEPRECISION)
    message(STATUS "Using double precision")
else()
    add_compile_definitions(SINGLEPRECISION)
    message(STATUS "Using single precision")
endif()

# Numbers setting
if(NOT DEFINED NUMBERS OR NUMBERS STREQUAL "complex")
    add_compile_definitions(COMPLEXNUMBERS)
    message(STATUS "Using complex numbers")
else()
    add_compile_definitions(REALNUMBERS)
    message(STATUS "Using real numbers")
endif()

# Default file format setting - only set DEFAULT_FSTREAM if explicitly requested
# If not set, HDF5 is the default (no compile definition needed)
if(DEFINED DEFAULT_FILE_FORMAT AND DEFAULT_FILE_FORMAT STREQUAL "fstream")
    add_compile_definitions(DEFAULT_FSTREAM)
    message(STATUS "Using fstream as default file format")
else()
    message(STATUS "Using HDF5 as default file format")
endif()

# Always enable these features for Sigmond
add_compile_definitions(XML)
add_compile_definitions(LAPACK)

# Set default ensembles file from configuration
if(NOT DEFINED DEFAULTENSFILE OR DEFAULTENSFILE STREQUAL "")
    set(DEFAULTENSFILE "${CMAKE_CURRENT_SOURCE_DIR}/ensembles.xml")
endif()
add_compile_definitions(DEFAULTENSFILE="${DEFAULTENSFILE}")
message(STATUS "Using default ensembles file: ${DEFAULTENSFILE}")

# === LIBRARY DETECTION ===

# HDF5 (required) - Use find_package with HDF5_ROOT support
find_package(HDF5 COMPONENTS C HL REQUIRED)
if(HDF5_FOUND)
    # if the hdf5 include dir is not set, get it from the root
    if(NOT HDF5_INCLUDE_DIRS AND DEFINED HDF5_ROOT)
        set(HDF5_INCLUDE_DIRS "${HDF5_ROOT}/include")
    endif()
    message(STATUS "HDF5 include dirs: ${HDF5_INCLUDE_DIRS}")
    if(DEFINED HDF5_ROOT)
        message(STATUS "HDF5_ROOT was set to: ${HDF5_ROOT}")
    endif()
else()
    message(FATAL_ERROR "HDF5 not found. Please specify root_dir in sigmond.toml or install HDF5 development packages.")
endif()

# Set HDF5 includes globally for this project since multiple modules need it
include_directories(${HDF5_INCLUDE_DIRS})
add_compile_definitions(HDF5)

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
if(NOT NO_MINUIT AND ENABLE_MINUIT)
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
        message(WARNING "Minuit2 not found. Will compile with NO_MINUIT flag.")
        add_compile_definitions(NO_MINUIT)
    endif()
else()
    message(STATUS "Minuit2 disabled by configuration")
    add_compile_definitions(NO_MINUIT)
endif()

# GRACE (optional)
if(ENABLE_GRACE)
    find_path(GRACE_INCLUDE_DIR
            NAMES grace_np.h grace.h
            HINTS ${SIGMOND_GRACE_INCLUDE_DIR}
    )
    find_library(GRACE_LIBRARY
            NAMES grace_np grace
            HINTS ${SIGMOND_GRACE_LIBRARY_DIR}
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
        add_compile_definitions(GRACE)
    else()
        message(WARNING "GRACE not found. Will compile without GRACE support.")
        add_compile_definitions(NOGRACE)
    endif()
else()
    message(STATUS "GRACE disabled by configuration")
    add_compile_definitions(NOGRACE)
endif()

# === LINKING FUNCTIONS ===

# Standard library linking function
function(sigmond_link_libraries target_name)
    # Required libraries - link HDF5 with explicit library names
    if(HDF5_LIBRARIES)
        target_link_libraries(${target_name} PUBLIC ${HDF5_LIBRARIES})
    else()
        # Fallback to explicit library linking
        target_link_libraries(${target_name} PUBLIC -lhdf5 -lhdf5_hl)
    endif()

    # If we have an imported LAPACK target, it should carry what's needed (e.g., Accelerate)
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

    # Optional libraries
    if(MINUIT2_FOUND)
        target_link_libraries(${target_name} PRIVATE Minuit2::Minuit2)
    endif()

    if(GRACE_FOUND)
        target_link_libraries(${target_name} PRIVATE Grace::Grace)
    endif()

endfunction()

# Build component libraries
add_subdirectory(src/sigmond/cpp/analysis)
add_subdirectory(src/sigmond/cpp/data_handling)
add_subdirectory(src/sigmond/cpp/fitting)
add_subdirectory(src/sigmond/cpp/observables)
add_subdirectory(src/sigmond/cpp/plotting)
add_subdirectory(src/sigmond/cpp/tasks)

# Apply external library linking to all component libraries
sigmond_link_libraries(analysis)
sigmond_link_libraries(data_handling)
sigmond_link_libraries(observables)
sigmond_link_libraries(plotting)
sigmond_link_libraries(tasks)
sigmond_link_libraries(fitting)

# Keep component libs in the build tree (not installed to the wheel)
set_target_properties(analysis data_handling fitting observables plotting tasks
  PROPERTIES
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

if(APPLE)
    set_target_properties(analysis PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(data_handling PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(fitting PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(observables PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(plotting PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    set_target_properties(tasks PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
endif()

# Python extension: sigmond.*
pybind11_add_module(sigmond src/sigmond/cpp/pybind/pysigmond.cc)
target_link_libraries(sigmond PRIVATE
  tasks data_handling fitting observables plotting analysis)
sigmond_link_libraries(sigmond)
target_compile_definitions(sigmond PRIVATE VERSION_INFO=${VERSION_INFO})

# rpath for macOS/Linux
set_target_properties(sigmond PROPERTIES
  BUILD_RPATH "@loader_path"
  INSTALL_RPATH "@loader_path")

if (NOT APPLE)
    target_link_options(sigmond PRIVATE -Wl,--no-as-needed)
endif()

# Install the extension into the wheel's platlib/ (top level, not in subdirectory)
install(TARGETS sigmond
  LIBRARY DESTINATION "${SKBUILD_PLATLIB_DIR}"
  ARCHIVE DESTINATION "${SKBUILD_PLATLIB_DIR}"
  RUNTIME DESTINATION "${SKBUILD_PLATLIB_DIR}")  # Windows .pyd

# Build executables (optional)
if(NOT SKIP_SIGMOND_BATCH)
  add_executable(sigmond_batch_cli src/sigmond/cpp/apps/sigmond.cc)
  target_link_libraries(sigmond_batch_cli PRIVATE
    tasks analysis data_handling fitting observables plotting)
  sigmond_link_libraries(sigmond_batch_cli)
  set_target_properties(sigmond_batch_cli PROPERTIES OUTPUT_NAME "sigmond_batch")
  # Install native binary to the environment's Scripts/bin via scikit-build-core
  # if the dir is defined, else put in build dir
  if (DEFINED SKBUILD_SCRIPTS_DIR)
      set(BATCH_BUILD_DIR "${SKBUILD_SCRIPTS_DIR}")
  else()
      set(BATCH_BUILD_DIR "${SIGMOND_BATCH_INSTALL_DIR}")
  endif()
  message(STATUS "Installing sigmond_batch binary to: ${BATCH_BUILD_DIR}")
  install(TARGETS sigmond_batch_cli RUNTIME DESTINATION "${SKBUILD_SCRIPTS_DIR}")
  if (NOT APPLE)
      target_link_options(sigmond_batch_cli PRIVATE -Wl,--no-as-needed)
  endif()
endif()

if(NOT SKIP_SIGMOND_QUERY)
  add_executable(sigmond_query_cli src/sigmond/cpp/apps/sigmond_query.cc)
  target_link_libraries(sigmond_query_cli PRIVATE
    data_handling observables tasks analysis)
  sigmond_link_libraries(sigmond_query_cli)
  set_target_properties(sigmond_query_cli PROPERTIES OUTPUT_NAME "sigmond_query")
  # Install native binary to the environment's Scripts/bin via scikit-build-core
  if (DEFINED SKBUILD_SCRIPTS_DIR)
      set(QUERY_BUILD_DIR "${SKBUILD_SCRIPTS_DIR}")
  else()
      set(QUERY_BUILD_DIR "${SIGMOND_QUERY_INSTALL_DIR}")
  endif()
  message(STATUS "Installing sigmond_query binary to: ${QUERY_BUILD_DIR}")
  install(TARGETS sigmond_query_cli RUNTIME DESTINATION "${SKBUILD_SCRIPTS_DIR}")
  if (NOT APPLE)
      target_link_options(sigmond_query_cli PRIVATE -Wl,--no-as-needed)
  endif()
endif()

# Testing
if(ENABLE_TESTING)
    message(STATUS "Building tests")
    enable_testing()
    # add_subdirectory(tests)  # Uncomment when tests directory exists
endif()