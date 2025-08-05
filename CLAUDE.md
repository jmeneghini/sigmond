# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build System

### Python Package Installation (Recommended)
```bash
pip install pybind11
pip install .
```

### Configuration File (Recommended)
Create a `sigmond.toml` file in the project root:
```toml
[build]
skip_query = false      # Skip sigmond_query executable
skip_batch = false      # Skip sigmond_batch executable  
scalar_type = "COMPLEXNUMBERS"
verbose = false
disable_rpath_macos = true  # Force absolute paths instead of @rpath on macOS (helpful for conda)

[libraries.hdf5]
hdf5_root = "/opt/hdf5"  # Custom HDF5 root path

[libraries.lapack]  
libraries = ["openblas"]  # Use OpenBLAS instead of default
```

### Environment Variables (Alternative)
```bash
# Skip building sigmond_query executable (faster builds)
SIGMOND_SKIP_QUERY=1 pip install .

# Skip building sigmond batch executable 
SIGMOND_SKIP_BATCH=1 pip install .

# Build only Python bindings (skip both executables)
SIGMOND_SKIP_QUERY=1 SIGMOND_SKIP_BATCH=1 pip install .

# Specify custom config file location
SIGMOND_CONFIG=/path/to/custom.toml pip install .
```

### Legacy Build System
The original Makefile-based build system is in `build/batch/`:
```bash
cd build/batch
# Edit Makefile to set INSTALL_DIR
make
make install  # optional
```

For Python bindings only:
```bash
cd build/pysigmond  
# Edit Makefile to set INSTALL_DIR, PYTHON, PYTHON_CONFIG
make
make install
```

## Dependencies

**Required:**
- C++ compiler with C++17 support
- Fortran compiler  
- Python 3.9+
- CMake 3.12+
- LAPACK library
- HDF5 library (version 1.10+)
- pybind11

The `install_dependencies.sh` script can install LAPACK and HDF5 dependencies if not available system-wide.

## Architecture Overview

Sigmond is a lattice QCD analysis suite organized into modular components:

### Core Modules
- **analysis/**: Bootstrap sampling, histograms, matrix operations, Monte Carlo estimates, observable handlers
- **data_handling/**: I/O handlers for binary/HDF5 files, ensemble/bins info, correlation data handlers  
- **fitting/**: Chi-squared fitting routines, minimizers, temporal correlation models
- **observables/**: Operator info, correlator definitions, momentum handling
- **plotting/**: Grace plot generation
- **tasks/**: Main task execution engine, XML parsing, utility functions

### Key Classes
- `MCObsHandler`: Central class for handling Monte Carlo observables
- `CorrelatorInfo`: Represents correlation function metadata
- `TaskHandler`: Executes analysis tasks from XML input
- `ChiSquare`: Base class for fitting routines
- `Bootstrapper`: Statistical bootstrap resampling
- `XMLHandler`: XML document parsing and manipulation

### Executables Built
- **sigmond_batch**: Main analysis program (XML-driven batch mode) - supports `-h/--help`
- **sigmond_query**: Binary file inspection tool
- **sigmond.so**: Python extension module (via pybind11)

## Usage Patterns

### XML-Driven Analysis
The main `sigmond_batch` executable processes XML input files with this structure:
```bash
sigmond_batch input.xml
sigmond_batch --help  # Show detailed usage information
```
```xml
<SigMonD>
  <Initialize>
    <ProjectName>NameOfProject</ProjectName>
    <Logfile>output.log</Logfile>
    <KnownEnsemblesFile>/path/ensembles.xml</KnownEnsemblesFile>
    <MCBinsInfo>...</MCBinsInfo>
    <MCSamplingInfo>...</MCSamplingInfo>
    <MCObservables>...</MCObservables>
  </Initialize>
  <TaskSequence>
    <Task><Action>...</Action></Task>
    <!-- Multiple tasks -->
  </TaskSequence>
</SigMonD>
```

### Python Interface
After installation, import as:
```python
import sigmond
```

### Configuration
- `ensembles.xml`: Contains ensemble definitions for lattice QCD runs
- Testing inputs: Located in `src/sigmond/testing/inputs/`

## Scalar Type Configuration

Set environment variable `SIGMOND_SCALAR_TYPE` to control numeric precision:
- `COMPLEXNUMBERS` (default): Complex number support
- Alternative types can be specified for specialized builds

## Configuration System

Sigmond supports both TOML configuration files and environment variables for build customization.

### Configuration File Locations (in order of precedence)
1. Path specified by `SIGMOND_CONFIG` environment variable
2. `./sigmond.toml` (project root)
3. `./.sigmond.toml` (hidden file in project root)  
4. `~/.config/sigmond.toml` (user config directory)

### Environment Variables
- `SIGMOND_SKIP_QUERY=1`: Skip building sigmond_query executable
- `SIGMOND_SKIP_BATCH=1`: Skip building sigmond_batch executable
- `SIGMOND_SCALAR_TYPE`: Set scalar number type (default: COMPLEXNUMBERS)
- `SIGMOND_CONFIG`: Path to custom configuration file
- `SIGMOND_VERBOSE=1`: Enable verbose build output

### Advanced Configuration
The TOML configuration allows specifying:
- Custom library search paths for HDF5, LAPACK/BLAS
- Compiler flags and linker options
- Platform-specific build settings
- Multiple library alternatives (e.g., OpenBLAS vs Intel MKL)

See `sigmond.example.toml` for detailed configuration examples.

## Testing

Testing is primarily done through XML input files in `src/sigmond/testing/inputs/`. These contain various test scenarios for:
- Correlator analysis
- Fitting procedures  
- Bootstrap sampling
- Matrix operations
- Data I/O operations

Run tests by executing sigmond_batch with the appropriate input XML files:
```bash
sigmond_batch src/sigmond/testing/inputs/input_sigmond1.xml
```

## macOS Support

The build system includes specific macOS compatibility:
- Uses Accelerate framework for BLAS/LAPACK operations
- Proper linking of gfortran and system libraries
- Cross-platform CMake configuration handles library differences

### Conda Environment Support

For conda environments on macOS, the build system can force absolute paths instead of using `@rpath` (relative paths), which can cause linking issues:

```toml
[build]
disable_rpath_macos = true  # Force absolute paths (default: true)
```

When `disable_rpath_macos = true`:
- Libraries use absolute install paths instead of `@rpath`
- Helps avoid "library not found" errors in conda environments
- Recommended for most conda users

To use `@rpath` instead (macOS default behavior):
```toml
[build]
disable_rpath_macos = false
```