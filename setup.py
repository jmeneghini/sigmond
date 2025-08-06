#stolen from https://stackoverflow.com/questions/53397121/python-pip-packaging-how-to-move-built-files-to-install-directory
import os
import re
import sys
import sysconfig
import site
import subprocess
import pathlib
import shutil

from distutils.version import LooseVersion
from setuptools import setup, Extension
from setuptools.command.install import install
from setuptools.command.build_ext import build_ext as build_ext_orig

# === CONFIGURATION SYSTEM ===

def load_configuration():
    """Load Sigmond configuration with robust error handling."""
    try:
        # Add current directory to path to ensure config_reader can be found
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        from config_reader import load_sigmond_config
        return load_sigmond_config()
    except ImportError as e:
        print(f"Warning: Could not load config_reader ({e}). Using fallback configuration.")
        return create_fallback_config()
    except Exception as e:
        print(f"Error loading configuration: {e}. Using fallback configuration.")
        return create_fallback_config()

def create_fallback_config():
    """Create fallback configuration when config_reader is unavailable."""
    class FallbackConfig:
        def should_skip_query(self): 
            return os.environ.get('SIGMOND_SKIP_QUERY', '').lower() in ('1', 'true', 'yes')
        
        def should_skip_batch(self): 
            return os.environ.get('SIGMOND_SKIP_BATCH', '').lower() in ('1', 'true', 'yes')
        
        def get_cmake_args(self): 
            return []
        
        def get_env_dict(self): 
            return {}
        
        def is_verbose(self): 
            return os.environ.get('SIGMOND_VERBOSE', '').lower() in ('1', 'true', 'yes')
        
        def get_build_jobs(self): 
            try:
                return int(os.environ.get('SIGMOND_BUILD_JOBS', str(os.cpu_count() or 1)))
            except (ValueError, TypeError):
                return 1
        
        def get_compiler_definitions(self): 
            return ['DOUBLEPRECISION', 'COMPLEXNUMBERS', 'DEFAULT_HDF5', 'NOGRACE', 'NO_MINUIT', 'XML', 'HDF5', 'LAPACK']
        # note: Only DEFAULT_FSTREAM exists (not DEFAULT_HDF5)
        # note: only GRACE exists (not NOGRACE)
        # note: only NO_MINUIT exists (not MINUIT)
        # note: Seems we should always have XML on
        # note: Only HDF5 exists 
        # note: Only LAPACK exists
        def get_extra_cxx_flags(self): 
            return []
    
    return FallbackConfig()

#https://stackoverflow.com/questions/47360113/compile-c-library-on-pip-install
        
class CMakeExtension(Extension):
    def __init__(self, name, sources=[]):
        Extension.__init__(self, name, sources=[])
        print(name, sources)
        self.sourcedir = os.path.join(os.path.abspath(''), "src", "sigmond", "source" )

class CMakeBuild(build_ext_orig):
    """Enhanced CMake build system with cross-platform support."""
    
    def run(self):
        self.check_cmake_available()
        for ext in self.extensions:
            self.build_extension(ext)
    
    def check_cmake_available(self):
        """Verify CMake is available and get version."""
        try:
            result = subprocess.check_output(['cmake', '--version'], stderr=subprocess.STDOUT, text=True)
            cmake_version = result.split('\n')[0]
            print(f"Using {cmake_version}")
        except (OSError, subprocess.CalledProcessError) as e:
            raise RuntimeError(
                f"CMake must be installed to build Sigmond extensions.\n"
                f"Error: {e}\n"
                f"Please install CMake 3.12+ and ensure it's in your PATH."
            )

    def build_extension(self, ext):
        """Build extension with robust configuration and error handling."""
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        
        # Load configuration with error handling
        config = load_configuration()
        
        # Validate configuration
        self.validate_build_environment(config)
        
        # Prepare build
        self.prepare_build_directory()
        cmake_args = self.generate_cmake_args(extdir, config)
        env = self.setup_build_environment(config)
        
        # Execute build steps
        self.configure_cmake(ext, cmake_args, env, config)
        self.build_cmake(config)
        self.install_cmake(config)
    
    def validate_build_environment(self, config):
        """Validate the build environment and configuration."""
        try:
            # Check Python version
            if sys.version_info < (3, 9):
                raise RuntimeError("Python 3.9+ is required for Sigmond")
            
            # Validate build jobs setting
            build_jobs = config.get_build_jobs()
            if not isinstance(build_jobs, int) or build_jobs < 1:
                raise RuntimeError(f"Invalid build_jobs setting: {build_jobs}")
            
            print(f"Build environment validated: Python {sys.version.split()[0]}, {build_jobs} parallel jobs")
            
        except Exception as e:
            raise RuntimeError(f"Build environment validation failed: {e}")
    
    def prepare_build_directory(self):
        """Ensure build directory exists."""
        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)
    
    def generate_cmake_args(self, extdir, config):
        """Generate CMake configuration arguments."""
        cfg = 'Debug' if self.debug else 'Release'
        
        cmake_args = [
            f'-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}',
            f'-DPYTHON_EXECUTABLE={sys.executable}',
            '-DCMAKE_VERBOSE_MAKEFILE:BOOL=OFF',
            '-Wno-dev',
            '--no-warn-unused-cli',
            '-DCMAKE_POLICY_DEFAULT_CMP0074=NEW',  # Suppress policy warnings
            f'-DCMAKE_RUNTIME_OUTPUT_DIRECTORY={extdir}',
            f'-DCMAKE_INSTALL_PREFIX={sys.prefix}',
            '-DVERSION_INFO=0.0.1',
            f'-DCMAKE_BUILD_TYPE={cfg}'
        ]
        
        # Add configuration-specific args
        cmake_args.extend(config.get_cmake_args())
        
        # Build C++ flags
        cxx_flags = ['-DDEFAULTENSFILE=\'\"\"\'', '-std=c++17']
        if cfg == 'Release':
            cxx_flags.extend(['-O3', '-w'])  # -w suppresses all warnings
        else:
            cxx_flags.append('-w')  # Suppress warnings in debug too
        
        # Add compiler definitions
        for definition in config.get_compiler_definitions():
            cxx_flags.append(f'-D{definition}')
        
        # Add extra flags
        cxx_flags.extend(config.get_extra_cxx_flags())
        cmake_args.append(f"-DCMAKE_CXX_FLAGS='{' '.join(cxx_flags)}'")
        
        return cmake_args
    
    def setup_build_environment(self, config):
        """Setup environment variables for build."""
        env = os.environ.copy()
        env['CXXFLAGS'] = '{} -DVERSION_INFO=\\"{}\\"'.format(
            env.get('CXXFLAGS', ''), self.distribution.get_version())
        
        # Apply configuration environment variables
        config_env = config.get_env_dict()
        env.update(config_env)
        
        return env
    
    def configure_cmake(self, ext, cmake_args, env, config):
        """Run CMake configure step."""
        cmake_verbose_args = ['--log-level=VERBOSE'] if config.is_verbose() else []
        cmake_cmd = ['cmake'] + cmake_verbose_args + [ext.sourcedir] + cmake_args
        
        if config.is_verbose():
            print(f"CMake configure command: {' '.join(cmake_cmd)}")
            print(f"CMake args: {cmake_args}")
        
        try:
            subprocess.check_call(cmake_cmd, cwd=self.build_temp, env=env)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"CMake configure failed with exit code {e.returncode}")
    
    def build_cmake(self, config):
        """Run CMake build step."""
        build_verbose_args = ['--verbose'] if config.is_verbose() else []
        build_cmd = ['cmake', '--build', '.', '--parallel', str(config.get_build_jobs())] + build_verbose_args
        
        if config.is_verbose():
            print(f"CMake build command: {' '.join(build_cmd)}")
        
        try:
            subprocess.check_call(build_cmd, cwd=self.build_temp)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"CMake build failed with exit code {e.returncode}")
    
    def install_cmake(self, config):
        """Run CMake install step."""
        install_verbose_args = ['--verbose'] if config.is_verbose() else []
        install_cmd = ['cmake', '--install', '.'] + install_verbose_args
        
        if config.is_verbose():
            print(f"CMake install command: {' '.join(install_cmd)}")
        
        try:
            subprocess.check_call(install_cmd, cwd=self.build_temp)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"CMake install failed with exit code {e.returncode}")

setup(
    name='sigmond',
    version="0.0.0.dev1",
    author="Sarah Skinner",
    author_email="sarakski@andrew.cmu.edu",
    description='A python interface and query toolfor the Sigmond analysis software.',
    long_description='',
    packages=['sigmond'],
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux"
    ],
    ext_modules=[CMakeExtension('sigmond',['src/sigmond/source/pysigmond/pysigmond.cc'])],
    python_requires='>=3.6',
    cmdclass=dict(build_ext=CMakeBuild),
    zip_safe=False,
)
