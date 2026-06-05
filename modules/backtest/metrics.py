import numpy as np
import pandas as pd

def calculate_metrics(trades, initial_capital):
    if not trades:
        return {"error": "No trades to analyze"}
    df = pd.DataFrame(trades)
    total_trades = len(df)
    winning_trades = df[df["pnl"] > 0]
    losing_trades = df[df["pnl"] < 0]
    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = win_count / total_trades if total_trades > 0 else 0
    total_pnl = df["pnl"].sum()
    final_capital = initial_capital + total_pnl
    gross_profit = winning_trades["pnl"].sum() if win_count > 0 else 0
    gross_loss = abs(losing_trades["pnl"].sum()) if loss_count > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    avg_win = winning_trades["pnl"].mean() if win_count > 0 else 0
    avg_loss = abs(losing_trades["pnl"].mean()) if loss_count > 0 else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if total_trades > 0 else 0
    total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100
    df["cumulative_pnl"] = df["pnl"].cumsum()
    peak = df["cumulative_pnl"].cummax()
    drawdown = peak - df["cumulative_pnl"]
    max_dd = drawdown.max()
    max_dd_pct = (max_dd / initial_capital) * 100
    if len(df) > 1 and max_dd > 0:
        daily_returns = df["pnl"] / initial_capital
        sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    else:
        sharpe = 0
    avg_bars_held = df["bars_held"].mean() if "bars_held" in df.columns else 0
    return {
        "total_trades": total_trades,
        "winning_trades": win_count,
        "losing_trades": loss_count,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "final_capital": final_capital,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": sharpe,
        "avg_bars_held": avg_bars_held,
    }
