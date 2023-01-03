#!/usr/bin/env python3
import logging
import sys

import pandas_common as pc

common_string = pc.common_substring(sys.argv[1:])
merged = "merged_{}.csv".format(common_string)
baseline_name = "msfem.all"

header, current = pc.read_files(sys.argv[1:])
headerlist = header["profiler"]
current = pc.sorted_f(current, True)
current = pc.speedup(headerlist, current, baseline_name)
# pprint(t_sections)
# pc.plot_msfem(current, merged, baseline_name=baseline_name)
# pc.plot_msfem(current, merged, series_name='parallel_efficiency', baseline_name=baseline_name)
try:
    for x, fn, base in [
        ("problem.epsilon", "eps", 10),
        ("grids.macro_cells_per_dim", "macro_cells", None),
    ]:
        pc.plot_error(
            data_frame=current,
            filename_base=merged,
            error_cols=["msfem_exact_H1s", "msfem_exact_L2"],
            xcol=x,
            labels=["$H^1_s$", "$L^2$", "walltime"],
            baseline_name=baseline_name,
            logy_base=None,
            logx_base=base,
        )

except KeyError as k:
    logging.error("No error data")
    logging.error(k)
current.transpose().to_csv(merged)
# current.transpose().to_excel(merged+'.xls')
# current.to_csv(merged)
