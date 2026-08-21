using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

namespace NextStabil.Recovery
{
    internal sealed class CheckpointValidator
    {
        internal const string ManifestSchema = "NEXT_STABIL_BACKUP_V1";
        internal const string CurrentDbRevision = "followup_admin_backup_restore_ui_20260821";
        internal const string CurrentAppVersion = "1.0.2+25";

        private static readonly string[] FullRequired =
        {
            "postgres.dump", "document-storage.tar.gz", "release-stable.tar.gz",
            "qdrant.snapshot", "n8n-workflows.json",
            "n8n-credentials.encrypted.json", "configuration.tar.gz"
        };

        public CheckpointResult Validate(string selectedPath, Action<ValidationProgress> progress)
        {
            var result = new CheckpointResult();
            try
            {
                Report(progress, "Odczyt manifestu", "Sprawdzanie wybranego folderu");
                if (string.IsNullOrWhiteSpace(selectedPath)) throw new InvalidDataException("checkpoint_path_required");
                var checkpoint = Path.GetFullPath(selectedPath.Trim()).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                result.CheckpointPath = checkpoint;
                if (!Directory.Exists(checkpoint)) throw new InvalidDataException("checkpoint_not_found");
                var manifestPath = Path.Combine(checkpoint, "backup-manifest.json");
                result.ManifestPath = manifestPath;
                if (!File.Exists(manifestPath)) throw new InvalidDataException("backup_manifest_missing");

                var manifestBytes = File.ReadAllBytes(manifestPath);
                result.ManifestSha256 = HashBytes(manifestBytes);
                var json = Encoding.UTF8.GetString(manifestBytes).TrimStart('\uFEFF');
                var root = new JavaScriptSerializer { MaxJsonLength = 16 * 1024 * 1024 }.DeserializeObject(json) as IDictionary<string, object>;
                if (root == null) throw new InvalidDataException("backup_manifest_invalid");
                if (Text(root, "schema_version") != ManifestSchema) throw new InvalidDataException("backup_manifest_unsupported");
                var artifactArray = Value(root, "artifacts") as object[];
                if (artifactArray == null || artifactArray.Length == 0 || artifactArray.Length > 1000) throw new InvalidDataException("backup_manifest_artifacts_invalid");

                result.CreatedAt = Text(root, "created_at");
                result.Scope = Text(root, "scope");
                if (!new[] { "full", "database", "documents", "qdrant", "n8n_config" }.Contains(result.Scope))
                    throw new InvalidDataException("backup_scope_invalid");
                result.AppVersion = FirstText(root, "app_version", "release");
                result.SourceHead = Text(root, "source_head");
                result.DbRevision = Text(root, "db_revision");
                result.QdrantRestoreVerified = Boolean(root, "qdrant_restore_verified");
                var qdrantProof = Value(root, "qdrant_restore_result") as IDictionary<string, object>;
                if (qdrantProof != null)
                {
                    long points, dimensions;
                    if (TryInteger64(Value(qdrantProof, "points"), out points)) result.QdrantPoints = points;
                    if (TryInteger64(Value(qdrantProof, "dimensions"), out dimensions) && dimensions >= 0 && dimensions <= int.MaxValue)
                        result.QdrantDimensions = (int)dimensions;
                    result.QdrantDistance = Text(qdrantProof, "distance");
                    result.QdrantRestoreVerified = result.QdrantRestoreVerified &&
                        result.QdrantPoints >= 0 && result.QdrantDimensions == 1024 &&
                        string.Equals(result.QdrantDistance, "Cosine", StringComparison.Ordinal) &&
                        !Boolean(qdrantProof, "production_volume_mounted");
                }
                else result.QdrantRestoreVerified = false;
                result.SecretEscrowRequired = !Boolean(root, "secrets_in_protected_backup");

                Report(progress, "Sprawdzanie plików", "Weryfikacja ścieżek, rozmiarów i allowlisty");
                var seenRelative = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (var raw in artifactArray)
                {
                    var artifact = raw as IDictionary<string, object>;
                    if (artifact == null) throw new InvalidDataException("backup_artifact_invalid");
                    var relative = Text(artifact, "file");
                    if (!IsSafeRelativePath(relative)) throw new InvalidDataException("backup_artifact_path_invalid");
                    var normalized = relative.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
                    if (!seenRelative.Add(normalized)) throw new InvalidDataException("backup_artifact_duplicate");
                    var full = Path.GetFullPath(Path.Combine(checkpoint, normalized));
                    if (!IsDescendant(checkpoint, full)) throw new InvalidDataException("backup_artifact_path_invalid");
                    if (!File.Exists(full)) throw new InvalidDataException("backup_artifact_missing");
                    var expectedBytes = Integer64(artifact, "bytes");
                    var expectedHash = Text(artifact, "sha256").ToLowerInvariant();
                    if (expectedHash.Length != 64 || expectedHash.Any(c => !Uri.IsHexDigit(c))) throw new InvalidDataException("backup_artifact_hash_invalid");
                    var actualBytes = new FileInfo(full).Length;
                    if (actualBytes != expectedBytes) throw new InvalidDataException("backup_artifact_size_mismatch");
                    var name = Path.GetFileName(full);
                    if (result.Artifacts.ContainsKey(name)) throw new InvalidDataException("backup_artifact_name_duplicate");
                    result.Artifacts[name] = new ArtifactInfo
                    {
                        RelativePath = relative.Replace('\\', '/'), FullPath = full,
                        Bytes = expectedBytes, Sha256 = expectedHash
                    };
                    checked { result.TotalBytes += expectedBytes; }
                }

                Report(progress, "Weryfikacja SHA-256", "Obliczanie skrótów artefaktów");
                foreach (var artifact in result.Artifacts.Values.OrderBy(x => x.RelativePath, StringComparer.OrdinalIgnoreCase))
                {
                    if (!string.Equals(HashFile(artifact.FullPath), artifact.Sha256, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException("backup_artifact_hash_mismatch");
                }
                result.ArtifactCount = result.Artifacts.Count;

                result.DatabaseAvailable = result.Artifacts.ContainsKey("postgres.dump");
                result.DocumentsAvailable = result.Artifacts.ContainsKey("document-storage.tar.gz");
                result.QdrantAvailable = result.Artifacts.ContainsKey("qdrant.snapshot");
                result.N8nConfigAvailable = result.Artifacts.ContainsKey("n8n-workflows.json") && result.Artifacts.ContainsKey("n8n-credentials.encrypted.json");
                result.ReleaseConfigAvailable = result.Artifacts.ContainsKey("release-stable.tar.gz") && result.Artifacts.ContainsKey("configuration.tar.gz");

                Report(progress, "Sprawdzanie zgodności bazy", "Kontrola formatu dump i rewizji");
                result.DatabaseArchiveReadable = result.DatabaseAvailable && HasPostgresCustomHeader(result.Artifacts["postgres.dump"].FullPath);
                result.Compatibility = ClassifyCompatibility(result.AppVersion, result.DbRevision);

                if (result.QdrantAvailable)
                {
                    Report(progress, "Sprawdzanie snapshotu Qdrant", "Kontrola archiwum i WAL");
                    string qdrantReason;
                    result.QdrantStructurallyValid = ValidateQdrantSnapshot(result.Artifacts["qdrant.snapshot"].FullPath, out qdrantReason);
                    result.QdrantReason = qdrantReason;
                }

                var compatible = result.Compatibility == CompatibilityKind.Compatible ||
                                 result.Compatibility == CompatibilityKind.OlderSupported ||
                                 result.Compatibility == CompatibilityKind.RequiresMigration;
                result.DatabaseEligible = compatible && result.DatabaseArchiveReadable;
                result.FullEligible = result.DatabaseEligible &&
                    FullRequired.All(name => result.Artifacts.ContainsKey(name)) &&
                    result.QdrantStructurallyValid && result.QdrantRestoreVerified;
                result.Valid = true;
                result.Stages.Add("artifact_hash_verified");
                if (result.QdrantStructurallyValid) result.Stages.Add("snapshot_structurally_valid");
                if (result.QdrantRestoreVerified) result.Stages.Add("restore_drill_verified");
                Report(progress, "Gotowy", result.FullEligible ? "Checkpoint gotowy do obu trybów" : "Checkpoint zweryfikowany");
                return result;
            }
            catch (Exception error)
            {
                result.Valid = false;
                result.ErrorCode = SafeCode(error.Message);
                result.Compatibility = CompatibilityKind.Invalid;
                return result;
            }
        }

        private static CompatibilityKind ClassifyCompatibility(string appVersion, string revision)
        {
            int comparison;
            if (!CompareVersions(appVersion, CurrentAppVersion, out comparison)) return CompatibilityKind.Invalid;
            if (comparison > 0) return CompatibilityKind.NewerUnsupported;
            if (string.Equals(revision, CurrentDbRevision, StringComparison.Ordinal)) return CompatibilityKind.Compatible;
            if (string.IsNullOrWhiteSpace(revision)) return CompatibilityKind.Invalid;
            return comparison < 0 ? CompatibilityKind.OlderSupported : CompatibilityKind.RequiresMigration;
        }

        internal static bool CompareVersions(string left, string right, out int result)
        {
            result = 0;
            Version a, b;
            if (!Version.TryParse((left ?? string.Empty).Split('+')[0], out a) ||
                !Version.TryParse((right ?? string.Empty).Split('+')[0], out b)) return false;
            result = a.CompareTo(b);
            return true;
        }

        internal static bool IsSafeRelativePath(string value)
        {
            if (string.IsNullOrWhiteSpace(value) || Path.IsPathRooted(value)) return false;
            var normalized = value.Replace('\\', '/');
            if (normalized.StartsWith("/", StringComparison.Ordinal) || normalized.Contains("\0") ||
                normalized.IndexOf('"') >= 0 || normalized.Any(c => c < 32)) return false;
            return !normalized.Split('/').Any(part => part == ".." || part.Length == 0);
        }

        private static bool IsDescendant(string root, string path)
        {
            var prefix = root.TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
            return path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
        }

        private static bool HasPostgresCustomHeader(string path)
        {
            using (var stream = File.OpenRead(path))
            {
                var header = new byte[5];
                return stream.Read(header, 0, header.Length) == header.Length && Encoding.ASCII.GetString(header) == "PGDMP";
            }
        }

        private static bool ValidateQdrantSnapshot(string path, out string reason)
        {
            reason = null;
            var entriesResult = Run("tar.exe", "-tf " + Quote(path), 120000, 4 * 1024 * 1024);
            if (entriesResult.ExitCode != 0) { reason = "archive_invalid"; return false; }
            var entries = entriesResult.Output.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(x => x.Trim().Replace('\\', '/').TrimStart('.', '/')).Where(x => x.Length > 0).ToArray();
            if (entries.Length == 0 || entries.Any(x => !IsSafeArchivePath(x))) { reason = "archive_entries_invalid"; return false; }
            if (!entries.Contains("config.json") || !entries.Contains("version.info") || !entries.Any(IsShardConfig))
            { reason = "collection_metadata_missing"; return false; }
            foreach (var entry in entries.Where(IsFirstIndex))
            {
                var extracted = RunBytes("tar.exe", "-xOf " + Quote(path) + " " + Quote(entry), 120000, 64 * 1024);
                if (extracted.ExitCode != 0 || extracted.Bytes.Length == 0 || extracted.Bytes.All(x => x == 0))
                { reason = "wal_first_index_empty_or_nul"; return false; }
                try
                {
                    var obj = new JavaScriptSerializer().DeserializeObject(Encoding.UTF8.GetString(extracted.Bytes)) as IDictionary<string, object>;
                    long ack;
                    if (obj == null || !TryInteger64(Value(obj, "ack_index"), out ack) || ack < 0)
                    { reason = "wal_first_index_invalid_value"; return false; }
                }
                catch { reason = "wal_first_index_invalid_json"; return false; }
            }
            return true;
        }

        private static bool IsShardConfig(string value)
        {
            var parts = value.Split('/');
            int shard;
            return parts.Length == 2 && int.TryParse(parts[0], out shard) && parts[1] == "shard_config.json";
        }

        private static bool IsFirstIndex(string value)
        {
            var parts = value.Split('/');
            int shard;
            return parts.Length == 3 && int.TryParse(parts[0], out shard) && parts[1] == "wal" && parts[2] == "first-index";
        }

        private static bool IsSafeArchivePath(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return false;
            var normalized = value.Replace('\\', '/').TrimEnd('/');
            if (normalized.Length == 0 || normalized.StartsWith("/", StringComparison.Ordinal) ||
                (normalized.Length >= 2 && char.IsLetter(normalized[0]) && normalized[1] == ':') ||
                normalized.IndexOf('"') >= 0 || normalized.Any(c => c < 32)) return false;
            return !normalized.Split('/').Any(part => part == "..");
        }

        internal static string HashFile(string path)
        {
            using (var sha = SHA256.Create())
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
                return Hex(sha.ComputeHash(stream));
        }

        private static string HashBytes(byte[] bytes)
        {
            using (var sha = SHA256.Create()) return Hex(sha.ComputeHash(bytes));
        }

        private static string Hex(byte[] bytes) { return BitConverter.ToString(bytes).Replace("-", string.Empty).ToLowerInvariant(); }
        private static string Quote(string value) { return "\"" + value.Replace("\"", "\\\"") + "\""; }
        private static void Report(Action<ValidationProgress> progress, string stage, string detail)
        { if (progress != null) progress(new ValidationProgress { Stage = stage, Detail = detail }); }
        private static string SafeCode(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return "checkpoint_validation_failed";
            var first = value.Split(new[] { '\r', '\n', ':' }, 2)[0];
            return first.Length > 100 ? first.Substring(0, 100) : first;
        }

        private static object Value(IDictionary<string, object> map, string key) { object value; return map.TryGetValue(key, out value) ? value : null; }
        private static string Text(IDictionary<string, object> map, string key) { return Convert.ToString(Value(map, key), CultureInfo.InvariantCulture) ?? string.Empty; }
        private static string FirstText(IDictionary<string, object> map, params string[] keys) { foreach (var key in keys) { var value = Text(map, key); if (!string.IsNullOrWhiteSpace(value)) return value; } return string.Empty; }
        private static bool Boolean(IDictionary<string, object> map, string key) { var value = Value(map, key); return value is bool && (bool)value; }
        private static long Integer64(IDictionary<string, object> map, string key) { long parsed; if (!TryInteger64(Value(map, key), out parsed) || parsed < 0) throw new InvalidDataException("backup_artifact_size_invalid"); return parsed; }
        private static bool TryInteger64(object value, out long parsed) { return long.TryParse(Convert.ToString(value, CultureInfo.InvariantCulture), NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed); }

        private sealed class ProcessResult { public int ExitCode; public string Output; }
        private sealed class ProcessBytesResult { public int ExitCode; public byte[] Bytes; }
        private static ProcessResult Run(string file, string arguments, int timeoutMs, int maxBytes)
        {
            var info = new ProcessStartInfo(file, arguments) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
            using (var process = Process.Start(info))
            {
                var output = process.StandardOutput.ReadToEnd();
                var error = process.StandardError.ReadToEnd();
                if (!process.WaitForExit(timeoutMs)) { process.Kill(); throw new InvalidDataException("validator_timeout"); }
                if (Encoding.UTF8.GetByteCount(output) > maxBytes) throw new InvalidDataException("validator_output_too_large");
                return new ProcessResult { ExitCode = process.ExitCode, Output = output + (process.ExitCode == 0 ? string.Empty : error) };
            }
        }

        private static ProcessBytesResult RunBytes(string file, string arguments, int timeoutMs, int maxBytes)
        {
            var info = new ProcessStartInfo(file, arguments) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
            using (var process = Process.Start(info))
            using (var memory = new MemoryStream())
            {
                var buffer = new byte[8192]; int read;
                while ((read = process.StandardOutput.BaseStream.Read(buffer, 0, buffer.Length)) > 0)
                { if (memory.Length + read > maxBytes) { process.Kill(); throw new InvalidDataException("validator_output_too_large"); } memory.Write(buffer, 0, read); }
                process.StandardError.ReadToEnd();
                if (!process.WaitForExit(timeoutMs)) { process.Kill(); throw new InvalidDataException("validator_timeout"); }
                return new ProcessBytesResult { ExitCode = process.ExitCode, Bytes = memory.ToArray() };
            }
        }
    }
}
