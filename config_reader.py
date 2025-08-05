"""
Sigmond configuration file reader.
Handles reading TOML configuration files and environment variable overrides.
"""

import os
import sys
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
                'verbose': False,
                'precision': 'double',
                'numbers': 'complex',
                'default_file_format': 'hdf5',
                'enable_minuit': False,
                'enable_grace': False,
                'build_jobs': os.cpu_count() or 1,
                'batch_install_dir': '',
                'query_install_dir': ''
            },
            'libraries': {
                'hdf5': {'hdf5_root': ''},
                'lapack': {'include_dirs': [], 'library_dirs': []},
                'accelerate': {'framework_dirs': []},
                'minuit2': {'include_dirs': [], 'library_dirs': []},
                'grace': {'include_dirs': [], 'library_dirs': []}
            },
            'compiler': {
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
            if not minuit_config.get('include_dirs') and not minuit_config.get('library_dirs'):
                warnings.append("Minuit2 is enabled but no library paths specified. Auto-detection will be attempted.")
        
        if build_config.get('enable_grace', False):
            grace_config = self.config.get('libraries', {}).get('grace', {})
            if not grace_config.get('include_dirs') and not grace_config.get('library_dirs'):
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
        
        # Build control flags
        if self.config['build']['skip_query']:
            args.append('-DSKIP_SIGMOND_QUERY=ON')
        if self.config['build']['skip_batch']:
            args.append('-DSKIP_SIGMOND_BATCH=ON')
        
        # Custom install directories
        if self.config['build']['batch_install_dir']:
            args.append(f'-DSIGMOND_BATCH_INSTALL_DIR={self.config["build"]["batch_install_dir"]}')
        if self.config['build']['query_install_dir']:
            args.append(f'-DSIGMOND_QUERY_INSTALL_DIR={self.config["build"]["query_install_dir"]}')
        
        # HDF5 root path (if specified)
        if 'hdf5' in self.config['libraries']:
            hdf5_config = self.config['libraries']['hdf5']
            if hdf5_config.get('hdf5_root'):
                args.append(f'-DHDF5_ROOT={hdf5_config["hdf5_root"]}')
        
        # LAPACK manual library paths
        if 'lapack' in self.config['libraries']:
            lib_config = self.config['libraries']['lapack']
            if lib_config.get('include_dirs'):
                inc_dirs = ';'.join(lib_config['include_dirs'])
                args.append(f'-DSIGMOND_LAPACK_INCLUDE_DIR={inc_dirs}')
            if lib_config.get('library_dirs'):
                lib_dirs = ';'.join(lib_config['library_dirs'])
                args.append(f'-DSIGMOND_LAPACK_LIBRARY_DIR={lib_dirs}')
        
        # Optional libraries (only if enabled)
        if self.config['build']['enable_minuit'] and 'minuit2' in self.config['libraries']:
            lib_config = self.config['libraries']['minuit2']
            if lib_config.get('include_dirs'):
                inc_dirs = ';'.join(lib_config['include_dirs'])
                args.append(f'-DSIGMOND_MINUIT2_INCLUDE_DIR={inc_dirs}')
            if lib_config.get('library_dirs'):
                lib_dirs = ';'.join(lib_config['library_dirs'])
                args.append(f'-DSIGMOND_MINUIT2_LIBRARY_DIR={lib_dirs}')
        
        if self.config['build']['enable_grace'] and 'grace' in self.config['libraries']:
            lib_config = self.config['libraries']['grace']
            if lib_config.get('include_dirs'):
                inc_dirs = ';'.join(lib_config['include_dirs'])
                args.append(f'-DSIGMOND_GRACE_INCLUDE_DIR={inc_dirs}')
            if lib_config.get('library_dirs'):
                lib_dirs = ';'.join(lib_config['library_dirs'])
                args.append(f'-DSIGMOND_GRACE_LIBRARY_DIR={lib_dirs}')
        
        # Special handling for Accelerate framework (macOS only)
        if 'accelerate' in self.config['libraries']:
            accel_config = self.config['libraries']['accelerate']
            if accel_config.get('framework_dirs'):
                framework_dirs = ';'.join(accel_config['framework_dirs'])
                args.append(f'-DSIGMOND_ACCELERATE_FRAMEWORK_DIR={framework_dirs}')
        
        return args
    
    def get_compiler_definitions(self) -> List[str]:
        """Generate compiler definitions based on configuration."""
        definitions = []
        
        # Precision setting
        precision = self.config['build']['precision'].lower()
        if precision == 'single':
            definitions.append('SINGLEPRECISION')
        else:  # default to double
            definitions.append('DOUBLEPRECISION')
        
        # Number type setting  
        numbers = self.config['build']['numbers'].lower()
        if numbers == 'real':
            definitions.append('REALNUMBERS')
        else:  # default to complex
            definitions.append('COMPLEXNUMBERS')
        
        # Default file format setting
        file_format = self.config['build']['default_file_format'].lower()
        if file_format == 'fstream':
            definitions.append('DEFAULT_FSTREAM')
        else:  # default to hdf5
            definitions.append('DEFAULT_HDF5')
        
        # Always include these for current build
        definitions.extend(['NOGRACE', 'NO_MINUIT', 'NOXML', 'HDF5', 'LAPACK'])
        
        # Optional features
        if self.config['build']['enable_minuit']:
            definitions.remove('NO_MINUIT')  # Remove the disable flag
        if self.config['build']['enable_grace']:
            definitions.remove('NOGRACE')   # Remove the disable flag
        
        # Check if we're building batch executable for XML support
        building_batch = not self.config['build']['skip_batch']
        if building_batch:
            definitions.remove('NOXML')     # Remove the disable flag
        
        return definitions
    
    def get_extra_cxx_flags(self) -> List[str]:
        """Get additional C++ compiler flags from configuration."""
        flags = []
        
        # Add user-specified flags
        if self.config['compiler']['cxx_flags']:
            flags.extend(self.config['compiler']['cxx_flags'])
        
        return flags
    
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
        import os
        cpu_count = os.cpu_count() or 1
        content = f"""# Sigmond Configuration
[build]
skip_query = false
skip_batch = false
precision = "double"
numbers = "complex"
default_file_format = "hdf5"
enable_minuit = false
enable_grace = false
verbose = false
build_jobs = {cpu_count}           # Number of parallel build jobs (0 = auto-detect)
batch_install_dir = ""     # Custom install directory for sigmond_batch (empty = default bin/)
query_install_dir = ""     # Custom install directory for sigmond_query (empty = default bin/)

[libraries]
# Manual library paths (only specify if auto-detection fails)

[libraries.hdf5]
hdf5_root = ""

[libraries.lapack]
include_dirs = []
library_dirs = []

[libraries.accelerate]
framework_dirs = []

[libraries.minuit2]
include_dirs = []
library_dirs = []

[libraries.grace]
include_dirs = []
library_dirs = []

[compiler]
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
        epilog="""
Examples:
  %(prog)s show                          # Show current configuration
  %(prog)s create sigmond.toml          # Create basic config file
  %(prog)s create --template config.toml # Create from template
  %(prog)s validate                     # Validate current config
  %(prog)s validate myconfig.toml       # Validate specific file
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Show command
    subparsers.add_parser('show', help='Show current configuration')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create new configuration file')
    create_parser.add_argument('output', help='Output file path')
    create_parser.add_argument('--template', action='store_true', 
                              help='Create from example template')
    
    # Validate command  
    validate_parser = subparsers.add_parser('validate', help='Validate configuration file')
    validate_parser.add_argument('config', nargs='?', help='Config file to validate (default: auto-detect)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'show':
        show_config()
    elif args.command == 'create':
        create_config(args.output, args.template)
    elif args.command == 'validate':
        if validate_config(args.config):
            return 0
        else:
            return 1
    
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