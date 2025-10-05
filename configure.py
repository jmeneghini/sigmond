#!/usr/bin/env python3
"""
Sigmond configuration file reader.
Handles reading TOML configuration files and environment variable overrides.
Enhanced with KBfit-style features: CMake presets, cache generation, and improved management.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python versions
    except ImportError:
        tomllib = None


class SigmondConfig:
    """Configuration manager for Sigmond build settings."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self._apply_env_overrides()
        self._validate_config()
    
    def _load_config(self, config_path: Optional[str] = None) -> dict:
        """Load configuration from TOML file."""
        if tomllib is None:
            print("Warning: tomllib/tomli not available. Using environment variables only.")
            return self._default_config()
        
        # Determine config file path
        if config_path:
            config_file = Path(config_path)
        else:
            # Check environment variable first
            env_config = os.environ.get('SIGMOND_CONFIG')
            if env_config:
                config_file = Path(env_config)
            else:
                # Look for config file in standard locations
                search_paths = [
                    Path.cwd() / "sigmond.toml",
                    Path.cwd() / ".sigmond.toml", 
                    Path.home() / ".config" / "sigmond.toml",
                    Path(__file__).parent / "sigmond.toml"
                ]
                config_file = None
                for path in search_paths:
                    if path.exists():
                        config_file = path
                        break
        
        if config_file and config_file.exists():
            try:
                with open(config_file, 'rb') as f:
                    config = tomllib.load(f)
                print(f"Loaded Sigmond config from: {config_file}")
                return config
            except Exception as e:
                print(f"Warning: Failed to load config file {config_file}: {e}")
        
        return self._default_config()
    
    def _default_config(self) -> dict:
        """Return default configuration."""
        import os
        return {
            'build': {
                'skip_query': False,
                'skip_batch': False,
                'enable_testing': True,
                'verbose': False,
                'precision': 'double',
                'numbers': 'complex',
                'default_file_format': 'hdf5',
                'enable_minuit': False,
                'enable_grace': False,
                'build_jobs': os.cpu_count() or 1,
                'batch_install_dir': '',
                'query_install_dir': '',
                'extra_cmake_definitions': [],
                'default_ensembles_file': '/Users/johnmeneghini/Documents/LatticeQCD/spectrums/software/sigmond/ensembles.xml'
            },
            'libraries': {
                'hdf5': {'root_dir': ''},
                'blas': {'library_path': ''},
                'lapack': {'library_path': ''},
                'accelerate': {'framework_dir': ''},
                'minuit2': {'include_dir': '', 'library_dir': ''},
                'grace': {'include_dir': '', 'library_dir': ''}
            },
            'compiler': {
                'c_compiler': '',
                'cxx_compiler': '',
                'cxx_flags': []
            }
        }
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        # Build settings
        if os.environ.get('SIGMOND_SKIP_QUERY', '').lower() in ('1', 'true', 'yes'):
            self.config['build']['skip_query'] = True
        if os.environ.get('SIGMOND_SKIP_BATCH', '').lower() in ('1', 'true', 'yes'):
            self.config['build']['skip_batch'] = True
        if os.environ.get('SIGMOND_VERBOSE', '').lower() in ('1', 'true', 'yes'):
            self.config['build']['verbose'] = True

        # Default ensembles file override
        if os.environ.get('DEFAULTENSFILE'):
            self.config['build']['default_ensembles_file'] = os.environ.get('DEFAULTENSFILE')
    
    def _validate_config(self):
        """Validate configuration values and provide helpful error messages."""
        errors = []
        warnings = []
        
        # Validate build settings
        build_config = self.config.get('build', {})
        
        # Check precision setting
        precision = build_config.get('precision', 'double')
        if precision not in ['double', 'single']:
            errors.append(f"Invalid precision '{precision}'. Must be 'double' or 'single'.")
        
        # Check numbers setting
        numbers = build_config.get('numbers', 'complex')
        if numbers not in ['complex', 'real']:
            errors.append(f"Invalid numbers type '{numbers}'. Must be 'complex' or 'real'.")
        
        # Check file format setting
        file_format = build_config.get('default_file_format', 'hdf5')
        if file_format not in ['hdf5', 'fstream']:
            errors.append(f"Invalid file format '{file_format}'. Must be 'hdf5' or 'fstream'.")
        
        # Check build_jobs setting
        build_jobs = build_config.get('build_jobs', 0)
        if not isinstance(build_jobs, int) or build_jobs < 0:
            errors.append(f"Invalid build_jobs '{build_jobs}'. Must be a non-negative integer.")
        
        # Validate optional feature consistency
        if build_config.get('enable_minuit', False):
            minuit_config = self.config.get('libraries', {}).get('minuit2', {})
            if not minuit_config.get('include_dir') and not minuit_config.get('library_dir'):
                warnings.append("Minuit2 is enabled but no library paths specified. Auto-detection will be attempted.")
        
        if build_config.get('enable_grace', False):
            grace_config = self.config.get('libraries', {}).get('grace', {})
            if not grace_config.get('include_dir') and not grace_config.get('library_dir'):
                warnings.append("Grace is enabled but no library paths specified. Auto-detection will be attempted.")
        
        # Check for potentially problematic configurations
        if build_config.get('skip_query', False) and build_config.get('skip_batch', False):
            warnings.append("Both executables are disabled - only Python bindings will be built.")
        
        # Report errors and warnings
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)
        
        if warnings and build_config.get('verbose', False):
            print("Configuration warnings:")
            for warning in warnings:
                print(f"  - {warning}")
    
    def get_cmake_args(self) -> List[str]:
        """Generate CMake arguments from configuration."""
        args = []

        # Precision and numbers settings as CMake variables
        precision = self.config['build']['precision'].lower()
        args.append(f'-DPRECISION={precision}')

        numbers = self.config['build']['numbers'].lower()
        args.append(f'-DNUMBERS={numbers}')

        # Default file format setting as CMake variable
        file_format = self.config['build']['default_file_format'].lower()
        args.append(f'-DDEFAULT_FILE_FORMAT={file_format}')

        # Build control flags
        if self.config['build']['skip_query']:
            args.append('-DSKIP_SIGMOND_QUERY=ON')
        if self.config['build']['skip_batch']:
            args.append('-DSKIP_SIGMOND_BATCH=ON')
        if self.config['build']['enable_minuit']:
            args.append('-DENABLE_MINUIT=ON')
        if self.config['build']['enable_grace']:
            args.append('-DENABLE_GRACE=ON')

        # Verbose output
        if self.config['build']['verbose']:
            args.append('-DSIGMOND_VERBOSE=ON') # not currently used
            args.append('-DCMAKE_FIND_DEBUG_MODE=ON')

        # Enable testing
        if self.config['build']['enable_testing']:
            args.append('-DENABLE_TESTING=ON')
        else:
            args.append('-DENABLE_TESTING=OFF')

        # Custom install directories
        if self.config['build']['batch_install_dir']:
            args.append(f'-DSIGMOND_BATCH_INSTALL_DIR={self.config["build"]["batch_install_dir"]}')
        if self.config['build']['query_install_dir']:
            args.append(f'-DSIGMOND_QUERY_INSTALL_DIR={self.config["build"]["query_install_dir"]}')

        # Default ensembles file
        default_ens_file = self.config['build'].get('default_ensembles_file', '')
        if default_ens_file:
            args.append(f'-DDEFAULTENSFILE={default_ens_file}')

        # Extra user-provided -D definitions
        extra_defs = self.config['build'].get('extra_cmake_definitions', [])
        if isinstance(extra_defs, dict):
            items = extra_defs.items()
        elif isinstance(extra_defs, list):
            items = []
            for entry in extra_defs:
                if isinstance(entry, str):
                    # Accept forms: "FOO", "FOO=BAR", "-DFOO=BAR"
                    s = entry.strip()
                    if s.startswith('-D'):
                        args.append(s)
                        continue
                    args.append(f'-D{s}')
                elif isinstance(entry, dict):
                    items.extend(entry.items())
        else:
            items = []
        # Process dict-style entries (key -> value)
        for k, v in (items or []):
            # Normalize boolean to ON/OFF, lists to semicolon list
            if isinstance(v, bool):
                vv = 'ON' if v else 'OFF'
            elif isinstance(v, (list, tuple)):
                vv = ';'.join(str(x) for x in v)
            else:
                vv = str(v)
            args.append(f'-D{k}={vv}')

        # HDF5 root path (if specified)
        if 'hdf5' in self.config['libraries']:
            hdf5_config = self.config['libraries']['hdf5']
            if hdf5_config.get('root_dir'):
                args.append(f'-DHDF5_DIR={hdf5_config["root_dir"]}')

        # BLAS manual library paths
        if 'blas' in self.config['libraries']:
            blas_config = self.config['libraries']['blas']
            if blas_config.get('library_path'):
                args.append(f'-DBLAS_LIBRARIES={blas_config["library_path"]}')

        # LAPACK manual library paths
        if 'lapack' in self.config['libraries']:
            lib_config = self.config['libraries']['lapack']
            if lib_config.get('library_path'):
                args.append(f'-DLAPACK_LIBRARIES={lib_config["library_path"]}')

        # Optional libraries (only if enabled)
        if self.config['build']['enable_minuit'] and 'minuit2' in self.config['libraries']:
            lib_config = self.config['libraries']['minuit2']
            if lib_config.get('include_dir'):
                args.append(f'-DSIGMOND_MINUIT2_INCLUDE_DIR={lib_config["include_dir"]}')
            if lib_config.get('library_dir'):
                args.append(f'-DSIGMOND_MINUIT2_LIBRARY_DIR={lib_config["library_dir"]}')

        if self.config['build']['enable_grace'] and 'grace' in self.config['libraries']:
            lib_config = self.config['libraries']['grace']
            if lib_config.get('include_dir'):
                args.append(f'-DSIGMOND_GRACE_INCLUDE_DIR={lib_config["include_dir"]}')
            if lib_config.get('library_dir'):
                args.append(f'-DSIGMOND_GRACE_LIBRARY_DIR={lib_config["library_dir"]}')

        # Special handling for Accelerate framework (macOS only)
        if 'accelerate' in self.config['libraries']:
            accel_config = self.config['libraries']['accelerate']
            if accel_config.get('framework_dir'):
                args.append(f'-DSIGMOND_ACCELERATE_FRAMEWORK_DIR={accel_config["framework_dir"]}')

        # C/C++ compilers (KBfit-style)
        if 'compiler' in self.config:
            compiler_config = self.config['compiler']
            if compiler_config.get('c_compiler'):
                args.append(f'-DCMAKE_C_COMPILER={compiler_config["c_compiler"]}')
            if compiler_config.get('cxx_compiler'):
                args.append(f'-DCMAKE_CXX_COMPILER={compiler_config["cxx_compiler"]}')

        return args
    
    def get_extra_cxx_flags(self) -> List[str]:
        """Get additional C++ compiler flags from configuration."""
        flags = []
        
        # Add user-specified flags
        if self.config['compiler']['cxx_flags']:
            flags.extend(self.config['compiler']['cxx_flags'])
        
        return flags

    def generate_cmake_presets(self, output_path: str = "src/sigmond/cpp/CMakeUserPresets.json", clear_cache: bool = False):
        """Generate CMakePresets.json from configuration."""
        # Detect conda environment
        conda_prefix = os.environ.get('CONDA_PREFIX', '')
        if not conda_prefix:
            print("Warning: CONDA_PREFIX not detected. Preset may not work correctly.")

        # Build cache variables from configuration
        cache_vars = {
            "CMAKE_BUILD_TYPE": "Release",
            "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
            "CMAKE_CXX_STANDARD": "17",
            "CMAKE_CXX_STANDARD_REQUIRED": "ON",
            "CMAKE_CXX_EXTENSIONS": "OFF"
        }

        # Add conda paths if available
        if conda_prefix:
            cache_vars.update({
                "CMAKE_PREFIX_PATH": conda_prefix,
                "CMAKE_BUILD_RPATH": f"{conda_prefix}/lib",
                "HDF5_ROOT": conda_prefix,
                "PYTHON_EXECUTABLE": f"{conda_prefix}/bin/python"
            })

        # Add configuration-specific CMake variables
        cmake_args = self.get_cmake_args()
        for arg in cmake_args:
            if arg.startswith('-D') and '=' in arg:
                key, value = arg[2:].split('=', 1)
                cache_vars[key] = value
            elif arg.startswith('-D'):
                key = arg[2:]
                cache_vars[key] = "ON"

        # Handle compiler paths
        if clear_cache:
            # Explicitly unset compiler variables to force CMake auto-detection
            cache_vars.update({
                'CMAKE_C_COMPILER': '',
                'CMAKE_CXX_COMPILER': ''
            })
        else:
            # Add compiler paths from config (only if non-empty and exist on system)
            c_compiler = self.config['compiler']['c_compiler']
            if c_compiler and c_compiler.strip() and os.path.exists(c_compiler):
                cache_vars['CMAKE_C_COMPILER'] = c_compiler

            cxx_compiler = self.config['compiler']['cxx_compiler']
            if cxx_compiler and cxx_compiler.strip() and os.path.exists(cxx_compiler):
                cache_vars['CMAKE_CXX_COMPILER'] = cxx_compiler

        # Create preset structure
        presets = {
            "version": 5,
            "configurePresets": [
                {
                    "name": "sigmond-auto-release",
                    "displayName": "Sigmond Auto Release",
                    "generator": "Unix Makefiles",
                    "binaryDir": "${sourceDir}/../../../build",
                    "cacheVariables": cache_vars.copy()
                },
                {
                    "name": "sigmond-auto-debug",
                    "displayName": "Sigmond Auto Debug",
                    "inherits": "sigmond-auto-release",
                    "binaryDir": "${sourceDir}/../../../build-debug",
                    "cacheVariables": {
                        "CMAKE_BUILD_TYPE": "Debug"
                    }
                }
            ],
            "buildPresets": [
                {
                    "name": "build-auto-release",
                    "configurePreset": "sigmond-auto-release",
                    "verbose": self.is_verbose(),
                    "jobs": self.get_build_jobs()
                },
                {
                    "name": "build-auto-debug",
                    "configurePreset": "sigmond-auto-debug",
                    "verbose": self.is_verbose(),
                    "jobs": self.get_build_jobs()
                }
            ]
        }

        # Write presets file
        output_file = Path(output_path)
        try:
            with open(output_file, 'w') as f:
                json.dump(presets, f, indent=2)
            print(f"Generated CMake presets: {output_file}")
            return True
        except Exception as e:
            print(f"Error generating presets: {e}")
            return False

    def write_cache(self, output_path: str = str(Path(__file__).parent / "_sigmond_cache_init.cmake"),
                    clear_cache: bool = False) -> bool:
        """Emit a CMake init-cache file mirroring generate_cmake_presets."""
        conda_prefix = os.environ.get('CONDA_PREFIX', '')

        # 1) base cache vars (same as presets)
        cache_vars = {
            "CMAKE_BUILD_TYPE": "Release",
            "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
            "CMAKE_CXX_STANDARD": "17",
            "CMAKE_CXX_STANDARD_REQUIRED": "ON",
            "CMAKE_CXX_EXTENSIONS": "OFF",
        }

        # 2) conda-derived suggestions
        if conda_prefix:
            cache_vars.update({
                "CMAKE_PREFIX_PATH": conda_prefix,
                "CMAKE_BUILD_RPATH": f"{conda_prefix}/lib",
                "HDF5_ROOT": conda_prefix,
                "PYTHON_EXECUTABLE": f"{conda_prefix}/bin/python",
            })
        else:
            print("Warning: CONDA_PREFIX not detected. Cache may be suboptimal.")

        # 3) fold in your -D flags from sigmond.toml/env
        for arg in self.get_cmake_args():
            if arg.startswith('-D'):
                body = arg[2:]
                if '=' in body:
                    k, v = body.split('=', 1)
                    cache_vars[k] = v
                else:
                    cache_vars[body] = "ON"

        # 4) compilers handling
        if clear_cache:
            cache_vars.update({
                'CMAKE_C_COMPILER': '',
                'CMAKE_CXX_COMPILER': ''
            })
        else:
            c = self.config['compiler'].get('c_compiler', '')
            if c and os.path.exists(c):
                cache_vars['CMAKE_C_COMPILER'] = c
            cxx = self.config['compiler'].get('cxx_compiler', '')
            if cxx and os.path.exists(cxx):
                cache_vars['CMAKE_CXX_COMPILER'] = cxx

        # 5) render as CMake cache init
        def _ctype(k: str, v: str) -> str:
            vv = v.upper()
            if vv in ("ON", "OFF", "TRUE", "FALSE"):
                return "BOOL"
            if k.endswith(("_COMPILER",)) or k in ("PYTHON_EXECUTABLE",):
                return "FILEPATH"
            if k.endswith(("_DIR", "_ROOT", "_PREFIX_PATH")) or k == "CMAKE_PREFIX_PATH":
                return "PATH"
            return "STRING"

        def _q(s: str) -> str:
            return s.replace('\\', '/').replace('"', '\\"')

        lines = []
        for k, v in cache_vars.items():
            typ = _ctype(k, str(v))
            lines.append(f'set({k} "{_q(str(v))}" CACHE {typ} "")')

        try:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(lines) + "\n")
            print(f"Wrote CMake init cache: {p}")
            return True
        except Exception as e:
            print(f"Error writing cache: {e}")
            return False

    def _get_enabled_optional_libraries(self) -> List[str]:
        """Determine which optional libraries are enabled."""
        enabled = []

        # Minuit2 if enabled
        if self.config['build']['enable_minuit']:
            enabled.append('minuit2')

        # Grace if enabled
        if self.config['build']['enable_grace']:
            enabled.append('grace')

        return enabled

    def get_env_dict(self) -> Dict[str, str]:
        """Get environment variables to set for the build."""
        env = {}
        # No environment variables currently needed
        return env
    
    def should_skip_query(self) -> bool:
        """Check if sigmond_query should be skipped."""
        return self.config['build']['skip_query']
    
    def should_skip_batch(self) -> bool:
        """Check if sigmond_batch should be skipped."""
        return self.config['build']['skip_batch']
    
    def is_verbose(self) -> bool:
        """Check if verbose output is enabled."""
        return self.config['build']['verbose']
    
    def get_precision(self) -> str:
        """Get the precision setting."""
        return self.config['build']['precision']
    
    def get_numbers_type(self) -> str:
        """Get the numbers type setting."""
        return self.config['build']['numbers']
    
    def get_default_file_format(self) -> str:
        """Get the default file format setting."""
        return self.config['build']['default_file_format']
    
    def get_build_jobs(self) -> int:
        """Get the number of parallel build jobs."""
        jobs = self.config['build']['build_jobs']
        # If 0 or invalid, auto-detect CPU count
        if jobs <= 0:
            import os
            jobs = os.cpu_count() or 1
        return jobs
    
    def get_batch_install_dir(self) -> str:
        """Get custom install directory for sigmond_batch."""
        return self.config['build']['batch_install_dir']
    
    def get_query_install_dir(self) -> str:
        """Get custom install directory for sigmond_query."""
        return self.config['build']['query_install_dir']

    def is_testing_enabled(self) -> bool:
        """Check if testing is enabled."""
        return self.config['build']['enable_testing']

    def get_default_ensembles_file(self) -> str:
        """Get the default ensembles file path."""
        return self.config['build']['default_ensembles_file']


# Convenience function for setup.py
def load_sigmond_config(config_path: Optional[str] = None) -> SigmondConfig:
    """Load Sigmond configuration."""
    return SigmondConfig(config_path)


# CLI functionality
def create_config(output_path: str, template: bool = False):
    """Create a new configuration file."""
    config_file = Path(output_path)
    
    if config_file.exists():
        response = input(f"File {config_file} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    if template:
        # Copy from example file
        example_file = Path(__file__).parent / "sigmond.example.toml"
        if example_file.exists():
            with open(example_file, 'r') as src:
                content = src.read()
        else:
            print(f"Error: Template file {example_file} not found.")
            return
    else:
        # Create minimal config
        content = """# Sigmond Configuration
[build]
skip_query = false
skip_batch = false
precision = "double"
numbers = "complex"
default_file_format = "hdf5"
enable_minuit = false
enable_grace = false
enable_testing = true
verbose = false
build_jobs = 0             # Number of parallel build jobs (0 = auto-detect)
batch_install_dir = ""     # Custom install directory for sigmond_batch (empty = default bin/)
query_install_dir = ""     # Custom install directory for sigmond_query (empty = default bin/)
extra_cmake_definitions = [] # Additional -D flags passed to CMake
default_ensembles_file = "" # Path to ensembles XML file for DEFAULTENSFILE

[libraries]
# Manual library paths (only specify if auto-detection fails)

[libraries.hdf5]
root_dir = ""              # Directory containing /include and /lib subdirectories
                           # with HDF5 headers and libraries
                    
[libraries.blas]
library_path = ""          # Path to BLAS .so/dylib file (e.g. libopenblas.so)

[libraries.lapack]
library_path = ""          # Path to LAPACK .so/dylib file (e.g. libopenblas.so)

[libraries.accelerate]
framework_dir = ""

[libraries.minuit2]
include_dir = ""            # e.g. /usr/include
library_dir = ""            # e.g. /usr/lib

[libraries.grace]
include_dir = ""
library_dir = ""

[compiler]
c_compiler = ""
cxx_compiler = ""
cxx_flags = []
"""
    
    try:
        with open(config_file, 'w') as f:
            f.write(content)
        print(f"Created configuration file: {config_file}")
    except Exception as e:
        print(f"Error creating file: {e}")


def show_config():
    """Show current configuration."""
    try:
        config = load_sigmond_config()
        print("Current Sigmond Configuration:")
        print("=" * 40)
        print(f"Skip query executable: {config.should_skip_query()}")
        print(f"Skip batch executable: {config.should_skip_batch()}")
        print(f"Precision: {config.get_precision()}")
        print(f"Numbers type: {config.get_numbers_type()}")
        print(f"Default file format: {config.get_default_file_format()}")
        print(f"Verbose build: {config.is_verbose()}")
        
        enabled_libs = config._get_enabled_optional_libraries()
        if enabled_libs:
            print(f"Enabled optional libraries: {', '.join(enabled_libs)}")
        else:
            print("Enabled optional libraries: none")
        
        cmake_args = config.get_cmake_args()
        if cmake_args:
            print(f"\nAdditional CMake arguments:")
            for arg in cmake_args:
                print(f"  {arg}")
        
        env_vars = config.get_env_dict()
        if env_vars:
            print(f"\nEnvironment variables:")
            for key, value in env_vars.items():
                print(f"  {key}={value}")
                
    except Exception as e:
        print(f"Error loading configuration: {e}")


def validate_config(config_path: str = None):
    """Validate a configuration file."""
    try:
        config = load_sigmond_config(config_path)
        print("✓ Configuration file is valid")
        
        # Check for common issues
        warnings = []
        
        if config.should_skip_query() and config.should_skip_batch():
            warnings.append("Both executables are disabled - only Python bindings will be built")
        
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"  ⚠ {warning}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return False


def main():
    """CLI main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sigmond Configuration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Show command
    subparsers.add_parser('show', help='Show current configuration')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create new sigmond.toml configuration file')

    # Generate-presets command
    gen_parser = subparsers.add_parser('generate-presets', help='Generate CMakeUserPresets.json from config')
    gen_parser.add_argument('-o', '--output', default='src/sigmond/cpp/CMakeUserPresets.json',
                            help='Output file path (default: src/sigmond/cpp/CMakeUserPresets.json)')
    gen_parser.add_argument('--clear-cache', action='store_true',
                            help='Clear compiler cache variables to force CMake auto-detection')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration file')

    # CMake args command
    cmake_args_p = subparsers.add_parser('cmake-args', help='Print -D CMake args derived from sigmond.toml/env')
    cmake_args_p.add_argument('--as-env', action='store_true', help='Emit: export CMAKE_ARGS="..."')

    # Output cache files
    wc = subparsers.add_parser('write-cache', help='Write CMake init cache from sigmond.toml/env')
    wc.add_argument('-o', '--output', default=str(Path(__file__).parent / "_sigmond_cache_init.cmake"))
    wc.add_argument('--clear-cache', action='store_true')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'show':
        show_config()
    elif args.command == 'create':
        create_config(output_path='sigmond.toml', template=False)
    elif args.command == 'generate-presets':
        try:
            config = load_sigmond_config()
            success = config.generate_cmake_presets(args.output, args.clear_cache)
            return 0 if success else 1
        except Exception as e:
            print(f"Error generating presets: {e}")
            return 1
    elif args.command == 'validate':
        if validate_config('sigmond.toml'):
            return 0
        else:
            return 1
    elif args.command == 'cmake-args':
        cfg = load_sigmond_config()
        vals = cfg.get_cmake_args()
        s = ' '.join(vals)
        if args.as_env:
            print(f'export CMAKE_ARGS="{s}"')
        else:
            print(s)
        return 0
    elif args.command == 'write-cache':
        cfg = load_sigmond_config()
        ok = cfg.write_cache(args.output, args.clear_cache)
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    # If run as script, provide CLI functionality
    sys.exit(main())
else:
    # If imported as module, also provide test functionality
    if __name__ == "__main__":
        # Test the configuration loader
        config = load_sigmond_config()
        print("Build settings:")
        print(f"  Skip query: {config.should_skip_query()}")
        print(f"  Skip batch: {config.should_skip_batch()}")
        print(f"  Precision: {config.get_precision()}")
        print(f"  Numbers: {config.get_numbers_type()}")
        print(f"  Default file format: {config.get_default_file_format()}")
        print(f"  Verbose: {config.is_verbose()}")
        print(f"\nEnabled optional libraries: {config._get_enabled_optional_libraries()}")
        print("CMake args:", config.get_cmake_args())
        print("Environment:", config.get_env_dict())
