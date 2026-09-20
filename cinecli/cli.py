import typer
from rich.console import Console

from cinecli.api import search_movies
from cinecli.config import ConfigError, load_config
from cinecli.magnets import build_delivery_backend
from cinecli.session import (
    BrowseToLaunchSession,
    InvalidSelection,
    MovieIdEntry,
    PromptCancelled,
    RichPromptAdapter,
    SearchSelectionEntry,
    SessionResult,
    SessionStatus,
    validate_index,
)
from cinecli.ui import render_session_result, show_movies

# -------------------------------------------------
# App + Console
# -------------------------------------------------

app = typer.Typer(
    help="🎬 CineCLI — Browse and torrent movies from your terminal",
)

console = Console()

# -------------------------------------------------
# Shared wiring
# -------------------------------------------------

def _run_browse_session(entry) -> None:
    """Assemble a session with freshly validated, explicitly injected
    dependencies, render its terminal state and apply one exit-code
    mapping for every entry point."""
    try:
        config = load_config()
    except ConfigError as exc:
        console.print(f"[red]❌ Invalid configuration: {exc}[/red]")
        raise typer.Exit(code=2)

    session = BrowseToLaunchSession(
        config=config,
        prompter=RichPromptAdapter(),
        delivery=build_delivery_backend(config.transmission),
    )

    _finish(session.run(entry))


def _finish(result: SessionResult) -> None:
    render_session_result(result)
    if result.exit_code:
        raise typer.Exit(code=result.exit_code)


# -------------------------------------------------
# Search command
# -------------------------------------------------

@app.command()
def search(
    query: list[str] = typer.Argument(..., help="Movie name to search for"),
    limit: int = typer.Option(10),
):
    search_query = " ".join(query)
    movies = search_movies(search_query, limit)

    if not movies:
        console.print("[red]❌ No movies found.[/red]")
        raise typer.Exit(code=1)

    show_movies(movies)

# -------------------------------------------------
# Watch command — enters the session from a movie id
# -------------------------------------------------

@app.command()
def watch(movie_id: int):
    """
    View movie details and open torrent (magnet or .torrent file)
    """
    _run_browse_session(MovieIdEntry(movie_id=movie_id))

# -------------------------------------------------
# Interactive command — enters from a search selection
# -------------------------------------------------

@app.command()
def interactive():
    """
    Interactive movie browser (search → select → torrent)
    """
    prompter = RichPromptAdapter()

    try:
        query = prompter.ask_search_query()
    except PromptCancelled:
        _finish(SessionResult(status=SessionStatus.CANCELLED))
        return

    movies = search_movies(query, limit=10)
    if not movies:
        console.print("[red]❌ No movies found.[/red]")
        raise typer.Exit(code=1)

    show_movies(movies)

    try:
        index = validate_index(prompter.choose_movie_index(len(movies)), len(movies))
    except PromptCancelled:
        _finish(SessionResult(status=SessionStatus.CANCELLED))
        return
    except InvalidSelection:
        _finish(SessionResult(status=SessionStatus.INVALID_SELECTION))
        return

    _run_browse_session(SearchSelectionEntry(movie=movies[index]))
