import io

import matplotlib

matplotlib.use("Agg")  # draw without opening a window
import matplotlib.pyplot as plt  # noqa: E402


def draw_gantt(schedule, num_machines, title, window=None):
    """Draw the schedule as a Gantt chart and return the PNG as bytes.

    One row per machine, one colour per job. A red band shows a breakdown window.
    """
    colors = plt.get_cmap("tab20").colors
    figure, axis = plt.subplots(figsize=(11, 0.55 * num_machines + 1.8))

    for op in schedule:
        axis.barh(op["machine"], op["end"] - op["start"], left=op["start"],
                  color=colors[op["job"] % len(colors)], edgecolor="black", linewidth=0.5)
        if op["end"] - op["start"] >= 3:
            axis.text((op["start"] + op["end"]) / 2, op["machine"], str(op["job"]),
                      ha="center", va="center", fontsize=7)

    if window:
        axis.barh(window["machine"], window["end"] - window["start"], left=window["start"],
                  color="red", alpha=0.35, hatch="//", edgecolor="red", label="machine down")
        axis.legend(loc="upper right")

    axis.set_yticks(range(num_machines))
    axis.set_yticklabels([f"machine {m}" for m in range(num_machines)])
    axis.invert_yaxis()
    axis.set_xlabel("time (numbers in bars are job ids)")
    axis.set_title(title)
    figure.tight_layout()

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=110)
    plt.close(figure)
    return buffer.getvalue()
