# $\Lambda$(1405) Correlator Analysis Example

See [arXiv:2307.13471](http://arxiv.org/abs/2307.13471) for the full analysis. In short, we are considering the $J=1/2$, negative parity resonance, the $\Lambda$(1405), in the strangeness $S=-1$ and isospin $I=0$ channel.

# Directory Structure

- `F_I0_Sm1.h5bins`: The averaged correlator bins in sigmond's HDF5 format. The only path is `/isosinglet_Sm1_G1u_P0`, which contains the correlator matrix for the G1u irrep at rest
- `PSQ0_G1u_rotation_input.xml`: Use `sigmond_batch` to run. Calculates the diagonal correlators and generates effective energy plots (comment DoPlot task out if built without Grace)
- `PSQ0_G1u_fit_input.xml`: Again, use `sigmond_batch` to run. Performs a "varying tmin" fit with a 2-exponential model and generates the corresponding plot (comment the task out if built without Grace)
