cmake_minimum_required(VERSION 3.15) # Using a reasonably modern version
project(SigmondProject CXX)

# --- Standard and Compiler Options ---
set(CMAKE_CXX_STANDARD 11) # Default based on last active COMMONFLAGS in Makefile.inc
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF) # Good practice

# Option to use C++17 (matches one of the COMMONFLAGS)
option(SIGMOND_USE_CXX17 "Build with C++17 standard" OFF)
if(SIGMOND_USE_CXX17)
    set(CMAKE_CXX_STANDARD 17)
endif()

# --- Project Options (derived from Makefile.inc defines and choices) ---
option(SIGMOND_USE_SINGLE_PRECISION "Use single precision for data files (default is double)" OFF)
option(SIGMOND_USE_REAL_NUMBERS "Use real numbers for data types (default is complex)" OFF)
option(SIGMOND_USE_FSTREAM_DEFAULT "Use fstreams as default I/O (default is HDF5)" OFF)
option(SIGMOND_DISABLE_MINUIT "Disable Minuit2 dependency and related features" ON)

set(KNOWN_ENSEMBLES_FILE_PATH "" CACHE FILEPATH "Path to the known ensembles XML file (e.g., ensembles_simon.xml)")
if(NOT KNOWN_ENSEMBLES_FILE_PATH)
    message(STATUS "KNOWN_ENSEMBLES_FILE_PATH is not set. Please configure it (e.g., using -DKNOWN_ENSEMBLES_FILE_PATH=/path/to/file.xml)")
endif()

# --- General Compile Options ---
add_compile_options(-Wall -O3)

# --- Compiler Definitions based on Options ---
# For PRECISION: Defines SINGLEPRECISION or DOUBLEPRECISION directly
if(SIGMOND_USE_SINGLE_PRECISION)
    add_compile_definitions(SINGLEPRECISION)
else()
    add_compile_definitions(DOUBLEPRECISION)
endif()

# For NUMBER TYPE: Defines REALNUMBERS or COMPLEXNUMBERS directly
if(SIGMOND_USE_REAL_NUMBERS)
    add_compile_definitions(REALNUMBERS)
else()
    add_compile_definitions(COMPLEXNUMBERS)
endif()

# For IOTYPE: Defines DEFAULT_FSTREAM or DEFAULT_HDF5 directly
if(SIGMOND_USE_FSTREAM_DEFAULT)
    add_compile_definitions(DEFAULT_FSTREAM)
else()
    add_compile_definitions(DEFAULT_HDF5)
    add_compile_definitions(H5_USE_110_API) # This was specifically tied to HDF5 in Makefile.inc
endif()

# For KNOWN_ENSEMBLES_FILE: Defines DEFAULTENSFILE as a string literal path
if(KNOWN_ENSEMBLES_FILE_PATH AND EXISTS "${KNOWN_ENSEMBLES_FILE_PATH}")
    add_compile_definitions("DEFAULTENSFILE=\"${KNOWN_ENSEMBLES_FILE_PATH}\"")
else()
    if(KNOWN_ENSEMBLES_FILE_PATH) # Path was given but doesn't exist
        message(WARNING "KNOWN_ENSEMBLES_FILE_PATH '${KNOWN_ENSEMBLES_FILE_PATH}' does not exist.")
    endif()
    add_compile_definitions("DEFAULTENSFILE=\"\"") # Define as empty string if not provided or invalid
endif()

if(SIGMOND_DISABLE_MINUIT)
    add_compile_definitions(NO_MINUIT)
endif()

# --- Finding Dependencies ---
# Grace
find_path(GRACE_INCLUDE_DIR NAMES grace_np.h
    HINTS ENV GRACE_INCDIR "${GRACE_DIR}/include" /usr/include /usr/local/include)
find_library(GRACE_LIBRARY NAMES grace_np
    HINTS ENV GRACE_LIBDIR "${GRACE_DIR}/lib" "${GRACE_DIR}/lib64" /usr/lib /usr/local/lib /usr/local/lib64)

set(GRACE_FOUND FALSE)
if(GRACE_INCLUDE_DIR AND GRACE_LIBRARY)
    set(GRACE_FOUND TRUE)
    add_library(Grace::Grace UNKNOWN IMPORTED)
    set_target_properties(Grace::Grace PROPERTIES
        IMPORTED_LOCATION "${GRACE_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${GRACE_INCLUDE_DIR}")
    message(STATUS "Found Grace: ${GRACE_LIBRARY} (include: ${GRACE_INCLUDE_DIR})")
else()
    message(STATUS "Grace not found (GRACE_INCLUDE_DIR: ${GRACE_INCLUDE_DIR}, GRACE_LIBRARY: ${GRACE_LIBRARY}). Grace-dependent features might not build or link correctly.")
endif()

# Minuit2
if(NOT SIGMOND_DISABLE_MINUIT)
    find_package(ROOT QUIET)
    find_package(Minuit2 QUIET)
    if(NOT Minuit2_FOUND)
        find_path(MINUIT2_INCLUDE_DIR NAMES Minuit2/Minuit2Minimizer.h
            HINTS ENV MINUIT2_INCDIR "${Minuit2_DIR}/include" /usr/include/Minuit2 /usr/include /usr/local/include)
        find_library(MINUIT2_LIBRARY NAMES Minuit2
            HINTS ENV MINUIT2_LIBDIR "${Minuit2_DIR}/lib" /usr/lib /usr/local/lib)
        find_library(MINUIT2_MATH_LIBRARY NAMES Minuit2Math
            HINTS ENV MINUIT2_LIBDIR "${Minuit2_DIR}/lib" /usr/lib /usr/local/lib)

        if(MINUIT2_INCLUDE_DIR AND MINUIT2_LIBRARY)
            set(Minuit2_FOUND TRUE)
            add_library(Minuit2::Minuit2 INTERFACE IMPORTED GLOBAL)
            set_target_properties(Minuit2::Minuit2 PROPERTIES
                INTERFACE_INCLUDE_DIRECTORIES "${MINUIT2_INCLUDE_DIR}")
            target_link_libraries(Minuit2::Minuit2 INTERFACE "${MINUIT2_LIBRARY}")
            if(MINUIT2_MATH_LIBRARY)
                target_link_libraries(Minuit2::Minuit2 INTERFACE "${MINUIT2_MATH_LIBRARY}")
                message(STATUS "Found Minuit2 (manual): ${MINUIT2_LIBRARY} and Minuit2Math: ${MINUIT2_MATH_LIBRARY} (include: ${MINUIT2_INCLUDE_DIR})")
            else()
                message(STATUS "Found Minuit2 (manual): ${MINUIT2_LIBRARY} (include: ${MINUIT2_INCLUDE_DIR}). Minuit2Math not found.")
            endif()
        else()
            message(WARNING "Minuit2 not found (MINUIT2_INCLUDE_DIR: ${MINUIT2_INCLUDE_DIR}, MINUIT2_LIBRARY: ${MINUIT2_LIBRARY}). Minuit2-dependent features might not build/link.")
        endif()
    else()
        message(STATUS "Found Minuit2 using find_package.")
        if(NOT TARGET Minuit2::Minuit2 AND Minuit2_LIBRARIES AND Minuit2_INCLUDE_DIRS) # Check if find_package created a target
            add_library(Minuit2::Minuit2 INTERFACE IMPORTED GLOBAL)
            set_target_properties(Minuit2::Minuit2 PROPERTIES
                INTERFACE_INCLUDE_DIRECTORIES "${Minuit2_INCLUDE_DIRS}"
                INTERFACE_LINK_LIBRARIES "${Minuit2_LIBRARIES}")
        endif()
    endif()
endif()

# LAPACK
find_package(LAPACK REQUIRED)

# HDF5
if(NOT SIGMOND_USE_FSTREAM_DEFAULT OR TRUE) # Always try to find HDF5 as some files might include its headers
    find_package(HDF5 COMPONENTS CXX HL REQUIRED)
endif()

# OpenMP
find_package(OpenMP REQUIRED)

# --- Source File Definitions ---
set(SRC_BASE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/source)
set(PROJECT_INCLUDE_DIRS
    ${SRC_BASE_DIR}/analysis
    ${SRC_BASE_DIR}/tasks
    ${SRC_BASE_DIR}/data_handling
    ${SRC_BASE_DIR}/plotting
    ${SRC_BASE_DIR}/fitting
    ${SRC_BASE_DIR}/observables
)
include_directories(${PROJECT_INCLUDE_DIRS})

macro(add_sources_from_list_in_subdir var_name subdir filelist)
    set(${var_name})
    foreach(file ${filelist})
        list(APPEND ${var_name} "${SRC_BASE_DIR}/${subdir}/${file}")
    endforeach()
endmacro()

set(DRIVER_SRC ${SRC_BASE_DIR}/tasks/sigmond.cc)

add_sources_from_list_in_subdir(TASKS_SRCS "tasks" "scalar_defs.cc;single_pivot.cc;rolling_pivot.cc;stopwatch.cc;task_handler.cc;task_check.cc;task_fit.cc;task_get_from_pivot.cc;task_obsfunc.cc;task_plot.cc;task_print.cc;task_rotate_corrs.cc;task_utils.cc;xml_handler.cc")
add_sources_from_list_in_subdir(ANAL_SRCS "analysis" "bootstrapper.cc;histogram.cc;matrix.cc;mc_estimate.cc;mcobs_handler.cc;sampling_info.cc")
add_sources_from_list_in_subdir(DATA_SRCS "data_handling" "bins_info.cc;byte_handler.cc;corr_data_handler.cc;ensemble_info.cc;filelist_info.cc;io_handler_fstream.cc;io_handler_hdf5.cc;obs_get_handler.cc;vev_data_handler.cc")
add_sources_from_list_in_subdir(OBS_SRCS "observables" "basic_laph_operator_info.cc;diag_corr_set.cc;correlator_info.cc;correlator_matrix_info.cc;encoder.cc;gen_irrep_operator_info.cc;mcobs_info.cc;momenta.cc;operator_info.cc")
add_sources_from_list_in_subdir(PLOT_SRCS "plotting" "create_plots.cc;grace_plot.cc")
add_sources_from_list_in_subdir(FIT_SRCS "fitting" "chisq_anisotropy.cc;chisq_base.cc;chisq_disp.cc;chisq_fit.cc;chisq_tcorr.cc;chisq_logtcorr.cc;lmder.cc;minimizer.cc;minpack.cc;model_logtcorr.cc;model_tcorr.cc;nl2sol.cc")

set(SIGMOND_MAIN_SRCS ${DRIVER_SRC} ${TASKS_SRCS} ${ANAL_SRCS} ${DATA_SRCS} ${OBS_SRCS} ${PLOT_SRCS} ${FIT_SRCS})

set(SIGQUERY_APP_MAIN_SRC ${SRC_BASE_DIR}/data_handling/sigmond_query.cc)
set(SIGQUERY_COMMON_SRCS
    ${SRC_BASE_DIR}/observables/basic_laph_operator_info.cc ${SRC_BASE_DIR}/data_handling/byte_handler.cc
    ${SRC_BASE_DIR}/observables/correlator_info.cc ${SRC_BASE_DIR}/observables/correlator_matrix_info.cc
    ${SRC_BASE_DIR}/observables/encoder.cc ${SRC_BASE_DIR}/observables/gen_irrep_operator_info.cc
    ${SRC_BASE_DIR}/data_handling/io_handler_fstream.cc ${SRC_BASE_DIR}/data_handling/io_handler_hdf5.cc
    ${SRC_BASE_DIR}/analysis/matrix.cc ${SRC_BASE_DIR}/observables/mcobs_info.cc
    ${SRC_BASE_DIR}/observables/momenta.cc ${SRC_BASE_DIR}/observables/operator_info.cc
    ${SRC_BASE_DIR}/tasks/scalar_defs.cc ${SRC_BASE_DIR}/tasks/xml_handler.cc
)
set(SIGQUERY_ALL_SRCS ${SIGQUERY_APP_MAIN_SRC} ${SIGQUERY_COMMON_SRCS})

set(SIGCONV_APP_MAIN_SRC ${SRC_BASE_DIR}/data_handling/sigmond_convert.cc)
set(SIGCONV_COMMON_SRCS
    ${SRC_BASE_DIR}/observables/basic_laph_operator_info.cc ${SRC_BASE_DIR}/data_handling/bins_info.cc
    ${SRC_BASE_DIR}/data_handling/byte_handler.cc ${SRC_BASE_DIR}/observables/correlator_info.cc
    ${SRC_BASE_DIR}/observables/encoder.cc ${SRC_BASE_DIR}/data_handling/ensemble_info.cc
    ${SRC_BASE_DIR}/observables/gen_irrep_operator_info.cc ${SRC_BASE_DIR}/data_handling/io_handler_fstream.cc
    ${SRC_BASE_DIR}/data_handling/io_handler_hdf5.cc ${SRC_BASE_DIR}/observables/mcobs_info.cc
    ${SRC_BASE_DIR}/observables/operator_info.cc ${SRC_BASE_DIR}/tasks/scalar_defs.cc
    ${SRC_BASE_DIR}/tasks/xml_handler.cc
)
set(SIGCONV_ALL_SRCS ${SIGCONV_APP_MAIN_SRC} ${SIGCONV_COMMON_SRCS})

set(SIGIOLIB_SRCS
    ${SRC_BASE_DIR}/observables/basic_laph_operator_info.cc ${SRC_BASE_DIR}/data_handling/bins_info.cc
    ${SRC_BASE_DIR}/data_handling/byte_handler.cc ${SRC_BASE_DIR}/observables/correlator_info.cc
    ${SRC_BASE_DIR}/observables/correlator_matrix_info.cc ${SRC_BASE_DIR}/observables/encoder.cc
    ${SRC_BASE_DIR}/data_handling/ensemble_info.cc ${SRC_BASE_DIR}/data_handling/filelist_info.cc
    ${SRC_BASE_DIR}/observables/gen_irrep_operator_info.cc ${SRC_BASE_DIR}/data_handling/io_handler_fstream.cc
    ${SRC_BASE_DIR}/data_handling/io_handler_hdf5.cc ${SRC_BASE_DIR}/analysis/matrix.cc
    ${SRC_BASE_DIR}/observables/mcobs_info.cc ${SRC_BASE_DIR}/observables/momenta.cc
    ${SRC_BASE_DIR}/observables/operator_info.cc ${SRC_BASE_DIR}/tasks/scalar_defs.cc
    ${SRC_BASE_DIR}/tasks/stopwatch.cc ${SRC_BASE_DIR}/tasks/xml_handler.cc
)

# --- Helper function to link common dependencies ---
function(link_common_dependencies target_name)
    if(GRACE_FOUND)
        target_link_libraries(${target_name} PRIVATE Grace::Grace)
    endif()
    if(Minuit2_FOUND AND NOT SIGMOND_DISABLE_MINUIT)
        target_link_libraries(${target_name} PRIVATE Minuit2::Minuit2)
    endif()
    target_link_libraries(${target_name} PRIVATE LAPACK::LAPACK)
    # Link HDF5 if it's not fstream default OR if the HDF5 target exists (meaning it was found)
    # This ensures HDF5 is linked if needed, even if fstream is default but HDF5 sources are compiled.
    if(NOT SIGMOND_USE_FSTREAM_DEFAULT OR TARGET HDF5::HDF5)
        if(TARGET HDF5::HDF5) # Check if HDF5 target was successfully created by find_package
            target_link_libraries(${target_name} PRIVATE HDF5::HDF5)
        else()
            message(WARNING "HDF5 was requested or potentially needed but HDF5::HDF5 target not found. Linking may fail.")
        endif()
    endif()
    target_link_libraries(${target_name} PRIVATE OpenMP::OpenMP_CXX)
endfunction()

# --- Define Executables ---
add_executable(sigmond ${SIGMOND_MAIN_SRCS})
link_common_dependencies(sigmond)
install(TARGETS sigmond DESTINATION bin)

add_executable(sigmond_query ${SIGQUERY_ALL_SRCS})
link_common_dependencies(sigmond_query)
install(TARGETS sigmond_query DESTINATION bin)

add_executable(sigmond_convert ${SIGCONV_ALL_SRCS})
link_common_dependencies(sigmond_convert)
install(TARGETS sigmond_convert DESTINATION bin)

# --- Define Libraries (libsigmondio) ---
set(SIGMONDIOLIB_PUBLIC_HEADERS
    "${SRC_BASE_DIR}/data_handling/data_io_handler.h"
    "${SRC_BASE_DIR}/data_handling/io_map.h"
    "${SRC_BASE_DIR}/data_handling/io_map_base.h"
    "${SRC_BASE_DIR}/data_handling/io_map_fstream.h"
    "${SRC_BASE_DIR}/data_handling/io_map_hdf5.h"
    "${SRC_BASE_DIR}/data_handling/ensemble_info.h"
    "${SRC_BASE_DIR}/observables/mcobs_info.h"
    "${SRC_BASE_DIR}/observables/operator_info.h"
    "${SRC_BASE_DIR}/tasks/args_handler.h"
    "${SRC_BASE_DIR}/data_handling/array.h"
    "${SRC_BASE_DIR}/observables/basic_laph_operator_info.h"
)

add_library(sigmondio_shared SHARED ${SIGIOLIB_SRCS})
target_include_directories(sigmondio_shared PUBLIC
    $<BUILD_INTERFACE:${PROJECT_INCLUDE_DIRS}>
    $<INSTALL_INTERFACE:include/sigmondio>
)
set_target_properties(sigmondio_shared PROPERTIES PUBLIC_HEADER "${SIGMONDIOLIB_PUBLIC_HEADERS}")
link_common_dependencies(sigmondio_shared)
install(TARGETS sigmondio_shared LIBRARY DESTINATION lib ARCHIVE DESTINATION lib PUBLIC_HEADER DESTINATION include/sigmondio)

add_library(sigmondio_static STATIC ${SIGIOLIB_SRCS})
target_include_directories(sigmondio_static PUBLIC
    $<BUILD_INTERFACE:${PROJECT_INCLUDE_DIRS}>
    $<INSTALL_INTERFACE:include/sigmondio>
)
set_target_properties(sigmondio_static PROPERTIES PUBLIC_HEADER "${SIGMONDIOLIB_PUBLIC_HEADERS}")
link_common_dependencies(sigmondio_static)
install(TARGETS sigmondio_static ARCHIVE DESTINATION lib PUBLIC_HEADER DESTINATION include/sigmondio)

# --- sigmondiolib.inc generation ---
set(SIGMOND_APP_SRC_DIR_FOR_TEMPLATE "${SRC_BASE_DIR}")
set(LIB_TEMPLATE_FILE "${CMAKE_CURRENT_SOURCE_DIR}/batch/lib.template")
set(GENERATED_INC_FILE "${CMAKE_CURRENT_BINARY_DIR}/lib/sigmondiolib.inc")

if(EXISTS "${LIB_TEMPLATE_FILE}")
    message(STATUS "Found lib.template at: ${LIB_TEMPLATE_FILE}")
    configure_file("${LIB_TEMPLATE_FILE}" "${GENERATED_INC_FILE}" @ONLY)
    install(FILES "${GENERATED_INC_FILE}" DESTINATION lib)
else()
    message(WARNING "Template file ${LIB_TEMPLATE_FILE} not found. sigmondiolib.inc will not be generated.")
endif()

# --- Configuration Summary ---
message(STATUS "--- Configuration Summary ---")
message(STATUS "CXX Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Single Precision (SIGMOND_USE_SINGLE_PRECISION=${SIGMOND_USE_SINGLE_PRECISION}): Defining ${PROJECT_DEFINITIONS_SINGLE_PRECISION}")
message(STATUS "Real Numbers (SIGMOND_USE_REAL_NUMBERS=${SIGMOND_USE_REAL_NUMBERS}): Defining ${PROJECT_DEFINITIONS_REAL_NUMBERS}")
message(STATUS "Default I/O FStream (SIGMOND_USE_FSTREAM_DEFAULT=${SIGMOND_USE_FSTREAM_DEFAULT}): Defining ${PROJECT_DEFINITIONS_IO_TYPE}")
message(STATUS "Disable Minuit (SIGMOND_DISABLE_MINUIT=${SIGMOND_DISABLE_MINUIT})")
message(STATUS "Known Ensembles File: ${KNOWN_ENSEMBLES_FILE_PATH}")
message(STATUS "Grace Found: ${GRACE_FOUND}")
if(NOT SIGMOND_DISABLE_MINUIT)
    message(STATUS "Minuit2 Found: ${Minuit2_FOUND}")
endif()
if(TARGET HDF5::HDF5)
    message(STATUS "HDF5 Found and Target HDF5::HDF5 exists.")
else()
    message(STATUS "HDF5 Target HDF5::HDF5 does NOT exist (may be an issue if HDF5 I/O is used).")
endif()
message(STATUS "--------------------------")

# For more detailed debugging of compile definitions, you can add:
# get_directory_property(defs COMPILE_DEFINITIONS)
# message(STATUS "Current compile definitions: ${defs}")
# get_target_property(sigmond_defs sigmond COMPILE_DEFINITIONS)
# message(STATUS "Sigmond compile definitions: ${sigmond_defs}")

