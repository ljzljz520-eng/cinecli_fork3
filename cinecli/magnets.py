from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Protocol

from transmission_rpc import Client

from cinecli.config import TransmissionConfig

TRACKERS = [
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:80/announce",
    "udp://tracker.coppersurfer.tk:6969/announce",
    "udp://glotorrents.pw:6969/announce",
]


def build_magnet(hash_: str, name: str) -> str:
    trackers = "".join(f"&tr={urllib.parse.quote(t)}" for t in TRACKERS)
    dn = urllib.parse.quote(name)
    return f"magnet:?xt=urn:btih:{hash_}&dn={dn}{trackers}"


def select_best_torrent(torrents: list[dict]) -> dict:
    """
    Pick the torrent with the highest quality and seeds.
    Quality order: 2160p > 1080p > 720p
    """
    quality_rank = {"2160p": 3, "1080p": 2, "720p": 1}

    return max(
        torrents,
        key=lambda t: (quality_rank.get(t["quality"], 0), t.get("seeds", 0)),
    )


class DeliveryBackend(Protocol):
    """Delivers a magnet link or .torrent URL to a download target."""

    label: str

    def deliver(self, url: str) -> None:
        ...


class WebBrowserBackend:
    """Falls back to the OS default browser / magnet handler."""

    label = "web browser"

    def deliver(self, url: str) -> None:
        webbrowser.open(url)


class TransmissionBackend:
    """Adds the torrent directly to a Transmission daemon."""

    label = "Transmission client"

    def __init__(self, client_options: dict):
        self._client_options = dict(client_options)

    def deliver(self, url: str) -> None:
        Client(**self._client_options).add_torrent(url)


def build_delivery_backend(
    transmission: TransmissionConfig,
) -> DeliveryBackend:
    if transmission.enabled:
        return TransmissionBackend(transmission.client_options)
    return WebBrowserBackend()
