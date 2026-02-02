"""
YouTube Transcript Fetcher

A standalone module for fetching YouTube video transcripts.
Based on youtube_transcript_api, refactored for standalone use.

Dependencies: requests, defusedxml
"""

from dataclasses import dataclass, asdict
from enum import Enum
from itertools import chain
from html import unescape
from typing import List, Dict, Iterator, Iterable, Pattern, Optional, Any
from defusedxml import ElementTree
import re
from requests import HTTPError, Session, Response


# =============================================================================
# Settings
# =============================================================================

WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1/player?key={api_key}"
INNERTUBE_CONTEXT = {
    "client": {
        "clientName": "WEB",
        "clientVersion": "2.20230804.00.00",
    }
}


# =============================================================================
# Proxy Configuration
# =============================================================================

@dataclass
class ProxyConfig:
    """Configuration for proxy settings."""
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    retries_when_blocked: int = 3

    def to_requests_proxies(self) -> Optional[Dict[str, str]]:
        """Convert to requests-compatible proxy dict."""
        if not self.http_proxy and not self.https_proxy:
            return None
        proxies = {}
        if self.http_proxy:
            proxies["http"] = self.http_proxy
        if self.https_proxy:
            proxies["https"] = self.https_proxy
        return proxies


# =============================================================================
# Exceptions
# =============================================================================

class TranscriptError(Exception):
    """Base exception for transcript errors."""
    pass


class VideoUnavailable(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Video {video_id} is unavailable")


class YouTubeRequestFailed(TranscriptError):
    def __init__(self, video_id: str, error: HTTPError):
        self.video_id = video_id
        self.error = error
        super().__init__(f"Request failed for video {video_id}: {error}")


class NoTranscriptFound(TranscriptError):
    def __init__(self, video_id: str, language_codes: Iterable[str], transcript_list: Any):
        self.video_id = video_id
        self.language_codes = list(language_codes)
        self.transcript_list = transcript_list
        super().__init__(
            f"No transcript found for {video_id} in languages: {self.language_codes}\n"
            f"Available: {transcript_list}"
        )


class TranscriptsDisabled(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Transcripts are disabled for video {video_id}")


class NotTranslatable(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Transcript for video {video_id} is not translatable")


class TranslationLanguageNotAvailable(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Translation language not available for video {video_id}")


class FailedToCreateConsentCookie(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Failed to create consent cookie for video {video_id}")


class InvalidVideoId(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Invalid video ID: {video_id}")


class IpBlocked(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"IP blocked while fetching video {video_id}")


class RequestBlocked(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        self._proxy_config: Optional[ProxyConfig] = None
        super().__init__(f"Request blocked for video {video_id}")

    def with_proxy_config(self, proxy_config: Optional[ProxyConfig]) -> "RequestBlocked":
        self._proxy_config = proxy_config
        return self


class AgeRestricted(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Video {video_id} is age-restricted")


class VideoUnplayable(TranscriptError):
    def __init__(self, video_id: str, reason: Optional[str], subreasons: List[str]):
        self.video_id = video_id
        self.reason = reason
        self.subreasons = subreasons
        msg = f"Video {video_id} is unplayable: {reason}"
        if subreasons:
            msg += f" ({', '.join(subreasons)})"
        super().__init__(msg)


class YouTubeDataUnparsable(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"Could not parse YouTube data for video {video_id}")


class PoTokenRequired(TranscriptError):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"PoToken required for video {video_id}")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FetchedTranscriptSnippet:
    text: str
    start: float
    duration: float


@dataclass
class FetchedTranscript:
    """Represents a fetched transcript. Iterable over snippets."""

    snippets: List[FetchedTranscriptSnippet]
    video_id: str
    language: str
    language_code: str
    is_generated: bool

    def __iter__(self) -> Iterator[FetchedTranscriptSnippet]:
        return iter(self.snippets)

    def __getitem__(self, index) -> FetchedTranscriptSnippet:
        return self.snippets[index]

    def __len__(self) -> int:
        return len(self.snippets)

    def to_raw_data(self) -> List[Dict]:
        return [asdict(snippet) for snippet in self]


@dataclass
class _TranslationLanguage:
    language: str
    language_code: str


class _PlayabilityStatus(str, Enum):
    OK = "OK"
    ERROR = "ERROR"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"


class _PlayabilityFailedReason(str, Enum):
    BOT_DETECTED = "Sign in to confirm you're not a bot"
    AGE_RESTRICTED = "This video may be inappropriate for some users."
    VIDEO_UNAVAILABLE = "This video is unavailable"


# =============================================================================
# HTTP Helpers
# =============================================================================

def _raise_http_errors(response: Response, video_id: str) -> Response:
    try:
        if response.status_code == 429:
            raise IpBlocked(video_id)
        response.raise_for_status()
        return response
    except HTTPError as error:
        raise YouTubeRequestFailed(video_id, error)


# =============================================================================
# Transcript Classes
# =============================================================================

class Transcript:
    def __init__(
        self,
        http_client: Session,
        video_id: str,
        url: str,
        language: str,
        language_code: str,
        is_generated: bool,
        translation_languages: List[_TranslationLanguage],
    ):
        self._http_client = http_client
        self.video_id = video_id
        self._url = url
        self.language = language
        self.language_code = language_code
        self.is_generated = is_generated
        self.translation_languages = translation_languages
        self._translation_languages_dict = {
            tl.language_code: tl.language for tl in translation_languages
        }

    def fetch(self, preserve_formatting: bool = False) -> FetchedTranscript:
        if "&exp=xpe" in self._url:
            raise PoTokenRequired(self.video_id)
        response = self._http_client.get(self._url)
        snippets = _TranscriptParser(preserve_formatting=preserve_formatting).parse(
            _raise_http_errors(response, self.video_id).text,
        )
        return FetchedTranscript(
            snippets=snippets,
            video_id=self.video_id,
            language=self.language,
            language_code=self.language_code,
            is_generated=self.is_generated,
        )

    def __str__(self) -> str:
        return '{language_code} ("{language}"){translatable}'.format(
            language=self.language,
            language_code=self.language_code,
            translatable="[TRANSLATABLE]" if self.is_translatable else "",
        )

    @property
    def is_translatable(self) -> bool:
        return len(self.translation_languages) > 0

    def translate(self, language_code: str) -> "Transcript":
        if not self.is_translatable:
            raise NotTranslatable(self.video_id)
        if language_code not in self._translation_languages_dict:
            raise TranslationLanguageNotAvailable(self.video_id)
        return Transcript(
            self._http_client,
            self.video_id,
            f"{self._url}&tlang={language_code}",
            self._translation_languages_dict[language_code],
            language_code,
            True,
            [],
        )


class TranscriptList:
    """List of available transcripts for a YouTube video."""

    def __init__(
        self,
        video_id: str,
        manually_created_transcripts: Dict[str, Transcript],
        generated_transcripts: Dict[str, Transcript],
        translation_languages: List[_TranslationLanguage],
    ):
        self.video_id = video_id
        self._manually_created_transcripts = manually_created_transcripts
        self._generated_transcripts = generated_transcripts
        self._translation_languages = translation_languages

    @staticmethod
    def build(http_client: Session, video_id: str, captions_json: Dict) -> "TranscriptList":
        translation_languages = [
            _TranslationLanguage(
                language=tl["languageName"]["runs"][0]["text"],
                language_code=tl["languageCode"],
            )
            for tl in captions_json.get("translationLanguages", [])
        ]

        manually_created_transcripts = {}
        generated_transcripts = {}

        for caption in captions_json["captionTracks"]:
            is_asr = caption.get("kind", "") == "asr"
            transcript_dict = generated_transcripts if is_asr else manually_created_transcripts

            transcript_dict[caption["languageCode"]] = Transcript(
                http_client,
                video_id,
                caption["baseUrl"].replace("&fmt=srv3", ""),
                caption["name"]["runs"][0]["text"],
                caption["languageCode"],
                is_asr,
                translation_languages if caption.get("isTranslatable", False) else [],
            )

        return TranscriptList(
            video_id,
            manually_created_transcripts,
            generated_transcripts,
            translation_languages,
        )

    def __iter__(self) -> Iterator[Transcript]:
        return chain(
            self._manually_created_transcripts.values(),
            self._generated_transcripts.values(),
        )

    def find_transcript(self, language_codes: Iterable[str]) -> Transcript:
        return self._find_transcript(
            language_codes,
            [self._manually_created_transcripts, self._generated_transcripts],
        )

    def find_generated_transcript(self, language_codes: Iterable[str]) -> Transcript:
        return self._find_transcript(language_codes, [self._generated_transcripts])

    def find_manually_created_transcript(self, language_codes: Iterable[str]) -> Transcript:
        return self._find_transcript(language_codes, [self._manually_created_transcripts])

    def _find_transcript(
        self,
        language_codes: Iterable[str],
        transcript_dicts: List[Dict[str, Transcript]],
    ) -> Transcript:
        for language_code in language_codes:
            for transcript_dict in transcript_dicts:
                if language_code in transcript_dict:
                    return transcript_dict[language_code]
        raise NoTranscriptFound(self.video_id, language_codes, self)

    def __str__(self) -> str:
        def fmt(transcripts: Iterable) -> str:
            items = [f" - {t}" for t in transcripts]
            return "\n".join(items) if items else "None"

        return (
            f"Transcripts for {self.video_id}:\n\n"
            f"(MANUALLY CREATED)\n{fmt(self._manually_created_transcripts.values())}\n\n"
            f"(GENERATED)\n{fmt(self._generated_transcripts.values())}\n\n"
            f"(TRANSLATION LANGUAGES)\n{fmt(f'{tl.language_code} ({tl.language})' for tl in self._translation_languages)}"
        )


class TranscriptListFetcher:
    def __init__(self, http_client: Session, proxy_config: Optional[ProxyConfig] = None):
        self._http_client = http_client
        self._proxy_config = proxy_config

    def fetch(self, video_id: str) -> TranscriptList:
        return TranscriptList.build(
            self._http_client,
            video_id,
            self._fetch_captions_json(video_id),
        )

    def _fetch_captions_json(self, video_id: str, try_number: int = 0) -> Dict:
        try:
            html = self._fetch_video_html(video_id)
            api_key = self._extract_innertube_api_key(html, video_id)
            innertube_data = self._fetch_innertube_data(video_id, api_key)
            return self._extract_captions_json(innertube_data, video_id)
        except RequestBlocked as exception:
            retries = 0 if self._proxy_config is None else self._proxy_config.retries_when_blocked
            if try_number + 1 < retries:
                return self._fetch_captions_json(video_id, try_number=try_number + 1)
            raise exception.with_proxy_config(self._proxy_config)

    def _extract_innertube_api_key(self, html: str, video_id: str) -> str:
        pattern = r'"INNERTUBE_API_KEY":\s*"([a-zA-Z0-9_-]+)"'
        match = re.search(pattern, html)
        if match and len(match.groups()) == 1:
            return match.group(1)
        if 'class="g-recaptcha"' in html:
            raise IpBlocked(video_id)
        raise YouTubeDataUnparsable(video_id)

    def _extract_captions_json(self, innertube_data: Dict, video_id: str) -> Dict:
        self._assert_playability(innertube_data.get("playabilityStatus", {}), video_id)
        captions_json = innertube_data.get("captions", {}).get("playerCaptionsTracklistRenderer")
        if captions_json is None or "captionTracks" not in captions_json:
            raise TranscriptsDisabled(video_id)
        return captions_json

    def _assert_playability(self, playability_status_data: Dict, video_id: str) -> None:
        playability_status = playability_status_data.get("status")
        if playability_status != _PlayabilityStatus.OK.value and playability_status is not None:
            reason = playability_status_data.get("reason")
            if playability_status == _PlayabilityStatus.LOGIN_REQUIRED.value:
                if reason == _PlayabilityFailedReason.BOT_DETECTED.value:
                    raise RequestBlocked(video_id)
                if reason == _PlayabilityFailedReason.AGE_RESTRICTED.value:
                    raise AgeRestricted(video_id)
            if (
                playability_status == _PlayabilityStatus.ERROR.value
                and reason == _PlayabilityFailedReason.VIDEO_UNAVAILABLE.value
            ):
                if video_id.startswith("http://") or video_id.startswith("https://"):
                    raise InvalidVideoId(video_id)
                raise VideoUnavailable(video_id)
            subreasons = (
                playability_status_data.get("errorScreen", {})
                .get("playerErrorMessageRenderer", {})
                .get("subreason", {})
                .get("runs", [])
            )
            raise VideoUnplayable(video_id, reason, [run.get("text", "") for run in subreasons])

    def _create_consent_cookie(self, html: str, video_id: str) -> None:
        match = re.search('name="v" value="(.*?)"', html)
        if match is None:
            raise FailedToCreateConsentCookie(video_id)
        self._http_client.cookies.set("CONSENT", "YES+" + match.group(1), domain=".youtube.com")

    def _fetch_video_html(self, video_id: str) -> str:
        html = self._fetch_html(video_id)
        if 'action="https://consent.youtube.com/s"' in html:
            self._create_consent_cookie(html, video_id)
            html = self._fetch_html(video_id)
            if 'action="https://consent.youtube.com/s"' in html:
                raise FailedToCreateConsentCookie(video_id)
        return html

    def _fetch_html(self, video_id: str) -> str:
        response = self._http_client.get(WATCH_URL.format(video_id=video_id))
        return unescape(_raise_http_errors(response, video_id).text)

    def _fetch_innertube_data(self, video_id: str, api_key: str) -> Dict:
        response = self._http_client.post(
            INNERTUBE_API_URL.format(api_key=api_key),
            json={"context": INNERTUBE_CONTEXT, "videoId": video_id},
        )
        return _raise_http_errors(response, video_id).json()


class _TranscriptParser:
    _FORMATTING_TAGS = ["strong", "em", "b", "i", "mark", "small", "del", "ins", "sub", "sup"]

    def __init__(self, preserve_formatting: bool = False):
        self._html_regex = self._get_html_regex(preserve_formatting)

    def _get_html_regex(self, preserve_formatting: bool) -> Pattern[str]:
        if preserve_formatting:
            formats_regex = "|".join(self._FORMATTING_TAGS)
            formats_regex = r"<\/?(?!\/?(" + formats_regex + r")\b).*?\b>"
            return re.compile(formats_regex, re.IGNORECASE)
        return re.compile(r"<[^>]*>", re.IGNORECASE)

    def parse(self, raw_data: str) -> List[FetchedTranscriptSnippet]:
        return [
            FetchedTranscriptSnippet(
                text=re.sub(self._html_regex, "", unescape(xml_element.text)),
                start=float(xml_element.attrib["start"]),
                duration=float(xml_element.attrib.get("dur", "0.0")),
            )
            for xml_element in ElementTree.fromstring(raw_data)
            if xml_element.text is not None
        ]


# =============================================================================
# High-Level API
# =============================================================================

class YouTubeTranscriptApi:
    """
    High-level API for fetching YouTube transcripts.
    
    Usage:
        api = YouTubeTranscriptApi()
        transcript = api.get_transcript("VIDEO_ID")
        for snippet in transcript:
            print(f"{snippet.start}: {snippet.text}")
    """

    def __init__(self, proxy_config: Optional[ProxyConfig] = None):
        self._proxy_config = proxy_config

    def _get_session(self) -> Session:
        session = Session()
        if self._proxy_config:
            proxies = self._proxy_config.to_requests_proxies()
            if proxies:
                session.proxies.update(proxies)
        return session

    def list_transcripts(self, video_id: str) -> TranscriptList:
        session = self._get_session()
        fetcher = TranscriptListFetcher(session, self._proxy_config)
        return fetcher.fetch(video_id)

    def get_transcript(
        self,
        video_id: str,
        languages: Optional[List[str]] = None,
        preserve_formatting: bool = False,
    ) -> FetchedTranscript:
        if languages is None:
            languages = ["en"]
        transcript_list = self.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(languages)
        return transcript.fetch(preserve_formatting=preserve_formatting)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python transcripts.py <video_id> [language_code]")
        print("Example: python transcripts.py dQw4w9WgXcQ en")
        sys.exit(1)

    video_id = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "en"

    api = YouTubeTranscriptApi()
    try:
        transcript = api.get_transcript(video_id, languages=[language])
        print(json.dumps(transcript.to_raw_data(), indent=2))
    except TranscriptError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
