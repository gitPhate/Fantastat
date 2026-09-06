"""Browser-level behavioral tests for the offline auction UI."""

from __future__ import annotations

from contextlib import closing
import hashlib
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
REAL_DATABASE = ROOT / "output" / "fantastat.sqlite3"
CHROME_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
)


def _free_port() -> int:
    with closing(socket.socket()) as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])


def _add_synthetic_season(database: Path) -> None:
    """Add a small second season to the copied database, never the real one."""
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO seasons (season_start, label) VALUES (?, ?)",
            [(2025, "2025/26")],
        )
        connection.executemany(
            """
            INSERT INTO players
              (season_start, player_id, name, role, club, quotation, fvm)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (2025, 900001, "Test Rossi", "A", "Test FC", 10, 20),
                (2025, 900002, "Test Bianchi", "D", "Test FC", 5, 10),
                (2025, 900003, "Rossi", "A", "Test FC", 8, 15),
                (2025, 900004, "Rossini", "A", "Test FC", 7, 14),
                (2025, 900005, "Il Rossi", "A", "Test FC", 6, 13),
                (2025, 900006, "Test Zero", "C", "Test FC", 1, 2),
                (2025, 900007, "Test Stats Only", "C", "Test FC", 1, 2),
                (2025, 900008, "Test Ranking Only", "C", "Test FC", 1, 2),
            ],
        )
        connection.execute(
            """
            INSERT INTO rankings
              (season_start, player_id, rank, predicted_appearances,
               predicted_fantasy_average, expected_points, validation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (2025, 900001, 1, 30, 7.0, 210.4, "VALIDATO"),
        )
        connection.execute(
            """
            INSERT INTO guides
              (season_start, player_id, tier, function, notes, injuries,
               risks, set_pieces, hierarchy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (2025, 900001, "Top", "Titolare", "Nota test", None, None, None, None),
        )
        connection.execute(
            """
            INSERT INTO statistics
              (season_start, player_id, name, role, club, appearances,
               fantasy_average)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (2025, 900001, "Test Rossi", "A", "Test FC", 28, 6.8),
        )
        connection.executemany(
            """
            INSERT INTO statistics
              (season_start, player_id, name, role, club, appearances,
               fantasy_average)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (2025, 900006, "Test Zero", "C", "Test FC", 0, None),
                (2025, 900007, "Test Stats Only", "C", "Test FC", 12, 5.5),
            ],
        )
        connection.executemany(
            """
            INSERT INTO rankings
              (season_start, player_id, rank, predicted_appearances,
               predicted_fantasy_average, expected_points, validation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (2025, 900008, 8, 20, 6.0, 120, "PARZIALE"),
            ],
        )


class OfflineAuctionUiTests(unittest.TestCase):
    """Exercise the UI through its real local server and browser boundary."""

    @classmethod
    def setUpClass(cls) -> None:
        if not REAL_DATABASE.is_file():
            raise FileNotFoundError(
                f"Real UI database is required for integration tests: {REAL_DATABASE}"
            )
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Install the Python Playwright package before running UI integration tests. "
                "Do not install Playwright browsers; the suite uses installed Chrome."
            ) from exc

        chrome = next((path for path in CHROME_PATHS if path.is_file()), None)
        if chrome is None:
            raise FileNotFoundError(
                "Chrome executable not found in the configured Windows locations."
            )

        cls.tempdir = tempfile.TemporaryDirectory(prefix="fantastat-ui-")
        cls.database = Path(cls.tempdir.name) / "fantastat.sqlite3"
        shutil.copy2(REAL_DATABASE, cls.database)
        _add_synthetic_season(cls.database)

        cls.port = _free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "src" / "auction_ui.py"),
                "--database",
                str(cls.database),
                "--port",
                str(cls.port),
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls._wait_for_server()

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            headless=True,
            executable_path=str(chrome),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "playwright"):
            cls.playwright.stop()
        if hasattr(cls, "server"):
            cls.server.terminate()
            try:
                cls.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=5)
        if hasattr(cls, "tempdir"):
            cls.tempdir.cleanup()

    @classmethod
    def _wait_for_server(cls) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                raise RuntimeError("UI server exited during startup")
            try:
                with urlopen(f"{cls.base_url}/api/bootstrap", timeout=1) as response:
                    if response.status == 200:
                        return
            except (URLError, OSError):
                time.sleep(0.1)
        raise TimeoutError("UI server did not become ready within 10 seconds")

    def setUp(self) -> None:
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(self.base_url)
        self.page.wait_for_selector("#players tr")

    def tearDown(self) -> None:
        self.context.close()

    def _names(self) -> list[str]:
        return self.page.locator("#players tr td:first-child").all_text_contents()

    def _click_player(self, player_id: int, expected_text: str) -> None:
        self.page.locator(f'tr[data-id="{player_id}"]').click()
        self.page.wait_for_function(
            "text => document.querySelector('#detail').innerText.includes(text)",
            arg=expected_text,
        )

    @classmethod
    def _startup_error(cls, database: Path) -> str:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "src" / "auction_ui.py"),
                "--database",
                str(database),
                "--port",
                str(_free_port()),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            raise AssertionError("UI server unexpectedly started with an invalid snapshot")
        return result.stderr

    def test_startup_renders_real_catalogue_and_season_picker(self) -> None:
        self.assertEqual("2026", self.page.locator("#season").input_value())
        self.assertIn("2026/27", self.page.locator("#season").inner_text())
        self.assertIn("Adams C.", self._names())
        self.assertGreater(self.page.locator("#players tr").count(), 0)
        self.assertRegex(self.page.locator("#count").inner_text(), r"\d+ giocatori")
        self.assertEqual("2026", self.page.locator("#season").input_value())

    def test_catalogue_exposes_all_auction_evidence_columns(self) -> None:
        headers = self.page.locator("thead th").all_text_contents()
        self.assertEqual(
            ["Nome", "R", "Squadra", "Qt.", "FVM", "Pt.", "Pres.", "FM", "Fascia"],
            headers,
        )

    def test_catalogue_rounds_expected_points_for_display(self) -> None:
        self.page.locator("#season").select_option("2025")
        row = self.page.locator('tr[data-id="900001"]')
        self.assertEqual("210", row.locator("td").nth(5).inner_text())

    def test_search_filters_and_sorting_use_loaded_catalogue(self) -> None:
        self.page.locator("#search").fill("adams")
        self.assertEqual({"Adams C.", "Adams A."}, set(self._names()))

        self.page.locator("#role").select_option("A")
        self.page.locator("#club").select_option(label="Venezia")
        self.assertEqual(["Adams A."], self._names())
        self.assertEqual("1 giocatori", self.page.locator("#count").inner_text())

        self.page.locator("#search").fill("")
        self.page.locator("#role").select_option("")
        self.page.locator("#club").select_option("")
        expected_points = self.page.locator('th[data-key="expected_points"]')
        expected_points.click()
        expected_points.click()
        self.assertGreater(self.page.locator("#players tr").count(), 0)

    def test_search_orders_exact_prefix_and_substring_matches(self) -> None:
        self.page.locator("#season").select_option("2025")
        self.page.wait_for_selector('tr[data-id="900001"]')
        self.page.locator("#search").fill("rossi")
        names = self._names()
        self.assertEqual("Rossi", names[0])
        self.assertEqual("Rossini", names[1])
        self.assertEqual({"Test Rossi", "Il Rossi"}, set(names[2:]))

    def test_tier_filter_and_combined_filters(self) -> None:
        self.page.locator("#season").select_option("2025")
        self.page.wait_for_selector('tr[data-id="900001"]')
        self.page.locator("#fascia").select_option(label="Top")
        self.assertEqual(["Test Rossi"], self._names())
        self.page.locator("#role").select_option("D")
        self.assertEqual(["Test Bianchi"], self._names())
        self.assertEqual("", self.page.locator("#fascia").input_value())
        self.page.locator("#role").select_option("A")
        self.page.locator("#fascia").select_option(label="Top")
        self.page.locator("#club").select_option(label="Test FC")
        self.assertEqual(["Test Rossi"], self._names())

    def test_each_table_column_can_be_sorted_without_losing_rows(self) -> None:
        for header in self.page.locator("th[data-key]").all():
            header.click()
            self.assertGreater(self.page.locator("#players tr").count(), 0)
            header.click()
            self.assertGreater(self.page.locator("#players tr").count(), 0)

    def test_selecting_player_shows_current_evidence_and_history(self) -> None:
        self.page.locator('tr[data-id="6646"]').click()
        detail = self.page.locator("#detail")
        self.assertIn("Adams C.", detail.inner_text())
        self.assertIn("ID Fantacalcio: 6646", detail.inner_text())
        self.assertIn("Punti attesi", detail.inner_text())
        self.assertIn("Storico", detail.inner_text())
        self.assertGreaterEqual(detail.locator("table.history tbody tr").count(), 2)
        self.assertEqual(
            ["Stagione", "Squadra", "Pv", "FM", "Rank", "Pt. attesi"],
            detail.locator("table.history tr").first.locator("th").all_text_contents(),
        )
        self.assertEqual(2, detail.locator("svg.chart").count())

    def test_missing_guide_data_is_explicitly_unavailable(self) -> None:
        self.page.locator('tr[data-id="6021"]').click()
        detail = self.page.locator("#detail").inner_text()
        self.assertIn("Abankwah", detail)
        self.assertIn("Fascia\nNon disponibile", detail)
        self.assertIn("Infortuni\nNon disponibile", detail)

    def test_switching_players_preserves_catalogue_state(self) -> None:
        self.page.locator("#search").fill("Adams")
        self._click_player(6646, "Adams C.")
        self._click_player(7484, "Adams A.")
        self.assertEqual("Adams", self.page.locator("#search").input_value())
        self.assertIn("Adams A.", self.page.locator("#detail").inner_text())

    def test_injury_information_has_a_visible_alert(self) -> None:
        row = self.page.locator('tr[data-id="2167"]')
        icon = row.locator(".injury-alert")
        self.assertEqual(1, icon.count())
        self.assertEqual("Infortunato", icon.get_attribute("data-tooltip"))
        icon.hover()
        self.assertEqual("Infortunato", self.page.locator(".column-tooltip").inner_text())

    def test_partial_history_keeps_each_source_visible(self) -> None:
        self.page.locator("#season").select_option("2025")
        self.page.wait_for_selector('tr[data-id="900007"]')
        self._click_player(900007, "Test Stats Only")
        self.assertIn("12", self.page.locator("#detail").inner_text())
        self.assertIn("5.5", self.page.locator("#detail").inner_text())
        self.assertIn("—", self.page.locator("#detail").inner_text())

        self._click_player(900008, "Test Ranking Only")
        detail = self.page.locator("#detail").inner_text()
        self.assertIn("8", detail)
        self.assertIn("120", detail)
        self.assertIn("—", detail)

    def test_zero_appearances_are_not_missing_statistics(self) -> None:
        self.page.locator("#season").select_option("2025")
        self.page.wait_for_selector('tr[data-id="900006"]')
        self._click_player(900006, "Test Zero")
        self.assertIn("0", self.page.locator("#detail").inner_text())
        self.assertEqual(1, self.page.locator("svg.chart").count())

    def test_player_without_history_has_an_empty_history_state(self) -> None:
        self.page.locator("#season").select_option("2025")
        self.page.wait_for_selector('tr[data-id="900002"]')
        self._click_player(900002, "Test Bianchi")
        detail = self.page.locator("#detail")
        self.assertIn("Nessuna evidenza storica disponibile", detail.inner_text())
        self.assertEqual(0, detail.locator("svg.chart").count())

    def test_changing_season_resets_catalogue_state(self) -> None:
        self.page.locator("#search").fill("Adams")
        self.page.locator("#role").select_option("A")
        self.page.locator('tr[data-id="6646"]').click()

        self.page.locator("#season").select_option("2025")
        self.page.wait_for_function(
            """
            () => document.querySelector('#season').value === '2025'
              && Array.from(document.querySelectorAll('#players tr'))
                .some(row => row.textContent.includes('Test Rossi'))
            """
        )
        self.assertEqual("", self.page.locator("#search").input_value())
        self.assertEqual("", self.page.locator("#role").input_value())
        self.assertEqual("", self.page.locator("#club").input_value())
        self.assertEqual("", self.page.locator("#fascia").input_value())
        self.assertIn("Test Rossi", self._names())
        self.assertIn("Seleziona un giocatore", self.page.locator("#detail").inner_text())

    def test_documents_open_in_index_and_back_button_navigates_in_one_tab(self) -> None:
        self.page.locator("#guide").click()
        self.page.wait_for_url("**/guide.html*")
        self.page.wait_for_selector(".document-list a")
        self.assertIn("GUIDA_ASTA.md", self.page.locator(".document-list").inner_text())
        link = self.page.locator('.document-list a[href*="GUIDA_ASTA.md"]')
        link.click()
        self.page.wait_for_selector("#guide-content h1")
        self.assertIn("Guida all'asta", self.page.locator("#guide-content").inner_text())
        self.page.locator("#back").click()
        self.page.wait_for_url("**/guide.html*")
        self.page.locator("#back").click()
        self.page.wait_for_url(f"{self.base_url}/")

    def test_documents_do_not_require_a_season(self) -> None:
        self.page.goto(f"{self.base_url}/guide.html")
        self.page.wait_for_selector(".document-list")
        self.assertIn("RULES.md", self.page.locator("#guide-content").inner_text())

    def test_documents_ignore_the_old_season_query(self) -> None:
        self.page.goto(f"{self.base_url}/guide.html?season=9999")
        self.page.wait_for_selector(".document-list")
        self.assertIn("RULES.md", self.page.locator("#guide-content").inner_text())

    def test_static_assets_are_served_locally(self) -> None:
        for asset in ("/style.css", "/app.js", "/guide.js", "/marked.umd.js"):
            response = self.context.request.get(f"{self.base_url}{asset}")
            try:
                self.assertEqual(200, response.status)
                self.assertNotRegex(response.text(), r"<script[^>]+src=[\"']https?://")
            finally:
                response.dispose()

    def test_normal_workflow_makes_no_external_requests(self) -> None:
        external_requests: list[str] = []
        self.page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if not request.url.startswith(self.base_url)
            else None,
        )
        self.page.locator("#search").fill("Adams")
        self.page.locator("#role").select_option("A")
        self.page.locator('tr[data-id="6646"]').click()
        self.page.locator("#season").select_option("2025")
        self.page.wait_for_selector('tr[data-id="900001"]')
        self.assertEqual([], external_requests)

    def test_post_requests_are_rejected_as_read_only(self) -> None:
        response = self.context.request.post(f"{self.base_url}/api/catalogue")
        try:
            self.assertEqual(405, response.status)
            self.assertIn("sola lettura", response.json()["error"])
        finally:
            response.dispose()

    def test_normal_workflow_does_not_modify_the_snapshot(self) -> None:
        before = hashlib.sha256(self.database.read_bytes()).digest()
        self.page.locator("#search").fill("Adams")
        self.page.locator('tr[data-id="6646"]').click()
        self.page.locator("#season").select_option("2025")
        self.page.wait_for_selector('tr[data-id="900001"]')
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).digest())

    def test_invalid_api_inputs_return_actionable_errors(self) -> None:
        urls = (
            "/api/catalogue",
            "/api/catalogue?season=9999",
            "/api/player?season=2026&id=999999",
            "/api/guide?season=9999",
        )
        for path in urls:
            response = self.context.request.get(f"{self.base_url}{path}")
            try:
                self.assertEqual(400, response.status, path)
                self.assertTrue(response.json()["error"], path)
            finally:
                response.dispose()

    def test_missing_snapshot_has_recovery_instructions(self) -> None:
        missing = Path(self.tempdir.name) / "missing.sqlite3"
        self.assertIn("Snapshot mancante", self._startup_error(missing))

    def test_incompatible_snapshot_has_recovery_instructions(self) -> None:
        incompatible = Path(self.tempdir.name) / "incompatible.sqlite3"
        with sqlite3.connect(incompatible) as connection:
            connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO metadata VALUES ('schema_version', '999')")
        self.assertIn("Snapshot incompatibile", self._startup_error(incompatible))

    def test_snapshot_without_seasons_has_recovery_instructions(self) -> None:
        empty = Path(self.tempdir.name) / "empty.sqlite3"
        shutil.copy2(self.database, empty)
        with sqlite3.connect(empty) as connection:
            connection.execute("DELETE FROM seasons")
        self.assertIn("non contiene stagioni selezionabili", self._startup_error(empty))


if __name__ == "__main__":
    unittest.main()
