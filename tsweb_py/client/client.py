"""Main TestSys HTTP client with scraping capabilities."""

import getpass
import re
from typing import List, Optional
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from rich.console import Console

from .models import Contest, Submission, Test, Problem, Compiler
from ..config.global_config import GlobalConfig


console = Console()


class TestSysClient:
    """HTTP client for interacting with TestSys online judge."""

    BASE_URL = "https://tsweb.ru"
    ENCODING = "koi8-r"

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the client."""
        self.config_path = config_path or Path.home() / ".tsweb_py.global"
        self.cookies_path = Path.home() / ".tsweb_py.cookies"
        self.session = requests.Session()
        self.config = GlobalConfig.load(self.config_path)

        # Restore cookies from pickle file
        saved_cookies = GlobalConfig.load_cookies(self.cookies_path)
        if saved_cookies:
            self.session.cookies = saved_cookies

    def _save_config(self):
        """Save current config and cookies to disk."""
        # Save credentials
        self.config.save(self.config_path)
        # Save cookies separately using pickle
        GlobalConfig.save_cookies(self.session.cookies, self.cookies_path)

    def _get(self, path: str, **kwargs) -> str:
        """Make GET request and decode with KOI8-R."""
        url = f"{self.BASE_URL}{path}"
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response.content.decode(self.ENCODING, errors="ignore")

    def _post(self, path: str, data: dict = None, **kwargs) -> str:
        """Make POST request and decode with KOI8-R."""
        url = f"{self.BASE_URL}{path}"
        # Encode form data to KOI8-R if provided
        if data:
            encoded_data = {
                k: v.encode(self.ENCODING) if isinstance(v, str) else v
                for k, v in data.items()
            }
        else:
            encoded_data = None
        response = self.session.post(url, data=encoded_data, **kwargs)
        response.raise_for_status()
        return response.content.decode(self.ENCODING, errors="ignore")

    def login(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> bool:
        """
        Authenticate with TestSys.
        If credentials not provided, prompts for them.
        """
        if username is None:
            username = input("Username (team): ")
        if password is None:
            password = getpass.getpass("Password: ")

        # Clear existing cookies to avoid conflicts
        self.session.cookies.clear()

        # GET login with params
        try:
            login_response = self.session.get(
                f"{self.BASE_URL}/t/index.html",
                params={
                    "team": username,
                    "password": password,
                    "op": "login",
                    "contestid": "",
                },
            )

            if login_response.status_code != 200:
                console.print("[red]Login failed: Server error[/red]")
                return False

            # Check if we're actually logged in by checking main page
            main_response = self.session.get(f"{self.BASE_URL}/t/")
            main_response.encoding = self.ENCODING
            main_html = main_response.text

            # Check for error page
            if "<HTML><HEAD><TITLE>Error</TITLE>" in main_html:
                console.print("[red]Login failed: Invalid credentials[/red]")
                return False

            # Check if not logged in
            if "You are currently not logged in" in main_html:
                console.print("[red]Login failed: Invalid credentials[/red]")
                return False

            # Save credentials and cookies
            self.config.user = username
            self.config.password = password
            self._save_config()

            console.print(f"[green]Successfully logged in as {username}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Login error: {e}[/red]")
            return False

    def auto_login(self) -> bool:
        """Attempt to login with saved credentials."""
        if not self.config.has_credentials():
            return False

        # First check if current session is still valid
        try:
            html = self._get("/t/")
            if "You are currently not logged in" not in html:
                console.print(
                    f"[green]Using saved session for {self.config.user}[/green]"
                )
                return True
        except:
            pass

        # Session expired, re-login
        return self.login(self.config.user, self.config.password)

    def get_available_contests(self) -> List[Contest]:
        """Scrape list of available contests."""
        html = self._get("/t/contests", params={"mask": "1"})
        soup = BeautifulSoup(html, "html.parser")
        contests = []

        # Find contest table
        table = soup.find("table", {"border": "1"})
        if not table:
            return contests

        rows = table.find_all("tr")[1:]  # Skip header
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            # Extract contest info
            contest_id = cols[0].get_text(strip=True)
            name = cols[1].get_text(strip=True)
            status = cols[2].get_text(strip=True)

            contest = Contest(id=contest_id, name=name, status=status)
            contests.append(contest)

        return contests

    def change_contest(self, contest_id: str) -> bool:
        """Switch to a different contest."""
        try:
            # Use session directly to avoid cookie issues
            response = self.session.get(
                f"{self.BASE_URL}/t/index",
                params={"op": "changecontest", "newcontestid": contest_id},
            )
            response.encoding = self.ENCODING
            html = response.text

            # Check for success - the page should redirect or show success
            # Usually after changing contest, we get redirected to main page
            if response.status_code == 200:
                self._save_config()
                return True
            return False
        except Exception as e:
            console.print(f"[red]Failed to change contest: {e}[/red]")
            return False

    def get_user_info(self) -> dict:
        """Get current user information."""
        html = self._get("/t/")
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text()
        lines = page_text.split("\n")

        user_info = {}
        for line in lines:
            line = line.strip()
            if line.startswith("You are") and not line.startswith("You are currently"):
                user_info["name"] = line.replace("You are ", "")
            if line.startswith("Assigned contest:"):
                user_info["contest"] = line.replace("Assigned contest: ", "")

        return user_info

    def get_problems(self) -> List[Problem]:
        """Scrape available problems from submit page."""
        html = self._get("/t/submit")
        soup = BeautifulSoup(html, "html.parser")
        problems = []

        # Find problem select dropdown
        select = soup.find("select", {"name": "prob"})
        if not select:
            return problems

        for option in select.find_all("option"):
            problem_id = option.get("value", "")
            problem_name = option.get_text(strip=True)

            # Skip disabled/placeholder options
            if problem_id and not option.get("disabled"):
                problems.append(
                    Problem(problem_id=problem_id, problem_name=problem_name)
                )

        return problems

    def get_compilers(self) -> List[Compiler]:
        """Scrape available compilers from submit page."""
        html = self._get("/t/submit")
        soup = BeautifulSoup(html, "html.parser")
        compilers = []

        # Find compiler select dropdown
        select = soup.find("select", {"name": "lang"})
        if not select:
            return compilers

        for option in select.find_all("option"):
            compiler_id = option.get("value", "")
            full_name = option.get_text(strip=True)

            # Skip disabled/placeholder options
            if compiler_id and not option.get("disabled"):
                # Extract language prefix (e.g., "cpp:", "py:")
                lang = "Unknown"
                if ":" in full_name:
                    lang_prefix = full_name.split(":")[0].strip()
                    lang = lang_prefix

                compilers.append(
                    Compiler(
                        compiler_id=compiler_id,
                        compiler_name=full_name,
                        compiler_lang=lang,
                    )
                )

        return compilers

    def submit(self, problem_id: str, compiler_id: str, solution_path: Path) -> bool:
        """Submit a solution."""
        try:
            with open(solution_path, "rb") as f:
                files = {"file": (solution_path.name, f, "application/octet-stream")}
                data = {"prob": problem_id, "lang": compiler_id}

                url = f"{self.BASE_URL}/t/submit"
                response = self.session.post(url, data=data, files=files)
                response.raise_for_status()

                html = response.content.decode(self.ENCODING, errors="ignore")

                # Check for errors
                soup = BeautifulSoup(html, "html.parser")
                if "<TITLE>Error</TITLE>" in html or "error" in html.lower():
                    console.print(f"[red]Submission may have failed[/red]")
                    return False

                console.print(f"[cyan]Submitted {solution_path.name}[/cyan]")
                console.print(
                    f"[yellow]Problem: {problem_id}  [magenta]Compiler: {compiler_id}[/magenta][/yellow]"
                )
                return True
        except Exception as e:
            console.print(f"[red]Failed to submit: {e}[/red]")
            return False

    def get_all_submissions(self) -> List[Submission]:
        """Scrape all submissions from the submissions page."""
        html = self._get("/t/allsubmits")
        soup = BeautifulSoup(html, "html.parser")
        submissions = []

        # Find submissions table
        table = soup.find("table", {"border": "1"})
        if not table:
            return submissions

        rows = table.find_all("tr")
        # Find header row to determine column positions
        header_found = False
        for row in rows:
            if not header_found:
                # Skip until we find the header row
                cells = row.find_all("td")
                if cells and cells[0].get_text(strip=True) == "ID":
                    header_found = True
                continue

            cols = row.find_all("td")
            if len(cols) < 6:
                continue

            submission = Submission(
                id=cols[0].get_text(strip=True),
                problem=cols[1].get_text(strip=True),
                compiler=cols[4].get_text(strip=True),
                result=cols[5].get_text(strip=True),
                time=cols[3].get_text(strip=True),
            )
            submissions.append(submission)

        return submissions

    def get_feedback(self, submission_id: str) -> List[Test]:
        """Get detailed test feedback for a submission."""
        html = self._get("/t/feedback", params={"id": submission_id})
        soup = BeautifulSoup(html, "html.parser")
        tests = []

        # Find test results table
        table = soup.find("table")
        if not table:
            return tests

        rows = table.find_all("tr")[1:]  # Skip header

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            test = Test(
                test_id=cols[0].get_text(strip=True),
                result=cols[1].get_text(strip=True),
                time=cols[2].get_text(strip=True) if len(cols) > 2 else "",
                memory=cols[3].get_text(strip=True) if len(cols) > 3 else "",
                comment=cols[4].get_text(strip=True) if len(cols) > 4 else "",
            )
            tests.append(test)

        return tests
