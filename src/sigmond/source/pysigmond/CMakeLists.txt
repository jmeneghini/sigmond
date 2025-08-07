add_library(sigmond STATIC pysigmond.cc)
target_compile_definitions(sigmond PUBLIC sigmond)
