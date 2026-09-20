"""Shared browse-to-launch session used by every CLI entry point.

Both ``watch`` and ``interactive`` only collect their own pre-input (a movie
id vs. a search hit) and then hand control to :class:`BrowseToLaunchSession`,
which owns the common flow:

    fetch details -> confirm torrents -> pick strategy -> pick action
    -> deliver to a backend -> report a terminal state

Configuration (already validated), a prompt adapter and a delivery backend
are injected explicitly per invocation, so the two commands can no longer
drift in default actions, Transmission handling or failure semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from rich.prompt import Prompt

from cinecli.api import get_movie_details
from cinecli.config import AppConfig
from cinecli.magnets import build_magnet, select_best_torrent
from cinecli.ui import show_auto_selected, show_movie_details, show_torrents


# -------------------------------------------------
# Terminal states
# -------------------------------------------------

class SessionStatus(str, Enum):
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    NO_TORRENTS = "no_torrents"
    INVALID_SELECTION = "invalid_selection"
    DELIVERY_FAILED = "delivery_failed"


@dataclass(frozen=True)
class SessionResult:
    status: SessionStatus
    action: str | None = None
    backend_label: str | None = None
    error: str | None = None

    @property
    def exit_code(self) -> int:
        return 0 if self.status is SessionStatus.DELIVERED else 1


# -------------------------------------------------
# Entry states
# -------------------------------------------------

@dataclass(frozen=True)
class MovieIdEntry:
    """``watch`` enters the session with a raw movie id."""

    movie_id: int


@dataclass(frozen=True)
class SearchSelectionEntry:
    """``interactive`` enters after the user picked a search hit."""

    movie: dict


# -------------------------------------------------
# Prompt port
# -------------------------------------------------

class PromptCancelled(Exception):
    """The user aborted a prompt (Ctrl+C / EOF)."""


class InvalidSelection(Exception):
    """The user entered a value outside the valid choice range."""


def validate_index(index, count: int) -> int:
    """Single range rule shared by pre-input and the session itself."""
    if not isinstance(index, int) or not 0 <= index < count:
        raise InvalidSelection
    return index


@runtime_checkable
class PromptAdapter(Protocol):
    """All interactive input the session (and command pre-input) needs."""

    def ask_search_query(self) -> str:
        ...

    def choose_movie_index(self, count: int) -> int:
        ...

    def choose_torrent_strategy(self) -> str:
        """Return ``"auto"`` or ``"manual"``."""
        ...

    def choose_torrent_index(self, count: int) -> int:
        ...

    def choose_action(self, default: str) -> str:
        """Return ``"magnet"`` or ``"torrent"``."""
        ...


class RichPromptAdapter:
    """Default adapter backed by rich/typer terminal prompts."""

    @staticmethod
    def _read(prompt: str, **kwargs) -> str:
        try:
            return Prompt.ask(prompt, **kwargs)
        except (KeyboardInterrupt, EOFError) as exc:
            raise PromptCancelled from exc

    @staticmethod
    def _read_index(prompt: str, count: int) -> int:
        raw = RichPromptAdapter._read(prompt)
        try:
            index = int(raw)
        except (TypeError, ValueError) as exc:
            raise InvalidSelection from exc
        if not 0 <= index < count:
            raise InvalidSelection
        return index

    def ask_search_query(self) -> str:
        return self._read("🔍 Search movies")

    def choose_movie_index(self, count: int) -> int:
        return self._read_index("Select movie index", count)

    def choose_torrent_strategy(self) -> str:
        return self._read(
            "Choose torrent strategy",
            choices=["auto", "manual"],
            default="auto",
        )

    def choose_torrent_index(self, count: int) -> int:
        return self._read_index("Select torrent index", count)

    def choose_action(self, default: str) -> str:
        return self._read(
            "Choose action",
            choices=["magnet", "torrent"],
            default=default,
        )


# -------------------------------------------------
# Session
# -------------------------------------------------

class BrowseToLaunchSession:
    def __init__(
        self,
        *,
        config: AppConfig,
        prompter: PromptAdapter,
        delivery,
    ):
        self._config = config
        self._prompter = prompter
        self._delivery = delivery

    def run(self, entry) -> SessionResult:
        if isinstance(entry, SearchSelectionEntry):
            movie_id = entry.movie["id"]
        elif isinstance(entry, MovieIdEntry):
            movie_id = entry.movie_id
        else:
            raise TypeError(f"unknown session entry state: {entry!r}")

        movie = get_movie_details(movie_id)
        return self._browse(movie)

    # -------------------------------------------------
    # Shared browse-to-launch flow
    # -------------------------------------------------

    def _browse(self, movie: dict) -> SessionResult:
        show_movie_details(movie)

        torrents = movie.get("torrents") or []
        if not torrents:
            return SessionResult(status=SessionStatus.NO_TORRENTS)

        show_torrents(torrents)

        try:
            torrent = self._select_torrent(torrents)
            action = self._prompter.choose_action(self._config.default_action)
        except PromptCancelled:
            return SessionResult(status=SessionStatus.CANCELLED)
        except InvalidSelection:
            return SessionResult(status=SessionStatus.INVALID_SELECTION)

        return self._deliver(movie, torrent, action)

    def _select_torrent(self, torrents: list[dict]) -> dict:
        strategy = self._prompter.choose_torrent_strategy()
        if strategy == "auto":
            torrent = select_best_torrent(torrents)
            show_auto_selected(torrent)
            return torrent
        index = self._prompter.choose_torrent_index(len(torrents))
        return torrents[validate_index(index, len(torrents))]

    def _deliver(
        self,
        movie: dict,
        torrent: dict,
        action: str,
    ) -> SessionResult:
        if action == "magnet":
            url = build_magnet(
                torrent["hash"],
                f"{movie['title']} {torrent['quality']}",
            )
        else:
            url = torrent["url"]

        try:
            self._delivery.deliver(url)
        except Exception as exc:  # backend failure is a terminal state
            return SessionResult(
                status=SessionStatus.DELIVERY_FAILED,
                action=action,
                backend_label=self._delivery.label,
                error=f"{type(exc).__name__}: {exc}",
            )

        return SessionResult(
            status=SessionStatus.DELIVERED,
            action=action,
            backend_label=self._delivery.label,
        )
