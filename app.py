import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict

# Simulated cloud storage directory for saved code files.
CLOUD_STORAGE_DIR = Path("cloud_storage")
CLOUD_STORAGE_DIR.mkdir(exist_ok=True)


@dataclass
class CodeFile:
    user_id: str
    filename: str
    content: str
    path: Path = field(init=False)

    def __post_init__(self):
        self.path = CLOUD_STORAGE_DIR / f"{self.user_id}_{self.filename}"
        self.save()

    def save(self) -> None:
        self.path.write_text(self.content, encoding="utf-8")

    def load(self) -> str:
        return self.path.read_text(encoding="utf-8")


class CodeEditor:
    def open(self, code: str, filename: str = "main.py", user_id: str = "user") -> CodeFile:
        return CodeFile(user_id=user_id, filename=filename, content=code)

    def update(self, code_file: CodeFile, new_code: str) -> None:
        code_file.content = new_code
        code_file.save()


class CompilerEngine:
    def check(self, code: str, filename: str = "<user_code>") -> Optional[SyntaxError]:
        try:
            compile(code, filename, "exec")
            return None
        except SyntaxError as exc:
            return exc

    def suggest_fix(self, code: str, error: SyntaxError) -> Optional[str]:
        message = error.msg or ""
        lines = code.splitlines()

        if "expected ':'" in message and 1 <= error.lineno <= len(lines):
            line = lines[error.lineno - 1]
            if not line.rstrip().endswith(":"):
                lines[error.lineno - 1] = line + ":"
                return "\n".join(lines)

        if "EOL while scanning string literal" in message and 1 <= error.lineno <= len(lines):
            line = lines[error.lineno - 1]
            if line.count('"') % 2 != 0:
                lines[error.lineno - 1] = line + '"'
                return "\n".join(lines)

        return None


class ExecutionEngine:
    def run(self, code_file: CodeFile, timeout: int = 5) -> Dict[str, str]:
        with tempfile.TemporaryDirectory() as sandbox_dir:
            sandbox_path = Path(sandbox_dir)
            exec_path = sandbox_path / code_file.filename
            exec_path.write_text(code_file.content, encoding="utf-8")

            result = subprocess.run(
                ["python3", str(exec_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }


class EventDrivenIDE:
    def __init__(self, max_users: int = 4):
        self.editor = CodeEditor()
        self.compiler = CompilerEngine()
        self.executor = ExecutionEngine()
        self.pool = ThreadPoolExecutor(max_workers=max_users)

    def submit_code(self, code: str, user_id: str = "user", filename: str = "main.py") -> Future:
        return self.pool.submit(self._process_submission, code, user_id, filename)

    def _process_submission(self, code: str, user_id: str, filename: str) -> Dict[str, str]:
        code_file = self.editor.open(code, filename=filename, user_id=user_id)
        syntax_error = self.compiler.check(code_file.content, filename=filename)

        if syntax_error is not None:
            correction = self.compiler.suggest_fix(code_file.content, syntax_error)
            return {
                "status": "compile_error",
                "message": self._format_syntax_error(code_file.content, syntax_error),
                "suggested_fix": correction or "No automatic fix available.",
            }

        execution_result = self.executor.run(code_file)

        if execution_result["returncode"] != 0:
            return {
                "status": "runtime_error",
                "stdout": execution_result["stdout"],
                "stderr": execution_result["stderr"],
            }

        return {
            "status": "success",
            "stdout": execution_result["stdout"],
            "stderr": execution_result["stderr"],
        }

    def _format_syntax_error(self, code: str, error: SyntaxError) -> str:
        return format_error_location(code, error.lineno, error.offset, error.msg)


def format_error_location(code: str, lineno: int, offset: Optional[int], message: str) -> str:
    lines = code.splitlines()
    if lineno < 1 or lineno > len(lines):
        return f"SyntaxError: {message} at line {lineno}"

    error_line = lines[lineno - 1]
    pointer = " " * (offset - 1) + "^" if offset and offset > 0 else "^"
    numbered_line = f"{lineno}: {error_line}"
    return f"SyntaxError: {message}\n{numbered_line}\n{' ' * (len(str(lineno)) + 2)}{pointer}"


def main() -> None:
    ide = EventDrivenIDE(max_users=8)

    # ✅ FIXED CODE HERE
    user_code = """
def greet():
    print('Hello from the cloud IDE')

greet()
""".strip()

    future = ide.submit_code(user_code, user_id="alice", filename="greet.py")
    result = future.result()

    print("--- Submission Result ---")
    for key, value in result.items():
        print(f"{key}: {value}\n")

    if result.get("status") == "compile_error" and result.get("suggested_fix"):
        print("--- Suggested Fix ---")
        print(result["suggested_fix"])


if __name__ == "__main__":
    main()
