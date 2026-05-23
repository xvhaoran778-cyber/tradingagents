import sys
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box
from workflow.pipeline import TradingPipeline
from workflow.state import AgentState

app = typer.Typer(
    name="trading-agent",
    help="A股多智能体交易分析系统 - Multi-Agent LLM Trading Framework for A-Shares",
)
console = Console()


def _display_results(state: AgentState):
    d = state.final_decision
    if not d:
        console.print("[red]未生成决策[/red]")
        return

    rating_colors = {
        "Buy": "bold green", "Overweight": "green",
        "Hold": "bold yellow", "Underweight": "red",
        "Sell": "bold red",
    }
    color = rating_colors.get(d.rating, "white")

    console.print()
    console.print(Panel(
        f"[{color}]{d.rating_cn} ({d.rating})[/{color}]  |  "
        f"[bold]{d.executive_summary}[/bold]",
        title="🏛️ 最终投资决策",
        box=box.HEAVY,
    ))

    table = Table.grid(padding=(0, 2))
    table.add_row("[bold]投资论点[/bold]", d.investment_thesis)
    table.add_row("[bold]风险提示[/bold]", f"[red]{d.risk_warning}[/red]")
    table.add_row("[bold]目标价[/bold]", d.price_target or "未指定")
    table.add_row("[bold]持有周期[/bold]", d.time_horizon)
    console.print(Panel(table, title="📋 决策详情", box=box.ROUNDED))

    console.print()

    details = Table(title="📊 完整分析过程", box=box.ROUNDED)
    details.add_column("环节", style="bold cyan")
    details.add_column("内容", style="white", no_wrap=False)

    for label, content in [
        ("技术分析", state.technical_report),
        ("情绪分析", state.sentiment_report),
        ("新闻分析", state.news_report),
        ("基本面分析", state.fundamental_report),
    ]:
        summary = content[:200] + "..." if len(content) > 200 else content
        details.add_row(label, summary)

    if state.research_plan:
        rp = state.research_plan
        plan_text = (
            f"推荐: {rp.recommendation} (置信度: {rp.confidence})\n"
            f"理由: {rp.rationale}\n"
            f"风险: {', '.join(rp.key_risks)}"
        )
        details.add_row("研究结论", plan_text)

    if state.trade_proposal:
        tp = state.trade_proposal
        trade_text = (
            f"操作: {tp.action}\n"
            f"入场: {tp.entry_price_range or 'N/A'}\n"
            f"仓位: {tp.position_sizing or 'N/A'}\n"
            f"止损: {tp.stop_loss or 'N/A'}\n"
            f"目标: {tp.target_price or 'N/A'}"
        )
        details.add_row("交易方案", trade_text)

    for ra in state.risk_assessments:
        summary = ra.assessment[:150] + "..." if len(ra.assessment) > 150 else ra.assessment
        details.add_row(f"风控({ra.agent})", summary)

    console.print(details)
    console.print()


@app.command()
def analyze(
    ticker: str = typer.Argument(..., help="股票代码，如 600036"),
):
    """分析指定 A 股股票"""
    pipeline = TradingPipeline()
    try:
        state = pipeline.run(ticker)
        _display_results(state)
    except Exception as e:
        console.print(f"[red]分析出错: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def interactive():
    """交互式分析模式"""
    console.print(Panel.fit(
        "[bold cyan]A股多智能体交易分析系统[/bold cyan]\n"
        "基于 DeepSeek LLM 的多智能体协作框架\n"
        "分析师团队 → 研究员辩论 → 交易员 → 风控 → 投资组合经理",
        border_style="cyan",
    ))

    while True:
        ticker = typer.prompt("\n请输入股票代码（输入 q 退出）", default="600036")
        if ticker.lower() in ("q", "quit", "exit"):
            break

        pipeline = TradingPipeline()
        try:
            with console.status(f"[bold green]正在分析 {ticker}...") as status:
                state = pipeline.run(ticker)
            _display_results(state)
        except Exception as e:
            console.print(f"[red]分析出错: {e}[/red]")

    console.print("[green]感谢使用，再见！[/green]")


def main():
    if len(sys.argv) == 1:
        sys.argv.append("interactive")
    app()


if __name__ == "__main__":
    main()
