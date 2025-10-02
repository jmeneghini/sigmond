# Sigmond Analysis Suite

SigMonD is a software suite for analyzing Monte Carlo correlation functions in lattice QCD. It provides efficient tools for statistical analysis, fitting, and data visualization of two-point correlation functions.

## Installation

### Requirements

- C++ compiler with C++17 support
- CMake 3.13 or higher
- Python 3.9 or higher
- [LAPACK/BLAS](https://www.openmathlib.org/OpenBLAS/docs/install) libraries
- HDF5 library (version 1.10+)
- pybind11 (automatically installed)

Optional dependencies:
- [Grace](https://plasma-gate.weizmann.ac.il/Grace/) library for plotting
- [Minuit2](https://root.cern.ch/doc/master/Minuit2Page.html) for additional minimization algorithms


### Cloning

Clone the project's GitHub repository to your computer (and move into it) using

```bash
git clone https://github.com/jmeneghini/sigmond
cd sigmond
```

### Configuration

SigMonD's build system can be configured using a `sigmond.toml` configuration file. Create one using:

```bash
python configure.py create
```

### Configuration Options

Key configuration options in `sigmond.toml`:

- `build.skip_query`: Disable building of sigmond_query
- `build.skip_batch`: Disable building of sigmond_batch
- `build.precision`: Set floating-point precision (double/single)
- `build.numbers`: Set expected data type from input files (real, complex)
- `build.default_file_format`: Set the default output file format (hdf5, fstream)
- `build.enable_minuit`: Enable Minuit2 fitting algorithms  
- `build.enable_grace`: Enable Grace plotting support
- `build.verbose`: Enable verbose build output
- `build.build_jobs`: Specify the number of cores to use for building (0 = auto-detect)
- `build.batch_install_dir`: Specify the output directory for the sigmond_batch executable
- `build.query_install_dir`: Specify the output directory for the sigmond_query executable
- `libraries.*`: Specify custom library paths

Edit the configuration to specify library paths and build options as needed.

### Build & Install

Once the configuration is adjusted to your liking, 

```bash
pip install . -v
```

## Project Structure

```
sigmond/
├── configure.py           # Configuration management
├── src/sigmond/           # Python package
│   └── cpp/               # C++ source code
│       ├── analysis/      # Monte Carlo analysis algorithms
│       ├── data_handling/ # Data I/O and management
│       ├── fitting/       # Correlation function fitting
│       ├── observables/   # Observable definitions
│       ├── plotting/      # Plotting and visualization
│       ├── tasks/         # Analysis task framework
│       ├── apps/          # Standalone applications
│       └── pybind/        # Python bindings
├── tests/                 # Test suite
├── examples/              # Example input files
├── doc/                   # Documentation
└── ensembles.xml          # Ensemble definitions
```

## Usage

### Command Line Tools

**Batch analysis:**
Use `sigmond_batch` for running the numerical analysis

```bash
sigmond_batch input.xml
```

**Data queries:**

Use `sigmond_query` to analyze SigMonD formatted sampling files (`fstream` or `hdf5`)

```bash
sigmond_query --help
```

### Python Interface

```python
import sigmond
```

See the projects [sigmond_scripts](https://github.com/andrewhanlon/sigmond_scripts) and [PyCALQ](https://github.com/jmeneghini/PyCALQ.git)
for use of the `sigmond` Python interface, and to try yourself!

### Configuration Management

View current configuration:
```bash
./configure.py show
```

Validate configuration:
```bash
./configure.py validate
```

## Input Files

SigMonD uses XML input files to specify analysis tasks. The input format supports:

- Monte Carlo ensemble information
- Data file specifications
- Analysis task sequences
- Output formatting options

Example input files are available in the `examples/` directory.

## Ensemble Definitions

The `ensembles.xml` file contains metadata about lattice ensembles, including:
- Lattice dimensions and parameters
- Configuration counts and streaming information
- Ensemble-specific weights and corrections

## Documentation

Comprehensive documentation (not up to date) is available in the `doc/` directory.

## Contributing

This software is research code developed for lattice QCD analysis. For bug reports and feature requests, please use the project's issue tracker.

## License

See LICENSE file for licensing information.