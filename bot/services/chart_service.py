import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date


def build_metric_chart(
    metric_name: str,
    dates: list[date],
    values: list[float],
    ref_min: float | None = None,
    ref_max: float | None = None,
) -> bytes:
    """Build a trend chart for a metric and return PNG bytes."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dates, values, marker="o", linewidth=2, color="#2196F3")

    if ref_min is not None and ref_max is not None:
        ax.axhspan(ref_min, ref_max, alpha=0.15, color="green", label="Норма")
    elif ref_min is not None:
        ax.axhline(ref_min, color="green", linestyle="--", alpha=0.5, label=f"Мин. норма: {ref_min}")
    elif ref_max is not None:
        ax.axhline(ref_max, color="red", linestyle="--", alpha=0.5, label=f"Макс. норма: {ref_max}")

    ax.set_title(metric_name, fontsize=14, fontweight="bold")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Значение")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    if ref_min is not None or ref_max is not None:
        ax.legend()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
