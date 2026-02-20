"""Main TestSys HTTP client with scraping capabilities."""

import getpass
import re
from typing import List, Optional
from pathlib import Path
from datetime import datetime, timedelta

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
        # Add default timeout if not specified
        # Use tuple (connect_timeout, read_timeout) for better control
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (10, 30)  # 10s to connect, 30s to read
        
        # Close existing connections to avoid keep-alive issues
        # This helps prevent hanging on repeated requests
        if hasattr(self.session, 'close') and path == "/t/allsubmits":
            # Only for allsubmits to avoid breaking other requests
            for adapter in self.session.adapters.values():
                adapter.close()
        
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
        # Add default timeout if not specified
        # Use tuple (connect_timeout, read_timeout) for better control
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (10, 30)  # 10s to connect, 30s to read
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
            
            # Parse contest deadline
            # Format: "Contest starts at 16.02.2026 00:00:00 and lasts 7199 minutes"
            if line.startswith("Contest starts at") and "lasts" in line:
                try:
                    # Extract start time and duration
                    match = re.search(
                        r"Contest starts at (\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}) and lasts (\d+) minutes",
                        line
                    )
                    if match:
                        start_str = match.group(1)
                        duration_minutes = int(match.group(2))
                        
                        # Parse start time: "16.02.2026 00:00:00"
                        start_time = datetime.strptime(start_str, "%d.%m.%Y %H:%M:%S")
                        
                        # Calculate deadline
                        deadline = start_time + timedelta(minutes=duration_minutes)
                        
                        # Store both formatted string and datetime object
                        user_info["deadline"] = deadline.strftime("%d.%m.%Y %H:%M:%S")
                        user_info["deadline_obj"] = deadline
                except (ValueError, AttributeError) as e:
                    # If parsing fails, just skip
                    pass

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

    def get_all_submissions(self, debug: bool = False) -> List[Submission]:
        """Scrape all submissions from the submissions page."""
        import time
        start_time = time.time()
        try:
            if debug:
                console.print(f"[cyan]DEBUG: [{time.strftime('%H:%M:%S')}] Starting HTTP GET request to /t/allsubmits...[/cyan]")
            
            html = self._get("/t/allsubmits")
            
            if debug:
                elapsed = time.time() - start_time
                console.print(f"[cyan]DEBUG: [{time.strftime('%H:%M:%S')}] HTTP request completed in {elapsed:.2f}s, received {len(html)} bytes[/cyan]")
                console.print(f"[cyan]DEBUG: Starting BeautifulSoup parsing...[/cyan]")
            
            soup = BeautifulSoup(html, "html.parser")
            
            if debug:
                console.print(f"[cyan]DEBUG: BeautifulSoup parsing completed[/cyan]")
            submissions = []

            # Find submissions table
            table = soup.find("table", {"border": "1"})
            if not table:
                if debug:
                    console.print("[yellow]DEBUG: No submissions table found[/yellow]")
                return submissions

            rows = table.find_all("tr")
            if debug:
                console.print(f"[dim]DEBUG: Found {len(rows)} rows in submissions table[/dim]")
            
            # Find header row to determine column positions
            header_found = False
            for idx, row in enumerate(rows):
                if not header_found:
                    # Skip until we find the header row
                    cells = row.find_all("td")
                    if cells and cells[0].get_text(strip=True) == "ID":
                        header_found = True
                        if debug:
                            console.print(f"[dim]DEBUG: Header row found at index {idx}[/dim]")
                    continue

                cols = row.find_all("td")
                if len(cols) < 6:
                    if debug:
                        console.print(f"[dim]DEBUG: Skipping row with {len(cols)} columns (need 6+)[/dim]")
                    continue

                submission = Submission(
                    id=cols[0].get_text(strip=True),
                    problem=cols[1].get_text(strip=True),
                    compiler=cols[4].get_text(strip=True),
                    result=cols[5].get_text(strip=True),
                    time=cols[3].get_text(strip=True),
                )
                submissions.append(submission)

            if debug:
                console.print(f"[dim]DEBUG: Parsed {len(submissions)} submissions[/dim]")
            return submissions
        except requests.exceptions.Timeout:
            console.print(f"[red]ERROR: Request to /t/allsubmits timed out after 30 seconds[/red]")
            console.print(f"[yellow]This may indicate a slow network or server issue.[/yellow]")
            return []
        except requests.exceptions.RequestException as e:
            console.print(f"[red]ERROR: Network error in get_all_submissions: {e}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]ERROR in get_all_submissions: {e}[/red]")
            if debug:
                import traceback
                console.print(f"[red]{traceback.format_exc()}[/red]")
            return []

    def get_feedback(self, submission_id: str) -> List[Test]:
        """Get detailed test feedback for a submission."""
        try:
            html = self._get("/t/feedback", params={"id": submission_id})
            soup = BeautifulSoup(html, "html.parser")
            tests = []

            # Find test results table
            table = soup.find("table")
            if not table:
                console.print("[yellow]Warning: No test results table found[/yellow]")
                return tests

            rows = table.find_all("tr")
            if len(rows) <= 1:
                console.print("[yellow]Warning: Empty test results table[/yellow]")
                return tests

            # Skip header row
            data_rows = rows[1:]

            for row in data_rows:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue

                # Handle different table formats
                test = Test(
                    test_id=cols[0].get_text(strip=True) if len(cols) > 0 else "",
                    result=cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    time=cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    memory=cols[3].get_text(strip=True) if len(cols) > 3 else "",
                    comment=cols[4].get_text(strip=True) if len(cols) > 4 else "",
                )
                tests.append(test)

            return tests
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to fetch test results: {e}[/yellow]")
            return []

    def get_statements_url(self) -> Optional[str]:
        """Get statements PDF URL from contest page."""
        try:
            html = self._get("/t/index.html")
            soup = BeautifulSoup(html, "html.parser")
            
            # Find link with text "Statements" or similar
            for link in soup.find_all("a"):
                link_text = link.get_text(strip=True).lower()
                if "statement" in link_text:
                    url = link.get("href")
                    if url:
                        return url
            
            console.print("[yellow]No statements link found on contest page[/yellow]")
            return None
        except Exception as e:
            console.print(f"[red]Failed to fetch statements URL: {e}[/red]")
            return None

    def download_statements(self, output_path: Optional[Path] = None) -> bool:
        """Download statements PDF with progress bar."""
        from rich.progress import Progress, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
        
        # Get statements URL
        url = self.get_statements_url()
        if not url:
            return False
        
        # Handle Google Drive links
        if "drive.google.com" in url:
            url = self._convert_gdrive_url(url)
        
        # Determine output filename
        if output_path is None:
            # Try to extract filename from URL
            if url.endswith(".pdf"):
                filename = url.split("/")[-1]
            else:
                filename = "statements.pdf"
            output_path = Path.cwd() / filename
        
        try:
            console.print(f"[cyan]Downloading from: {url}[/cyan]")
            
            # Stream download with progress bar
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get("content-length", 0))
            
            with Progress(
                *Progress.get_default_columns(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"[cyan]Downloading {output_path.name}",
                    total=total_size
                )
                
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))
            
            console.print(f"[green]Successfully downloaded to: {output_path}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to download statements: {e}[/red]")
            return False

    def _convert_gdrive_url(self, url: str) -> str:
        """Convert Google Drive view URL to direct download URL."""
        # Extract file ID from various Google Drive URL formats
        # https://drive.google.com/file/d/FILE_ID/view?usp=sharing
        # https://drive.google.com/open?id=FILE_ID
        
        file_id = None
        
        # Pattern 1: /file/d/FILE_ID/
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
        
        # Pattern 2: ?id=FILE_ID
        if not file_id:
            match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
            if match:
                file_id = match.group(1)
        
        if file_id:
            console.print(f"[cyan]Detected Google Drive file ID: {file_id}[/cyan]")
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        
        # If can't extract ID, return original URL
        return url

    def get_monitor_html(self) -> str:
        """
        Fetch the monitor (leaderboard) page HTML.
        Monitor page uses windows-1251 encoding instead of KOI8-R.
        """
        url = f"{self.BASE_URL}/t/monitor"
        response = self.session.get(url, timeout=(10, 30))
        response.raise_for_status()
        # Monitor page uses windows-1251 encoding
        return response.content.decode('windows-1251', errors="ignore")
