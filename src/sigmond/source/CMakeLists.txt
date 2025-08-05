set(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")
project(sigmond) #CMAKE_CXX_COMPILER set this using python
cmake_minimum_required(VERSION 3.4...3.18)
set(CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}" ${CMAKE_MODULE_PATH})

#set(CMAKE_BUILD_TYPE Debug)

find_package(Python COMPONENTS Interpreter Development)

message("${Python_LIBRARY_DIRS}")
find_package(pybind11 REQUIRED 
                      HINTS "${Python_LIBRARY_DIRS}/python${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}/site-packages"
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

# set the project name
project(Sigmond VERSION 1.0)

# === SIGMOND CONFIGURATION SYSTEM ===

# Debug configuration
function(sigmond_debug_config)
    message(STATUS "=== Sigmond Build Configuration ===")
    message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
    message(STATUS "C++ Compiler: ${CMAKE_CXX_COMPILER}")
    message(STATUS "C++ Flags: ${CMAKE_CXX_FLAGS}")
    message(STATUS "Skip Query: ${SKIP_SIGMOND_QUERY}")
    message(STATUS "Skip Batch: ${SKIP_SIGMOND_BATCH}")
    message(STATUS "Platform: ${CMAKE_SYSTEM_NAME}")
endfunction()

# Unified library finder with cross-platform support
function(sigmond_find_library LIB_NAME)
    # Parse arguments: HEADER library_names... [REQUIRED] [APPLE_FRAMEWORK framework_name]
    cmake_parse_arguments(ARG "REQUIRED" "HEADER;APPLE_FRAMEWORK" "LIBRARIES" ${ARGN})
    
    string(TOUPPER ${LIB_NAME} LIB_UPPER)
    set(${LIB_UPPER}_FOUND FALSE PARENT_SCOPE)
    
    message(STATUS "--- Finding ${LIB_NAME} library ---")
    
    # Check for manual configuration
    set(MANUAL_INCLUDE_VAR "SIGMOND_${LIB_UPPER}_INCLUDE_DIR")
    set(MANUAL_LIBRARY_VAR "SIGMOND_${LIB_UPPER}_LIBRARY_DIR")
    
    # Manual path configuration
    if(DEFINED ${MANUAL_LIBRARY_VAR})
        message(STATUS "Using manual paths for ${LIB_NAME}")
        if(DEFINED ${MANUAL_INCLUDE_VAR})
            message(STATUS "  Include dirs: ${${MANUAL_INCLUDE_VAR}}")
        endif()
        message(STATUS "  Library dirs: ${${MANUAL_LIBRARY_VAR}}")
        
        # Try to find each library in the specified directories
        set(FOUND_LIBRARIES)
        foreach(lib_name ${ARG_LIBRARIES})
            find_library(${LIB_UPPER}_${lib_name}_LIB ${lib_name} HINTS ${${MANUAL_LIBRARY_VAR}} NO_DEFAULT_PATH)
            if(${LIB_UPPER}_${lib_name}_LIB)
                list(APPEND FOUND_LIBRARIES ${${LIB_UPPER}_${lib_name}_LIB})
            endif()
        endforeach()
        
        # Find header if specified
        if(ARG_HEADER AND DEFINED ${MANUAL_INCLUDE_VAR})
            find_path(${LIB_UPPER}_INCLUDE_DIR ${ARG_HEADER} HINTS ${${MANUAL_INCLUDE_VAR}} NO_DEFAULT_PATH)
        endif()
        
        if(FOUND_LIBRARIES)
            set(${LIB_UPPER}_FOUND TRUE PARENT_SCOPE)
            set(${LIB_UPPER}_LIBRARIES ${FOUND_LIBRARIES} PARENT_SCOPE)
            sigmond_create_imported_target(${LIB_NAME} "${FOUND_LIBRARIES}" "${${LIB_UPPER}_INCLUDE_DIR}")
            message(STATUS "Found ${LIB_NAME} (manual): ${FOUND_LIBRARIES}")
            return()
        endif()
    endif()
    
    # Auto-detection
    message(STATUS "Auto-detecting ${LIB_NAME}")
    set(${LIB_UPPER}_AUTO_DETECT TRUE PARENT_SCOPE)
endfunction()

# Create imported target
function(sigmond_create_imported_target LIB_NAME LIBRARIES INCLUDE_DIR)
    string(TOUPPER ${LIB_NAME} LIB_UPPER)
    
    if(NOT TARGET ${LIB_NAME}::${LIB_NAME})
        add_library(${LIB_NAME}::${LIB_NAME} INTERFACE IMPORTED)
        if(LIBRARIES)
            set_target_properties(${LIB_NAME}::${LIB_NAME} PROPERTIES
                INTERFACE_LINK_LIBRARIES "${LIBRARIES}")
        endif()
        if(INCLUDE_DIR)
            set_target_properties(${LIB_NAME}::${LIB_NAME} PROPERTIES
                INTERFACE_INCLUDE_DIRECTORIES "${INCLUDE_DIR}")
        endif()
    endif()
endfunction()

# macOS-specific framework finder
function(sigmond_find_macos_framework FRAMEWORK_NAME)
    if(APPLE)
        string(TOUPPER ${FRAMEWORK_NAME} FRAMEWORK_UPPER)
        set(MANUAL_FRAMEWORK_VAR "SIGMOND_${FRAMEWORK_UPPER}_FRAMEWORK_DIR")
        
        if(DEFINED ${MANUAL_FRAMEWORK_VAR})
            find_library(${FRAMEWORK_UPPER}_FRAMEWORK ${FRAMEWORK_NAME} 
                HINTS ${${MANUAL_FRAMEWORK_VAR}} NO_DEFAULT_PATH)
        else()
            find_library(${FRAMEWORK_UPPER}_FRAMEWORK ${FRAMEWORK_NAME})
        endif()
        
        if(${FRAMEWORK_UPPER}_FRAMEWORK)
            set(${FRAMEWORK_UPPER}_FOUND TRUE PARENT_SCOPE)
            message(STATUS "Found ${FRAMEWORK_NAME} framework: ${${FRAMEWORK_UPPER}_FRAMEWORK}")
        endif()
    endif()
endfunction()

sigmond_debug_config()

# === LIBRARY DETECTION ===

# HDF5 (required)
sigmond_find_library(HDF5 HEADER "hdf5.h" LIBRARIES "hdf5" REQUIRED)
if(HDF5_AUTO_DETECT)
    find_package(HDF5 COMPONENTS C QUIET)
    if(HDF5_FOUND)
        sigmond_create_imported_target(HDF5 "${HDF5_LIBRARIES}" "${HDF5_INCLUDE_DIRS}")
        message(STATUS "Found HDF5 (auto-detect): ${HDF5_LIBRARIES}")
    endif()
endif()

if(NOT HDF5_FOUND)
    message(FATAL_ERROR "HDF5 not found. Please specify paths in sigmond.toml or install HDF5 development packages.")
endif()

# LAPACK (required) - Cross-platform with macOS Accelerate support
sigmond_find_library(LAPACK LIBRARIES "lapack" "blas" REQUIRED)
if(LAPACK_AUTO_DETECT)
    if(APPLE)
        # Try Accelerate framework first on macOS
        sigmond_find_macos_framework(Accelerate)
        if(ACCELERATE_FOUND)
            sigmond_create_imported_target(LAPACK "${ACCELERATE_FRAMEWORK}" "")
            set(LAPACK_FOUND TRUE)
            message(STATUS "Found LAPACK via Accelerate framework: ${ACCELERATE_FRAMEWORK}")
        endif()
    endif()
    
    # Fallback to standard LAPACK detection
    if(NOT LAPACK_FOUND)
        find_package(LAPACK QUIET)
        if(LAPACK_FOUND)
            sigmond_create_imported_target(LAPACK "${LAPACK_LIBRARIES}" "")
            message(STATUS "Found LAPACK (auto-detect): ${LAPACK_LIBRARIES}")
        endif()
    endif()
endif()

if(NOT LAPACK_FOUND)
    message(FATAL_ERROR "LAPACK not found. Please specify paths in sigmond.toml or install LAPACK development packages.")
endif()

# MINUIT2 (optional)
sigmond_find_library(MINUIT2 HEADER "Minuit2/FCNBase.h" LIBRARIES "Minuit2")
if(MINUIT2_AUTO_DETECT)
    find_package(PkgConfig QUIET)
    if(PKG_CONFIG_FOUND)
        pkg_check_modules(MINUIT2 QUIET minuit2)
        if(MINUIT2_FOUND)
            sigmond_create_imported_target(MINUIT2 "${MINUIT2_LIBRARIES}" "${MINUIT2_INCLUDE_DIRS}")
            message(STATUS "Found Minuit2 (pkg-config): ${MINUIT2_LIBRARIES}")
        endif()
    endif()
endif()

# GRACE (optional)
sigmond_find_library(GRACE HEADER "grace_np.h" LIBRARIES "grace_np")

# === LIBRARY SUMMARY ===
message(STATUS "=== Library Detection Summary ===")
message(STATUS "HDF5_FOUND: ${HDF5_FOUND}")
message(STATUS "LAPACK_FOUND: ${LAPACK_FOUND}")
message(STATUS "MINUIT2_FOUND: ${MINUIT2_FOUND}")
message(STATUS "GRACE_FOUND: ${GRACE_FOUND}")
message(STATUS "=====================================")

# === LINKING FUNCTIONS ===

# Cross-platform library linking with automatic dependency resolution
function(sigmond_link_libraries target_name)
    # Always required libraries
    target_link_libraries(${target_name} PRIVATE HDF5::HDF5 LAPACK::LAPACK)
    
    # Optional libraries (only if found and enabled)
    if(MINUIT2_FOUND)
        target_link_libraries(${target_name} PRIVATE MINUIT2::MINUIT2)
        message(STATUS "${target_name}: Linked Minuit2")
    endif()
    
    if(GRACE_FOUND)
        target_link_libraries(${target_name} PRIVATE GRACE::GRACE)
        message(STATUS "${target_name}: Linked Grace")
    endif()
    
    # Platform-specific Fortran runtime linking
    if(NOT APPLE OR NOT ACCELERATE_FOUND)
        # Link Fortran runtime for LAPACK (not needed with macOS Accelerate)
        target_link_libraries(${target_name} PRIVATE -lgfortran)
    endif()
    
    message(STATUS "${target_name}: Configured with all required libraries")
endfunction()

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

target_link_libraries(tasks PUBLIC LAPACK::LAPACK)
if(APPLE)
    # On macOS, gfortran usually not needed if using system LAPACK/Accelerate
    find_library(ACCELERATE_FRAMEWORK Accelerate)
    if(NOT ACCELERATE_FRAMEWORK)
        target_link_libraries(tasks PUBLIC -lgfortran)
    endif()
else()
    # Linux: LAPACK usually needs gfortran
    target_link_libraries(tasks PUBLIC -lgfortran)
endif()
target_link_libraries(data_handling PRIVATE HDF5::HDF5)

target_compile_definitions(sigmond PRIVATE VERSION_INFO=${VERSION_INFO})

# --- Build sigmond batch executable (unless skipped) ---
option(SKIP_SIGMOND_BATCH "Skip building sigmond batch executable" OFF)
message(STATUS "=== Executable Build Configuration ===")
message(STATUS "SKIP_SIGMOND_BATCH: ${SKIP_SIGMOND_BATCH}")
if(NOT SKIP_SIGMOND_BATCH)
    message(STATUS "Building sigmond_batch executable")
    # Source files for sigmond batch executable
    set(SIGMOND_MAIN_SRCS
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/sigmond.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/scalar_defs.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/single_pivot.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/rolling_pivot.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/stopwatch.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_check.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_fit.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_get_from_pivot.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_obsfunc.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_plot.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_print.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_rebin.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_rotate_corrs.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/task_utils.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/tasks/xml_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/analysis/bootstrapper.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/analysis/histogram.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/analysis/matrix.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/analysis/mc_estimate.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/analysis/mcobs_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/analysis/sampling_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/bins_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/byte_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/corr_data_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/ensemble_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/filelist_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/io_handler_fstream.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/io_handler_hdf5.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/obs_get_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/data_handling/vev_data_handler.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/basic_laph_operator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/diag_corr_set.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/correlator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/correlator_matrix_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/encoder.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/gen_irrep_operator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/mcobs_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/momenta.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/observables/operator_info.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/plotting/create_plots.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/plotting/grace_plot.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/chisq_anisotropy.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/chisq_base.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/chisq_disp.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/chisq_fit.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/chisq_tcorr.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/chisq_logtcorr.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/lmder.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/minimizer.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/minpack.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/model_logtcorr.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/model_tcorr.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/nl2sol.cc
        ${CMAKE_CURRENT_SOURCE_DIR}/fitting/prior.cc
    )

    add_executable(sigmond_batch ${SIGMOND_MAIN_SRCS})
    sigmond_link_libraries(sigmond_batch)
    install(TARGETS sigmond_batch DESTINATION bin)
    message(STATUS "sigmond_batch executable will be built and installed")
else()
    message(STATUS "sigmond_batch executable is SKIPPED")
endif()

# --- Build sigmond_query executable (unless skipped) ---
option(SKIP_SIGMOND_QUERY "Skip building sigmond_query executable" OFF)
message(STATUS "SKIP_SIGMOND_QUERY: ${SKIP_SIGMOND_QUERY}")
if(NOT SKIP_SIGMOND_QUERY)
    message(STATUS "Building sigmond_query executable")
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
    sigmond_link_libraries(sigmond_query)
    install(TARGETS sigmond_query DESTINATION bin)
    message(STATUS "sigmond_query executable will be built and installed")
else()
    message(STATUS "sigmond_query executable is SKIPPED")
endif()

# Final build summary
message(STATUS "=== Final Build Summary ===")
message(STATUS "Targets to build:")
if(TARGET sigmond)
    message(STATUS "  - sigmond (Python extension)")
endif()
if(TARGET sigmond_batch)
    message(STATUS "  - sigmond_batch (batch executable)")
endif()
if(TARGET sigmond_query)
    message(STATUS "  - sigmond_query (query executable)")
endif()
message(STATUS "===============================")
