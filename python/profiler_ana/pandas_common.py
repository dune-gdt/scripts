import math


__author__ = "r_milk01"

import os
import pandas as pd

try:
    from configparser import ConfigParser
except ImportError:
    pass
import matplotlib.pyplot as plt
import itertools
import logging
import difflib
import colors as color_util

TIMINGS = ["usr", "sys", "wall"]
MEASURES = ["max", "avg"]
SPECIALS = ["run", "threads", "ranks", "cores"]
"""markers = {0: u'tickleft', 1: u'tickright', 2: u'tickup', 3: u'tickdown', 4: u'caretleft', u'D': u'diamond',
           6: u'caretup', 7: u'caretdown', u's': u'square', u'|': u'vline', u'': u'nothing', u'None': u'nothing',
           None: u'nothing', u'x': u'x', 5: u'caretright', u'_': u'hline', u'^': u'triangle_up', u' ': u'nothing',
           u'd': u'thin_diamond', u'h': u'hexagon1', u'+': u'plus', u'*': u'star', u',': u'pixel', u'o': u'circle',
           u'.': u'point', u'1': u'tri_down', u'p': u'pentagon', u'3': u'tri_left', u'2': u'tri_up', u'4': u'tri_right',
           u'H': u'hexagon2', u'v': u'triangle_down', u'8': u'octagon', u'<': u'triangle_left', u'>': u'triangle_right'}
"""
MARKERS = ["s", "o", 4, 5, 7, "|", "*", 1, 2, 3, 4, 6, 7]
FIGURE_OUTPUTS = ["png", "eps", "svg"]


import matplotlib  # noqa: E402

matplotlib.style.use("ggplot")
matplotlib.rc("font", family="sans-serif")
# http://nerdjusttyped.blogspot.de/2010/07/type-1-fonts-and-matplotlib-figures.html
matplotlib.rcParams["ps.useafm"] = True
matplotlib.rcParams["pdf.use14corefonts"] = True
matplotlib.rcParams["text.usetex"] = True
# plt.xkcd()

greyish = 0.9


class mdict(dict):
    def __missing__(self, key):
        key = key.replace("_", " ")
        return key


texsafe = mdict(
    {
        "cores": "\# Cores",
        "grids.total_macro_cells": "\# Macro Cells",
        "parallel_efficiency": "Parallel efficiency",
    }
)


def common_substring(strings, glue="_"):
    first, last = strings[0], strings[-1]
    seq = difflib.SequenceMatcher(None, first, last, autojunk=False)
    mb = seq.get_matching_blocks()
    return glue.join([first[m.a : m.a + m.size] for m in mb]).replace(os.path.sep, "")


def make_val(val, round_digits=8):
    try:
        return round(float(val), round_digits)
    except ValueError:
        return str(val)


def m_strip(s, timings=None, measures=None):
    timings = timings or TIMINGS
    measures = measures or MEASURES
    for t, m in itertools.product(timings, measures):
        s = s.replace("_{}_{}".format(m, t), "")
    return s


def read_files(dirnames, specials=None, cellcount=1):
    current = None
    specials = specials or SPECIALS
    header = {"memory": [], "profiler": [], "params": [], "errors": []}
    for fn in dirnames:
        assert os.path.isdir(fn), fn
        prof = os.path.join(fn, "profiler.csv")
        try:
            new = pd.read_csv(prof)
        except pd.parser.CParserError as e:
            logging.error("Failed parsing {}".format(prof))
            raise e
        header["profiler"] = list(new.columns.values)
        params = ConfigParser()
        param_fn = ["dsc_parameter.log", "dxtc_parameter.log"]
        subdirs = ["", "logs", "logdata"]
        params.read(
            [
                os.path.join(fn, sd, pfn)
                for sd, pfn in itertools.product(subdirs, param_fn)
            ]
        )
        p = {}
        for section in params.sections():
            p.update(
                {
                    "{}.{}".format(section, n): make_val(v)
                    for n, v in params.items(section)
                }
            )
        try:
            p["grids.total_macro_cells"] = math.pow(
                p["grids.macro_cells_per_dim"], p["grids.dim"]
            )
            p["grids.total_fine_cells"] = p["grids.total_macro_cells"] * math.pow(
                p["grids.micro_cells_per_macrocell_dim"], p["grids.dim"]
            )
        except KeyError:
            p["grids.total_macro_cells"] = p["grids.total_fine_cells"] = cellcount
        param = pd.DataFrame(p, index=[0])
        # mem
        mem = os.path.join(fn, "memory.csv")
        mem = pd.read_csv(mem)
        new = pd.concat((new, param, mem), axis=1)
        header["memory"] = mem.columns.values
        header["params"] = param.columns.values
        err = os.path.join(fn, "errors.csv")
        if os.path.isfile(err):
            err = pd.read_csv(err)
            header["errors"] = err.columns.values
            new = pd.concat((new, err), axis=1)

        current = current.append(new, ignore_index=True) if current is not None else new
    # ideal speedup account for non-uniform thread/rank ratio across columns
    count = len(current["ranks"])

    def cmp_value(j):
        return current["grids.total_macro_cells"][j] / (
            current["ranks"][j] * current["threads"][j]
        )

    values = [cmp_value(i) / cmp_value(0) for i in range(0, count)]
    current.insert(len(specials), "ideal_scaleup", pd.Series(values))

    def cmp_value(j):
        return current["ranks"][j] * current["threads"][j]

    values = [cmp_value(i) / cmp_value(0) for i in range(0, count)]
    current.insert(len(specials), "ideal_speedup", pd.Series(values))
    cores = [cmp_value(i) for i in range(0, count)]
    current.insert(len(specials), "cores", pd.Series(cores))
    current.insert(
        len(specials),
        "ideal_parallel_efficiency",
        pd.Series([1 for _ in range(0, count)]),
    )
    return header, current


def sorted_f(frame, ascending=True, sort_cols=None):
    sort_cols = sort_cols or ["ranks", "threads"]
    return frame.sort(columns=sort_cols, na_position="last", ascending=ascending)


def speedup(
    headerlist,
    current,
    baseline_name,
    specials=None,
    round_digits=3,
    timings=None,
    measures=None,
):
    timings = timings or TIMINGS
    measures = measures or MEASURES
    specials = specials or SPECIALS
    t_sections = set([m_strip(h) for h in headerlist]) - set(specials)

    for sec in t_sections:
        for t, m in itertools.product(timings, measures):
            source_col = "{}_{}_{}".format(sec, m, t)
            source = current[source_col]

            speedup_col = source_col + "_speedup"
            ref_value = source[0]
            values = [
                round(ref_value / source[i], round_digits) for i in range(len(source))
            ]
            current[speedup_col] = pd.Series(values)

            values = [
                current[speedup_col][i] / current["ideal_speedup"][i]
                for i in range(len(source))
            ]
            current[source_col + "_parallel_efficiency"] = pd.Series(values)

            # relative part of overall absolut timing category
            abspart_col = source_col + "_abspart"

            def ref_value(j):
                return float(current["{}_{}_{}".format(baseline_name, m, t)][j])

            values = [
                round(source[i] / ref_value(i), round_digits)
                for i in range(len(source))
            ]
            current[abspart_col] = pd.Series(values)

            # relative part of overall total walltime
            wallpart_col = source_col + "_wallpart"

            def ref_value(j):
                return float(current["{}_{}_{}".format(baseline_name, m, "wall")][j])

            values = [
                round(source[i] / ref_value(i), round_digits)
                for i in range(len(source))
            ]
            current[wallpart_col] = pd.Series(values)

        for m in measures:
            # thread efficiency
            source_col = "{}_{}_{}".format(sec, m, "usr")
            threadeff_col = source_col + "_threadeff"
            wall = current["{}_{}_{}".format(sec, m, "wall")]
            source = current[source_col]

            def value(j):
                return float(source[j] / (current["threads"][j] * wall[j]))

            values = [round(value(i), round_digits) for i in range(len(source))]
            current[threadeff_col] = pd.Series(values)

    current = sorted_f(current, True)
    return current


def scaleup(
    headerlist,
    current,
    baseline_name,
    specials=None,
    round_digits=3,
    timings=None,
    measures=None,
):
    timings = timings or TIMINGS
    measures = measures or MEASURES
    specials = specials or SPECIALS
    t_sections = set([m_strip(h) for h in headerlist]) - set(specials)

    for sec in t_sections:
        for t, m in itertools.product(timings, measures):
            source_col = "{}_{}_{}".format(sec, m, t)
            source = current[source_col]

            speedup_col = "{}_{}".format(source_col, "scaleup")
            ref_value = source[0]
            values = [
                round(ref_value / source[i], round_digits) for i in range(len(source))
            ]
            current[speedup_col] = pd.Series(values)

            # relative part of overall absolut timing category
            abspart_col = source_col + "_abspart"

            def ref_value(j):
                return float(current["{}_{}_{}".format(baseline_name, m, t)][j])

            values = [
                round(source[i] / ref_value(i), round_digits)
                for i in range(len(source))
            ]
            current[abspart_col] = pd.Series(values)

            # relative part of overall total walltime
            wallpart_col = source_col + "_wallpart"

            def ref_value(j):
                return float(current["{}_{}_{}".format(baseline_name, m, "wall")][j])

            values = [
                round(source[i] / ref_value(i), round_digits)
                for i in range(len(source))
            ]
            current[wallpart_col] = pd.Series(values)

        for m in measures:
            # thread efficiency
            source_col = "{}_{}_{}".format(sec, m, "usr")
            threadeff_col = source_col + "_threadeff"
            wall = current["{}_{}_{}".format(sec, m, "wall")]
            source = current[source_col]

            def value(j):
                return float(source[j] / (current["threads"][j] * wall[j]))

            values = [round(value(i), round_digits) for i in range(len(source))]
            current[threadeff_col] = pd.Series(values)

    current = sorted_f(current, True)
    return current


def plot_msfem(current, filename_base, series_name=None, xcol=None, baseline_name=None):
    xcol = xcol or "cores"
    series_name = series_name or "speedup"
    categories = ["all", "coarse.solve", "local.solve_for_all_cells", "coarse.assemble"]
    ycols = ["msfem.{}_avg_wall_{}".format(v, series_name) for v in categories] + [
        "ideal_{}".format(series_name)
    ]
    bar_cols = ["msfem.{}_avg_wall_abspart".format(v) for v in categories[1:]]
    labels = [
        "Overall",
        "Coarse solve",
        "Local assembly + solve",
        "Coarse assembly",
    ] + ["Ideal"]
    plot_common(
        current,
        filename_base,
        ycols,
        labels,
        bar=(bar_cols, ["Coarse solve", "Local assembly + solve", "Coarse assembly"]),
        xcol=xcol,
        series_name=series_name,
        baseline_name=baseline_name,
    )


def plot_fem(current, filename_base, series_name=None, xcol=None, baseline_name=None):
    xcol = xcol or "cores"
    series_name = series_name or "speedup"
    categories = ["apply", "solve", "constraints", "assemble"]
    ycols = ["fem.{}_avg_wall_speedup".format(v) for v in categories] + [
        "ideal_speedup"
    ]
    labels = ["Overall", "Solve", "Constraints", "Assembly", "Ideal"]
    plot_common(
        current, filename_base, ycols, labels, categories, baseline_name=baseline_name
    )


def _set_ax_margin(ax, margin=(0.05, 0.05)):
    xl, xr = ax.get_xlim()
    xmargin = math.fabs(xl - xr) * margin[0]
    ax.set_xlim((xl - xmargin, xr + xmargin))
    yb, yt = ax.get_ylim()
    ymargin = math.fabs(yb - yt) * margin[1]
    ax.set_ylim((yb - ymargin, yt + ymargin))


def plot_common(
    current,
    filename_base,
    ycols,
    labels,
    xcol,
    series_name,
    bar=None,
    logx_base=None,
    logy_base=None,
    color_map=None,
    bg_color=(greyish, greyish, greyish),
    margin=(0.05, 0.05),
    baseline_name=None,
):
    fig = plt.figure()  # noqa: F841
    color_map = color_map or color_util.discrete_cmap(len(labels), bg_color=bg_color)
    subplot = current.plot(x=xcol, y=ycols, colormap=color_map)
    for i, line in enumerate(subplot.lines):
        line.set_marker(MARKERS[i])
    plt.ylabel(texsafe[series_name].capitalize())
    plt.xlabel(texsafe[xcol])
    ax = subplot.figure.axes[0]
    if logx_base is not None:
        ax.set_xscale("log", basex=logx_base)
    if logy_base is not None:
        ax.set_yscale("log", basey=logy_base)
    lgd = plt.legend(
        ax.lines, labels, loc=2
    )  # , bbox_to_anchor=(1.05, 1),  borderaxespad=0., loc=2)
    ax.set_facecolor(bg_color)

    _set_ax_margin(ax, margin)

    lgd.get_frame().set_facecolor(bg_color)

    for fmt in FIGURE_OUTPUTS:
        plt.savefig(
            filename_base + "_{}.{}".format(series_name, fmt),
            bbox_extra_artists=(lgd,),
            dpi=1200,
        )

    if bar is None:
        return
    cols, labels = bar
    selection = current[cols]

    if baseline_name:
        baseline = current[baseline_name + "_avg_wall_abspart"]
        current["remainder"] = baseline - selection.transpose().sum()
        cols.append("remainder")
        labels.append("Remainder")
        selection = current[cols]

    labels = [texsafe[l] for l in labels]  # noqa: E741
    donot_data = selection.transpose()
    per_row = 4
    col_count = len(cols) if len(cols) < per_row else per_row
    layout = (len(cols) // col_count + 1, col_count)
    radius = 0.51
    datarows = len(selection)

    # donot
    for i in range(1, datarows + 1):
        ax = plt.subplot(layout[0], layout[1], i)
        donot_data[i - 1].plot(
            kind="pie",
            subplots=False,
            colormap=color_map,
            startangle=0,
            labels=None,
            autopct="$%.2f\\%% $",
            layout=layout,
            pctdistance=1.25,
            radius=radius,
            ax=ax,
        )
        ax.set_ylabel("")
        # setting radius is possbile if we comment next line
        ax.axis("equal")

        if i < datarows - 1:
            lgd = plt.legend(
                labels=labels,
                ncol=per_row,
                borderaxespad=1.0,
                loc="upper center",
                bbox_to_anchor=(0.5, 0.1),
                bbox_transform=plt.gcf().transFigure,
            )
        my_circle = plt.Circle((0, 0), radius=radius * 0.75, color="white")
        ax.add_patch(my_circle)
        ax.text(
            x=0,
            y=0,
            s="{}\ncores".format(current["cores"][i - 1]),
            color="black",
            ha="center",
            va="center",
        )

    for fmt in FIGURE_OUTPUTS:
        plt.savefig(
            filename_base + "_distribution_pie.{}".format(fmt),
            bbox_extra_artists=(lgd,),
            bbox_inches="tight",
            dpi=1200,
        )

    # bar
    xticks = ["{}\ncores".format(current["cores"][i]) for i in range(datarows)]
    ax = selection.plot(
        kind="bar",
        stacked=True,
        colormap=color_map,
    )
    for p in ax.patches:
        l, r = (  # noqa: E741
            p.get_x() + p.get_width() / 2,
            p.get_y() + p.get_height() / 2,
        )
        bbox_props = dict(boxstyle="round,pad=0.1", fc="white", alpha=0.6)
        ax.text(
            l,
            r,
            str(round(p.get_height(), 2)),
            bbox=bbox_props,
            ha="center",
        )
        ax.set_xticklabels(xticks, rotation=0, ha="center")
    patches, _ = ax.get_legend_handles_labels()
    lgd = ax.legend(
        patches,
        labels=labels,
        ncol=per_row,
        borderaxespad=1.0,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.05),
        bbox_transform=plt.gcf().transFigure,
    )
    for fmt in FIGURE_OUTPUTS:
        plt.savefig(
            filename_base + "_distribution_bar.{}".format(fmt),
            bbox_extra_artists=(lgd,),
            bbox_inches="tight",
            dpi=1200,
        )


def plot_error(
    data_frame,
    filename_base,
    error_cols,
    xcol,
    labels,
    baseline_name,
    logx_base=None,
    logy_base=None,
    color_map=None,
):
    wallt = "{}_avg_wall".format(baseline_name)
    select = error_cols + [wallt, xcol]
    data = data_frame.copy()[select]
    for i in error_cols + [wallt]:
        data[i] /= data[i].max()

    color_map = color_map or color_util.discrete_cmap(len(labels))
    ax = data.plot(x=xcol, y=error_cols + [wallt], colormap=color_map)
    for i, line in enumerate(ax.lines):
        line.set_marker(MARKERS[i])
    plt.ylabel("Normalized Error/Walltime")
    plt.xlabel(xcol)

    if logx_base is not None:
        ax.set_xscale("log", basex=logx_base)
    if logy_base is not None:
        ax.set_yscale("log", basey=logy_base)
    _set_ax_margin(ax)
    lgd = plt.legend(
        ax.lines, labels, loc="lower center"
    )  # , bbox_to_anchor=(1.05, 1),  borderaxespad=0., loc=2)

    common = common_substring(error_cols)
    for fmt in FIGURE_OUTPUTS:
        plt.savefig(
            "{}_error_{}_{}.{}".format(filename_base, common, xcol, fmt),
            bbox_extra_artists=(lgd,),
            bbox_inches="tight",
            dpi=1200,
        )
