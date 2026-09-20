# cinecli/ui.py

from rich.table import Table
from rich.console import Console
from rich.panel import Panel

console = Console()


def show_movies(movies):
    table = Table(title="🎬 Search Results")

    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Title", style="bold")
    table.add_column("Year", justify="center")

    for movie in movies:
        table.add_row(
            str(movie["id"]),
            movie["title"],
            str(movie["year"]),
        )

    console.print(table)


def show_movie_details(movie):
    description = (
        movie.get("summary")
        or movie.get("description_full")
        or "No description available."
    )

    text = (
        f"[bold]{movie['title']} ({movie['year']})[/bold]\n\n"
        f"🎭 Genres: {', '.join(movie.get('genres', []))}\n\n"
        f"{description}"
    )
    console.print(Panel(text, title="🎬 Movie Details", expand=False))


def show_torrents(torrents):
    table = Table(title="🧲 Available Torrents")

    table.add_column("Index", justify="center")
    table.add_column("Quality")
    table.add_column("Size")
    table.add_column("Seeds", justify="center")
    table.add_column("Peers", justify="center")

    for idx, torrent in enumerate(torrents):
        table.add_row(
            str(idx),
            torrent["quality"],
            torrent["size"],
            str(torrent["seeds"]),
            str(torrent["peers"]),
        )

    console.print(table)


def show_auto_selected(torrent):
    console.print(
        f"🎯 Auto-selected torrent: {torrent['quality']} ({torrent['size']})"
    )


def render_session_result(result):
    """Render a session's terminal state. Imported lazily to avoid a
    session <-> ui import cycle (session drives the ui views)."""
    from cinecli.session import SessionStatus

    if result.status is SessionStatus.DELIVERED:
        if result.action == "magnet":
            console.print(
                f"[green]🧲 Magnet link opened in your "
                f"{result.backend_label}![/green]"
            )
        else:
            console.print(
                f"[green]⬇ Torrent file download started in your "
                f"{result.backend_label}.[/green]"
            )
    elif result.status is SessionStatus.NO_TORRENTS:
        console.print("[red]❌ No torrents available.[/red]")
    elif result.status is SessionStatus.CANCELLED:
        console.print("[yellow]⚠ Operation cancelled.[/yellow]")
    elif result.status is SessionStatus.INVALID_SELECTION:
        console.print("[red]❌ Invalid selection.[/red]")
    elif result.status is SessionStatus.DELIVERY_FAILED:
        console.print(
            f"[red]❌ Failed to deliver to {result.backend_label}: "
            f"{result.error}[/red]"
        )
