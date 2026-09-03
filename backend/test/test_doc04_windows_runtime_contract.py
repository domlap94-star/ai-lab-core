from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "operations/windows/doc04-metadata-repair"
LOCK_PATH = TOOL / "runtime-lock.json"
EXPECTED_FILES = {
    "operations/windows/doc04-metadata-repair/runtime-lock.json",
    "operations/windows/doc04-metadata-repair/build-runtime.ps1",
    "operations/windows/doc04-metadata-repair/invoke-repair.ps1",
    "operations/windows/doc04-metadata-repair/runtime-entrypoint.py",
    "operations/windows/doc04-metadata-repair/test-runtime.ps1",
    "operations/windows/doc04-metadata-repair/README.md",
    "backend/test/test_doc04_windows_runtime_contract.py",
}
TOP_LEVEL = {
    "SQLAlchemy": "2.0.43",
    "psycopg": "3.2.10",
    "psycopg-binary": "3.2.10",
    "pydantic": "2.11.7",
    "pydantic-settings": "2.11.0",
    "alembic": "1.16.5",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class Doc04WindowsRuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))

    def test_exact_authorized_file_set_exists(self) -> None:
        actual = {
            path.relative_to(ROOT).as_posix()
            for path in TOOL.rglob("*")
            if path.is_file()
        }
        actual.add("backend/test/test_doc04_windows_runtime_contract.py")
        self.assertEqual(actual, EXPECTED_FILES)

    def test_runtime_lock_v4_python_profiles_paths_and_variance(self) -> None:
        self.assertEqual(
            self.lock["schema"],
            "NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V4",
        )
        python = self.lock["runtime_python"]
        self.assertEqual(python["implementation"], "CPython")
        self.assertEqual(python["version"], "3.12.10")
        self.assertEqual(python["architecture"], "amd64")
        self.assertEqual(python["distribution"], "official_embeddable")
        self.assertEqual(
            python["filename"], "python-3.12.10-embed-amd64.zip"
        )
        self.assertEqual(python["bytes"], 11_133_606)
        self.assertEqual(
            python["sha256"],
            "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3",
        )
        reference = self.lock["backend_reference_python"]
        self.assertEqual(reference["version"], "3.12.13")
        self.assertEqual(reference["purpose"], "behavioral_reference_only")
        variance = self.lock["patch_variance"]
        self.assertFalse(variance["exact_patch_identity"])
        self.assertTrue(variance["parity_required"])
        self.assertTrue(variance["security_delta_review_required"])
        self.assertEqual(variance["production_general_use"], "forbidden")
        self.assertEqual(set(self.lock["profiles"]), {"Production", "Qualification"})
        policies = self.lock["path_policies"]
        self.assertEqual(
            set(policies),
            {
                "runtime_cache",
                "nonproduction_working",
                "production_configuration",
                "production_working_forbidden_roots",
            },
        )
        policy = policies["runtime_cache"]
        self.assertEqual(
            policy["authorized_runtime_parent"],
            r"C:\ai-lab-core-staging\doc04b-runtime",
        )
        self.assertEqual(
            policy["authorized_cache_parent"],
            r"C:\ai-lab-core-staging\doc04b-cache",
        )
        for root in (r"C:\ai-lab-core-backups", "E:\\", "F:\\"):
            self.assertIn(root, policy["forbidden_roots"])
            self.assertIn(root, policies["nonproduction_working"]["forbidden_roots"])
            self.assertIn(root, policies["production_configuration"]["forbidden_roots"])
        self.assertNotIn(r"C:\ai-lab-core", policies["production_configuration"]["forbidden_roots"])
        self.assertTrue(policies["production_configuration"]["explicit_application_root_allowed"])

    def test_locked_artifacts_are_unique_and_allowlisted(self) -> None:
        packages = self.lock["packages"]
        self.assertEqual(len(packages), 65)
        keys = set()
        targets = set()
        allowed = set(self.lock["allowed_download_hosts"])
        for package in packages:
            key = (
                package["project"].lower(),
                package["version"],
                package["filename"].lower(),
            )
            self.assertNotIn(key, keys)
            keys.add(key)
            self.assertNotIn(package["filename"].lower(), targets)
            targets.add(package["filename"].lower())
            self.assertEqual(urlparse(package["url"]).scheme, "https")
            self.assertIn(urlparse(package["url"]).hostname, allowed)
            self.assertEqual(urlparse(package["metadata_url"]).hostname, "pypi.org")
            self.assertTrue(HEX64.fullmatch(package["sha256"]))
            self.assertGreater(package["bytes"], 0)
            if package["classification"] == "locked_pure_sdist":
                self.assertEqual(package["project"], "odfpy")
                self.assertEqual(package["version"], "1.4.1")
                self.assertEqual(package["filename"], "odfpy-1.4.1.tar.gz")
                self.assertIsNone(package["wheel_tag"])
                self.assertEqual(package["install_prefix"], "odfpy-1.4.1/odf/")
                self.assertEqual(package["install_target"], "odf")
                continue
            self.assertTrue(package["filename"].endswith(".whl"))
            self.assertNotIn("cp313", package["wheel_tag"])
            self.assertNotIn("cp314", package["wheel_tag"])
            self.assertNotIn("win32", package["wheel_tag"])
            self.assertNotIn("arm64", package["wheel_tag"].lower())
            self.assertIn(
                package["wheel_tag"],
                {
                    "cp312-cp312-win_amd64", "cp312-abi3-win_amd64",
                    "cp311-abi3-win_amd64", "cp310-abi3-win_amd64",
                    "cp39-abi3-win_amd64", "cp38-abi3-win_amd64",
                    "cp37-abi3-win_amd64", "cp36-abi3-win_amd64",
                    "py3-none-any", "py2.py3-none-any",
                },
            )
        production = self.lock["profiles"]["Production"]["package_projects"]
        self.assertEqual(len(production), 12)
        by_name = {item["project"]: item for item in packages}
        self.assertTrue(all(by_name[name]["classification"] != "locked_pure_sdist" for name in production))
        forbidden = {
            "odfpy", "fastapi", "uvicorn", "qdrant-client", "pymupdf",
            "pillow", "pillow_heif", "pytesseract", "numpy", "openpyxl",
            "xlrd", "xlsxwriter", "python-docx", "python-pptx", "grpcio",
            "watchfiles", "websockets",
        }
        self.assertFalse({name.lower() for name in production} & forbidden)
        qualification_sdists = [item for item in packages if item["classification"] == "locked_pure_sdist"]
        self.assertEqual([(item["project"], item["version"]) for item in qualification_sdists], [("odfpy", "1.4.1")])

    def test_top_level_versions_match_backend_requirements(self) -> None:
        versions = {item["project"]: item["version"] for item in self.lock["packages"]}
        self.assertEqual({name: versions[name] for name in TOP_LEVEL}, TOP_LEVEL)
        requirements = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        for project, version in TOP_LEVEL.items():
            requirement_name = (
                "psycopg[binary]"
                if project in {"psycopg", "psycopg-binary"}
                else project
            )
            self.assertRegex(
                requirements,
                rf"(?im)^{re.escape(requirement_name)}=={re.escape(version)}(?:\s|$)",
            )

    def test_runtime_identity_is_frozen(self) -> None:
        identities = {
            "Production": (1327, "c5fa06a3e21ab2ea0e8df3dcfa4abee10015f9c0a240b66a8ae10a955ce99fad"),
            "Qualification": (4710, "0ceaf9fb3876b3ee0ddfeb77bb70ad92dfd783b19cce97e82279395ef25b687e"),
        }
        for profile, (count, digest) in identities.items():
            installed = self.lock["profiles"][profile]["installed_runtime"]
            self.assertEqual(installed["expected_file_count"], count)
            self.assertEqual(installed["expected_tree_sha256"], digest)
            self.assertTrue(HEX64.fullmatch(digest))

        self.assertIn("tzdata", self.lock["profiles"]["Production"]["package_projects"])
        self.assertEqual(
            self.lock["python312_pth"],
            ["python312.zip", ".", "Lib\\site-packages", "import site"],
        )

    def test_security_delta_is_complete_and_fail_closed(self) -> None:
        delta = self.lock["security_delta"]
        releases = {item["release"] for item in delta}
        self.assertEqual(releases, {"3.12.11", "3.12.12", "3.12.13"})
        components = " ".join(item["component"].lower() for item in delta)
        for required in (
            "tarfile", "unicode_escape", "ipaddress", "expat", "zipfile",
            "html.parser", "email", "wsgiref", "http.cookies", "data url",
            "plistlib", "http.client", "http.server", "expandvars", "ssl",
        ):
            self.assertIn(required, components)
        for item in delta:
            self.assertEqual(
                set(item),
                {
                    "release", "component", "issue", "present",
                    "imported_smoke", "imported_synthetic_repair",
                    "untrusted_production_reachable", "mitigation", "verdict",
                },
            )
            self.assertFalse(item["untrusted_production_reachable"])
            self.assertTrue(item["mitigation"])
            self.assertNotEqual(item["verdict"], "accepted_reachable")

    def test_repair_has_no_vulnerable_codec_or_parser_path(self) -> None:
        sources = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "backend/app/scripts/repair_document_metadata_surrogates.py",
                "backend/app/services/document_metadata_unicode_safety.py",
            )
        )
        for forbidden in (
            "codecs.decode", "errors=\"ignore\"", "errors=\"replace\"",
            "raw_unicode_escape", "import tarfile", "import xml.parsers",
            "import html.parser", "import http.server", "import plistlib",
        ):
            self.assertNotIn(forbidden, sources)
        self.assertNotRegex(sources, r"(?m)^\s*import\s+codecs\b")

    def test_powershell_has_no_unsafe_system_or_execution_primitive(self) -> None:
        powershell = "\n".join(
            path.read_text(encoding="utf-8")
            for path in TOOL.glob("*.ps1")
        )
        for forbidden in (
            "Invoke-Expression", "Set-ExecutionPolicy", "New-ItemProperty",
            "Register-ScheduledTask", "New-Service", "Set-Service",
            "Start-Process",
        ):
            self.assertNotIn(forbidden, powershell)
        self.assertNotRegex(powershell, r"(?i)\b(?:winget|choco)\b")
        self.assertNotRegex(powershell, r"(?i)\$env:path\s*=")
        builder = (TOOL / "build-runtime.ps1").read_text(encoding="utf-8")
        self.assertNotRegex(
            builder,
            r"(?im)^\s*(?:\$env:(?:PYTHONDONTWRITEBYTECODE|PYTHONNOUSERSITE|PYTHONUTF8)\s*=|Remove-Item\s+Env:(?:PYTHONHOME|PYTHONPATH))",
        )

    def test_entrypoint_top_level_imports_are_standard_library_only(self) -> None:
        entrypoint = TOOL / "runtime-entrypoint.py"
        tree = ast.parse(entrypoint.read_text(encoding="utf-8"))
        allowed = {
            "__future__", "argparse", "contextlib", "hashlib",
            "importlib", "io", "json", "math", "ntpath", "os",
            "pathlib", "platform", "re", "socket", "subprocess", "sys",
            "typing", "unittest",
        }
        imported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".", 1)[0])
        self.assertLessEqual(imported, allowed)
        self.assertFalse(imported & {"app", "sqlalchemy", "psycopg", "pydantic", "pydantic_settings", "alembic"})

    def test_entrypoint_installs_isolation_before_backend_path(self) -> None:
        source = (TOOL / "runtime-entrypoint.py").read_text(encoding="utf-8")
        main_start = source.index("def main(")
        main_source = source[main_start:]
        audit = main_source.index("_install_env_audit_guard(")
        chdir = main_source.index("os.chdir(working_directory)")
        verify = main_source.index("repo, lock = _verify_source()")
        backend_path = main_source.index("sys.path.insert(0, str(repo / \"backend\"))")
        self.assertLess(audit, chdir)
        self.assertLess(chdir, verify)
        self.assertLess(verify, backend_path)
        self.assertIn("sys.addaudithook(audit)", source)
        self.assertIn("_install_network_audit_guard(policy)", source)
        self.assertIn("DOC04B_NETWORK_ENDPOINT_FORBIDDEN", source)
        self.assertIn('getattr(socket, "_fallback_socketpair", None)', source)
        self.assertIn("frame.f_code is fallback_socketpair_code", source)
        self.assertIn("DOC04_RUNTIME_ENV_FILE_FORBIDDEN", source)
        self.assertIn("isinstance(value, int)", source)
        self.assertIn("os.fspath(value)", source)
        self.assertIn("os.fsdecode(raw)", source)

    def test_launcher_clears_environment_and_sets_explicit_working_directory(self) -> None:
        launcher = (TOOL / "invoke-repair.ps1").read_text(encoding="utf-8")
        for required in (
            "System.Diagnostics.ProcessStartInfo",
            "$info.UseShellExecute = $false",
            "$info.WorkingDirectory = $WorkingDirectory",
            "$info.EnvironmentVariables.Clear()",
            "NEXT_DOC04_ENVIRONMENT_ROOT",
            "NEXT_DOC04_WORKING_DIRECTORY",
            "NEXT_DOC04_FORBIDDEN_ROOTS_JSON",
            "NEXT_DOC04_RUNTIME_PROFILE",
            "NEXT_DOC04_ALLOWED_ENV_FILE",
            "NEXT_DOC04_EXPECTED_ENV_SHA256",
            "NEXT_DOC04_NETWORK_ALLOWED_HOST",
            "NEXT_DOC04_NETWORK_ALLOWED_PORT",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE",
            "PYTHONUTF8",
        ):
            self.assertIn(required, launcher)
        for sensitive in (
            "OPENAI_API_KEY", "PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE",
            "VIRTUAL_ENV", "PIP_CONFIG_FILE", "PIP_INDEX_URL",
            "PIP_EXTRA_INDEX_URL", "VISION_SUPERVISOR_URL",
            "BACKUP_SUPERVISOR_URL",
        ):
            self.assertIn(sensitive, (TOOL / "runtime-entrypoint.py").read_text(encoding="utf-8"))
        self.assertNotRegex(launcher, r"(?im)^\s*&\s*\$python\b")

    def test_nonproduction_modes_require_a_synthetic_root(self) -> None:
        launcher = (TOOL / "invoke-repair.ps1").read_text(encoding="utf-8")
        for parameter_set in (
            "Readiness", "RepairHelp", "CompatibilityVectors", "IsolatedTest",
            "IsolatedAlembicUpgrade", "AuditEnvProbe", "SyntheticProductionAudit",
            "ProductionImportTrace", "NetworkForbiddenProbe",
            "ProductionProfilePreflightIntegration", "RepairRelaySelfTest",
        ):
            self.assertRegex(
                launcher,
                rf"Mandatory = \$true, ParameterSetName = '{parameter_set}'",
            )
        self.assertIn("DOC04B_SYNTHETIC_ROOT_FORBIDDEN", launcher)
        self.assertIn("C:\\ai-lab-core-backups", launcher)
        self.assertIn("Assert-NoReparseChain", launcher)
        self.assertIn("Assert-NonReparseTree", launcher)

    def test_production_modes_require_explicit_environment_root(self) -> None:
        launcher = (TOOL / "invoke-repair.ps1").read_text(encoding="utf-8")
        environment_parameter = re.compile(
            r"\[Parameter\(Mandatory = \$true, ParameterSetName = 'ProductionPreflight'\)\]"
            r"\s*\[Parameter\(Mandatory = \$true, ParameterSetName = 'ExecuteProduction'\)\]"
            r"\s*\[Parameter\(Mandatory = \$true, ParameterSetName = 'ProductionProfilePreflightIntegration'\)\]"
            r"\[string\]\$EnvironmentRoot",
            re.MULTILINE,
        )
        self.assertRegex(launcher, environment_parameter)
        self.assertIn("'production-preflight'", launcher)
        self.assertIn("'production-execute'", launcher)
        self.assertIn("POSTGRES_DB']='ai_lab'", launcher)
        self.assertIn("POSTGRES_HOST']='127.0.0.1'", launcher)
        self.assertIn("POSTGRES_PORT']='5432'", launcher)

    def test_harness_exercises_every_environment_isolation_gate(self) -> None:
        harness = (TOOL / "test-runtime.ps1").read_text(encoding="utf-8")
        for index in range(1, 21):
            self.assertIn(f"Pass-L 'L{index:02d}'", harness)
        for index in range(1, 31):
            self.assertRegex(harness, rf"['\"]M{index:02d}['\"]")
        for index in range(1, 29):
            self.assertRegex(harness, rf"['\"]N{index:02d}['\"]")
        self.assertIn("hostile-parent-marker", harness)
        self.assertIn("SyntheticProductionAudit", harness)
        self.assertIn("AuditEnvProbe", harness)
        self.assertIn("caller with spaces", harness)

    def test_no_direct_repair_module_diagnostic(self) -> None:
        diagnostics = "\n".join(
            (TOOL / name).read_text(encoding="utf-8")
            for name in ("test-runtime.ps1", "README.md")
        )
        self.assertNotRegex(
            diagnostics,
            r"(?i)python(?:\.exe)?\s+(?:-m\s+app\.scripts\.repair_document_metadata_surrogates|[^\r\n]*repair_document_metadata_surrogates\.py)",
        )
        self.assertIn("invoke-repair.ps1", diagnostics)

    def test_builder_is_locked_direct_extraction(self) -> None:
        builder = (TOOL / "build-runtime.ps1").read_text(encoding="utf-8")
        self.assertIn("System.IO.Compression.ZipFile", builder)
        self.assertIn("System.IO.Compression.GZipStream", builder)
        self.assertIn("maximum_archive_output_bytes", builder)
        self.assertIn("wheel_executable_payload_rejected", builder)
        self.assertIn("sdist_unsupported_tar_type", builder)
        self.assertIn("Install-LockedPureSdist", builder)
        self.assertIn("Assert-PypiMetadata", builder)
        self.assertIn("[ValidateSet('Production','Qualification')]", builder)
        self.assertIn("production_profile_sdist_forbidden", builder)
        self.assertIn("Remove-OwnedPartial", builder)
        self.assertIn("DOC04B_DOWNLOAD_CLEANUP_PROBE_PASS", builder)
        self.assertIn("_NEXT_DOC04_RUNTIME_PROFILE.json", builder)
        self.assertIn("runtime_cache_path_overlap", builder)
        self.assertNotIn("Expand-Archive", builder)
        self.assertNotRegex(builder, r"(?i)\bpip(?:\.exe)?\s+install\b")
        self.assertIn("$probeInfo.WorkingDirectory = $staging", builder)
        self.assertIn("$probeInfo.EnvironmentVariables.Clear()", builder)
        self.assertNotRegex(builder, r"(?im)^\s*\$probe\s*=\s*&\s*")
        self.assertIn("[string]::Join('', $records.ToArray())", builder)
        self.assertIn("[System.Array]::Sort($relativePaths, [System.StringComparer]::Ordinal)", builder)

        launcher = (TOOL / "invoke-repair.ps1").read_text(encoding="utf-8")
        self.assertIn("[string]::Join('', $records.ToArray())", launcher)
        self.assertIn("[System.Array]::Sort($relativePaths, [System.StringComparer]::Ordinal)", launcher)
        self.assertNotIn("[string]::Concat($records)", builder + launcher)

    def test_launcher_has_explicit_mutually_exclusive_production_gates(self) -> None:
        launcher = (TOOL / "invoke-repair.ps1").read_text(encoding="utf-8")
        self.assertIn("ParameterSetName = 'Readiness'", launcher)
        self.assertIn("ParameterSetName = 'ProductionPreflight'", launcher)
        self.assertIn("ParameterSetName = 'ExecuteProduction'", launcher)
        self.assertIn("IUnderstandThisWritesProduction", launcher)
        self.assertIn("DOC04_PRODUCTION_WRITE_APPROVED", launcher)
        self.assertIn("--preflight-production", launcher)
        self.assertIn("--execute", launcher)
        self.assertIn("POSTGRES_HOST']='127.0.0.1'", launcher)
        self.assertIn("POSTGRES_PORT']='5432'", launcher)
        self.assertIn("$productionPayload = ConvertFrom-BoundedJson $child.stdout", launcher)
        self.assertIn("exit $child.exit_code", launcher)
        self.assertIn("Assert-RegularNonReparseFile $Path 'DOC04B_PRODUCTION_ENV_FILE_INVALID'", launcher)
        self.assertIn("Open-VerifiedEnvironmentFile $productionEnvFile $ExpectedEnvironmentFileSha256", launcher)
        self.assertIn("function ConvertTo-IsoTimestampArgument", launcher)
        self.assertIn("[Globalization.CultureInfo]::InvariantCulture", launcher)
        self.assertIn("[System.IO.FileShare]::Read", launcher)
        for code in (
            "DOC04B_PRODUCTION_ENV_HASH_MISMATCH",
            "DOC04B_PRODUCTION_ENV_LOCK_FAILED",
            "DOC04B_PRODUCTION_ENV_CHANGED",
        ):
            self.assertIn(code, launcher)

        harness = (TOOL / "test-runtime.ps1").read_text(encoding="utf-8")
        self.assertIn("docker inspect --format '{{.Image}}' ai-lab-backend", harness)
        self.assertIn("DOC04B_BACKEND_IMAGE_ID_MISMATCH", harness)
        self.assertNotIn("[Parameter(Mandatory = $true)][ValidatePattern('^sha256:[0-9a-f]{64}$')][string]$BackendImage", harness)
        self.assertIn("Get-Command powershell.exe -CommandType Application", harness)
        self.assertNotIn("Join-Path $PSHOME 'powershell.exe'", harness)
        self.assertIn("$builderSuccessEnvironmentUnchanged", harness)
        self.assertIn("$builderFailureEnvironmentUnchanged", harness)
        self.assertIn("@($runtimeB,$qualificationA,$qualificationB,$scratch)", harness)
        self.assertIn("Remove-CampaignPath $path", harness)
        self.assertIn("@(($runtimeB + '.manifest.json'),($qualificationA + '.manifest.json'),($qualificationB + '.manifest.json'))", harness)
        self.assertIn("Pass-M 'M30'", harness)

    def test_entrypoint_has_only_fixed_modes(self) -> None:
        entrypoint = (TOOL / "runtime-entrypoint.py").read_text(encoding="utf-8")
        for mode in (
            "smoke", "repair", "isolated-test", "isolated-alembic-upgrade",
            "compatibility-vectors", "synthetic-production-audit",
            "production-source-security-trace", "network-forbidden-probe",
            "production-profile-preflight-fixture", "repair-relay-self-test",
        ):
            self.assertIn(f'"{mode}"', entrypoint)
        for forbidden in ("eval(", "exec(", "run_module", "run_path", "shell=True"):
            self.assertNotIn(forbidden, entrypoint)
        self.assertIn("FIXED_TEST_SUITES", entrypoint)
        self.assertIn("NEXT_DOC04_BACKEND_REFERENCE", entrypoint)
        self.assertIn("nonproduction-audit-probe", entrypoint)
        self.assertIn('if suite_name == "intake":', entrypoint)
        self.assertIn("module.main()", entrypoint)
        self.assertIn(
            'ISOLATED_DATABASE_REVISION = "followup_assistant_chat_history_20260829"',
            entrypoint,
        )
        self.assertIn("command.upgrade(config, ISOLATED_DATABASE_REVISION)", entrypoint)
        self.assertNotIn('command.upgrade(config, "head")', entrypoint)
        self.assertIn("def _invoke_and_relay_repair(", entrypoint)
        self.assertIn("return _invoke_and_relay_repair(args.repair_args)", entrypoint)
        self.assertIn("MAX_REPAIR_OUTPUT_BYTES = 65_536", entrypoint)
        self.assertIn("DOC04B_REPAIR_SUCCESS_REFUSAL_CONTRADICTION", entrypoint)
        self.assertIn("def _production_source_security_trace(", entrypoint)
        self.assertIn("def _production_preflight_fixture(", entrypoint)
        self.assertIn('"hash-object", "--stdin-paths"', entrypoint)

    def test_v4_source_and_dynamic_security_contract_is_frozen(self) -> None:
        closure = self.lock["source_closure"]
        self.assertEqual(
            closure["backend_app_git_tree_sha"],
            "345fb06ec50a573ad9eae938609e34695bb3131a",
        )
        self.assertEqual(
            closure["expected_application_import_closure_sha256"],
            "cbc9e7e4b66e4df4b9944699de6383aef469bed9b090afbcfb48937a12a85f76",
        )
        self.assertTrue(HEX64.fullmatch(closure["expected_application_import_closure_sha256"]))
        self.assertNotEqual(closure["expected_application_import_closure_sha256"], "0" * 64)
        self.assertEqual(
            closure["stdlib_import_observations"]["windows_3_12_10"],
            closure["stdlib_import_observations"]["backend_3_12_13"],
        )
        for relative in (
            "backend/app/core/config.py",
            "backend/app/models/document.py",
            "backend/app/models/backup_operation.py",
            "backend/app/services/backup_restore_service.py",
            "backend/app/services/backup_supervisor_client.py",
        ):
            self.assertIn(relative, self.lock["critical_git_paths"])

    def test_no_secret_or_production_value_is_committed(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in TOOL.rglob("*")
            if path.is_file()
        )
        self.assertNotRegex(combined, r"postgresql(?:\+psycopg)?://")
        self.assertNotIn("xmin=", combined)
        self.assertNotIn("updated_at=", combined)
        self.assertNotIn("OWNER_" + "APPROVAL_ID=", combined)

    def test_no_binary_or_runtime_payload_is_in_repository(self) -> None:
        forbidden_suffixes = {".exe", ".dll", ".pyd", ".whl", ".zip", ".msi"}
        offending = [
            path for path in TOOL.rglob("*")
            if path.is_file() and path.suffix.lower() in forbidden_suffixes
        ]
        self.assertEqual(offending, [])
        self.assertFalse((ROOT / "operations/windows/doc04-metadata-repair/runtime").exists())
        self.assertFalse((ROOT / "operations/windows/doc04-metadata-repair/cache").exists())


if __name__ == "__main__":
    unittest.main()
