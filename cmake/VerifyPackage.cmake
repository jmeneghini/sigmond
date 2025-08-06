# Verify that a found package is actually usable.
# Usage:
#   verify_package(<PkgName> [TARGETS tgt1 tgt2 ...])
#
# Examples:
#   verify_package(HDF5 TARGETS hdf5::hdf5 hdf5::hdf5_hl)
#   verify_package(LAPACK TARGETS LAPACK::LAPACK)
#   verify_package(ZLIB)                      # legacy variables fallback

function(verify_package PKG)
  set(options)
  set(oneValueArgs)
  set(multiValueArgs TARGETS)
  cmake_parse_arguments(VP "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

  string(TOUPPER "${PKG}" PKG_UP)
  if(NOT DEFINED ${PKG_UP}_FOUND OR NOT ${PKG_UP}_FOUND)
    message(FATAL_ERROR "${PKG}: package not found (did you call find_package?).")
  endif()

  if(VP_TARGETS)
    foreach(t IN LISTS VP_TARGETS)
      if(NOT TARGET ${t})
        message(FATAL_ERROR "${PKG}: expected target '${t}' is missing.")
      endif()
      # Consider target usable if it has interface link deps OR a concrete imported location.
      set(_ok FALSE)

      get_target_property(_iface ${t} INTERFACE_LINK_LIBRARIES)
      if(_iface)
        set(_ok TRUE)
      endif()

      # Generic location
      get_target_property(_loc ${t} IMPORTED_LOCATION)
      if(_loc AND NOT _loc MATCHES "-NOTFOUND$")
        set(_ok TRUE)
      endif()

      # Per-config locations
      get_target_property(_cfgs ${t} IMPORTED_CONFIGURATIONS)
      foreach(cfg IN LISTS _cfgs)
        get_target_property(_loc_${cfg} ${t} IMPORTED_LOCATION_${cfg})
        if(_loc_${cfg} AND NOT _loc_${cfg} MATCHES "-NOTFOUND$")
          set(_ok TRUE)
        endif()
      endforeach()

      if(NOT _ok)
        message(FATAL_ERROR "${PKG}: target '${t}' provides no usable libraries "
                            "(locations are NOTFOUND and no interface libs).")
      endif()
    endforeach()
  else()
    # Legacy Find-module variables fallback
    set(_any FALSE)
    foreach(var LIBRARIES INCLUDE_DIRS)
      if(DEFINED ${PKG_UP}_${var})
        set(_any TRUE)
        if("${var}" STREQUAL "LIBRARIES")
          foreach(lib IN LISTS ${PKG_UP}_LIBRARIES)
            if(lib MATCHES "-NOTFOUND$")
              message(FATAL_ERROR "${PKG}: entry '${lib}' in ${PKG_UP}_LIBRARIES is NOTFOUND.")
            endif()
            # Skip non-path flags (e.g., -lm) but check paths if they look like files.
            if(lib MATCHES "^/|^[A-Za-z]:/")
              if(NOT EXISTS "${lib}")
                message(FATAL_ERROR "${PKG}: library path does not exist: ${lib}")
              endif()
            endif()
          endforeach()
        endif()
      endif()
    endforeach()
    if(NOT _any)
      message(FATAL_ERROR "${PKG}: no targets and no legacy variables exposed; unusable package.")
    endif()
  endif()
endfunction()

# require_package(<Pkg> [VERSION <ver>] [COMPONENTS ...] [TARGETS ...])
function(require_package PKG)
  set(options)
  set(oneValueArgs VERSION)
  set(multiValueArgs COMPONENTS TARGETS)
  cmake_parse_arguments(RP "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

  if(RP_VERSION)
    find_package(${PKG} ${RP_VERSION} REQUIRED ${RP_COMPONENTS})
  else()
    find_package(${PKG} REQUIRED ${RP_COMPONENTS})
  endif()
  verify_package(${PKG} TARGETS ${RP_TARGETS})
endfunction()

