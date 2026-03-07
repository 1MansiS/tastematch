import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # loads .env into os.environ before any provider is instantiated

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from agent.matcher import match_profile
from agent.parser import parse_menu
from agent.retrieval import retrieve_menu_content
from agent.router import InputType, classify_input
from agent.venue_detector import detect_venue_type
from agent.verdict import build_verdict
from llm.factory import get_provider
from models.profile import TasteProfile

console = Console()


def load_profile(path: str = "profile.json") -> TasteProfile:
    data = json.loads(Path(path).read_text())
    return TasteProfile(**data)


def render_verdict(verdict: "VerdictModel") -> None:  # noqa: F821
    score = verdict.match_score
    if score >= 80:
        color, emoji = "green", "🟢"
    elif score >= 60:
        color, emoji = "yellow", "🟡"
    else:
        color, emoji = "red", "🔴"

    title = Text(
        f"{emoji} TasteMatch: {verdict.match_label} — {verdict.venue_name}",
        style=f"bold {color}",
    )

    lines = [
        f"[bold]Match Score  :[/bold] {score}/100",
        f"[bold]Venue Type   :[/bold] {verdict.venue_type}",
        f"[bold]Menu Items   :[/bold] {verdict.matching_items} matching of {verdict.total_items} total",
    ]

    if verdict.best_picks:
        lines.append("")
        lines.append("[bold]Best Picks:[/bold]")
        for pick in verdict.best_picks:
            lines.append(f"  • {pick}")

    if verdict.warnings:
        lines.append("")
        lines.append("[bold]Watch Out:[/bold]")
        for warning in verdict.warnings:
            lines.append(f"  • {warning}")

    lines += [
        "",
        f"[bold]Confidence   :[/bold] {verdict.confidence}",
        f"[bold]Source       :[/bold] {verdict.source}",
    ]

    console.print(Panel("\n".join(lines), title=title, border_style=color))


async def run(user_input: str, profile_path: str, config_path: str, debug: bool = False) -> None:
    console.print(f"\n[dim]Analyzing:[/dim] {user_input}\n")

    input_type = classify_input(user_input)
    if input_type == InputType.UNKNOWN:
        console.print(
            "[red]Error:[/red] Unrecognized input. Provide a URL (http/https), "
            "an image file (.jpg .png .webp), or a PDF file (.pdf)."
        )
        sys.exit(1)

    llm = get_provider(config_path)
    profile = load_profile(profile_path)

    if input_type == InputType.URL:
        console.print("[dim]Fetching menu...[/dim]")
    elif input_type == InputType.IMAGE:
        console.print("[dim]Reading image with vision...[/dim]")
    else:
        console.print("[dim]Extracting text from PDF...[/dim]")

    content, source, confidence = await retrieve_menu_content(user_input, input_type, llm)

    if not content:
        if input_type == InputType.PDF:
            console.print(
                "[red]Error:[/red] No text found in PDF. "
                "Scanned PDFs are not yet supported — try a text-based PDF or an image."
            )
        else:
            console.print("[red]Error:[/red] Could not extract any content.")
        sys.exit(1)

    if debug:
        console.print(f"\n[dim]--- Extracted content ({len(content)} chars) ---[/dim]")
        console.print(f"[dim]{content[:800]}[/dim]")
        console.print(f"[dim]--- end ---[/dim]\n")

    venue_type = detect_venue_type(content=content)
    console.print(f"[dim]Detected venue type:[/dim] {venue_type.value}")

    console.print("[dim]Parsing menu with LLM...[/dim]")
    menu = await parse_menu(content, source, llm, debug=debug)
    console.print(f"[dim]Found {len(menu.items)} menu items[/dim]")

    if not menu.items:
        console.print(
            "[yellow]Warning:[/yellow] No menu items found. "
            "The source may not contain a readable menu."
        )
        sys.exit(1)

    console.print("[dim]Matching against your taste profile...[/dim]")
    match_result = await match_profile(menu, profile.food, llm)

    if input_type == InputType.URL:
        venue_name = source.split("//")[-1].split("/")[0]
    else:
        from pathlib import Path as _Path
        venue_name = _Path(source).stem

    verdict = build_verdict(match_result, menu, venue_name, venue_type.value, confidence)

    console.print()
    render_verdict(verdict)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tastematch",
        description="Agentic menu analyzer — scores any restaurant or coffee shop against your taste profile.",
        epilog=(
            "Examples:\n"
            "  python main.py https://dishoom.com/menus\n"
            "  python main.py menu.jpg\n"
            "  python main.py menu.pdf"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        help="URL (http/https), image file (.jpg .png .webp), or PDF file (.pdf)",
    )
    parser.add_argument(
        "--profile",
        default="profile.json",
        metavar="PATH",
        help="Path to taste profile JSON (default: profile.json)",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        metavar="PATH",
        help="Path to LLM config JSON (default: config.json)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show raw fetched content and LLM response for diagnosis",
    )

    args = parser.parse_args()
    try:
        asyncio.run(run(args.input, args.profile, args.config, args.debug))
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
